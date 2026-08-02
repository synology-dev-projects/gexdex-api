# --- STAGE 1: Base Image & Dependencies ---
FROM python:3.13-slim AS base
WORKDIR /app

# 1. Copy dependencies first (Cached Docker Layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- STAGE 2: Test Verification Stage ---
FROM base AS test
COPY . .
RUN python -m pytest tests/ -v -ra

# --- STAGE 3: Production Final Image ---
FROM base AS production
COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
