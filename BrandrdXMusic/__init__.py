from BrandrdXMusic.core.bot import Hotty
from BrandrdXMusic.core.dir import dirr
from BrandrdXMusic.core.git import git
from BrandrdXMusic.core.userbot import Userbot
from BrandrdXMusic.misc import dbb, heroku

from SafoneAPI import SafoneAPI
from .logging import LOGGER

# ====================================================
# 🛠️ PATCH START: إصلاح مشكلة chat_id في الإصدار الجديد
# ====================================================
try:
    from pytgcalls.types import UpdateGroupCall
    
    # التأكد إذا كان chat_id غير موجود، نقوم بإضافته يدوياً
    if not hasattr(UpdateGroupCall, "chat_id"):
        UpdateGroupCall.chat_id = property(lambda self: getattr(getattr(self, "chat", None), "id", 0))
    LOGGER(__name__).info("✅ تم تطبيق إصلاح UpdateGroupCall بنجاح")
except ImportError:
    pass
except Exception as e:
    LOGGER(__name__).error(f"❌ فشل تطبيق الباتش: {e}")
# ====================================================
# 🛠️ PATCH END
# ====================================================

dirr()
git()
dbb()
heroku()

app = Hotty()
userbot = Userbot()
api = SafoneAPI()


from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()

APP = "Systumm_music_bot"  # connect music api key "Dont change it"
