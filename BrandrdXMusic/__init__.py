# BrandrdXMusic/__init__.py
import asyncio
import sys
from SafoneAPI import SafoneAPI
from BrandrdXMusic.core.bot import Hotty
from BrandrdXMusic.core.userbot import Userbot
from BrandrdXMusic.core.dir import dirr
from BrandrdXMusic.core.git import git
from BrandrdXMusic.misc import dbb, heroku
from .logging import LOGGER

# ====================================================
# 🚀 PERFORMANCE BOOST: تفعيل UVLOOP (من Alexa)
# ====================================================
if sys.platform != "win32":
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        LOGGER(__name__).info("✅ UVLOOP Enabled: Performance Optimized.")
    except ImportError:
        LOGGER(__name__).warning("⚠️ Uvloop not found, using default asyncio.")

# ====================================================
# 🛠️ SAFE PATCH: حماية إضافية للكراش
# ====================================================
try:
    from pytgcalls.types import UpdateGroupCall
    if not hasattr(UpdateGroupCall, "chat_id"):
        UpdateGroupCall.chat_id = property(lambda self: getattr(getattr(self, "chat", None), "id", 0))
except Exception:
    pass

# ====================================================
# 📂 INITIALIZATION: تهيئة النظام
# ====================================================
dirr()   # تنظيف المجلدات
git()    # فحص التحديثات
dbb()    # قاعدة البيانات
heroku() # إعدادات هيروكو

# ====================================================
# 🤖 CLIENTS: لم ننشئهم بعد، فقط دالة لتهيئتهم عند الحاجة
# ====================================================
app = None
userbot = None
api = None

def create_clients():
    """Create and return the bot, userbot and api instances."""
    global app, userbot, api
    app = Hotty()
    userbot = Userbot()
    api = SafoneAPI()
    return app, userbot, api

# ====================================================
# 🎵 PLATFORMS: منصات التشغيل
# ====================================================
from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()

APP = "Systumm_music_bot"
