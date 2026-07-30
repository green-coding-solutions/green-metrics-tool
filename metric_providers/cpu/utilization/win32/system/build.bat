@echo off
:: build.bat
::
:: Compiles source.c for the Windows CPU Utilization System Provider
::
:: Usage:
::   1. Open "x64 Native Tools Command Prompt for VS 2022"
::   2. cd to this folder
::   3. Run: build.bat

echo.
echo ============================================================
echo   CPU Utilization Windows System Provider - Build
echo ============================================================
echo.

where cl.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] cl.exe not found!
    echo Please run this script from the
    echo "x64 Native Tools Command Prompt for VS 2022"
    exit /b 1
)

echo [1/2] Compiling source.c ...
cl source.c /Fe:metric-provider-binary /O2 /W3 /nologo /link winmm.lib
if %errorlevel% neq 0 (
    echo [ERROR] Compilation failed!
    exit /b 1
)
echo [OK] Compiled successfully.
