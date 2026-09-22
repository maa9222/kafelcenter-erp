@echo off
chcp 65001 > nul
title KafelCenter - Kafel Do'koni Ombor va Kassa Tizimi
color 0b

echo =====================================================================
echo           KAFELCENTER - OMBOR VA KASSA TIZIMI ISHGA TUSHMOQDA
echo =====================================================================
echo.

cd /d "%~dp0"

echo Python kutubxonalari tekshirilmoqda...
python -m pip install -r requirements.txt --quiet

echo.
echo Tizim brauzerda ochilmoqda: http://localhost:5000
start "" "http://localhost:5000"

echo.
echo Server ishlamoqda. Dasturdan chiqish uchun ushbu oynani yopishingiz mumkin.
echo =====================================================================
python app.py
pause
