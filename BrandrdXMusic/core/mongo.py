import sys
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
import config
from ..logging import LOGGER

# =======================================================================
# 🗄️ MONGODB CONNECTION MANAGER
# =======================================================================

MONGO_DB_URI = config.MONGO_DB_URI

# 1. التحقق من وجود رابط القاعدة
if not MONGO_DB_URI:
    LOGGER(__name__).error("❌ لم يتم العثور على رابط قاعدة البيانات (MONGO_DB_URI)!")
    sys.exit(1)

try:
    # 2. إنشاء الاتصال (Async & Sync) مع مهلة زمنية (Timeout)
    # لو الاتصال فشل خلال 5 ثواني، البوت هيبلغك بدل ما يعلق
    _mongo_async_ = AsyncIOMotorClient(MONGO_DB_URI, serverSelectionTimeoutMS=5000)
    _mongo_sync_ = MongoClient(MONGO_DB_URI, serverSelectionTimeoutMS=5000)

    # 3. اختيار اسم قاعدة البيانات
    # استخدام اسم ثابت أفضل وأسرع من جلب اسم البوت كل مرة
    db_name = "BrandrdXMusic" 
    
    mongodb = _mongo_async_[db_name]
    pymongodb = _mongo_sync_[db_name]

    # 4. اختبار الاتصال الفعلي (Ping)
    # الخطوة دي مهمة عشان نتأكد إن الرابط شغال وصحيح
    _mongo_sync_.server_info()
    
    LOGGER(__name__).info(f"✅ تم الاتصال بقاعدة البيانات بنجاح: {db_name}")

except ServerSelectionTimeoutError:
    LOGGER(__name__).error("❌ فشل الاتصال بقاعدة البيانات! (تأكد من الرابط أو سماح الـ IP)")
    sys.exit(1)

except Exception as e:
    LOGGER(__name__).error(f"❌ حدث خطأ غير متوقع في قاعدة البيانات: {e}")
    sys.exit(1)
