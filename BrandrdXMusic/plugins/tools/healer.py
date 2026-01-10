# BrandrdXMusic/plugins/tools/healer.py
# ==============================================================================
# 🚑 HEALER TOOL: أداة العلاج الذكي
# المكان: plugins/tools/healer.py
# الوظيفة: إصلاح خطأ chat_id في pytgcalls تلقائياً بمجرد تحميل البلاجن
# ==============================================================================

import sys
import logging

# إعداد لوجر بسيط عشان تتابع العملية في التيرمينال
HEALER_LOG = logging.getLogger("HealerTool")

def apply_cure():
    """
    دالة تقوم بفحص وإصلاح كلاس UpdateGroupCall
    بدون الحاجة لتعديل ملفات النظام الأساسية.
    """
    try:
        # 1. محاولة استدعاء المكتبة (لو موجودة)
        # بنستخدم try عشان لو المكتبة مش متسطبة ميعملش كراش للبوت
        from pytgcalls.types import UpdateGroupCall
        
        # 2. الكشف عن المشكلة: هل chat_id ناقص؟
        if not hasattr(UpdateGroupCall, "chat_id"):
            
            # 3. تجهيز العلاج (Smart Getter)
            # الدالة دي بتبحث عن الايدي بذكاء وأمان
            def _healed_chat_id(self):
                try:
                    # السيناريو الطبيعي: موجود جوه chat
                    if hasattr(self, "chat") and self.chat:
                        return self.chat.id
                    
                    # سيناريو الطوارئ: البحث في القاموس الداخلي
                    if hasattr(self, "__dict__"):
                        return self.__dict__.get("chat_id", 0)
                        
                    return 0
                except:
                    return 0
            
            # 4. حقن العلاج (العملية الجراحية)
            # بنستخدم property عشان نحول الدالة لخاصية ثابتة
            UpdateGroupCall.chat_id = property(_healed_chat_id)
            
            HEALER_LOG.info("✅ [HEALER] System Cured: 'UpdateGroupCall' patched successfully.")
            print("✅ [HEALER] Tool loaded and system fixed.")
            
        else:
            # لو الخاصية موجودة أصلاً، يبقى تمام
            HEALER_LOG.info("ℹ️ [HEALER] System is already healthy.")

    except ImportError:
        # ده بيحصل لو pytgcalls لسه متحملتش، أو مش موجودة
        print("⚠️ [HEALER] pytgcalls module not found yet (Skipping fix).")
    except Exception as e:
        # أي خطأ تاني غير متوقع
        HEALER_LOG.error(f"⚠️ [HEALER] Error occurred: {e}")

# ==============================================================================
# تنفيذ العلاج فوراً عند تشغيل البوت وتحميل ملفات Tools
# ==============================================================================
apply_cure()
