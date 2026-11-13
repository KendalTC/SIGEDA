FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# postgresql-client: pg_dump/pg_restore/psql, que usa
# apps.respaldos (RF-16, ADR-03) para armar y restaurar el paquete de
# respaldo directamente contra el servicio "postgres" de Docker
# Compose (no hay acceso al socket de Docker desde este contenedor).
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt .

RUN pip install --no-cache-dir -r base.txt

COPY . .

EXPOSE 8000

CMD ["bash"]