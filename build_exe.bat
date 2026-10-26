@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo          VOIDORGANIZE STANDALONE BUILD SCRIPT
echo =======================================================
echo.

cd /d "%~dp0"

set PYTHON=python
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set PYTHON="%LocalAppData%\Programs\Python\Python312\python.exe"
)

echo [*] Checking icon assets...
if not exist "icon.ico" (
    echo [*] Generating icons...
    %PYTHON% generate_icon.py
)

echo [*] Checking and installing Python dependencies...
%PYTHON% -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [-] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [*] Compiling standalone portable VoidOrganize.exe with PyInstaller...
echo.

%PYTHON% -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --clean ^
    --icon "icon.ico" ^
    --add-data "icon.ico;." ^
    --add-data "icon.png;." ^
    --name "VoidOrganize" ^
    --collect-all "customtkinter" ^
    main.py

if errorlevel 1 (
    echo.
    echo [-] PyInstaller build failed! Review errors above.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo [x] BUILD SUCCESSFUL!
echo [x] Executable: dist\VoidOrganize.exe
echo =======================================================
echo.
pause
