FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=5000

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 5000

CMD ["sh", "-c", "gunicorn --workers=2 --threads=4 --worker-class=gthread --bind=0.0.0.0:${APP_PORT:-5000} wsgi:app"]
