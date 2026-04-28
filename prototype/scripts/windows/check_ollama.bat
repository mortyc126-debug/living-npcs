@echo off
REM Проверка что Ollama запущена и t-tech/T-lite-it-2.1 доступен.
REM Ollama запускается автоматически после установки, обычно на :11434.

echo Проверяем Ollama...
curl.exe -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [!] Ollama не отвечает на http://localhost:11434
    echo     Запусти Ollama (она ставится с installer и должна быть в трее).
    echo     Если не установлена: https://ollama.com/download/windows
    exit /b 1
)
echo [OK] Ollama работает.

echo Проверяем что t-tech/T-lite-it-2.1 скачан...
curl.exe -s http://localhost:11434/api/tags | findstr /C:"T-lite-it-2.1" >nul
if errorlevel 1 (
    echo [!] t-tech/T-lite-it-2.1 не найден.
    echo     Скачай: ollama pull t-tech/T-lite-it-2.1:Q4_K_M
    exit /b 1
)
echo [OK] T-lite-it-2.1 на месте.
echo.
echo Можно запускать middleware: scripts\windows\start_middleware.bat
