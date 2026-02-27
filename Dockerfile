FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias primero — esta capa se cachea si requirements.txt no cambia
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY src/ ./src/
COPY static/ ./static/
COPY main.py .

EXPOSE 8000

CMD ["python", "main.py", "--web"]
