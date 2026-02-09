FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies for cv2, pdf2image, paddle
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    tesseract-ocr \
    git \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install python dependencies without cache
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use python script to handle PORT variable (bypassing shell/docker syntax issues)
CMD ["python", "run_app.py"]
