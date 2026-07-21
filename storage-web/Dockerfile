FROM python:3.12-slim

# util-linux fournit nsenter + lsblk (accès aux infos de l'hôte)
RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8888

# 2 workers gunicorn, timeout large car df/lsblk peuvent être lents
CMD ["gunicorn", "--bind", "0.0.0.0:8888", "--workers", "2", "--timeout", "60", "app.main:app"]
