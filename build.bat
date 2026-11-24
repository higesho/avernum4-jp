@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul || exit /b 1
cd /d "%~dp0"
rem build.bat      : 配布版 dsound.dll (here)
rem build.bat test : 試験版 build\test\dsound.dll ([debug] in the ini works; do not distribute)
set O=build\release
set OUT=dsound.dll
set DEF=
if "%1"=="test" (
  set O=build\test
  set OUT=build\test\dsound.dll
  set DEF=/DAVJP_TEST
)
if not exist %O% mkdir %O%
rc /nologo /fo %O%\avernum_jp.res avernum_jp.rc || exit /b 1
cl /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS /utf-8 /LD /MT %DEF% /Fo%O%\ avernum_jp.c %O%\avernum_jp.res /link /DEF:dsound.def /OUT:%OUT% /IMPLIB:%O%\dsound.lib || exit /b 1
echo BUILD OK %OUT%
