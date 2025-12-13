@echo off
setlocal enabledelayedexpansion

:: Batch runner for chaining multiple msx1pq_cli.exe calls against a dropped file or folder.
if "%~1"=="" (
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "01_fast_" --pre-sat 1.35 --pre-contrast 1.15 --force
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "02_msx2_" --color-system msx2 --pre-contrast 1.3 --force
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "04_rgb_" --distance rgb --pre-contrast 1.5 --pre-sat 1.2 --force
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "06_best_" --8dot best --pre-sat 1.7 --pre-contrast 1.25 --force
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "08_moody_" --pre-gamma 1.4 --pre-sat 0.75 --pre-contrast 0.6 --force
)

set "INPUT_PATH=%~f1"
set "INPUT_NAME=%~n1"
set "INPUT_DIR=%~dp1"
set "SCRIPT_DIR=%~dp0"
set "OUTPUT_DIR=%SCRIPT_DIR%out"
set "LUT_PATH=%SCRIPT_DIR%ContrastAndSaturationBoost.cube"

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

if not exist "%LUT_PATH%" (
    echo [WARN] LUT file not found: %LUT_PATH%
)

cd /d %SCRIPT_DIR%
echo Processing "%INPUT_PATH%"...
echo

msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "01_fast_" --pre-sat 1.35 --pre-highlight 1.15 --force
if errorlevel 1 goto :abort
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "02_msx2_" --color-system msx2 --pre-highlight 1.3 --force
if errorlevel 1 goto :abort
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "03_hsv_" --weight-h 0.4 --weight-s 0.95 --weight-b 0.65 --force
if errorlevel 1 goto :abort
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "04_rgb_" --distance rgb --pre-highlight 1.5 --pre-sat 1.2 --force
if errorlevel 1 goto :abort
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "05_fast8dot_" --8dot fast --no-dark-dither --pre-gamma 0.7 --pre-sat 1.25 --force
if errorlevel 1 goto :abort
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "06_best_" --8dot best --pre-sat 1.7 --pre-highlight 1.25 --force
if errorlevel 1 goto :abort
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "07_poster_" --pre-posterize 10 --pre-gamma 1.3 --pre-hue 8 --force
if errorlevel 1 goto :abort
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "08_moody_" --pre-gamma 1.4 --pre-sat 0.75 --pre-highlight 0.6 --force
if errorlevel 1 goto :abort
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "09_clean_" --no-dither --pre-posterize 24 --pre-hue -12 --force
if errorlevel 1 goto :abort
msx1pq_cli.exe --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --out-prefix "10_lut_" --pre-lut "%LUT_PATH%" --force
if errorlevel 1 goto :abort


echo Done. Outputs are in "%OUTPUT_DIR%".
pause
exit /b 0

:abort
echo ERROR!
set "EXIT_CODE=%ERRORLEVEL%"
echo Aborting remaining commands (exit code %EXIT_CODE%).
pause
exit /b %EXIT_CODE%
