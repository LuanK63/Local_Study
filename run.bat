@echo off
chcp 65001 >nul
set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Ollama"
echo [..] Dang khoi dong Local Study RAG Agent...

:: Kich hoat virtualenv
call venv\Scripts\activate 2>nul
if errorlevel 1 (
    echo [LOI] Chua cai dat. Chay setup.bat truoc!
    pause & exit /b 1
)

:: Khoi dong Ollama ngam (neu chua chay)
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if errorlevel 1 (
    echo [..] Dang khoi dong Ollama...
    start /b ollama serve
    timeout /t 3 >nul
)

:: Chay app desktop PyQt6
python main.py
