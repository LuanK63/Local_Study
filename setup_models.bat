@echo off
chcp 65001 >nul
echo.
echo ================================================
echo   Setup Ollama Models cho Local Study RAG Agent
echo ================================================
echo.

ollama --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Ollama chua duoc cai.
    echo       Tai tai: https://ollama.com
    pause & exit /b 1
)

echo [..] Dang tai LLM (~4.7GB, lan dau mat 20-40 phut)...
ollama pull qwen2.5-coder:7b

echo [..] Dang tai Embedding model (~300MB)...
ollama pull nomic-embed-text

echo.
echo [OK] Tat ca model da san sang!
echo      Chay LocalStudyRAGAgent.exe de bat dau.
pause
