@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul || exit /b 1
cd /d "%~dp0"
cl /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS /utf-8 /LD /MT avernum_jp.c /link /DEF:dsound.def /OUT:dsound.dll || exit /b 1
echo BUILD OK
