FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir fastapi "uvicorn[standard]" pydantic

COPY main.py .

EXPOSE 11436

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "11436", "--workers", "1"]
