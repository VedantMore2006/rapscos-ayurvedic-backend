FROM python:3.12-slim

# Prevent Python from writing .pyc and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Create persistent storage directories
RUN mkdir -p /app/data /app/media

EXPOSE 8777

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8777"]
