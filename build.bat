@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo   Build LocalStudyRAGAgent_Setup.exe (Full Offline Installer)
echo ============================================================
echo.
echo Quy trinh build:
echo   1. PyInstaller: build app .exe
echo   2. Prepare bundle: Ollama installer + portable GCC + models
echo   3. Inno Setup: dong goi tat ca thanh 1 file cai dat

call venv\Scripts\activate

:: ── Step 1: PyInstaller ──────────────────────────────────────────────────────
echo.
echo [1/4] Dang build app voi PyInstaller...
pip install pyinstaller -q
pyinstaller ^
  --name "LocalStudyRAGAgent" ^
  --windowed ^
  --onedir ^
  --add-data "ui/style.qss;ui" ^
  --add-data "ui/setup_wizard.py;ui" ^
  --add-data "subjects;subjects" ^
  --add-data "global_config.yaml;." ^
  --hidden-import "PyQt6.QtWebEngineWidgets" ^
  --hidden-import "chromadb" ^
  --hidden-import "pdfplumber" ^
  --hidden-import "genanki" ^
  main.py
if errorlevel 1 (echo [LOI] PyInstaller that bai! & pause & exit /b 1)
echo [OK] App build xong.

:: ── Step 2: Prepare bundle folder ──────────────────────────────────────────
echo.
echo [2/4] Chuan bi bundle...
mkdir dist\bundle 2>nul

:: Download Ollama installer if not present
if not exist dist\bundle\OllamaSetup.exe (
    echo [..] Dang tai Ollama installer...
    powershell -Command "Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile 'dist\bundle\OllamaSetup.exe'"
)
echo [OK] Ollama installer san sang.

:: Download portable GCC (winlibs.com) if not present
if not exist dist\bundle\gcc\bin\gcc.exe (
    echo [..] Dang tai portable GCC/G++ (~120MB)...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/brechtsanders/winlibs_mingw/releases/download/14.2.0posix-12.0.0-ucrt-r1/winlibs-x86_64-posix-seh-gcc-14.2.0-mingw-w64ucrt-12.0.0-r1.zip' -OutFile 'dist\bundle\gcc.zip'"
    powershell -Command "Expand-Archive -Path 'dist\bundle\gcc.zip' -DestinationPath 'dist\bundle\gcc_temp'"
    move dist\bundle\gcc_temp\mingw64 dist\bundle\gcc >nul
    rmdir /s /q dist\bundle\gcc_temp
    del dist\bundle\gcc.zip
)
echo [OK] Portable GCC san sang.

:: ── Step 3: Copy Ollama models (pre-downloaded on dev machine) ──────────────
echo.
echo [3/4] Dang chuan bi model files...
set OLLAMA_MODELS=%LOCALAPPDATA%\Programs\Ollama\models
if exist "%OLLAMA_MODELS%" (
    echo [..] Copy model files vao bundle (~5GB, co the mat vai phut)...
    xcopy "%OLLAMA_MODELS%" "dist\bundle\models\" /E /I /Y /Q
    echo [OK] Model files da copy.
) else (
    echo [CANH BAO] Khong tim thay Ollama models tai: %OLLAMA_MODELS%
    echo            Nguoi dung se tu dong tai model lan dau chay app.
)

:: ── Step 4: Inno Setup ──────────────────────────────────────────────────────
echo.
echo [4/4] Dang build installer voi Inno Setup...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
)
if not exist %ISCC% (
    echo [LOI] Inno Setup chua duoc cai dat.
    echo       Tai tai: https://jrsoftware.org/isdl.php
    echo.
    echo       Sau khi cai, chay lai build.bat.
    pause & exit /b 1
)

%ISCC% installer.iss
if errorlevel 1 (echo [LOI] Inno Setup that bai! & pause & exit /b 1)

echo.
echo ============================================================
echo   BUILD HOAN TAT!
echo   Output: dist\installer\LocalStudyRAGAgent_Setup.exe
echo.
echo   Nguoi dung chi can:
echo   1. Chay LocalStudyRAGAgent_Setup.exe
echo   2. Bam Next -> Install -> Finish
echo   3. Dung app! (khong can cai gi them)
echo ============================================================
pause
