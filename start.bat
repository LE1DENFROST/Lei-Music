@echo off
TITLE Lei-Music Installer & Launcher

echo Kontrol ediliyor: Python kurulu mu?
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo HATA: Python bulunamadi. Lutfen Python'u yukleyin ve PATH'e ekleyin.
    pause
    exit
)

echo Gerekli Python kutuphaneleri kuruluyor/guncelleniyor...
pip install -r requirements.txt

echo.
echo Her sey hazir. Lei-Music baslatiliyor...
start "Lei-Music" pythonw main.py

