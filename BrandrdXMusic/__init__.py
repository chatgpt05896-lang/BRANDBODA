from BrandrdXMusic.core.bot import Hotty
from BrandrdXMusic.core.dir import dirr
from BrandrdXMusic.core.git import git
from BrandrdXMusic.core.userbot import Userbot
from BrandrdXMusic.misc import dbb, heroku

from SafoneAPI import SafoneAPI
from .logging import LOGGER

# ====================================================
# 🛠️ SAFE PATCH: حماية إضافية لخاصية Chat ID
# ====================================================
# هذا الجزء يضمن عدم توقف البوت حتى لو المكتبة اختلفت قليلاً
try:
    # محاولة استيراد الأنواع القديمة إذا وجدت
    from pytgcalls.types import UpdateGroupCall
    if not hasattr(UpdateGroupCall, "chat_id"):
        UpdateGroupCall.chat_id = property(lambda self: getattr(getattr(self, "chat", None), "id", 0))
except ImportError:
    # إذا لم تكن موجودة (في الإصدارات الحديثة)، نتجاهل الأمر لأننا عالجناه في call.py
    pass
except Exception:
    pass

# تهيئة المجلدات وقاعدة البيانات
dirr()
git()
dbb()
heroku()

# تعريف الكائنات الأساسية
# ملاحظة: Hotty هنا هو كلاس البوت (Bot Client) الموجود في core/bot.py
app = Hotty()
userbot = Userbot()
api = SafoneAPI()

# منصات التشغيل
from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()

APP = "Systumm_music_bot"
