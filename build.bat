@echo off
setlocal
title Phoenix Marketing — Build

echo ═══════════════════════════════════════════════════════
echo  Phoenix Solutions — Blog Marketing Automation Builder
echo ═══════════════════════════════════════════════════════
echo.

:: Activate virtual environment if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment activated.
) else (
    echo [WARN] No .venv found — using system Python.
)

:: Install / upgrade PyInstaller
echo.
echo Installing PyInstaller...
pip install pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause & exit /b 1
)

:: Clean previous build
echo.
echo Cleaning previous build...
if exist "dist\PhoenixMarketing" rmdir /s /q "dist\PhoenixMarketing"
if exist "build"                 rmdir /s /q "build"

:: Run PyInstaller (prefer venv binary so the correct Python is used)
echo.
echo Building exe...
if exist ".venv\Scripts\pyinstaller.exe" (
    .venv\Scripts\pyinstaller.exe phoenix.spec --clean --noconfirm
) else (
    pyinstaller phoenix.spec --clean --noconfirm
)
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check output above.
    pause & exit /b 1
)

:: Copy .env.example next to exe so user knows what to fill in
echo.
echo Copying .env.example to dist folder...
copy ".env.example" "dist\PhoenixMarketing\.env.example" >nul 2>&1

:: Create empty user-data folders next to exe
echo Creating output folders...
if not exist "dist\PhoenixMarketing\Blogs\images"   mkdir "dist\PhoenixMarketing\Blogs\images"
if not exist "dist\PhoenixMarketing\LinkedIn Posts" mkdir "dist\PhoenixMarketing\LinkedIn Posts"
if not exist "dist\PhoenixMarketing\MarketingSchedule" mkdir "dist\PhoenixMarketing\MarketingSchedule"

:: Copy ResearchTopics if it exists
if exist "MarketingSchedule\ResearchTopics.json" (
    copy "MarketingSchedule\ResearchTopics.json" "dist\PhoenixMarketing\MarketingSchedule\" >nul 2>&1
)

echo.
echo ═══════════════════════════════════════════════════════
echo  BUILD COMPLETE
echo ═══════════════════════════════════════════════════════
echo.
echo  Location : dist\PhoenixMarketing\PhoenixMarketing.exe
echo.
echo  BEFORE RUNNING:
echo    1. Copy your .env to:  dist\PhoenixMarketing\.env
echo    2. OR open the app and fill in Settings tab to create .env
echo.
pause
