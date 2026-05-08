# 1. Pobierz obraz Pythona (lekka wersja Linuxa z zainstalowanym Pythonem)
FROM python:3.11-slim

# 2. Stwórz folder /app wewnątrz kontenera i wejdź do niego
WORKDIR /app

# 3. Skopiuj listę bibliotek do kontenera
COPY requirements.txt .

# 4. Zainstaluj te biblioteki wewnątrz kontenera
RUN pip install --no-cache-dir -r requirements.txt

# 5. Skopiuj całą resztę plików Twojej aplikacji (kody, foldery templates itp.)
COPY . .

# 6. Poinformuj, że aplikacja będzie działać na porcie 5000
EXPOSE 5000

# 7. Uruchom aplikację po starcie kontenera
CMD ["python", "app.py"]