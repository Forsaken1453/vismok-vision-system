@echo off
rem =====================================================================
rem  Build VISMOK.exe  (one-folder, startup cepat)
rem  Jalankan dari folder project:  build_exe.cmd
rem =====================================================================
cd /d "%~dp0"

python -X utf8 -m PyInstaller --noconfirm --noconsole --onedir --name VISMOK ^
  --icon "assets\img\app.ico" ^
  --collect-binaries onnxruntime ^
  --collect-data onnxruntime ^
  --exclude-module tensorflow ^
  --exclude-module keras ^
  --exclude-module sklearn ^
  --exclude-module scipy ^
  --exclude-module pandas ^
  --exclude-module matplotlib ^
  --exclude-module PIL ^
  --exclude-module desktop_lib ^
  --exclude-module IPython ^
  --exclude-module jedi ^
  --exclude-module zmq ^
  --exclude-module tornado ^
  --exclude-module lxml ^
  --exclude-module h5py ^
  --exclude-module ml_dtypes ^
  --exclude-module optree ^
  --exclude-module grpc ^
  --exclude-module torch ^
  --exclude-module ultralytics ^
  --exclude-module tkinter ^
  --exclude-module _tkinter ^
  --exclude-module PySide6.QtWebEngineCore ^
  --exclude-module PySide6.QtWebEngineWidgets ^
  --exclude-module PySide6.QtQml ^
  --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.QtQuick3D ^
  --exclude-module PySide6.QtMultimedia ^
  --exclude-module PySide6.Qt3DCore ^
  --exclude-module PySide6.Qt3DRender ^
  --exclude-module PySide6.QtCharts ^
  --exclude-module PySide6.QtDataVisualization ^
  --exclude-module PySide6.QtPdf ^
  --exclude-module PySide6.QtNfc ^
  --exclude-module PySide6.QtLocation ^
  --exclude-module PySide6.QtSensors ^
  --exclude-module PySide6.QtSerialPort ^
  --exclude-module PySide6.QtPositioning ^
  run.py

rem salin folder models (berisi model.onnx bila sudah ada) ke samping exe
if not exist "dist\VISMOK\models" mkdir "dist\VISMOK\models"
xcopy /y /d models\* dist\VISMOK\models\ >nul 2>&1

rem salin font bawaan (Rajdhani/Inter) ke samping exe
if not exist "dist\VISMOK\assets\fonts" mkdir "dist\VISMOK\assets\fonts"
xcopy /y /d assets\fonts\* dist\VISMOK\assets\fonts\ >nul 2>&1
if not exist "dist\VISMOK\assets\img\fish" mkdir "dist\VISMOK\assets\img\fish"
if not exist "dist\VISMOK\assets\img\products" mkdir "dist\VISMOK\assets\img\products"
xcopy /y /d assets\img\fish\*.jpg dist\VISMOK\assets\img\fish\ >nul 2>&1
xcopy /y /d assets\img\products\*.jpg dist\VISMOK\assets\img\products\ >nul 2>&1
copy /y assets\img\app_icon_1024.png dist\VISMOK\assets\img\app_icon_1024.png >nul 2>&1

echo.
echo =====================================================================
echo  SELESAI! Jalankan:  dist\VISMOK\VISMOK.exe
echo =====================================================================
pause

