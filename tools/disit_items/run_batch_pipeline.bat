@echo off
setlocal enabledelayedexpansion

:: Batch runner for chaining multiple msx1pq_cli.exe calls against a dropped file or folder.
if "%~1"=="" (
    echo 使用法: このバッチファイルにファイルまたはフォルダーをドラッグ＆ドロップしてください。
    echo 入力ファイル（フォルダ）に対して異なるパラメーターで 10回の msxエフェクトを適用します。
    echo Usage: Drag and drop a file or folder onto this batch file.
    echo The script will run 10 msx1pq_cli.exe commands with varied parameters against the input.
    exit /b 1
)

set "INPUT_PATH=%~f1"
set "INPUT_NAME=%~n1"
set "INPUT_DIR=%~dp1"
set "SCRIPT_DIR=%~dp0"
set "CLI_EXE=%SCRIPT_DIR%msx1pq_cli.exe"
set "OUTPUT_DIR=%INPUT_DIR%out"
set "LUT_PATH=%SCRIPT_DIR%ContrastAndSaturationBoos.cube"

if not exist "%CLI_EXE%" (
    set "CLI_EXE=msx1pq_cli.exe"
)

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

if not exist "%LUT_PATH%" (
    echo [WARN] LUT file not found: %LUT_PATH%
)

echo Processing "%INPUT_PATH%"...

"%CLI_EXE%" --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --output-prefix "01_fast_" --pre-sat 1.35 --pre-highlight 1.15 --force
"%CLI_EXE%" --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --output-prefix "02_msx2_" --color-system msx2 --no-dither --pre-highlight 1.3 --force
"%CLI_EXE%" --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --output-prefix "03_hsb_" --weight-h 0.4 --weight-s 0.95 --weight-b 0.65 --force
"%CLI_EXE%" --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --output-prefix "04_rgb_" --distance rgb --pre-highlight 1.5 --pre-sat 1.2 --force
"%CLI_EXE%" --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --output-prefix "05_fast8dot_" --8dot fast --no-dark-dither --pre-gamma 0.7 --pre-sat 1.25 --force
"%CLI_EXE%" --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --output-prefix "06_bestattr_" --8dot best-attr --pre-sat 1.7 --pre-highlight 1.25 --force
"%CLI_EXE%" --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --output-prefix "07_poster_" --pre-posterize 10 --pre-gamma 1.3 --pre-hue 8 --force
"%CLI_EXE%" --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --output-prefix "08_moody_" --pre-gamma 1.4 --pre-sat 0.75 --pre-highlight 0.6 --force
"%CLI_EXE%" --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --output-prefix "09_clean_" --no-dither --pre-posterize 24 --pre-hue -12 --force
"%CLI_EXE%" --input "%INPUT_PATH%" --output "%OUTPUT_DIR%" --output-prefix "10_lut_" --pre-lut "%LUT_PATH%" --force

echo Done. Outputs are in "%OUTPUT_DIR%".
