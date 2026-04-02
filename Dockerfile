FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create data directory for CSV log
RUN mkdir -p data

# Default command — runs the digest for today
CMD ["python", "scripts/main.py"]
