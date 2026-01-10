import asyncio
import sys
from SafoneAPI import SafoneAPI
from BrandrdXMusic.core.bot import Hotty
from BrandrdXMusic.core.dir import dirr
from BrandrdXMusic.core.git import git
from BrandrdXMusic.core.userbot import Userbot
from BrandrdXMusic.misc import dbb, heroku
from .logging import LOGGER

# ====================================================
# 🚀 PERFORMANCE BOOST: UVLOOP
# ====================================================
if sys.platform != "win32":
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        LOGGER(__name__).info("✅ UVLOOP Enabled: Performance Optimized.")
    except ImportError:
        LOGGER(__name__).warning("⚠️ Uvloop not found, using default loop.")

# ====================================================
# 📂 INITIALIZATION
# ====================================================
dirr()
git()
dbb()
heroku()

# ====================================================
# 🤖 CLIENTS
# ====================================================
app = Hotty()
userbot = Userbot()
api = SafoneAPI()

# ====================================================
# 🎵 PLATFORMS
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
