@echo off
REM Запуск Python middleware для Странника.
REM Перед этим должны быть запущены: Ollama (с моделью Sweaterdog/Andy-4).

cd /d "%~dp0\..\.."

if not exist "configs\wanderer.yaml" (
    echo [!] Не нашёл configs\wanderer.yaml — запускайся из prototype/
    exit /b 1
)

REM Установить зависимости если ещё не установлены
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Устанавливаю Python-зависимости...
    pip install -r requirements.txt
)

echo Запуск middleware на 127.0.0.1:8090
python -m middleware.server --config configs\wanderer.yaml --host 127.0.0.1 --port 8090 --log-level info
