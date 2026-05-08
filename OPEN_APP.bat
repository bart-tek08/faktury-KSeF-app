@echo off
echo Trwa budowanie i uruchamianie aplikacji KSeF w Dockerze...
echo Prosze czekac, to moze chwile potrwac przy pierwszym razie...

:: 1. Budowanie obrazu (jeśli nie istnieje lub sa zmiany)
docker build -t ksef-app .

:: 2. Zatrzymanie i usuniecie starego kontenera, jesli juz jakis dzialal
docker stop moja-fajna-apka >nul 2>&1
docker rm moja-fajna-apka >nul 2>&1

:: 3. Uruchomienie nowego kontenera
docker run -d -p 5000:5000 --name moja-fajna-apka ksef-app

echo.
echo ======================================================
echo Aplikacja dziala pod adresem: http://localhost:5000
echo ======================================================
echo.
pause