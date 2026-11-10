// Avernum 4 - Japanese text support
// (ported from the Avernum: Escape From the Pit / Avernum 2 / Avernum 3 JP mods)
//
// Built as a proxy dsound.dll (DirectSoundCreate is passed through to the system dsound.dll).
// Avernum 4 draws text with GDI (DrawTextW on DirectDraw surfaces) after converting the
// game's byte strings with MultiByteToWideChar(CP_THREAD_ACP). So the DLL only has to:
//   * read the game's text as EUC-JP (code page 20932) instead of the ANSI code page:
//     EUC-JP bytes never collide with ASCII ('|', '\', '_' ...), unlike Shift-JIS;
//   * pass the real character count to DrawTextW / GetTextExtentPoint32W (the game passes
//     the byte count, which is twice the count for Japanese);
//   * return Japanese for the exe's string table (LoadStringW);
//   * redirect exe strings (.rdata) and the data files (scripts, scenario, pictures)
//     to the translated versions, as in the Avernum 3 mod.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "user32.lib")

static BYTE *g_base;
#define VA(x) ((void *)(g_base + ((DWORD)(x) - 0x400000)))
#define GAME_CP 20932 /* EUC-JP */
static int g_eucjp = 1; // used by to_game_encoding(): game text is EUC-JP

// ---------------------------------------------------------------- logging
static FILE *g_log;
static void jp_log(const char *fmt, ...)
{
    va_list ap;
    if (!g_log)
        return;
    va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fflush(g_log);
}

// ---------------------------------------------------------------- exe string replacement
//
// avernum_jp_exe.tsv (UTF-8, tab separated): va, sink, refs, english, japanese.
// For every row with a translation we check that the exe really has the English
// string at that address, then rewrite every relocated pointer to it (code
// immediates and data tables, found via the exe's base relocation table) so it
// points at the translated string instead. The exe file itself is untouched.

static const BYTE kSprintfPrologue[] = {0x8B, 0xFF, 0x55, 0x8B, 0xEC};

typedef struct
{
    DWORD oldPtr;
    DWORD newPtr;
} StrMap;
#define STRMAP_SIZE 4096
static StrMap g_strmap[STRMAP_SIZE];
static int g_strmapCount;

static void strmap_put(DWORD oldPtr, DWORD newPtr)
{
    DWORD h = (oldPtr * 2654435761u) & (STRMAP_SIZE - 1);
    while (g_strmap[h].oldPtr && g_strmap[h].oldPtr != oldPtr)
        h = (h + 1) & (STRMAP_SIZE - 1);
    if (!g_strmap[h].oldPtr)
        g_strmapCount++;
    g_strmap[h].oldPtr = oldPtr;
    g_strmap[h].newPtr = newPtr;
}
static DWORD strmap_get(DWORD oldPtr)
{
    DWORD h = (oldPtr * 2654435761u) & (STRMAP_SIZE - 1);
    while (g_strmap[h].oldPtr)
    {
        if (g_strmap[h].oldPtr == oldPtr)
            return g_strmap[h].newPtr;
        h = (h + 1) & (STRMAP_SIZE - 1);
    }
    return 0;
}

// In-place unescape of \n \r \t \\ (as written by the exporter).
static void unescape(char *s)
{
    char *o = s;
    for (; *s; s++)
    {
        if (*s == '\\' && s[1])
        {
            s++;
            *o++ = *s == 'n' ? '\n' : *s == 'r' ? '\r' : *s == 't' ? '\t' : *s;
        }
        else
            *o++ = *s;
    }
    *o = 0;
}

// UTF-8 -> game encoding (EUC-JP or UTF-8). Returns malloc'd string.
static char *to_game_encoding(const char *utf8, int *unmappable)
{
    int wn = MultiByteToWideChar(CP_UTF8, 0, utf8, -1, NULL, 0), i, n;
    WCHAR *w;
    char *out;
    BOOL usedDefault = FALSE;
    *unmappable = 0;
    if (!g_eucjp)
        return _strdup(utf8);
    w = (WCHAR *)malloc(wn * sizeof(WCHAR));
    MultiByteToWideChar(CP_UTF8, 0, utf8, -1, w, wn);
    for (i = 0; i < wn; i++) // same normalisation as tools/jpconv.py
        switch (w[i])
        {
        case 0xFF5E: w[i] = 0x301C; break;
        case 0xFF0D: w[i] = 0x2212; break;
        case 0x2225: w[i] = 0x2016; break;
        }
    n = WideCharToMultiByte(20932, 0, w, wn, NULL, 0, NULL, NULL);
    out = (char *)malloc(n + 1);
    WideCharToMultiByte(20932, 0, w, wn, out, n, "?", &usedDefault);
    out[n] = 0;
    *unmappable = usedDefault;
    free(w);
    return out;
}

static int g_needPositional;
static int g_forceScan; // [debug] force_scan=1: search everything as for another build (tests the search)

static int __cdecl my_sprintf(char *buf, const char *fmt, ...)
{
    va_list ap;
    int r;
    va_start(ap, fmt);
    if (strchr(fmt, '$'))
        r = _vsprintf_p(buf, 65536, fmt, ap); // supports %1$s style reordering
    else
        r = vsprintf(buf, fmt, ap);
    va_end(ap);
    return r;
}

static void install_sprintf_hook(void)
{
    jp_log("positional formats (%%1$s) are not supported in Avernum 4 exe strings\n");
}

static int is_positional(const char *s)
{
    for (; *s; s++)
        if (s[0] == '%' && s[1] >= '1' && s[1] <= '9' && s[2] == '$')
            return 1;
    return 0;
}

// Other builds keep the same strings at other addresses. A string is identified by its
// text and by how many relocated pointers refer to it (the "refs" column, counted in
// the Steam build), so short texts that also occur as plain data are not mistaken.
static DWORD *g_relocTargets; // values of all relocated pointers, sorted
static int g_relocCount;

static int cmp_dword(const void *a, const void *b)
{
    DWORD x = *(const DWORD *)a, y = *(const DWORD *)b;
    return x < y ? -1 : x > y;
}

static void build_reloc_targets(void)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)g_base;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(g_base + dos->e_lfanew);
    IMAGE_DATA_DIRECTORY *rd = &nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC];
    BYTE *rel = g_base + rd->VirtualAddress, *end = rel + rd->Size;
    int cap = rd->Size / 2 + 1;
    g_relocTargets = (DWORD *)malloc(cap * sizeof(DWORD));
    g_relocCount = 0;
    while (g_relocTargets && rd->VirtualAddress && rel < end)
    {
        IMAGE_BASE_RELOCATION *blk = (IMAGE_BASE_RELOCATION *)rel;
        WORD *e = (WORD *)(blk + 1);
        int n = (blk->SizeOfBlock - sizeof *blk) / 2, i;
        if (blk->SizeOfBlock < sizeof *blk)
            break;
        for (i = 0; i < n && g_relocCount < cap; i++)
            if ((e[i] >> 12) == IMAGE_REL_BASED_HIGHLOW)
                g_relocTargets[g_relocCount++] = *(DWORD *)(g_base + blk->VirtualAddress + (e[i] & 0xfff));
        rel += blk->SizeOfBlock;
    }
    if (g_relocTargets)
        qsort(g_relocTargets, g_relocCount, sizeof(DWORD), cmp_dword);
}

