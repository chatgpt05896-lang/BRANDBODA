# core/pytgcalls_patch.py
# ==============================================================================
# 👻 GHOST PATCH (الشبح الذكي)
# 1. Background Monitor: يعمل في الخلفية ولا يعطل تشغيل البوت.
# 2. Lazy Injection: ينتظر حتى يتم تحميل المكتبة ثم يصلحها.
# 3. No Crashes: لا يتأثر بمشاكل الـ Event Loop أو ترتيب الاستدعاء.
# ==============================================================================

import sys
import threading
import time
import logging

# إعداد اللوجر
PATCH_LOGGER = logging.getLogger("GhostPatch")

# ------------------------------------------------------------------------------
# 🧠 The Healer Logic (المعالج الذكي)
# ------------------------------------------------------------------------------
def _smart_chat_id(self):
    """
    يقوم بالبحث عن الـ Chat ID في كل مكان ممكن داخل الكائن.
    """
    try:
        # 1. المحاولة المباشرة
        if hasattr(self, "chat") and self.chat:
            return getattr(self.chat, "id", 0)
        
        # 2. التنقيب في البيانات الداخلية (Introspection)
        if hasattr(self, "__dict__"):
            d = self.__dict__
            if "chat_id" in d: return d["chat_id"]
            if "chat" in d:
                return getattr(d["chat"], "id", 0) if hasattr(d["chat"], "id") else 0
                
        return 0 # أمان من الفشل
    except:
        return 0

# ------------------------------------------------------------------------------
# 🕵️ The Monitor (المراقب)
# ------------------------------------------------------------------------------
def _monitor_and_patch():
    """
    تراقب هذه الدالة تحميل مكتبة pytgcalls.
    بمجرد ظهور المكتبة في الذاكرة، تقوم بتطبيق الإصلاح فوراً.
    """
    attempts = 0
    max_attempts = 30 # يحاول لمدة 15 ثانية تقريباً
    
    while attempts < max_attempts:
        try:
            # هل تم تحميل pytgcalls.types؟
            if "pytgcalls.types" in sys.modules:
                module = sys.modules["pytgcalls.types"]
                
                # هل الكلاس موجود؟
                if hasattr(module, "UpdateGroupCall"):
                    TargetClass = getattr(module, "UpdateGroupCall")
                    
                    # هل يحتاج لإصلاح؟
                    if not hasattr(TargetClass, "chat_id"):
                        TargetClass.chat_id = property(_smart_chat_id)
                        PATCH_LOGGER.info("✅ GHOST PATCH: 'UpdateGroupCall' detected and HEALED successfully.")
                        return # تمت المهمة، نغلق الخيط
                    else:
                        # قد يكون تم إصلاحه بالفعل
                        return 
            
            # لو لسه، ننتظر نصف ثانية ونحاول تاني
            time.sleep(0.5)
            attempts += 1
            
        except Exception as e:
            # لا نزعج اللوج بأخطاء الانتظار
            pass
            
    PATCH_LOGGER.warning("⚠️ GHOST PATCH: Timed out waiting for pytgcalls.")

# ------------------------------------------------------------------------------
# 🚀 Execution (التنفيذ)
# ------------------------------------------------------------------------------
# نشغل المراقب في خيط منفصل (Thread) عشان ميعطلش البوت وهو بيقوم
# ده بيحل مشكلة "No Event Loop" لأننا خرجنا برة الـ Async تماماً
threading.Thread(target=_monitor_and_patch, daemon=True).start()

print("✅ GHOST PATCH ARMED: Monitoring system for pytgcalls...")
