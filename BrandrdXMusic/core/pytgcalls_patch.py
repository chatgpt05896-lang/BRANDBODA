# BrandrdXMusic/core/pytgcalls_patch.py
import sys

def apply_patch():
    try:
        from pytgcalls.types import UpdateGroupCall
        
        # لو الكلاس محتاج إصلاح
        if not hasattr(UpdateGroupCall, "chat_id"):
            # بنزرع الخاصية
            UpdateGroupCall.chat_id = property(lambda self: getattr(getattr(self, "chat", None), "id", 0))
            print("✅ CORE INJECTOR: Fix applied successfully.")
            
    except ImportError:
        pass
    except Exception as e:
        print(f"⚠️ Injector Error: {e}")

# تشغيل الدالة فوراً
apply_patch()
