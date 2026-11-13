# Imagen única: compila el frontend (Vite) y sirve API + SPA desde FastAPI en el mismo origen.
# Construir desde la raíz del repositorio:  docker build -t aurora-ai .

# ---- Etapa 1: compilar el frontend -----------------------------------------
FROM node:22-alpine AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Las variables VITE_* quedan incrustadas en el JavaScript público (no son secretos).
# Solo se pasa la clave PÚBLICA (publishable). Nunca service_role.
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_PUBLISHABLE_KEY=""
ARG VITE_API_BASE_URL=""
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_PUBLISHABLE_KEY=$VITE_SUPABASE_PUBLISHABLE_KEY \
    VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ---- Etapa 2: runtime Python --------------------------------------------------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STATIC_DIR=/app/static \
    APP_ENV=production

RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/sena_cli ./sena_cli
COPY --from=frontend-build /src/frontend/dist ./static

USER app
EXPOSE 8000

# Render inyecta PORT; por defecto 8000 en local.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT','8000'), timeout=4)" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
