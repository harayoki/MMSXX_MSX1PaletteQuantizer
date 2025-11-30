@echo off
setlocal

echo このスクリプトは MSX1PaletteQuantizer.aex を Adobe MediaCore フォルダにコピーします。
echo (管理者権限が必要です)

set "TARGET_DIR=C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore"

:: Check for administrator privileges and relaunch if necessary
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo 管理者権限が必要です。管理者として再実行します。
    :: PAUSE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& {Start-Process -FilePath '%~f0' -Verb RunAs}"
    goto :eof
)

:: Resolve repository root based on this script location
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "SOURCE_AEX=%REPO_ROOT%\platform\Win\x64\MSX1PaletteQuantizer.aex"

if not exist "%SOURCE_AEX%" (
    echo aex ファイルが見つかりません: %SOURCE_AEX%
    PAUSE
    exit /b 1
)

if not exist "%TARGET_DIR%" (
    echo コピー先フォルダが存在しません: %TARGET_DIR%
    PAUSE
    exit /b 1
)

echo コピー元: %SOURCE_AEX%
echo コピー先: %TARGET_DIR%

echo コピーしています...
copy /Y "%SOURCE_AEX%" "%TARGET_DIR%"
if %errorlevel% neq 0 (
    echo コピーに失敗しました。
    PAUSE
    exit /b 1
)

echo コピーが完了しました。
endlocal
PAUSE
