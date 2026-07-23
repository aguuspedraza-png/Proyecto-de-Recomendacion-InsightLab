FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# requirements.txt está en la raíz de MLOps-InsightLab, no en src/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el código fuente
COPY src/ ./src

# Si api.py/streamlit_app.py necesitan el CSV, lo copiamos también
COPY Ecommerce.csv .

WORKDIR /app/src
EXPOSE 8000

# OJO: ahora api.py está en /app/src/api.py, no en /app/api.py
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]