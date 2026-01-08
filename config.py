import re
import os
from os import getenv

from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

# ━━━ إعــدادات الــبــوت الــأســاســيــة ━━━

# احــصــل عــلــيــه مــن my.telegram.org
API_ID = int(getenv("API_ID", "0"))
API_HASH = getenv("API_HASH", "")

# تــوكــن الــبــوت مــن @BotFather
BOT_TOKEN = getenv("BOT_TOKEN", "")

# رابــط قــاعــدة الــبــيــانــات مــن cloud.mongodb.com
MONGO_DB_URI = getenv("MONGO_DB_URI", "")

# اســم الــبــوت (يــظــهــر فــي الــقــوائــم)
MUSIC_BOT_NAME = getenv("MUSIC_BOT_NAME", "بُودَا | ʙᴏᴅَا")

# وضــع الــبــوت الــخــاص (None = عــام)
PRIVATE_BOT_MODE = getenv("PRIVATE_BOT_MODE", None)

# ━━━ إعــدادات الــأوامــر ━━━
# الــعــلامــة "" (الــفــارغــة) هــي الــتــي تــجــعــل الــبــوت يــعــمــل بــدون /
COMMAND_PREFIXES = ["/", "!", ".", "", "s", "S", "#"]

# حــدود الــتــشــغــيــل (بــالــدقــائــق)
DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 900))

# آيــدي جــروب الــســجــل (Log Group)
LOGGER_ID = int(getenv("LOGGER_ID", "0"))

# ━━━ آيــدي الــمــطــور الــأســاســي (تم التعديل) ━━━
OWNER_ID = int(getenv("OWNER_ID", "8313557781"))

# تــفــعــيــل الــســجــلــات
LOG = int(getenv("LOG", True))

# ━━━ إعــدادات هــيــروكــو ━━━
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

# ━━━ روابــط الــســورس والــتــحــديــثــات ━━━
# 🛑 تم تعطيل الرابط هنا لمنع إعادة تحميل السورس وحذف التعديلات
UPSTREAM_REPO = ""
UPSTREAM_BRANCH = "main"
GIT_TOKEN = getenv("GIT_TOKEN", None)

# ━━━ قــنــوات وجــروبــات الــدعــم ━━━
SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/SourceBoda")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/music0587")

# مــغــادرة الــمــســاعــد تــلــقــائــيــاً
AUTO_LEAVING_ASSISTANT = bool(getenv("AUTO_LEAVING_ASSISTANT", False))

# الــإذاعــة الــتــلــقــائــيــة
AUTO_GCAST = os.getenv("AUTO_GCAST")
AUTO_GCAST_MSG = getenv("AUTO_GCAST_MSG", "")

# ━━━ إعــدادات ســبــوتــيــفــاي ━━━
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", "bcfe26b0ebc3428882a0b5fb3e872473")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", "907c6a054c214005aeae1fd752273cc4")

# حــدود الــقــوائــم والــتــحــمــيــل
SERVER_PLAYLIST_LIMIT = int(getenv("SERVER_PLAYLIST_LIMIT", "50"))
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", "25"))
SONG_DOWNLOAD_DURATION = int(getenv("SONG_DOWNLOAD_DURATION_LIMIT", "500"))
SONG_DOWNLOAD_DURATION_LIMIT = int(getenv("SONG_DOWNLOAD_DURATION_LIMIT", "2000"))

# حــدود الــأحــجــام
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", 104857600))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", 1073741824))

# ━━━ جــلــســات بــايــروجــرام ━━━
STRING1 = getenv("STRING_SESSION",  None)
STRING2 = getenv("STRING_SESSION2", None)
STRING3 = getenv("STRING_SESSION3", None)
STRING4 = getenv("STRING_SESSION4", None)
STRING5 = getenv("STRING_SESSION5", None)

# قــوائــم الــذاكــرة الــمــؤقــتــة
BANNED_USERS = filters.user()
adminlist = {}
lyrical = {}
votemode = {}
autoclean = []
confirmer = {}

# ━━━ صــور الــبــوت ━━━

START_IMG_URL = getenv("START_IMG_URL", "https://files.catbox.moe/exvq3d.jpg")
PING_IMG_URL = getenv("PING_IMG_URL", "https://files.catbox.moe/kmn0a6.jpg")
PLAYLIST_IMG_URL = "https://files.catbox.moe/zs9g3f.jpg"
STATS_IMG_URL = "https://files.catbox.moe/b91yyd.jpg"
TELEGRAM_AUDIO_URL = "https://files.catbox.moe/wqipfn.jpg"
TELEGRAM_VIDEO_URL = "https://files.catbox.moe/4qhfqw.jpg"
STREAM_IMG_URL = "https://files.catbox.moe/b6533n.jpg"
SOUNCLOUD_IMG_URL = "https://files.catbox.moe/xi3mb1.jpg"
YOUTUBE_IMG_URL = "https://files.catbox.moe/efzuds.jpg"
SPOTIFY_ARTIST_IMG_URL = "https://files.catbox.moe/r1lc37.jpg"
SPOTIFY_ALBUM_IMG_URL = "https://files.catbox.moe/ht74e3.jpg"
SPOTIFY_PLAYLIST_IMG_URL = "https://files.catbox.moe/5e5uqo.jpg"


# دالــة تــحــويــل الــوقــت
def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))

DURATION_LIMIT = int(time_to_seconds(f"{DURATION_LIMIT_MIN}:00"))

# الــتــحــقــق مــن الــروابــط
if SUPPORT_CHANNEL:
    if not re.match("(?:http|https)://", SUPPORT_CHANNEL):
        raise SystemExit(
            "[ERROR] - رابــط قــنــاة الــدعــم غــيــر صــحــيــح. يــجــب أن يــبــدأ بـ https://"
        )

if SUPPORT_CHAT:
    if not re.match("(?:http|https)://", SUPPORT_CHAT):
        raise SystemExit(
            "[ERROR] - رابــط مــجــمــوعــة الــدعــم غــيــر صــحــيــح. يــجــب أن يــبــدأ بـ https://"
        )
