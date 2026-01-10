# core/pytgcalls_patch.py
# ----------------------------------------
# Monkey patch to ignore broken UpdateGroupCall objects
# that sometimes come from Telegram (missing chat_id).
# This avoids raising AttributeError inside
# pytgcalls/mtproto/pyrogram_client.py
#
# ✔ No library modification
# ✔ Safe for production
# ✔ Prevents bot crash
# ----------------------------------------

try:
    from pyrogram.raw.types import UpdateGroupCall
    from pytgcalls.mtproto.pyrogram_client import PyrogramClient
except Exception:
    # لو لأي سبب المكتبات مش جاهزة وقت التحميل
    # نسيب الباتش بهدوء بدون كسر البوت
    UpdateGroupCall = None
    PyrogramClient = None


if UpdateGroupCall is not None and PyrogramClient is not None:
    # حفظ الدالة الأصلية
    _original_on_update = getattr(PyrogramClient, "on_update", None)

    async def safe_on_update(self, update):
        try:
            # 🔥 تجاهل UpdateGroupCall المكسور (بدون chat_id)
            if isinstance(update, UpdateGroupCall) and not hasattr(update, "chat_id"):
                return None

            # تنفيذ الدالة الأصلية
            if _original_on_update:
                return await _original_on_update(self, update)

        except Exception:
            # أي Exception هنا لا يجب أن يسقط البوت
            return None

    try:
        if _original_on_update:
            PyrogramClient.on_update = safe_on_update
    except Exception:
        # في حال فشل الحقن لأي سبب
        # لا نكسر التشغيل
        pass
