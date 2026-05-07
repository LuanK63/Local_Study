@echo off
chcp 65001 >nul
echo ============================================================
echo   DONG GOI NHANH UNG DUNG RAG (TEST NHANH)
echo ============================================================
echo.
echo [1/2] Dang kich hoat moi truong ao...
call venv\Scripts\activate

echo.
echo [2/2] Dang tien hanh dong goi voi PyInstaller...
pyinstaller --noconfirm --clean ^
  --name "LocalStudyRAGAgent" ^
  --windowed ^
  --onedir ^
  --add-data "ui/style.qss;ui" ^
  --add-data "ui/setup_wizard.py;ui" ^
  --add-data "subjects;subjects" ^
  --add-data "global_config.yaml;." ^
  --hidden-import "PyQt6" ^
  --hidden-import "PyQt6.QtCore" ^
  --hidden-import "PyQt6.QtGui" ^
  --hidden-import "PyQt6.QtWidgets" ^
  --hidden-import "PyQt6.QtWebEngineWidgets" ^
  --hidden-import "pdfplumber" ^
  --hidden-import "genanki" ^
  --collect-all "chromadb" ^
  --collect-all "onnxruntime" ^
  --collect-all "tokenizers" ^
  --collect-all "posthog" ^
  main.py

echo.
if errorlevel 1 (
    echo [LOI] Dong goi that bai! Co loi xay ra.
) else (
    echo ============================================================
    echo [THANH CONG] Dong goi xong!
    echo File chay: dist\LocalStudyRAGAgent\LocalStudyRAGAgent.exe
    echo ============================================================
)
pause
