@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM Video Renderer - Workspace Cleanup Script (Windows)
REM Removes temporary files and optionally generated videos
REM ═══════════════════════════════════════════════════════════════════════════

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║           Video Renderer - Temizlik Scripti                  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM Check if tmp folder exists
if exist "tmp\" (
    echo [*] tmp/ klasoru temizleniyor...
    del /Q /F "tmp\*.mp4" 2>nul
    del /Q /F "tmp\*.w64" 2>nul
    del /Q /F "tmp\*.txt" 2>nul
    del /Q /F "tmp\*.json" 2>nul
    echo [OK] tmp/ klasoru temizlendi.
) else (
    echo [!] tmp/ klasoru bulunamadi.
)

echo.

REM Ask about generated videos
set /p "CLEAN_VIDEOS=Cikti videolarini da silmek ister misiniz? (E/H): "
if /I "%CLEAN_VIDEOS%"=="E" (
    echo [*] Cikti videolari temizleniyor...
    del /Q /F "final_*.mp4" 2>nul
    echo [OK] Cikti videolari silindi.
) else (
    echo [!] Cikti videolari korundu.
)

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    Temizlik Tamamlandi                       ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
pause