static int reloc_refs(DWORD ptr)
{
    int lo = 0, hi = g_relocCount, n = 0;
    while (lo < hi)
    {
        int mid = (lo + hi) / 2;
        if (g_relocTargets[mid] < ptr)
            lo = mid + 1;
        else
            hi = mid;
    }
    while (lo + n < g_relocCount && g_relocTargets[lo + n] == ptr)
        n++;
    return n;
}

// True when some relocated pointer points inside [ptr+1, ptr+len]: the compiler inlined a copy of
// this short string as 4-byte loads (mov eax,[s]; mov eax,[s+4] ...). Redirecting only the pointer
// to the first byte would mix the first 4 bytes of the translation with the rest of the English
// ("筋力ngth"), so such strings are overwritten in place instead.
static int reloc_interior(DWORD ptr, size_t len)
{
    int lo = 0, hi = g_relocCount;
    while (lo < hi)
    {
        int mid = (lo + hi) / 2;
        if (g_relocTargets[mid] <= ptr)
            lo = mid + 1;
        else
            hi = mid;
    }
    return lo < g_relocCount && g_relocTargets[lo] <= ptr + len;
}

// Returns the RVA of a whole NUL-terminated occurrence of s in the data sections with
// exactly `refs` references (refs < 0: any number above zero) that is not in used[].
static DWORD find_string_rva(const char *s, int refs, const DWORD *used, int nUsed)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)g_base;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(g_base + dos->e_lfanew);
    IMAGE_SECTION_HEADER *sec = IMAGE_FIRST_SECTION(nt);
    size_t len = strlen(s);
    int i, j, r;
    if (!len)
        return 0;
    if (!g_relocTargets)
        build_reloc_targets();
    for (i = 0; i < nt->FileHeader.NumberOfSections; i++)
    {
        BYTE *a, *p, *end;
        if ((sec[i].Characteristics & IMAGE_SCN_CNT_CODE) || !(sec[i].Characteristics & IMAGE_SCN_CNT_INITIALIZED_DATA))
            continue;
        a = g_base + sec[i].VirtualAddress;
        end = a + min(sec[i].Misc.VirtualSize, sec[i].SizeOfRawData);
        for (p = a; p + len < end; p++)
            if (*p == (BYTE)s[0] && (p == a || p[-1] == 0) && p[len] == 0 && memcmp(p, s, len) == 0)
            {
                DWORD rva = (DWORD)(p - g_base);
                r = reloc_refs((DWORD)p);
                for (j = 0; j < nUsed && used[j] != rva; j++)
                    ;
                if (j == nUsed && (refs < 0 ? r > 0 : r == refs))
                    return rva;
                p += len;
            }
    }
    return 0;
}

static void load_exe_strings(const char *dir)
{
    DWORD *used = (DWORD *)calloc(4096, sizeof(DWORD)); // RVAs of strings already taken
    int nUsed = 0, foundBySearch = 0;
    char path[MAX_PATH];
    FILE *f;
    long size;
    char *buf, *line, *next;
    int lineno = 0, ok = 0, skipped = 0, inPlace = 0;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)g_base;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(g_base + dos->e_lfanew);
    DWORD imageSize = nt->OptionalHeader.SizeOfImage;

    _snprintf(path, sizeof path, "%s\\avernum_jp_exe.tsv", dir);
    f = fopen(path, "rb");
    if (!f)
    {
        jp_log("no %s (exe strings stay English)\n", path);
        free(used);
        return;
    }
    fseek(f, 0, SEEK_END);
    size = ftell(f);
    fseek(f, 0, SEEK_SET);
    buf = (char *)malloc(size + 1);
    fread(buf, 1, size, f);
    buf[size] = 0;
    fclose(f);
    if (!g_relocTargets)
        build_reloc_targets();

    for (line = buf; line && *line; line = next)
    {
        char *col[5] = {0};
        char *p;
        int c = 0, unmappable;
        DWORD va, rva;
        next = strchr(line, '\n');
        if (next)
            *next++ = 0;
        lineno++;
        if ((p = strchr(line, '\r')) != NULL)
            *p = 0;
        if (lineno == 1 && (strncmp(line, "va\t", 3) == 0 || strncmp(line, "\xEF\xBB\xBFva\t", 6) == 0))
            continue;
        col[0] = line;
        for (p = line; *p && c < 4; p++)
            if (*p == '\t')
            {
                *p = 0;
                col[++c] = p + 1;
            }
        if (c < 4 || !col[4][0])
            continue; // untranslated
        unescape(col[3]);
        unescape(col[4]);
        va = strtoul(col[0], NULL, 16);
        rva = va - 0x400000;
        if (g_forceScan || va < 0x400000 || rva >= imageSize || strcmp((char *)g_base + rva, col[3]) != 0)
        {
            // not at the Steam build's address: look for the same text elsewhere
            char *e;
            long refs = strtol(col[2], &e, 10);
            rva = find_string_rva(col[3], (e != col[2] && refs > 0) ? (int)refs : -1, used, nUsed);
            if (!rva)
            {
                jp_log("exe_tsv line %d: English text not found in this exe (%s), skipped\n", lineno, col[0]);
                skipped++;
                continue;
            }
            if (rva != va - 0x400000)
                foundBySearch++;
        }
        if (nUsed < 4096)
            used[nUsed++] = rva;
        {
            char *jp = to_game_encoding(col[4], &unmappable);
            if (unmappable)
                jp_log("exe_tsv line %d: characters not in EUC-JP were replaced with '?'\n", lineno);
            if (strstr(col[1], "float") && strlen(jp) > 39)
                jp_log("exe_tsv line %d: floating text is %u bytes (max 39), it will not be shown\n", lineno, (unsigned)strlen(jp));
            if (g_relocTargets && reloc_interior((DWORD)(g_base + rva), strlen((char *)g_base + rva)))
            {
                BYTE *s = g_base + rva;
                size_t elen = strlen((char *)s), jl = strlen(jp);
                if (jl <= elen)
                {
                    DWORD old;
                    VirtualProtect(s, elen + 1, PAGE_READWRITE, &old);
                    memcpy(s, jp, jl + 1);
                    VirtualProtect(s, elen + 1, old, &old);
                    inPlace++;
                    ok++;
                }
                else
                {
                    jp_log("exe_tsv line %d: %s is copied 4 bytes at a time and the translation is longer than the English (%u > %u bytes), left English\n",
                           lineno, col[0], (unsigned)jl, (unsigned)elen);
                    skipped++;
                }
                continue;
            }
            if (is_positional(jp))
                g_needPositional = 1;
            strmap_put((DWORD)(g_base + rva), (DWORD)jp);
            ok++;
        }
    }
    free(buf);
    free(used);
    free(g_relocTargets);
    g_relocTargets = NULL;
    if (foundBySearch)
        jp_log("exe strings: %d found at other addresses than in the Steam build\n", foundBySearch);

    // Walk the exe's base relocations and redirect every pointer to a translated string.
    {
        IMAGE_DATA_DIRECTORY *rd = &nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC];
        BYTE *rel = g_base + rd->VirtualAddress, *end = rel + rd->Size;
        int patched = 0;
        while (rd->VirtualAddress && rel < end)
        {
            IMAGE_BASE_RELOCATION *blk = (IMAGE_BASE_RELOCATION *)rel;
            WORD *e = (WORD *)(blk + 1);
            int n = (blk->SizeOfBlock - sizeof *blk) / 2, i;
            if (blk->SizeOfBlock < sizeof *blk)
                break;
            for (i = 0; i < n; i++)
            {
                if ((e[i] >> 12) == IMAGE_REL_BASED_HIGHLOW)
                {
                    DWORD *site = (DWORD *)(g_base + blk->VirtualAddress + (e[i] & 0xfff));
                    DWORD np = strmap_get(*site);
                    if (np)
                    {
                        DWORD old;
                        VirtualProtect(site, 4, PAGE_EXECUTE_READWRITE, &old);
                        *site = np;
                        VirtualProtect(site, 4, old, &old);
                        patched++;
                    }
                }
            }
            rel += blk->SizeOfBlock;
        }
        FlushInstructionCache(GetCurrentProcess(), NULL, 0);
        jp_log("exe strings: %d translated (%d written in place), %d skipped, %d references patched\n", ok, inPlace, skipped, patched);
    }
    if (g_needPositional)
        install_sprintf_hook();
}

