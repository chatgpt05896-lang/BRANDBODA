# BrandrdXMusic/plugins/tools/healer.py
# ==============================================================================
# 🚑 HEALER TOOL (FORCE MODE): أداة العلاج الإجباري
# ==============================================================================
import sys
import logging

# إعداد اللوجر
HEALER_LOG = logging.getLogger("HealerTool")

def force_cure():
    print("🚑 [HEALER] Starting Force Patch...")
    
    try:
        # 1. استدعاء المكتبة إجبارياً (من غير try/pass)
        # ده هيخلي بايثون يحمل المكتبة حالاً لو مش محملة
        import pytgcalls
        from pytgcalls import types
        
        # بنحدد الهدف: UpdateGroupCall
        TargetClass = getattr(types, "UpdateGroupCall", None)
        
        if TargetClass:
            # 2. الكشف والعلاج
            if not hasattr(TargetClass, "chat_id"):
                
                # إعداد الخاصية (Getter)
                def _get_chat_id(self):
                    # محاولة الوصول للـ ID بأي طريقة
                    if hasattr(self, "chat") and self.chat:
                        return self.chat.id
                    return 0

                # 3. الحقن المباشر
                TargetClass.chat_id = property(_get_chat_id)
                
                HEALER_LOG.info("✅ [HEALER] UpdateGroupCall patched successfully!")
                print("✅ [HEALER] PATCH APPLIED: System is now safe.")
            else:
                print("ℹ️ [HEALER] System was already safe.")
        else:
            print("⚠️ [HEALER] UpdateGroupCall class not found in library.")

    except Exception as e:
        # لو حصل أي خطأ هنا، اطبعه عشان نعرف السبب
        print(f"🔥 [HEALER CRITICAL ERROR]: {e}")
        import traceback
        traceback.print_exc()

# تنفيذ فوري
force_cure()
