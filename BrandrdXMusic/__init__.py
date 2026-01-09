from BrandrdXMusic.core.bot import Hotty
from BrandrdXMusic.core.dir import dirr
from BrandrdXMusic.core.git import git
from BrandrdXMusic.core.userbot import Userbot
from BrandrdXMusic.misc import dbb, heroku

from SafoneAPI import SafoneAPI
from .logging import LOGGER

# تم حذف الباتش القديم لأنه كان يسبب Loop Restart
# ملف call.py الجديد يقوم بالواجب

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
