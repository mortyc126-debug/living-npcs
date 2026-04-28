@echo off
REM Подменяет prismarine-viewer импорты в Mindcraft на заглушки.
REM Это нужно потому что canvas/gl — нативные модули, требующие VS Build Tools.
REM Странник в игре через viewer не отображается — мы смотрим через свой client.

setlocal

set MINDCRAFT_DIR=%~dp0\..\..\..\..\mindcraft-ce
if not exist "%MINDCRAFT_DIR%" (
    echo [!] Mindcraft не найден: %MINDCRAFT_DIR%
    echo     Поставь его рядом с living-npcs.
    exit /b 1
)

set PATCH_DIR=%~dp0\..\..\patches\mindcraft

set BV_TARGET=%MINDCRAFT_DIR%\src\agent\vision\browser_viewer.js
set CAM_TARGET=%MINDCRAFT_DIR%\src\agent\vision\camera.js

if not exist "%BV_TARGET%" (
    echo [!] Не нашёл %BV_TARGET%
    exit /b 1
)
if not exist "%CAM_TARGET%" (
    echo [!] Не нашёл %CAM_TARGET%
    exit /b 1
)

REM Бэкапы оригиналов (один раз, не перетирая)
if not exist "%BV_TARGET%.orig" copy /Y "%BV_TARGET%" "%BV_TARGET%.orig" >nul
if not exist "%CAM_TARGET%.orig" copy /Y "%CAM_TARGET%" "%CAM_TARGET%.orig" >nul

copy /Y "%PATCH_DIR%\browser_viewer.stub.js" "%BV_TARGET%" >nul
copy /Y "%PATCH_DIR%\camera.stub.js" "%CAM_TARGET%" >nul

echo [OK] Vision-модули Mindcraft заглушены.
echo     Оригиналы сохранены как .orig (на случай если захочешь вернуть).
endlocal
