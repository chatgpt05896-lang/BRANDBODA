FROM python:3.10-slim-bullseye

# تحديث النظام وتثبيت الأدوات الضرورية (FFmpeg + Aria2 + Git + أدوات بناء)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    aria2 \
    git \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/
WORKDIR /app/

# تحديث pip وتثبيت المتطلبات
RUN python3 -m pip install --upgrade pip setuptools
RUN pip3 install --no-cache-dir --upgrade --requirement requirements.txt

CMD ["python3", "-m", "BrandrdXMusic"]
