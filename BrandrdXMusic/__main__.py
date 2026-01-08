import asyncio
import importlib

# ---------------------------------------------------
# 🔥 1. تفعيل التيربو (uvloop) في البداية
# ---------------------------------------------------
try:
    import uvloop
    uvloop.install()
except ImportError:
    pass
# ---------------------------------------------------

from sys import argv
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from BrandrdXMusic import LOGGER, app, userbot
from BrandrdXMusic.core.call import Hotty
from BrandrdXMusic.misc import sudo
from BrandrdXMusic.plugins import ALL_MODULES
from BrandrdXMusic.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()
    
    await sudo()
    
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    
    await app.start()
    
    for all_module in ALL_MODULES:
        importlib.import_module("BrandrdXMusic.plugins" + all_module)
    
    LOGGER("BrandrdXMusic.plugins").info("Successfully Imported Modules...")
    
    await userbot.start()
    await Hotty.start()
    
    try:
        await Hotty.stream_call("https://files.catbox.moe/7lvv4u.jpg")
    except NoActiveGroupCall:
        LOGGER("BrandrdXMusic").error(
            "Please turn on the videochat of your log group/channel.\n\nStopping Bot..."
        )
        exit()
    except:
        pass
    
    await Hotty.decorators()
    
    # ✅ الرسالة العربية المطلوبة
    print("-------------------------------------------------------")
    print("الـبـوت اشـتـغـل يـ عـزيـزي الـمـطـور @S_G0C7")
    print("قـنـاة الـتحـديـثـات https://t.me/SourceBoda")
    print("-------------------------------------------------------")
    
    # تسجيل في اللوج أيضاً للتأكيد
    LOGGER("BrandrdXMusic").info("Bot Started: @S_G0C7 - https://t.me/SourceBoda")
    
    await idle()
    
    await app.stop()
    await userbot.stop()
    LOGGER("BrandrdXMusic").info("Stopping Brandrd Music Bot...")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init())