// ---------------------------------------------------------------- dsound passthrough
typedef HRESULT(WINAPI *DSCreateFn)(const GUID *, void **, void *);
static HMODULE g_realDsound;
static FARPROC real_dsound(const char *name)
{
    if (!g_realDsound)
    {
        char path[MAX_PATH];
        GetSystemDirectoryA(path, MAX_PATH);
        strcat(path, "\\dsound.dll");
        g_realDsound = LoadLibraryA(path);
    }
    return g_realDsound ? GetProcAddress(g_realDsound, name) : NULL;
}
HRESULT WINAPI DirectSoundCreate(const GUID *dev, void **out, void *outer)
{
    DSCreateFn fn = (DSCreateFn)real_dsound("DirectSoundCreate");
    return fn ? fn(dev, out, outer) : E_FAIL;
}

// ---------------------------------------------------------------- translated data files (drop-in mode)
// The game's own files are never changed. avernum_jp\jp_patch.bin holds deltas against the
// original files; on start-up they are applied into avernum_jp\cache\ (only when the
// original's SHA-256 matches), and the exe's CreateFileA/W and FindFirstFileExA are
// redirected there. Removing dsound.dll restores the English game.
typedef struct
{
    DWORD h[8];
    BYTE buf[64];
    unsigned __int64 len;
    int n;
} Sha256;

