# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /build
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends libxml2 libxslt1.1 && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --create-home --shell /bin/bash appuser

COPY --from=builder /install /usr/local
COPY . .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
