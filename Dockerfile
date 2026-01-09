FROM python:3.10-slim-bullseye

# 1. تحديث النظام (الخطوة دي Docker هيحفظها ومش هيعيدها)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    aria2 \
    git \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. نحدد المسار الأول
WORKDIR /app/

# ✅ التعديل السحري هنا:
# انسخ ملف المتطلبات بس الأول
COPY requirements.txt .

# 3. سطب المكتبات
# (طالما requirements.txt ماتغيرش، Docker هيجيب الخطوة دي من الكاش ومش هيحمل حاجة)
RUN python3 -m pip install --upgrade pip setuptools
RUN pip3 install --no-cache-dir --upgrade --requirement requirements.txt

# 4. دلوقتي انسخ باقي الكود بتاعك
# (لو عدلت في الكود، Docker هيعيد الخطوة دي بس، ومش هيعيد التسطيب)
COPY . .

CMD ["python3", "-m", "BrandrdXMusic"]
