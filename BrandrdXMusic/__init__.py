from BrandrdXMusic.core.bot import Hotty
from BrandrdXMusic.core.dir import dirr
from BrandrdXMusic.core.git import git
from BrandrdXMusic.core.userbot import Userbot
from BrandrdXMusic.misc import dbb, heroku

from SafoneAPI import SafoneAPI
from .logging import LOGGER

# ====================================================
# 🛠️ PATCH START: إصلاح مشكلة chat_id في المكتبة
# ====================================================
try:
    from pytgcalls.types import UpdateGroupCall
    # بنضيف الخاصية دي يدوياً قبل ما البوت يشتغل
    if not hasattr(UpdateGroupCall, "chat_id"):
        UpdateGroupCall.chat_id = property(lambda self: getattr(getattr(self, "chat", None), "id", 0))
except:
    pass
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

APP = "Systumm_music_bot"
