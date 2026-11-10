
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

// ---------------------------------------------------------------- resolution at startup
// With "Don't Change Resolution" (also "Don't Change" / "Never Change" in the start-up question) the
// game only runs when the desktop is exactly 16-bit colour and at least 1024x768; otherwise it shows
// "Avernum 4 requires the monitor to be set to exactly 16 Bit color ..." and quits, every time, and
// the setting can no longer be changed in the game. Today's desktops are 32-bit, so in that case the
// game is sent down the "Change Resolution" path instead (the setting is changed to it as well).
//   res_keep (0x408eff): lea edx,[ebp-14h] / push edx / call [GetDesktopWindow]   -> jmp res_keep_stub
//   res_keep_back (0x408f09): the instruction after that call; res_done (0x408f56): "Change" path
#define A4_RES_SETTING g_hv[HV_RES_SETTING] /* word: 0 ask, 1 change, 2 don't change */
#define A4_RES_KEEP g_hv[HV_RES_KEEP]
#define A4_RES_KEEP_BACK g_hv[HV_RES_KEEP_BACK]
#define A4_RES_DONE g_hv[HV_RES_DONE]
static const BYTE kResKeepOrig[6] = {0x8D, 0x55, 0xEC, 0x52, 0xFF, 0x15};
static DWORD g_resKeepBack, g_resDone, g_resOk;
static HWND(WINAPI *g_getDesktopWindow)(void) = GetDesktopWindow;

static void __cdecl check_desktop_mode(void)
{
    HDC dc = GetDC(NULL);
    int bpp = GetDeviceCaps(dc, BITSPIXEL);
    RECT r;
    ReleaseDC(NULL, dc);
    GetWindowRect(GetDesktopWindow(), &r);
    g_resOk = bpp == 16 && r.right - r.left >= 1024 && r.bottom - r.top >= 768;
    if (!g_resOk)
    {
        jp_log("\"Don't Change Resolution\" needs a 16-bit desktop of 1024x768 or more (this one: %d bit, %dx%d): "
               "the resolution is changed instead\n", bpp, (int)(r.right - r.left), (int)(r.bottom - r.top));
        if (*(short *)VA(A4_RES_SETTING) == 2)
            *(short *)VA(A4_RES_SETTING) = 1;
    }
}

__declspec(naked) static void res_keep_stub(void)
{
    __asm {
        pushad
        call check_desktop_mode
        popad
        cmp g_resOk, 0
        je change
        lea edx, [ebp - 0x14]
        push edx
        call dword ptr [g_getDesktopWindow]
        jmp dword ptr [g_resKeepBack]
    change:
        jmp dword ptr [g_resDone]
    }
}

static void install_resolution_fix(void)
{
    BYTE *p = (BYTE *)VA(A4_RES_KEEP);
    DWORD old;
    if (memcmp(p, kResKeepOrig, sizeof kResKeepOrig) != 0)
    {
        jp_log("resolution fix skipped: unexpected bytes at %06x\n", A4_RES_KEEP);
        return;
    }
    g_resKeepBack = (DWORD)VA(A4_RES_KEEP_BACK);
    g_resDone = (DWORD)VA(A4_RES_DONE);
    VirtualProtect(p, 5, PAGE_EXECUTE_READWRITE, &old);
    p[0] = 0xE9;
    *(DWORD *)(p + 1) = (DWORD)res_keep_stub - (DWORD)(p + 5);
    VirtualProtect(p, 5, old, &old);
    FlushInstructionCache(GetCurrentProcess(), p, 5);
    jp_log("resolution fix installed\n");
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
        install_resolution_fix();
        load_string_table(data);
        load_exe_strings(data);
        prepare_redirects(dir, data);
    }
    return TRUE;
}
