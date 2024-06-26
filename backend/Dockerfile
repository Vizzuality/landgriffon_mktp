
FROM python:3.12.1-slim
RUN pip install poetry
WORKDIR /app
COPY requirements.txt .
COPY . .
RUN poetry install --no-dev
EXPOSE 8000
COPY .env.production /app/.env.production
COPY cred-production.json /app/cred-production.json
ENV ENVIRONMENT=production
CMD ["poetry", "run", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000", "--workers", "4"]