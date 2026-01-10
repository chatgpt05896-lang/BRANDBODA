# BrandrdXMusic/plugins/healer.py
# ==============================================================================
# 🚑 THE MEDIC PLUGIN: ملف "طبيب" خارجي
# بيشتغل أوتوماتيك مع البلاجن وبيصلح المكتبة من غير ما تلمس ملفات السيستم
# ==============================================================================

import sys
from pyrogram import Client

# بنعمل دالة بتشتغل أول ما الملف يتحمل
def inject_cure():
    try:
        # بننادي على المكتبة المريضة
        from pytgcalls.types import UpdateGroupCall
        
        # بنكشف عليها: هل ناقصها chat_id؟
        if not hasattr(UpdateGroupCall, "chat_id"):
            
            # 💊 العلاج: زرع الخاصية المفقودة
            # (ذكية: لو مفيش chat بترجع 0 عشان ميعملش كراش)
            def _healer_getter(self):
                try:
                    return self.chat.id
                except AttributeError:
                    return 0
            
            # حقن العلاج
            UpdateGroupCall.chat_id = property(_healer_getter)
            
            print("\n✅ [HEALER PLUGIN] System cured! 'UpdateGroupCall' is fixed.\n")
        else:
            print("ℹ️ [HEALER PLUGIN] System is already healthy.")
            
    except ImportError:
        # لو المكتبة مش موجودة، الطبيب بيمشي بهدوء
        print("⚠️ [HEALER] pytgcalls not found yet.")
    except Exception as e:
        print(f"⚠️ [HEALER] Error: {e}")

# تشغيل الطبيب فوراً عند تحميل البلاجن
inject_cure()