static const DWORD kShaK[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

#define ROR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static void sha_block(Sha256 *s, const BYTE *p)
{
    DWORD w[64], a, b, c, d, e, f, g, h, t1, t2;
    int i;
    for (i = 0; i < 16; i++)
        w[i] = (DWORD)p[i * 4] << 24 | (DWORD)p[i * 4 + 1] << 16 | (DWORD)p[i * 4 + 2] << 8 | p[i * 4 + 3];
    for (i = 16; i < 64; i++)
        w[i] = (ROR(w[i - 2], 17) ^ ROR(w[i - 2], 19) ^ (w[i - 2] >> 10)) + w[i - 7] +
               (ROR(w[i - 15], 7) ^ ROR(w[i - 15], 18) ^ (w[i - 15] >> 3)) + w[i - 16];
    a = s->h[0], b = s->h[1], c = s->h[2], d = s->h[3], e = s->h[4], f = s->h[5], g = s->h[6], h = s->h[7];
    for (i = 0; i < 64; i++)
    {
        t1 = h + (ROR(e, 6) ^ ROR(e, 11) ^ ROR(e, 25)) + ((e & f) ^ (~e & g)) + kShaK[i] + w[i];
        t2 = (ROR(a, 2) ^ ROR(a, 13) ^ ROR(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
        h = g, g = f, f = e, e = d + t1, d = c, c = b, b = a, a = t1 + t2;
    }
    s->h[0] += a, s->h[1] += b, s->h[2] += c, s->h[3] += d, s->h[4] += e, s->h[5] += f, s->h[6] += g, s->h[7] += h;
}

static void sha256(const BYTE *data, DWORD size, BYTE out[32])
{
    static const DWORD init[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                                  0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    Sha256 s;
    DWORD i;
    unsigned __int64 bits = (unsigned __int64)size * 8;
    memcpy(s.h, init, sizeof init);
    for (i = 0; i + 64 <= size; i += 64)
        sha_block(&s, data + i);
    s.n = size - i;
    memcpy(s.buf, data + i, s.n);
    s.buf[s.n++] = 0x80;
    if (s.n > 56)
    {
        memset(s.buf + s.n, 0, 64 - s.n);
        sha_block(&s, s.buf);
        s.n = 0;
    }
    memset(s.buf + s.n, 0, 56 - s.n);
    for (i = 0; i < 8; i++)
        s.buf[56 + i] = (BYTE)(bits >> (56 - 8 * i));
    sha_block(&s, s.buf);
    for (i = 0; i < 8; i++)
    {
        out[i * 4] = (BYTE)(s.h[i] >> 24);
        out[i * 4 + 1] = (BYTE)(s.h[i] >> 16);
        out[i * 4 + 2] = (BYTE)(s.h[i] >> 8);
        out[i * 4 + 3] = (BYTE)s.h[i];
    }
}

static BYTE *read_all(const char *path, DWORD *size)
{
    FILE *f = fopen(path, "rb");
    long n;
    BYTE *buf;
    if (!f)
        return NULL;
    fseek(f, 0, SEEK_END);
    n = ftell(f);
    fseek(f, 0, SEEK_SET);
    buf = (BYTE *)malloc(n > 0 ? n : 1);
    if (buf && fread(buf, 1, n, f) != (size_t)n)
    {
        free(buf);
        buf = NULL;
    }
    fclose(f);
    *size = (DWORD)n;
    return buf;
}

static void make_parent_dirs(const char *path)
{
    char tmp[MAX_PATH];
    char *p;
    lstrcpynA(tmp, path, MAX_PATH);
    for (p = tmp + 3; *p; p++)
        if (*p == '\\')
        {
            *p = 0;
            CreateDirectoryA(tmp, NULL);
            *p = '\\';
        }
}

#define MAX_REDIRECTS 1024
typedef struct
{
    char rel[MAX_PATH];   // lower case, '\' separated, relative to the game folder
    char cache[MAX_PATH]; // translated copy
} Redirect;
static Redirect *g_redir;
static int g_redirCount;
static char g_gameDirLower[MAX_PATH];
static int g_gameDirLen;

static void lower_path(char *s)
{
    for (; *s; s++)
        *s = *s == '/' ? '\\' : (*s >= 'A' && *s <= 'Z') ? *s + 32 : *s;
}

static const char *redirect_for(const char *path)
{
    char full[MAX_PATH * 2];
    DWORD n;
    int i;
    if (!g_redirCount || !path)
        return NULL;
    n = GetFullPathNameA(path, sizeof full, full, NULL);
    if (!n || n >= sizeof full)
        return NULL;
    lower_path(full);
    if (strncmp(full, g_gameDirLower, g_gameDirLen) != 0 || full[g_gameDirLen] != '\\')
        return NULL;
    for (i = 0; i < g_redirCount; i++)
        if (strcmp(full + g_gameDirLen + 1, g_redir[i].rel) == 0)
            return g_redir[i].cache;
    return NULL;
}

typedef HANDLE(WINAPI *CreateFileA_t)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
typedef HANDLE(WINAPI *CreateFileW_t)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
typedef HANDLE(WINAPI *FindFirstFileExA_t)(LPCSTR, FINDEX_INFO_LEVELS, LPVOID, FINDEX_SEARCH_OPS, LPVOID, DWORD);
static CreateFileA_t g_realCreateFileA;
static CreateFileW_t g_realCreateFileW;
static FindFirstFileExA_t g_realFindFirstFileExA;
static int g_redirLogged;

static void log_redirect(const char *from, const char *to)
{
    if (g_redirLogged < 5) // the first few, to confirm the redirect works
    {
        g_redirLogged++;
        jp_log("redirect %s -> %s\n", from, to);
    }
}

static HANDLE WINAPI my_CreateFileA(LPCSTR name, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                   DWORD disp, DWORD flags, HANDLE tmpl)
{
    const char *to = (access & (GENERIC_WRITE | GENERIC_ALL)) ? NULL : redirect_for(name);
    if (to)
    {
        log_redirect(name, to);
        name = to;
    }
    return g_realCreateFileA(name, access, share, sa, disp, flags, tmpl);
}

static HANDLE WINAPI my_CreateFileW(LPCWSTR name, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                   DWORD disp, DWORD flags, HANDLE tmpl)
{
    char a[MAX_PATH * 2];
    WCHAR w[MAX_PATH];
    const char *to = NULL;
    if (name && !(access & (GENERIC_WRITE | GENERIC_ALL)) && g_redirCount &&
        WideCharToMultiByte(CP_ACP, 0, name, -1, a, sizeof a, NULL, NULL))
        to = redirect_for(a);
    if (to && MultiByteToWideChar(CP_ACP, 0, to, -1, w, MAX_PATH))
    {
        log_redirect(a, to);
        name = w;
    }
    return g_realCreateFileW(name, access, share, sa, disp, flags, tmpl);
}

static HANDLE WINAPI my_FindFirstFileExA(LPCSTR name, FINDEX_INFO_LEVELS level, LPVOID data,
                                         FINDEX_SEARCH_OPS op, LPVOID filter, DWORD flags)
{
    const char *to = redirect_for(name); // stat() of a translated file reports the translated size
    return g_realFindFirstFileExA(to ? to : name, level, data, op, filter, flags);
}

// Replace one entry of the exe's import address table; returns the original function.
static void *patch_iat(const char *dll, const char *func, void *hook)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)g_base;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(g_base + dos->e_lfanew);
    IMAGE_DATA_DIRECTORY dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    IMAGE_IMPORT_DESCRIPTOR *d = (IMAGE_IMPORT_DESCRIPTOR *)(g_base + dir.VirtualAddress);
    for (; dir.VirtualAddress && d->Name; d++)
    {
        IMAGE_THUNK_DATA *names, *addrs;
        if (_stricmp((const char *)(g_base + d->Name), dll) != 0)
            continue;
        names = (IMAGE_THUNK_DATA *)(g_base + (d->OriginalFirstThunk ? d->OriginalFirstThunk : d->FirstThunk));
        addrs = (IMAGE_THUNK_DATA *)(g_base + d->FirstThunk);
        for (; names->u1.AddressOfData; names++, addrs++)
        {
            IMAGE_IMPORT_BY_NAME *ibn;
            DWORD old;
            void *orig;
            if (IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal))
                continue;
            ibn = (IMAGE_IMPORT_BY_NAME *)(g_base + names->u1.AddressOfData);
            if (strcmp((const char *)ibn->Name, func) != 0)
                continue;
            orig = (void *)addrs->u1.Function;
            VirtualProtect(&addrs->u1.Function, sizeof(DWORD), PAGE_READWRITE, &old);
            addrs->u1.Function = (DWORD)hook;
            VirtualProtect(&addrs->u1.Function, sizeof(DWORD), old, &old);
            return orig;
        }
    }
    return NULL;
}

static DWORD rd32(const BYTE *p) { return *(const DWORD *)p; }

// Apply one patch entry; returns a malloc'ed buffer of dst_len bytes or NULL.
static BYTE *apply_entry(const BYTE *ops, DWORD count, const BYTE *src, DWORD srcLen, DWORD dstLen)
{
    BYTE *o = (BYTE *)malloc(dstLen ? dstLen : 1);
    DWORD k, w = 0;
    for (k = 0; o && k < count; k++)
    {
        BYTE t = *ops++;
        DWORD off, len, i;
        if (t == 2)
        {
            len = rd32(ops), ops += 4;
            if (w + len > dstLen)
                goto bad;
            memcpy(o + w, ops, len);
            ops += len;
        }
        else
        {
            off = rd32(ops), len = rd32(ops + 4), ops += 8;
            if (w + len > dstLen || !srcLen)
                goto bad;
            if (t == 1)
            {
                if (off + len > srcLen)
                    goto bad;
                memcpy(o + w, src + off, len);
            }
            else
            {
                for (i = 0; i < len; i++)
                    o[w + i] = (BYTE)(ops[i] + src[(off + i) % srcLen]);
                ops += len;
            }
        }
        w += len;
    }
    if (o && w == dstLen)
        return o;
bad:
    free(o);
    return NULL;
}

// Skip over the ops of one entry (to reach the next entry).
static const BYTE *skip_ops(const BYTE *p, DWORD count)
{
    DWORD k;
    for (k = 0; k < count; k++)
    {
        BYTE t = *p++;
        p += t == 1 ? 8 : t == 2 ? 4 + rd32(p) : 8 + rd32(p + 4);
    }
    return p;
}

static void prepare_redirects(const char *gameDir, const char *dataDir)
{
    char path[MAX_PATH], stampPath[MAX_PATH], line[MAX_PATH + 64];
    BYTE *patch, h[32];
    const BYTE *p, *end;
    DWORD size, n, i;
    WIN32_FILE_ATTRIBUTE_DATA pa;
    char *stamps = NULL; // old stamp file contents, searched by line
    DWORD stampsLen = 0;
    FILE *out;
    int made = 0, reused = 0, already = 0, mismatch = 0;

    _snprintf(path, sizeof path, "%s\\jp_patch.bin", dataDir);
    patch = read_all(path, &size);
    if (!patch)
    {
        jp_log("no %s (data files are used as they are)\n", path);
        return;
    }
    if (size < 12 || memcmp(patch, "AJPATCH1", 8) != 0 || !GetFileAttributesExA(path, GetFileExInfoStandard, &pa))
    {
        jp_log("%s is broken\n", path);
        free(patch);
        return;
    }
    lstrcpynA(g_gameDirLower, gameDir, MAX_PATH);
    lower_path(g_gameDirLower);
    g_gameDirLen = (int)strlen(g_gameDirLower);
    g_redir = (Redirect *)calloc(MAX_REDIRECTS, sizeof(Redirect));

    // A stamp line per cached file: "rel <TAB> original size <TAB> original mtime <TAB> patch stamp".
    // A cached file is reused while the original and the patch file are unchanged.
    _snprintf(stampPath, sizeof stampPath, "%s\\cache\\stamp.txt", dataDir);
    stamps = (char *)read_all(stampPath, &stampsLen);
    if (stamps)
    {
        // keep a leading '\n' so that a search for "\n<line>" only matches whole lines
        char *s = (char *)malloc(stampsLen + 2);
        s[0] = '\n';
        memcpy(s + 1, stamps, stampsLen);
        s[stampsLen + 1] = 0;
        free(stamps);
        stamps = s;
    }
    make_parent_dirs(stampPath);
    out = fopen(stampPath, "wb");

    n = rd32(patch + 8);
    p = patch + 12;
    end = patch + size;
    for (i = 0; i < n && p < end && g_redirCount < MAX_REDIRECTS; i++)
    {
        char rel[MAX_PATH], target[MAX_PATH], cache[MAX_PATH], *q;
        WORD plen = *(const WORD *)p;
        const BYTE *srcHash, *dstHash, *ops;
        DWORD srcLen, dstLen, count;
        WIN32_FILE_ATTRIBUTE_DATA fa;
        p += 2;
        if (plen >= MAX_PATH)
            break;
        memcpy(rel, p, plen);
        rel[plen] = 0;
        p += plen;
        srcLen = rd32(p), srcHash = p + 4, p += 36;
        dstLen = rd32(p), dstHash = p + 4, p += 36;
        count = rd32(p), p += 4;
        ops = p;
        p = skip_ops(p, count);
        for (q = rel; *q; q++)
            if (*q == '/')
                *q = '\\';
        _snprintf(target, sizeof target, "%s\\%s", gameDir, rel);
        _snprintf(cache, sizeof cache, "%s\\cache\\%s", dataDir, rel);
        if (!GetFileAttributesExA(target, GetFileExInfoStandard, &fa))
            continue;
        _snprintf(line, sizeof line, "\n%s\t%lu\t%lu.%lu\t%lu.%lu\n", rel, fa.nFileSizeLow,
                  fa.ftLastWriteTime.dwHighDateTime, fa.ftLastWriteTime.dwLowDateTime,
                  pa.ftLastWriteTime.dwHighDateTime, pa.ftLastWriteTime.dwLowDateTime);
        if (stamps && strstr(stamps, line) && GetFileAttributesExA(cache, GetFileExInfoStandard, &fa) &&
            fa.nFileSizeLow == dstLen)
        {
            reused++;
        }
        else
        {
            DWORD olen;
            BYTE *orig = read_all(target, &olen), *res = NULL;
            if (!orig)
                continue;
            sha256(orig, olen, h);
            if (olen == dstLen && memcmp(h, dstHash, 32) == 0)
            {
                already++; // the game file is already the Japanese one
                free(orig);
                continue;
            }
            if (olen == srcLen && memcmp(h, srcHash, 32) == 0)
                res = apply_entry(ops, count, orig, olen, dstLen);
            if (res)
                sha256(res, dstLen, h);
            if (!res || memcmp(h, dstHash, 32) != 0)
            {
                if (mismatch++ < 10)
                    jp_log("not translated (the original differs): %s\n", rel);
                free(orig);
                free(res);
                continue;
            }
            {
                FILE *f;
                make_parent_dirs(cache);
                f = fopen(cache, "wb");
                if (!f || fwrite(res, 1, dstLen, f) != dstLen)
                {
                    jp_log("cannot write %s\n", cache);
                    if (f)
                        fclose(f);
                    free(orig);
                    free(res);
                    continue;
                }
                fclose(f);
            }
            made++;
            free(orig);
            free(res);
        }
        if (out)
            fputs(line + 1, out);
        lstrcpynA(g_redir[g_redirCount].rel, rel, MAX_PATH);
        lower_path(g_redir[g_redirCount].rel);
        lstrcpynA(g_redir[g_redirCount].cache, cache, MAX_PATH);
        g_redirCount++;
    }
    if (out)
        fclose(out);
    free(stamps);
    free(patch);
    jp_log("data files: %d translated (%d built, %d cached), %d already Japanese, %d left as they are\n",
           g_redirCount, made, reused, already, mismatch);
    if (!g_redirCount)
        return;
    g_realCreateFileA = (CreateFileA_t)patch_iat("kernel32.dll", "CreateFileA", (void *)my_CreateFileA);
    g_realCreateFileW = (CreateFileW_t)patch_iat("kernel32.dll", "CreateFileW", (void *)my_CreateFileW);
    g_realFindFirstFileExA = (FindFirstFileExA_t)patch_iat("kernel32.dll", "FindFirstFileExA", (void *)my_FindFirstFileExA);
    if (!g_realCreateFileA)
        g_realCreateFileA = CreateFileA;
    if (!g_realCreateFileW)
        g_realCreateFileW = CreateFileW;
    if (!g_realFindFirstFileExA)
        g_realFindFirstFileExA = FindFirstFileExA;
    jp_log("file redirect installed\n");
}


// ---------------------------------------------------------------- finding the hook points
// Every address the DLL uses is located at start-up with the byte patterns made by
// tools/gen_hooks.py from the Steam build (absolute addresses and call targets are wildcards),
// so that other builds of the same game can work too. In the Steam build each pattern is first
// checked at its known place; otherwise the whole code section is searched and only a unique
// match is used. Variables are read from the instructions of the functions found.
// When anything is missing, nothing is changed and the game runs in English.
typedef struct
{
    const char *name;
    DWORD steamVa;
    const char *pat;
} HookPat;
typedef struct
{
    const char *name;
    int pat, kind, off;
    DWORD steamVal;
} HookVal;
enum { HK_START, HK_ABS, HK_CALL };

// Generated by tools/gen_hooks.py from the Steam build. Do not edit by hand.
static const HookPat kHookPats[] = {
    {"tok_count", 0x457b40, "55 8B EC 51 53 8B 59 04 56 33 F6 3B DE 7F 08 5E 33 C0 5B 8B E5 5D C3 83 C8 FF 89 75 FC 3B DE 7E 5B 57 8B 39 8B D0 8A 04 37 3C 20 74 34 3C 0D 74 30 3C 09 74 2C 3C 30 7C 0B 3C 39 7F 07 B8 02 00 00 00 EB 26 3C 61 7C 04 3C 7A 7E 19 3C 41 7C 04 3C 5A 7E 11 33 C9 3C 5F 0F 95 C1 8D 44 09 01 EB 09 33 C0 EB 11 B8 01 00 00 00 3B D0 75 05 83 F8"},
};
enum { HP_TOK_COUNT, HP_COUNT };
static const HookVal kHookVals[] = {
    {"tok_class", HP_TOK_COUNT, HK_START, 53, 0x457b75},
    {"tok_digit", HP_TOK_COUNT, HK_START, 61, 0x457b7d},
    {"tok_other", HP_TOK_COUNT, HK_START, 68, 0x457b84},
    {"tok_letter", HP_TOK_COUNT, HK_START, 101, 0x457ba5},
};
enum { HV_TOK_CLASS, HV_TOK_DIGIT, HV_TOK_OTHER, HV_TOK_LETTER, HV_COUNT };


static DWORD g_hv[HV_COUNT];   // Steam-build style addresses (use with VA())
static BYTE *g_codeStart, *g_codeEnd;
static int g_forceScan;        // [debug] force_scan: 1 = always search, 2 = pretend one is missing

static int hook_parse(const char *s, BYTE *bytes, BYTE *mask)
{
    int n = 0;
    while (*s)
    {
        if (*s == ' ')
        {
            s++;
            continue;
        }
        if (s[0] == '?')
            bytes[n] = 0, mask[n] = 0;
        else
            bytes[n] = (BYTE)strtoul(s, NULL, 16), mask[n] = 1;
        n++;
        s += 2;
    }
    return n;
}

static int hook_match(const BYTE *p, const BYTE *bytes, const BYTE *mask, int n)
{
    int i;
    if (p < g_codeStart || p + n > g_codeEnd)
        return 0;
    for (i = 0; i < n; i++)
        if (mask[i] && p[i] != bytes[i])
            return 0;
    return 1;
}

static BYTE *hook_find(const HookPat *pt, int *scanned)
{
    size_t len = strlen(pt->pat) / 3 + 2;
    BYTE *bytes = (BYTE *)malloc(len), *mask = (BYTE *)malloc(len), *p, *hit = NULL;
    int n = hook_parse(pt->pat, bytes, mask), hits = 0, first = 0;
    *scanned = 0;
    if (!g_forceScan && hook_match((BYTE *)VA(pt->steamVa), bytes, mask, n))
        hit = (BYTE *)VA(pt->steamVa); // the Steam build: the known place
    else
    {
        *scanned = 1;
        while (first < n && !mask[first])
            first++;
        for (p = g_codeStart; p + n <= g_codeEnd; p++)
            if (p[first] == bytes[first] && hook_match(p, bytes, mask, n))
            {
                hits++;
                hit = p;
            }
        if (hits != 1)
        {
            jp_log("pattern %s: %d matches\n", pt->name, hits);
            hit = NULL;
        }
    }
    free(bytes);
    free(mask);
    return hit;
}

static DWORD unreloc_va(DWORD runtime) { return runtime - (DWORD)g_base + 0x400000; }

// Fills g_hv. Returns 1 when every hook point was found.
static int resolve_hooks(const char *exeName)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)g_base;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(g_base + dos->e_lfanew);
    IMAGE_SECTION_HEADER *sec = IMAGE_FIRST_SECTION(nt);
    BYTE *m[HP_COUNT];
    int i, scanned = 0, ok = 1, same = 1;
    for (i = 0; i < nt->FileHeader.NumberOfSections; i++)
        if (sec[i].Characteristics & IMAGE_SCN_CNT_CODE)
        {
            g_codeStart = g_base + sec[i].VirtualAddress;
            g_codeEnd = g_codeStart + sec[i].Misc.VirtualSize;
            break;
        }
    if (!g_codeStart)
        return 0;
    for (i = 0; i < HP_COUNT; i++)
    {
        int s;
        m[i] = hook_find(&kHookPats[i], &s);
        scanned += s;
        if (g_forceScan == 2 && i == HP_COUNT - 1)
            m[i] = NULL; // [debug] force_scan=2: pretend one is missing (tests the fall-back to English)
        if (!m[i])
        {
            jp_log("not found in this %s: %s\n", exeName, kHookPats[i].name);
            ok = 0;
        }
    }
    for (i = 0; i < HV_COUNT; i++)
    {
        const HookVal *v = &kHookVals[i];
        BYTE *p = m[v->pat];
        DWORD val = 0;
        if (p)
        {
            if (v->kind == HK_START)
                val = unreloc_va((DWORD)p + v->off);
            else if (v->kind == HK_ABS)
                val = unreloc_va(*(DWORD *)(p + v->off));
            else
                val = unreloc_va((DWORD)(p + v->off + 4) + *(DWORD *)(p + v->off));
        }
        g_hv[i] = val;
        if (val != v->steamVal)
        {
            same = 0;
            jp_log("  %-12s %06x (Steam build: %06x)\n", v->name, val, v->steamVal);
        }
    }
    jp_log("hook points: %s%s\n", same ? "same as the Steam build" : "differ from the Steam build (see above)",
           scanned ? (g_forceScan ? " [search forced by force_scan]" : " [searched]") : "");
    return ok;
}

