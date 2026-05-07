@echo off
chcp 65001 >nul
:: Them thu muc mac dinh cua Ollama vao PATH phong khi chua cap nhat bien moi truong
set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Ollama"
echo.
echo ================================================
echo   Local Study RAG Agent -- Cai dat lan dau
echo ================================================
echo.

:: --- Kiem tra Python --------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Python chua duoc cai dat.
    echo       Tai tai: https://www.python.org/downloads/
    echo       Nho tick "Add Python to PATH" khi cai!
    pause & exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER% da duoc cai dat.

:: --- Tao virtualenv ---------------------------------
if not exist "venv\" (
    echo [..] Dang tao virtual environment...
    python -m venv venv
    echo [OK] Virtual environment da tao.
) else (
    echo [OK] Virtual environment da ton tai.
)

:: --- Cai packages -----------------------------------
echo [..] Dang cai Python packages (co the mat vai phut)...
call venv\Scripts\activate
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q
echo [OK] Python packages da cai xong.

:: --- Kiem tra Ollama --------------------------------
ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [LOI] Ollama chua duoc cai dat.
    echo       Tai tai: https://ollama.com
    echo       Sau khi cai xong, chay lai file nay.
    pause & exit /b 1
)
echo [OK] Ollama da duoc cai dat.

:: --- Pull models ------------------------------------
echo.
echo [..] Dang tai LLM model (qwen2.5-coder:7b ~ 4.7GB).
echo      Lan dau co the mat 20-40 phut tuy toc do mang.
ollama pull qwen2.5-coder:7b
echo [OK] LLM model da san sang.

echo [..] Dang tai Embedding model (nomic-embed-text ~ 300MB)...
ollama pull nomic-embed-text
echo [OK] Embedding model da san sang.

:: --- Kiem tra GCC -----------------------------------
echo.
gcc --version >nul 2>&1
if errorlevel 1 (
    echo [CANH BAO] GCC/G++ chua duoc cai dat.
    echo            Code Sandbox C/C++ se KHONG hoat dong.
    echo            Tai MinGW-w64 tai: https://winlibs.com
    echo            Sau khi cai, them vao PATH roi chay lai file nay.
) else (
    echo [OK] GCC da san sang.
)

:: --- Khoi tao DB ------------------------------------
echo.
echo [..] Khoi tao co so du lieu...
call venv\Scripts\activate
python -c "from utils.db_schema import init_db; init_db()"
echo [OK] Co so du lieu da khoi tao.

echo.
echo ================================================
echo   Cai dat hoan tat!
echo   Chay run.bat de khoi dong ung dung.
echo ================================================
echo.
pause
