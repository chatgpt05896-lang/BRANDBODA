# ===============================
# 🔥 IMPORTANT BOOT ORDER 🔥
# ===============================
# لازم الباتش يتحمّل قبل أي حاجة
try:
    import BrandrdXMusic.core.pytgcalls_patch  # noqa
except Exception:
    try:
        import core.pytgcalls_patch  # noqa
    except Exception:
        pass

import asyncio
import importlib
from pyrogram import idle

import config
from BrandrdXMusic import LOGGER, create_clients
from BrandrdXMusic.core.call import Call  # ✅ كلاس المكالمات الصح
from BrandrdXMusic.misc import sudo
from BrandrdXMusic.plugins import ALL_MODULES
from BrandrdXMusic.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


call = Call()  # ✅ instance واحد فقط


async def init():
    # ===============================
    # Assistant check
    # ===============================
    if not any([
        config.STRING1,
        config.STRING2,
        config.STRING3,
        config.STRING4,
        config.STRING5,
    ]):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        return

    await sudo()

    # ===============================
    # Load bans
    # ===============================
    try:
        for uid in await get_gbanned():
            BANNED_USERS.add(uid)
        for uid in await get_banned_users():
            BANNED_USERS.add(uid)
    except Exception:
        pass

    # ===============================
    # Create clients (app, userbot, api)
    # ===============================
    app, userbot, api = create_clients()

    # ===============================
    # Start bot
    # ===============================
    await app.start()

    # ===============================
    # Load plugins
    # ===============================
    for module in ALL_MODULES:
        importlib.import_module("BrandrdXMusic.plugins" + module)

    LOGGER("BrandrdXMusic.plugins").info("Successfully Imported Modules...")

    # ===============================
    # Start assistants (userbots)
    # ===============================
    await userbot.start()

    # ===============================
    # Start pytgcalls engine
    # ===============================
    await call.start()        # ✔️ start + decorators داخليًا

    print("-------------------------------------------------------")
    print("🚀 البوت يعمل الآن بنجاح (VOICE ENGINE READY)")
    print("-------------------------------------------------------")

    LOGGER("BrandrdXMusic").info(f"Bot Started: @{app.username}")

    await idle()

    # ===============================
    # Graceful shutdown
    # ===============================
    await app.stop()
    await userbot.stop()


if __name__ == "__main__":
    asyncio.run(init())
