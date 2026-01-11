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

# 3. ننسخ ملف المتطلبات بس الأول
COPY requirements.txt .

# 🔥 التعديل الضروري هنا 🔥
# شلنا --no-cache-dir وضفنا --mount=type=cache
# ده بيخلي السيرفر يعمل فولدر سري يخزن فيه التحميلات وميمسحوش ابداً
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install --upgrade pip setuptools && \
    pip3 install --upgrade -r requirements.txt

# 4. دلوقتي انسخ باقي الكود بتاعك
# (لو عدلت في الكود، Docker هيعيد الخطوة دي بس، ومش هيعيد التسطيب)
COPY . .

CMD ["python3", "-m", "BrandrdXMusic"]
