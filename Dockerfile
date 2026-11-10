FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy dependency list first for better build caching
COPY requirements.txt .

# Install all runtime dependencies
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

COPY start.sh /app/start.sh

RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]