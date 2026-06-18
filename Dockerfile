FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN cd backend/diesel_engine_predictor && \
    python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

CMD ["sh", "-c", \
     "cd backend/diesel_engine_predictor && \
      python manage.py migrate --noinput && \
      python manage.py seed_demo_user && \
      daphne -b 0.0.0.0 -p ${PORT:-8000} diesel_engine_predictor.asgi:application"]