// ---------------------------------------------------------------- config
static char g_fontFace[64] = "";  // empty: keep the game's fonts (Japanese comes from Windows' font linking)
static int g_sizeAdjust = 0;       // added to the height of every font the game makes

static void load_config(const char *dir)
{
    char ini[MAX_PATH];
    _snprintf(ini, sizeof ini, "%s\\avernum_jp.ini", dir);
    GetPrivateProfileStringA("font", "face", g_fontFace, g_fontFace, sizeof g_fontFace, ini);
    g_sizeAdjust = GetPrivateProfileIntA("font", "size_adjust", g_sizeAdjust, ini);
    g_forceScan = GetPrivateProfileIntA("debug", "force_scan", 0, ini);
}

// ---------------------------------------------------------------- text encoding
// The game converts its text with CP_THREAD_ACP (3). Those conversions are switched to
// EUC-JP. CP_ACP (0) is used for file paths and is left alone, except for the one
// conversion of a string-table text right after LoadStringW (see my_LoadStringW).
typedef int(WINAPI *MB2WC_t)(UINT, DWORD, LPCCH, int, LPWSTR, int);
typedef int(WINAPI *WC2MB_t)(UINT, DWORD, LPCWCH, int, LPSTR, int, LPCCH, LPBOOL);
static MB2WC_t g_realMB2WC;
static WC2MB_t g_realWC2MB;
static volatile LONG g_nextAcpIsGame; // set by my_LoadStringW for the following CP_ACP conversion

