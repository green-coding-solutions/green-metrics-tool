@echo off
:: build_and_deploy.bat
::
:: Compiles rapl_reader_cli.c and deploys rapl_reader.exe to C:\rapl\
::
:: Usage:
::   1. Open "x64 Native Tools Command Prompt for VS 2022"
::   2. cd to this folder
::   3. Run: build_and_deploy.bat

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
cl rapl_reader_cli.c /Fe:rapl_reader.exe /O2 /W3 /nologo
if %errorlevel% neq 0 (
    echo [ERROR] Compilation failed!
    exit /b 1
)
echo [OK] Compiled successfully.
echo.

:: ── Create deploy folder ──────────────────────────────────────
echo [2/3] Creating C:\rapl\ ...
if not exist "C:\rapl\" (
    mkdir "C:\rapl\"
    echo [OK] Created C:\rapl\
) else (
    echo [OK] C:\rapl\ already exists.
)
echo.

:: ── Deploy ────────────────────────────────────────────────────
echo [3/3] Copying rapl_reader.exe to C:\rapl\ ...
copy /Y rapl_reader.exe "C:\rapl\rapl_reader.exe" >nul
if %errorlevel% neq 0 (
    echo [ERROR] Copy failed! Try running as Administrator.
    exit /b 1
)
echo [OK] Deployed to C:\rapl\rapl_reader.exe
echo.

:: ── Done ──────────────────────────────────────────────────────
echo ============================================================
echo   Done! rapl_reader.exe is ready at C:\rapl\
echo.
echo   Next steps:
echo   1. Make sure ScaphandreDrv driver is running
echo   2. In GMT config.yml set:
echo      rapl_reader_exe: 'C:\rapl\rapl_reader.exe'
echo ============================================================
echo.
