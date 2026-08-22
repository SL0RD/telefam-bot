FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py settings.py ./
COPY modules/ modules/

# Non-root runtime; named volumes inherit this ownership on first use.
RUN useradd --create-home --uid 1000 bot \
    && mkdir -p /app/chatlogs /data \
    && chown -R bot:bot /app /data
USER bot

CMD ["python", "bot.py"]
