import asyncio
import importlib
from sys import exit

from pyrogram import idle
# تأكد إن مجلد pytgcalls مرفوع جنب run.py عشان الاستيراد ده يشتغل
from pytgcalls.exceptions import NoActiveGroupCall

import config
from BrandrdXMusic import LOGGER, app, userbot
from BrandrdXMusic.core.call import Hotty
from BrandrdXMusic.misc import sudo
from BrandrdXMusic.plugins import ALL_MODULES
from BrandrdXMusic.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS

# الدالة دي اللي run.py بينادي عليها
async def init():
    # 1. التأكد من متغيرات المساعد
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()

    # 2. تفعيل صلاحيات المطورين
    await sudo()

    # 3. تحميل المحظورين
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass

    # 4. تشغيل البوت الأساسي
    await app.start()

    # 5. تحميل كل الملفات (Plugins)
    for module in ALL_MODULES:
        importlib.import_module("BrandrdXMusic.plugins" + module)

    LOGGER("BrandrdXMusic.plugins").info("Successfully Imported Modules...")

    # 6. تشغيل المساعد (Userbot)
    await userbot.start()

    # 7. تشغيل محرك الصوت (Hotty)
    await Hotty.start()
    
    # محاولة دخول المكالمة للتجربة (اختياري)
    try:
        await Hotty.stream_call("https://telegra.ph/file/b60b80ccb06f7a48f68b5.mp4")
    except NoActiveGroupCall:
        LOGGER("BrandrdXMusic").error(
            "Please turn on the videochat of your log group/channel.\n\nStopping Bot..."
        )
        exit()
    except:
        pass

    # تفعيل المعالجات (Decorators)
    await Hotty.decorators()

    LOGGER("BrandrdXMusic").info(f"Bot Started Successfully: @{app.username}")

    # 8. وضع الانتظار (عشان البوت ميفصلش)
    await idle()

    # 9. إغلاق نظيف عند الخروج
    await app.stop()
    await userbot.stop()
    LOGGER("BrandrdXMusic").info("Stopping Bot...")
