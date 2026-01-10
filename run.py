# run.py
import asyncio
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# -----------------------------
# 1) تفعيل UVLOOP بأمان (لو متوفر)
# -----------------------------
if sys.platform != "win32":
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        print("✅ UVLOOP Enabled")
    except Exception:
        print("⚠️ uvloop not available — using default asyncio")

# -----------------------------
# 2) تحميل الباتش مباشرة من الملف (بدون استيراد الحزمة BrandrdXMusic)
#    هذا يمنع استدعاء BrandrdXMusic.__init__ مبكرًا
# -----------------------------
patch_path = os.path.join(ROOT, "BrandrdXMusic", "core", "pytgcalls_patch.py")
if os.path.exists(patch_path):
    try:
        spec = importlib.util.spec_from_file_location("brandbx_pytgcalls_patch", patch_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        print("✅ pytgcalls_patch loaded (file import)")
    except Exception as e:
        print("⚠️ Failed loading pytgcalls_patch:", e)
else:
    print("⚠️ pytgcalls_patch.py not found at", patch_path)

# -----------------------------
# 3) أنشئ loop واحد واستخدمه (لا تستخدم asyncio.run)
# -----------------------------
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# -----------------------------
# 4) بعد ما ثبتنا الباتش والـ loop، استورد init وشغّله
# -----------------------------
try:
    # الآن آمن نستورد بقية الحزمة لأنها ستستخدم نفس الـ loop والباتش معمول
    from BrandrdXMusic.__main__ import init
except Exception as e:
    print("❌ Failed to import BrandrdXMusic.__main__:", e)
    raise

if __name__ == "__main__":
    try:
        loop.run_until_complete(init())
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()
