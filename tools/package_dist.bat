@echo off
setlocal EnableDelayedExpansion

:: Resolve paths
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "DIST_DIR=%REPO_ROOT%\dist"
set "SOURCE_DIR=%REPO_ROOT%\platform\Win\x64"
set "EXTRA_DIR=%SCRIPT_DIR%disit_items"

if not exist "%DIST_DIR%" (
    echo Creating dist directory: %DIST_DIR%
    mkdir "%DIST_DIR%"
)

call :CleanDist

echo Copying build outputs from %SOURCE_DIR% ...
set "COPIED_ANY=0"
for /r "%SOURCE_DIR%" %%I in (*.aex *.exe) do (
    echo    copying %%~nxI
    copy /Y "%%I" "%DIST_DIR%" >nul
    set "COPIED_ANY=1"
)
if "!COPIED_ANY!"=="0" (
    echo    (no .aex or .exe files found under x64)
)

if exist "%EXTRA_DIR%" (
    echo Copying additional dist items from %EXTRA_DIR% ...
    xcopy /E /I /Y "%EXTRA_DIR%\*" "%DIST_DIR%\" >nul
) else (
    echo Additional items directory not found: %EXTRA_DIR%
)

for /f %%I in ('powershell -NoProfile -Command "(Get-Date -Format yyyyMMdd)"') do set "TODAY=%%I"
for /f %%V in ('type "%SCRIPT_DIR%version.txt"') do set "VERSION=%%V"
set "ZIP_NAME=MSX1PaletteQuantizer_!TODAY!_!VERSION!.zip"
set "ZIP_PATH=%DIST_DIR%\%ZIP_NAME%"

if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%"

echo Creating ZIP archive: %ZIP_PATH%
powershell -NoProfile -Command "Set-StrictMode -Version Latest; Set-Location '%DIST_DIR%'; $global:LASTEXITCODE = 0; $items = Get-ChildItem -Force | Where-Object { $_.Extension -ne '.zip' -and $_.Name -ne '.keep' }; if (-not $items) { Write-Error 'No files to archive.'; exit 1 }; Compress-Archive -Path $items -DestinationPath '%ZIP_PATH%' -Force; $exitCode = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } elseif ($?) { 0 } else { 1 }; exit $exitCode"
if errorlevel 1 (
    echo Failed to create ZIP archive.
    exit /b 1
)

call :CleanDist

echo Completed packaging.

endlocal

goto :EOF

:CleanDist
echo Cleaning dist (keeping .keep and existing ZIP files)...
for /f "delims=" %%F in ('dir /a /b "%DIST_DIR%"') do (
    set "NAME=%%~nxF"
    set "EXT=%%~xF"
    if /I "!NAME!"==".keep" (
        rem preserve .keep
    ) else if /I "!EXT!"==".zip" (
        rem preserve ZIP archives
    ) else (
        if exist "%DIST_DIR%\%%F\NUL" (
            rd /s /q "%DIST_DIR%\%%F"
        ) else (
            del /f /q "%DIST_DIR%\%%F"
        )
    )
)
