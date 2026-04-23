@echo off
:: build_and_deploy.bat
::
:: Compiles rapl_reader_cli.c
::
:: Usage:
::   1. Open "x64 Native Tools Command Prompt for VS 2022"
::   2. cd to this folder
::   3. Run: build.bat

echo.
echo ============================================================
echo   Windows RAPL Reader - Build and Deploy
echo ============================================================
echo.

:: ── Check if cl.exe is available ─────────────────────────────
where cl.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] cl.exe not found!
    echo Please run this script from the
    echo "x64 Native Tools Command Prompt for VS 2022"
    exit /b 1
)

:: ── Compile ───────────────────────────────────────────────────
echo [1/3] Compiling rapl_reader_cli.c ...
cl rapl_reader_cli.c /Fe:metric-provider-binary /O2 /W3 /nologo /link winmm.lib
if %errorlevel% neq 0 (
    echo [ERROR] Compilation failed!
    exit /b 1
)
echo [OK] Compiled successfully.