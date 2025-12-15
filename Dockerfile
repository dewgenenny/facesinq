FROM python:3.9-slim

WORKDIR /app

# Install system dependencies if necessary (e.g. for psycopg2 if binary not sufficient, but binary is in requirements)
# RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set default environment variables
ENV PORT=3000

EXPOSE 3000

# Use shell form or sh -c to expand $PORT
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT} --timeout 120"]
