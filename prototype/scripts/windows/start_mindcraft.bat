@echo off
REM Запуск Mindcraft с конфигом Странника.
REM Перед этим должен быть запущен middleware на :8090 и Minecraft 1.21.6 server на :25565.

set MINDCRAFT_DIR=%~dp0\..\..\..\..\mindcraft-ce
if not exist "%MINDCRAFT_DIR%" (
    echo [!] Не нашёл mindcraft-ce: %MINDCRAFT_DIR%
    echo     Поставь:
    echo       cd ..\..\..\..
    echo       git clone https://github.com/mindcraft-ce/mindcraft-ce
    echo       cd mindcraft-ce ^&^& npm install
    exit /b 1
)

REM Скопировать profile-card если ещё нет
set PROFILE_SRC=%~dp0\..\..\mindcraft_config\andy_wanderer.json
set PROFILE_DST=%MINDCRAFT_DIR%\profiles\andy_wanderer.json
if not exist "%PROFILE_DST%" (
    copy "%PROFILE_SRC%" "%PROFILE_DST%"
    echo Profile скопирован: %PROFILE_DST%
)

REM Чистим сохранённое состояние Mindcraft. У нас своя память в middleware
REM (STM/LTM в Python), а Mindcraft восстанавливает self_prompter из этого
REM файла даже когда self_prompter заглушен — лишний мусор в context.
if exist "%MINDCRAFT_DIR%\bots\Wanderer\memory.json" (
    del /Q "%MINDCRAFT_DIR%\bots\Wanderer\memory.json"
    echo [reset] bots\Wanderer\memory.json удалён.
)

cd /d "%MINDCRAFT_DIR%"
echo Запуск Mindcraft...
npm start
