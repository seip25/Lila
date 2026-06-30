FROM python:3.11-slim

WORKDIR /app

# Copy project dependencies configuration
COPY pyproject.toml /app/

# Install lila-framework and project dependencies
RUN pip install --no-cache-dir .

# Copy application files
COPY . /app

EXPOSE 8000

CMD ["python", "main.py"]
