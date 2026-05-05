FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y git grep && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/devteam/
ENV PYTHONPATH=/app

CMD ["python", "-m", "devteam.main"]
