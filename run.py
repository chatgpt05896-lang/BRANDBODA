import asyncio
import sys

# ---------------------------------------------------
# 🔒 0. باتش pytgcalls (لازم ييجي الأول)
# ---------------------------------------------------
try:
    from BrandrdXMusic.core import pytgcalls_patch  # noqa
except Exception as e:
    print(f"⚠️ pytgcalls patch load skipped: {e}")

# ---------------------------------------------------
# 🚀 1. تفعيل UVLOOP (بعد الباتش)
# ---------------------------------------------------
if sys.platform != "win32":
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        print("✅ UVLOOP Started Successfully!")
    except ImportError:
        print("⚠️ UVLOOP not found, using default asyncio.")

# ---------------------------------------------------
# 🤖 2. تشغيل البوت
# ---------------------------------------------------
from BrandrdXMusic.__main__ import init

if __name__ == "__main__":
    asyncio.run(init())
