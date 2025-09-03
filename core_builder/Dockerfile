# Reproducible environment with pinned Python and tzdata
FROM python:3.11-slim

# System tzdata for OS-level tools + certs for TLS
RUN apt-get update && apt-get install -y --no-install-recommends tzdata ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default command shows help
CMD ["python","core.py","-h"]
