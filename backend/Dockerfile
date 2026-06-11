FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-hin \
    libpq-dev \
    poppler-utils \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# ADD THIS LINE — puts pip scripts on PATH
ENV PATH="/root/.local/bin:${PATH}"

# Copy app code
COPY . .

# Start command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
