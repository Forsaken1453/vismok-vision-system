@echo off
REM ============================================================
REM  Jalankan Dashboard Pelempar Pakan Ikan
REM  Klik 2x file ini, server akan otomatis terbuka di browser
REM ============================================================

title Dashboard Pelempar Pakan Ikan

REM Cari Python (installer winget / installer manual)
setlocal
set PY=

REM 1) Cari python.exe di lokasi install default
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    goto :found
)

REM 2) Kalau ada di PATH
for /f "delims=" %%i in ('where python 2^>nul') do (
    if not defined PY set PY=%%i
)
if defined PY goto :found

REM 3) Cek versi Python lain
for %%v in (313 314 311 310) do (
    if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" (
        set PY=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe
    )
)

if not defined PY (
    echo.
    echo   [ERROR] Python tidak ditemukan.
    echo.
    echo   Install Python 3.12 dari:  https://www.python.org/downloads/
    echo  _centang_ "Add python.exe to PATH" saat instalasi.
    echo.
    pause
    exit /b 1
)

:found
echo.
echo   Python : %PY%
%PY% --version
echo.

REM Pastikan Flask ada
%PY% -c "import flask" 2>nul
if errorlevel 1 (
    echo   Memasang Flask...
    %PY% -m pip install Flask
)

echo   Menjalankan server...
echo   Untuk menutup: tekan Ctrl+C
echo.

cd /d "%~dp0app"
%PY% server.py

endlocal
pause