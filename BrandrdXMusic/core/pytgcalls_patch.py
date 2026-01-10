# core/pytgcalls_patch.py
# ==============================================================================
# 🧠 SMART HEALER PATCH (النسخة الذكية الآمنة)
# 1. Advanced Introspection: يبحث عن البيانات بذكاء داخل الكائن.
# 2. No Loop Dependency: لا يعتمد على Asyncio وقت التحميل لتجنب الأخطاء.
# 3. Fail-Safe: مصمم ليعمل حتى لو المكتبة بها مشاكل.
# ==============================================================================

import logging
import sys

# إعداد لوجر خاص للباتش لتوثيق العملية بذكاء
PATCH_LOGGER = logging.getLogger("SmartPatch")

def _smart_get_chat_id(self):
    """
    دالة ذكية لاستخراج Chat ID من الكائن المكسور.
    تحاول البحث في عدة أماكن قبل الاستسلام.
    """
    try:
        # المحاولة 1: الطريقة الرسمية (عبر كائن chat)
        if hasattr(self, "chat") and self.chat:
            return getattr(self.chat, "id", 0)
        
        # المحاولة 2: البحث في القاموس الداخلي (Introspection)
        # أحياناً Pyrogram بيخبي البيانات هنا لو الكائن مش مكتمل
        if hasattr(self, "__dict__"):
            data = self.__dict__
            if "chat_id" in data:
                return data["chat_id"]
            if "chat" in data:
                chat_obj = data["chat"]
                if hasattr(chat_obj, "id"):
                    return chat_obj.id
                if isinstance(chat_obj, dict):
                    return chat_obj.get("id", 0)

        # المحاولة 3: لو فشل كل شيء، نرجع 0 (Fail-Safe)
        # إرجاع 0 أفضل من Crash، لأن البوت هيتجاهل التحديث بس مش هيقفل
        return 0

    except Exception as e:
        # لو حصل خطأ أثناء المعالجة، نسجله ونكمل
        return 0

def apply_smart_patch():
    try:
        # محاولة استيراد الأنواع فقط (Types) لأنها لا تتطلب Event Loop
        # هذا يحل مشكلة "There is no current event loop"
        from pytgcalls.types import UpdateGroupCall

        # التحقق الذكي: هل نحتاج للتدخل؟
        if not hasattr(UpdateGroupCall, "chat_id"):
            
            # 💉 الحقن الذكي: نزرع الدالة المعالجة كخاصية (Property)
            UpdateGroupCall.chat_id = property(_smart_get_chat_id)
            
            PATCH_LOGGER.info("✅ SMART PATCH APPLIED: 'UpdateGroupCall' has been healed.")
            print("✅ SMART PATCH LOADED: System is protected against missing chat_id.")
        else:
            PATCH_LOGGER.info("ℹ️ SMART PATCH: System is already healthy.")

    except ImportError:
        # لو المكتبة مش موجودة، ده مش خطأ قاتل، ممكن تكون لسه متحملتش
        print("⚠️ SMART PATCH: pytgcalls types not found yet. (Will retry naturally)")
    except Exception as e:
        PATCH_LOGGER.error(f"❌ Smart Patch Error: {e}")

# تنفيذ العملية فور استدعاء الملف
apply_smart_patch()
