import asyncio
import importlib
from sys import argv
from pytgcalls.exceptions import NoActiveGroupCall

# ---------------------------------------------------
# 🔥 الترتيب الذهبي: تفعيل التيربو قبل استدعاء البوت
# ---------------------------------------------------
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass
# ---------------------------------------------------

# دلوقتي نستدعي باقي ملفات البوت بأمان
import config
from pyrogram import idle
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
        return
    
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
        return
    except:
        pass
    
    await Hotty.decorators()
    
    print("-------------------------------------------------------")
    print("الـبـوت شـغـال بـنـظـام Worker الـسـريـع 🚀 @S_G0C7")
    print("قـنـاة الـتحـديـثـات https://t.me/SourceBoda")
    print("-------------------------------------------------------")
    
    LOGGER("BrandrdXMusic").info("Bot Started: @S_G0C7 - https://t.me/SourceBoda")
    
    await idle()
    
    # إغلاق نظيف
    await app.stop()
    await userbot.stop()
    LOGGER("BrandrdXMusic").info("Stopping Brandrd Music Bot...")

if __name__ == "__main__":
    # 🔥 التغليف النهائي: عشان ميبقاش فيه أي أخطاء وقت القفل
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(init())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        LOGGER("BrandrdXMusic").error(f"Stopping due to error: {e}")
