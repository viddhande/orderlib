FROM python:3.11-slim

WORKDIR /app

# Copy wheel built by pipeline
COPY dist/*.whl /app/

RUN pip install --no-cache-dir /app/*.whl

EXPOSE 5000
CMD ["python", "-m", "app.main"]
