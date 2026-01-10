# core/pytgcalls_patch.py
# Robust monkey-patch that wraps PyrogramClient.on_update
# and ignores broken UpdateGroupCall objects (missing chat_id).
# This version is tolerant to import order and avoids importing
# pyrogram.raw.types early (which can cause race conditions).

try:
    # حاول استيراد الموديول الداخلي لـ pytgcalls الذي يحتوي على PyrogramClient
    from pytgcalls.mtproto import pyrogram_client as _pc
    PyrogramClient = getattr(_pc, "PyrogramClient", None)
except Exception:
    PyrogramClient = None

# إذا ما لقيناش PyrogramClient، نركّ على أي حال (باتش سيتطبق لو ظهر لاحقاً)
if PyrogramClient is not None:
    _orig_on_update = getattr(PyrogramClient, "on_update", None)

    async def _safe_on_update(self, update):
        try:
            # If update doesn't have chat_id, ignore it safely.
            # This protects against 'UpdateGroupCall' objects missing chat_id.
            if not hasattr(update, "chat_id"):
                return None
            # call original handler if exists
            if _orig_on_update:
                return await _orig_on_update(self, update)
            return None
        except AttributeError:
            # أي محاولة للوصول لخاصية مفقودة نتجاهلها
            return None
        except Exception:
            # لا نسمح لأخطاء غير متوقعة أن تسقط التطبيق
            return None

    try:
        # استبدال الدالة الأصلية
        PyrogramClient.on_update = _safe_on_update
    except Exception:
        # لا نكسر التشغيل إن تعذر الحقن
        pass
