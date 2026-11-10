
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

/*HOOK_TABLES*/

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
