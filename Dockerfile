FROM python:3.10-slim-bullseye

# 1️⃣ System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    aria2 \
    git \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2️⃣ Workdir
WORKDIR /app

# 3️⃣ Upgrade pip only (بدون تثبيت requirements هنا)
RUN pip install --upgrade pip setuptools wheel

# 4️⃣ انسخ الكود كله
COPY . .

# 5️⃣ ENTRYPOINT = سكربت التنضيف + الحقن
# ⚠️ مهم جداً: ده بيشتغل كل مرة الكونتينر يبدأ
ENTRYPOINT ["python3", "/app/run_patch_clean.py"]

# 6️⃣ الأمر الحقيقي للبوت
CMD ["python3", "-m", "BrandrdXMusic"]
