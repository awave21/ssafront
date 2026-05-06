FROM python:3.12-slim

WORKDIR /app

# Системные утилиты + Node.js для claude CLI
RUN apt-get update && \
    apt-get install -y git grep curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g @anthropic-ai/claude-code && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/devteam/
ENV PYTHONPATH=/app

EXPOSE 8090

# ~/.claude монтируется снаружи через volume — см. docker-compose.yml
CMD ["python", "-m", "devteam.main"]