static int WINAPI my_MultiByteToWideChar(UINT cp, DWORD flags, LPCCH s, int n, LPWSTR w, int wn)
{
    if (cp == CP_THREAD_ACP)
    {
        cp = GAME_CP;
        flags = 0; // MB_PRECOMPOSED etc. are not accepted for 20932
    }
    return g_realMB2WC(cp, flags, s, n, w, wn);
}

static int WINAPI my_WideCharToMultiByte(UINT cp, DWORD flags, LPCWCH w, int wn, LPSTR s, int n,
                                         LPCCH def, LPBOOL used)
{
    if (cp == CP_THREAD_ACP || (cp == CP_ACP && InterlockedExchange(&g_nextAcpIsGame, 0)))
    {
        cp = GAME_CP;
        flags = 0;
    }
    return g_realWC2MB(cp, flags, w, wn, s, n, def, used);
}

// ---------------------------------------------------------------- character counts
// The game passes strlen() of the byte string as the character count of the converted
// wide string. For Japanese (2 bytes a character) that runs past the end of the text:
// the width comes out too large and garbage is drawn after the text.
typedef int(WINAPI *DrawTextW_t)(HDC, LPCWSTR, int, LPRECT, UINT);
typedef BOOL(WINAPI *GetTextExtentPoint32W_t)(HDC, LPCWSTR, int, LPSIZE);
static DrawTextW_t g_realDrawTextW;
static GetTextExtentPoint32W_t g_realGTEP32W;

