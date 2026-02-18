FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 
#ENV DT_PYTHON_FORKABLE=0

WORKDIR /app

# Install build dependencies (kept minimal) and clean up apt caches
RUN apt-get update \
	&& apt-get install -y --no-install-recommends build-essential gcc \
	&& rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create a non-root user and give ownership of the app directory
RUN groupadd -r appgrp && useradd -r -g appgrp appusr \
	&& chown -R appusr:appgrp /app

USER appusr

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "gateway:wapp", "--workers", "2"]

