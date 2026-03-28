FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput 2>/dev/null || true

# Run with gunicorn
EXPOSE 8001
CMD ["gunicorn", "creator_project.wsgi:application", \
     "--bind", "0.0.0.0:8001", \
     "--workers", "3", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