static int WINAPI my_DrawTextW(HDC dc, LPCWSTR s, int n, LPRECT r, UINT fmt)
{
    if (s && n > 0)
        n = (int)wcsnlen(s, n);
    return g_realDrawTextW(dc, s, n, r, fmt);
}

static BOOL WINAPI my_GetTextExtentPoint32W(HDC dc, LPCWSTR s, int n, LPSIZE sz)
{
    if (s && n > 0)
        n = (int)wcsnlen(s, n);
    return g_realGTEP32W(dc, s, n, sz);
}

// ---------------------------------------------------------------- fonts
typedef HFONT(WINAPI *CreateFontW_t)(int, int, int, int, int, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD,
                                     DWORD, DWORD, LPCWSTR);
static CreateFontW_t g_realCreateFontW;
static int g_fontLogged;

static HFONT WINAPI my_CreateFontW(int h, int w, int esc, int ori, int weight, DWORD italic, DWORD under,
                                   DWORD strike, DWORD charset, DWORD outPrec, DWORD clipPrec, DWORD quality,
                                   DWORD pitch, LPCWSTR face)
{
    WCHAR wface[64];
    if (g_fontLogged < 8)
    {
        char a[64] = "";
        if (face)
            WideCharToMultiByte(CP_UTF8, 0, face, -1, a, sizeof a, NULL, NULL);
        jp_log("CreateFontW h=%d w=%d weight=%d charset=%lu face=%s\n", h, w, weight, charset, a);
        g_fontLogged++;
    }
    if (g_fontFace[0] && MultiByteToWideChar(CP_UTF8, 0, g_fontFace, -1, wface, 64))
    {
        face = wface;
        charset = SHIFTJIS_CHARSET;
    }
    if (g_sizeAdjust && h)
        h += h < 0 ? -g_sizeAdjust : g_sizeAdjust;
    return g_realCreateFontW(h, w, esc, ori, weight, italic, under, strike, charset, outPrec, clipPrec,
                             quality, pitch, face);
}

// ---------------------------------------------------------------- string table
// avernum_jp_strtab.tsv (UTF-8, tab separated): id, english, japanese.
typedef int(WINAPI *LoadStringW_t)(HINSTANCE, UINT, LPWSTR, int);
static LoadStringW_t g_realLoadStringW;
typedef struct
{
    UINT id;
    WCHAR *text;
} StrTab;
static StrTab *g_strtab;
static int g_strtabCount;

static int cmp_strtab(const void *a, const void *b)
{
    UINT x = ((const StrTab *)a)->id, y = ((const StrTab *)b)->id;
    return x < y ? -1 : x > y;
}

static const WCHAR *strtab_get(UINT id)
{
    int lo = 0, hi = g_strtabCount;
    while (lo < hi)
    {
        int mid = (lo + hi) / 2;
        if (g_strtab[mid].id < id)
            lo = mid + 1;
        else
            hi = mid;
    }
    return lo < g_strtabCount && g_strtab[lo].id == id ? g_strtab[lo].text : NULL;
}

static int WINAPI my_LoadStringW(HINSTANCE inst, UINT id, LPWSTR buf, int max)
{
    const WCHAR *t = strtab_get(id);
    int n;
    InterlockedExchange(&g_nextAcpIsGame, 1); // the game converts the result with CP_ACP next
    if (!t)
        return g_realLoadStringW(inst, id, buf, max);
    n = (int)wcslen(t);
    if (max == 0)
    {
        *(const WCHAR **)buf = t; // read-only pointer, as LoadStringW does with cchBufferMax 0
        return n;
    }
    if (max < 1)
        return 0;
    if (n >= max)
        n = max - 1;
    memcpy(buf, t, n * sizeof(WCHAR));
    buf[n] = 0;
    return n;
}

static void load_string_table(const char *dir)
{
    char path[MAX_PATH], *buf, *line, *next;
    DWORD size;
    int cap = 0, skipped = 0;
    _snprintf(path, sizeof path, "%s\\avernum_jp_strtab.tsv", dir);
    buf = (char *)read_all(path, &size);
    if (!buf)
    {
        jp_log("no %s (string table stays English)\n", path);
        return;
    }
    buf = (char *)realloc(buf, size + 1);
    buf[size] = 0;
    for (line = buf; line && *line; line = next)
    {
        char *col[3] = {0}, *p;
        int c = 0, wn;
        next = strchr(line, '\n');
        if (next)
            *next++ = 0;
        if ((p = strchr(line, '\r')) != NULL)
            *p = 0;
        col[0] = line;
        for (p = line; *p && c < 2; p++)
            if (*p == '\t')
            {
                *p = 0;
                col[++c] = p + 1;
            }
        if (c < 2 || !col[2][0] || !(col[0][0] >= '0' && col[0][0] <= '9'))
            continue;
        unescape(col[2]);
        wn = MultiByteToWideChar(CP_UTF8, 0, col[2], -1, NULL, 0);
        if (wn <= 0)
        {
            skipped++;
            continue;
        }
        if (g_strtabCount == cap)
        {
            cap = cap ? cap * 2 : 1024;
            g_strtab = (StrTab *)realloc(g_strtab, cap * sizeof(StrTab));
        }
        g_strtab[g_strtabCount].id = (UINT)strtoul(col[0], NULL, 10);
        g_strtab[g_strtabCount].text = (WCHAR *)malloc(wn * sizeof(WCHAR));
        MultiByteToWideChar(CP_UTF8, 0, col[2], -1, g_strtab[g_strtabCount].text, wn);
        g_strtabCount++;
    }
    free(buf);
    qsort(g_strtab, g_strtabCount, sizeof(StrTab), cmp_strtab);
    jp_log("string table: %d translated, %d skipped\n", g_strtabCount, skipped);
}

