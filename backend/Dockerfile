
FROM python:3.12.1-slim
RUN apt-get update && apt-get install -y gdb
RUN pip install poetry
WORKDIR /app
COPY requirements.txt .
COPY . .
RUN poetry install --only main --no-root
EXPOSE 8000
COPY .env.production /app/.env.production
COPY cred-production.json /app/cred-production.json
ENV ENVIRONMENT=production
CMD ["sh", "-c", "poetry run alembic upgrade head && poetry run gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8080 --workers 1 --timeout 120"]