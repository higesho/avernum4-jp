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

