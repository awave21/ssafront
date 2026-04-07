FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Запуск через sh: при volume ./backend:/app берётся файл с хоста, у него может не быть +x
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
CMD ["gunicorn", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8000", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "--preload", \
     "app.main:app"]
