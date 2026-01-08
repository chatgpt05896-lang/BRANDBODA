import os
import asyncio
from config import autoclean

async def auto_clean(popped):
    try:
        rem = popped["file"]
        
        # 1. إزالة الملف من قائمة التتبع بأمان
        if rem in autoclean:
            autoclean.remove(rem)
            
        # 2. التأكد من أن الملف غير مستخدم في كول تاني (Reference Counting)
        # عشان لو جروبين بيسمعوا نفس الأغنية، منمسحهاش غير لما الاتنين يخلصوا
        count = autoclean.count(rem)
        if count == 0:
            
            # 3. تجاهل الروابط والبث المباشر (لأنها مش ملفات على الجهاز)
            if "http" in rem or "index_" in rem or "live_" in rem:
                return

            # 4. الحذف الآمن في الخلفية (Non-blocking)
            if os.path.exists(rem):
                try:
                    await asyncio.get_event_loop().run_in_executor(None, os.remove, rem)
                except:
                    pass
    except:
        pass
