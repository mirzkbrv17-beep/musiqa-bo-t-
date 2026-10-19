@echo off
chcp 65001 >nul
echo Kutubxonalar avtomatik o'rnatilmoqda...
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo Xatolik: Python o'rnatilganini va internetni tekshiring.
  pause
  exit /b 1
)
echo Bot ishga tushmoqda...
py bot.py
pause
