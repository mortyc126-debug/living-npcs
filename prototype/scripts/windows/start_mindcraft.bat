@echo off
REM Запуск Mindcraft с конфигом Странника.
REM Перед этим должен быть запущен middleware на :8090 и Minecraft 1.21.6 server на :25565.
REM Скрипт идемпотентен — каждый запуск:
REM   1) пересинхронизирует settings.js и profile из репо living-npcs
REM   2) применяет наши патчи к Mindcraft (vision-стабы + self_prompter)
REM   3) чистит сохранённое состояние Mindcraft (наша память живёт в middleware)
REM   4) запускает npm start

set MINDCRAFT_DIR=%~dp0\..\..\..\..\mindcraft-ce
if not exist "%MINDCRAFT_DIR%" (
    echo [!] Не нашёл mindcraft-ce: %MINDCRAFT_DIR%
    echo     Поставь:
    echo       cd ..\..\..\..
    echo       git clone https://github.com/mindcraft-ce/mindcraft-ce
    echo       cd mindcraft-ce ^&^& npm install
    exit /b 1
)

set CONFIG_SRC=%~dp0\..\..\mindcraft_config
set PATCH_BAT=%~dp0\patch_mindcraft.bat

REM 1) Безусловная пересинхронизация конфигов (settings.js + profile + keys).
echo [sync] settings.js и profile из living-npcs/prototype/mindcraft_config
copy /Y "%CONFIG_SRC%\settings.js.template" "%MINDCRAFT_DIR%\settings.js" >nul
copy /Y "%CONFIG_SRC%\andy_wanderer.json" "%MINDCRAFT_DIR%\profiles\andy_wanderer.json" >nul
if not exist "%MINDCRAFT_DIR%\keys.json" (
    if exist "%CONFIG_SRC%\keys.json.template" (
        copy /Y "%CONFIG_SRC%\keys.json.template" "%MINDCRAFT_DIR%\keys.json" >nul
        echo [sync] keys.json создан из template
    )
)

REM 2) Патчи Mindcraft (idempotent — он сам проверяет .orig).
call "%PATCH_BAT%"
if errorlevel 1 (
    echo [!] patch_mindcraft.bat упал — прерываюсь.
    exit /b 1
)

REM 3) Чистим сохранённое состояние Mindcraft. У нас своя память в middleware
REM (STM/LTM в Python), а Mindcraft восстанавливает self_prompter из этого
REM файла даже когда self_prompter заглушен — лишний мусор в context.
if exist "%MINDCRAFT_DIR%\bots\Wanderer\memory.json" (
    del /Q "%MINDCRAFT_DIR%\bots\Wanderer\memory.json"
    echo [reset] bots\Wanderer\memory.json удалён.
)

REM 4) Поехали.
cd /d "%MINDCRAFT_DIR%"
echo Запуск Mindcraft...
npm start
