@echo off
setlocal

cd /d "%~dp0"

set "APP_FILE=Leksikograf_v18.py"
set "VENV_DIR=.venv"
set "PYTHON_EXE="

if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
) else (
    py -3 -V >nul 2>&1
    if %errorlevel%==0 (
        echo [1/4] Sanal ortam olusturuluyor...
        py -3 -m venv "%VENV_DIR%"
        if errorlevel 1 goto :venv_error
        set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
    ) else (
        python -V >nul 2>&1
        if %errorlevel%==0 (
            echo [1/4] Sanal ortam olusturuluyor...
            python -m venv "%VENV_DIR%"
            if errorlevel 1 goto :venv_error
            set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
        ) else (
            goto :python_missing
        )
    )
)

echo [2/4] Pip guncelleniyor...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto :pip_error

echo [3/4] Gereksinimler yukleniyor...
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 goto :pip_error

echo [4/4] Uygulama baslatiliyor...
echo.
echo Not: OCR icin Tesseract kurulu olmali.
echo Indirme: https://github.com/tesseract-ocr/tesseract
echo.
"%PYTHON_EXE%" -m streamlit run "%APP_FILE%"
goto :eof

:python_missing
echo Python bulunamadi. Lutfen Python 3.10+ kurup tekrar deneyin.
pause
exit /b 1

:venv_error
echo Sanal ortam olusturulamadi.
pause
exit /b 1

:pip_error
echo Paket kurulumu basarisiz oldu.
echo Internet baglantinizi ve pip erisimini kontrol edin.
pause
exit /b 1
