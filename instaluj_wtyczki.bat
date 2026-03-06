@echo off
title Instalator pakietow Python
color 0A

echo ===================================================
echo     Rozpoczynam konfiguracje srodowiska Python
echo ===================================================
echo.

echo [1/5] Aktualizacja instalatora pip...
python -m pip install --upgrade pip
echo.

echo [2/5] Instalacja bibliotek GUI i manipulacji obrazem...
pip install Pillow tkcalendar
echo.

echo [3/5] Instalacja narzedzi OCR...
pip install pytesseract
echo.

echo [4/5] Instalacja bibliotek sieciowych, API i wideo...
pip install requests yt-dlp google-api-python-client ffmpeg-python
echo.

echo [5/5] Instalacja narzedzi do automatyzacji i przechwytywania wejscia...
pip install pynput pyautogui keyboard mouse
echo.

echo [6/5] Instalacja MoviePy (przycinanie i łączenie wideo
pip install moviepy

echo [7/5] Instalacja odtwarzacza wideo
pip install opencv-python

echo [8/5] Pobieranie list kanałów i EPG z sieci
pip install requests

echo [9/5] Obsluga ikonki w trayu (obok zegara)
pip install pystray

echo [10/5] Powiadomienia systemowe Windows o nagraniach
pip install plyer

echo [11/5] Ubijanie procesu i usuwanie pliku
pip install psutil

echo ===================================================
echo     Instalacja zakonczona pomyslnie!
echo ===================================================
echo.
pause