// ---------------------------------------------------------------- script token estimate
// Before tokenizing a script, the game (0x457b40) estimates the token count to size the token array.
// It counts every byte that is not a digit, letter, '_' or blank as its own token -- also
// inside string literals -- so Japanese adds 2 per character, a long dialogue file overflows
// the count, the allocation fails and the CRT aborts ("Runtime Error!" while loading
// dialogue scripts). A literal is still one token, so classify bytes >= 0x80 like letters.
//   tok_class (0x457b75): cmp al,30h / jl tok_other / cmp al,39h / jg tok_other -> jmp tok_class_stub
// (the DLL finds these places with src_hooks.c, so other builds of the game work too)
#define A4_TOKCLASS g_hv[HV_TOK_CLASS]
#define A4_TOK_DIGIT g_hv[HV_TOK_DIGIT]
#define A4_TOK_OTHER g_hv[HV_TOK_OTHER]
#define A4_TOK_LETTER g_hv[HV_TOK_LETTER]
static const BYTE kTokClassOrig[8] = {0x3C, 0x30, 0x7C, 0x0B, 0x3C, 0x39, 0x7F, 0x07};
static DWORD g_tokDigit, g_tokOther, g_tokLetter;

__declspec(naked) static void tok_class_stub(void)
{
    __asm {
        test al, al
        js letter
        cmp al, 0x30
        jl other
        cmp al, 0x39
        jg other
        jmp dword ptr [g_tokDigit]
    other:
        jmp dword ptr [g_tokOther]
    letter:
        jmp dword ptr [g_tokLetter]
    }
}

static void install_token_estimate_fix(void)
{
    BYTE *p = (BYTE *)VA(A4_TOKCLASS);
    DWORD old;
    if (memcmp(p, kTokClassOrig, sizeof kTokClassOrig) != 0)
    {
        jp_log("token estimate fix skipped: unexpected bytes at %06x\n", A4_TOKCLASS);
        return;
    }
    g_tokDigit = (DWORD)VA(A4_TOK_DIGIT);
    g_tokOther = (DWORD)VA(A4_TOK_OTHER);
    g_tokLetter = (DWORD)VA(A4_TOK_LETTER);
    VirtualProtect(p, 8, PAGE_EXECUTE_READWRITE, &old);
    p[0] = 0xE9;
    *(DWORD *)(p + 1) = (DWORD)tok_class_stub - (DWORD)(p + 5);
    p[5] = p[6] = p[7] = 0x90;
    VirtualProtect(p, 8, old, &old);
    FlushInstructionCache(GetCurrentProcess(), p, 8);
    jp_log("token estimate fix installed\n");
}

// ---------------------------------------------------------------- start-up
static void install_text_hooks(void)
{
    g_realMB2WC = (MB2WC_t)patch_iat("kernel32.dll", "MultiByteToWideChar", (void *)my_MultiByteToWideChar);
    g_realWC2MB = (WC2MB_t)patch_iat("kernel32.dll", "WideCharToMultiByte", (void *)my_WideCharToMultiByte);
    g_realDrawTextW = (DrawTextW_t)patch_iat("user32.dll", "DrawTextW", (void *)my_DrawTextW);
    g_realGTEP32W = (GetTextExtentPoint32W_t)patch_iat("gdi32.dll", "GetTextExtentPoint32W", (void *)my_GetTextExtentPoint32W);
    g_realCreateFontW = (CreateFontW_t)patch_iat("gdi32.dll", "CreateFontW", (void *)my_CreateFontW);
    g_realLoadStringW = (LoadStringW_t)patch_iat("user32.dll", "LoadStringW", (void *)my_LoadStringW);
    jp_log("hooks: MultiByteToWideChar %s, WideCharToMultiByte %s, DrawTextW %s, GetTextExtentPoint32W %s, "
           "CreateFontW %s, LoadStringW %s\n",
           g_realMB2WC ? "ok" : "MISSING", g_realWC2MB ? "ok" : "MISSING", g_realDrawTextW ? "ok" : "MISSING",
           g_realGTEP32W ? "ok" : "MISSING", g_realCreateFontW ? "ok" : "MISSING", g_realLoadStringW ? "ok" : "MISSING");
    if (!g_realMB2WC)
        g_realMB2WC = MultiByteToWideChar;
    if (!g_realWC2MB)
        g_realWC2MB = WideCharToMultiByte;
    if (!g_realDrawTextW)
        g_realDrawTextW = DrawTextW;
    if (!g_realGTEP32W)
        g_realGTEP32W = GetTextExtentPoint32W;
    if (!g_realCreateFontW)
        g_realCreateFontW = CreateFontW;
    if (!g_realLoadStringW)
        g_realLoadStringW = LoadStringW;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        char dir[MAX_PATH], data[MAX_PATH], path[MAX_PATH], *p;
        DWORD attr;
        DisableThreadLibraryCalls(inst);
        GetModuleFileNameA(inst, dir, MAX_PATH);
        p = strrchr(dir, '\\');
        if (p)
            *p = 0;
        _snprintf(data, sizeof data, "%s\\avernum_jp", dir);
        attr = GetFileAttributesA(data);
        if (attr == INVALID_FILE_ATTRIBUTES || !(attr & FILE_ATTRIBUTE_DIRECTORY))
            lstrcpynA(data, dir, MAX_PATH);
        _snprintf(path, sizeof path, "%s\\avernum_jp.log", data);
        g_log = fopen(path, "w");
        load_config(dir);
        g_base = (BYTE *)GetModuleHandleA(NULL);
        jp_log("Avernum 4 JP hook loaded. base=%p face=%s\n", g_base, g_fontFace[0] ? g_fontFace : "(game)");
        if (!resolve_hooks("Avernum 4.exe"))
        {
            jp_log("this Avernum 4.exe is not supported: Japanese is turned off and the game runs unchanged\n");
            return TRUE;
        }
        install_text_hooks();
        install_token_estimate_fix();
        load_string_table(data);
        load_exe_strings(data);
        prepare_redirects(dir, data);
    }
    return TRUE;
}
