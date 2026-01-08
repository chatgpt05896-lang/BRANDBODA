"""
███████╗██╗   ██╗███████╗████████╗███████╗███╗   ███╗
██╔════╝╚██╗ ██╔╝██╔════╝╚══██╔══╝██╔════╝████╗ ████║
███████╗ ╚████╔╝ ███████╗   ██║   █████╗  ██╔████╔██║
╚════██║  ╚██╔╝  ╚════██║   ██║   ██╔══╝  ██║╚██╔╝██║
███████║   ██║   ███████║   ██║   ███████╗██║ ╚═╝ ██║
╚══════╝   ╚═╝   ╚══════╝   ╚═╝   ╚══════╝╚═╝     ╚═╝

[النظام: النواة المطلقة - Aria2 Turbo]
[المعمارية: الهيكل العربي الموحد]
[الوظيفة: سرعة جنونية + ذكاء اصطناعي + حماية]
"""

import asyncio
import os
import re
import json
import glob
import random
import logging
import time
import shutil
import ssl
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from typing import Union, Optional, Dict, Any, List

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

# محاولة استيراد مكتبة مراقبة النظام
try:
    import psutil
    نظام_المراقبة = True
except ImportError:
    نظام_المراقبة = False

try:
    from BrandrdXMusic.utils.database import is_on_off
    from BrandrdXMusic.utils.formatters import time_to_seconds
    from BrandrdXMusic import LOGGER
except ImportError:
    logging.basicConfig(level=logging.ERROR)
    def LOGGER(name): return logging.getLogger(name)
    async def is_on_off(x): return True
    def time_to_seconds(t): return 0

# =======================================================================
# ⚙️ الإعدادات المركزية (The Core Config)
# =======================================================================

class اعدادات:
    مسار_التحميل = "downloads"
    عدد_المعالجات = 10
    
    # وكلاء متصفح لخداع الحماية
    وكلاء_المتصفح = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    ]

# تهيئة المجلدات
if not os.path.exists(اعدادات.مسار_التحميل):
    os.makedirs(اعدادات.مسار_التحميل)

سجل = LOGGER("النواة_العربية")

# تخفيف ضوضاء السجلات
logging.getLogger("yt_dlp").setLevel(logging.ERROR)

# =======================================================================
# 🛡️ الحماية من الانهيار (Anti-Crash Patch)
# =======================================================================

try:
    import pytgcalls
    from pytgcalls import types as pt
    
    def اصلاح_الدردشة(self):
        return getattr(self, "chat", 0)

    for item in dir(pt):
        cls = getattr(pt, item)
        if isinstance(cls, type) and ("Update" in item or "Call" in item):
            if not hasattr(cls, "chat_id"):
                setattr(cls, "chat_id", property(اصلاح_الدردشة))
    سجل.info("✅ تم تفعيل درع الحماية ضد الانهيار.")
except: pass

# =======================================================================
# 🧠 العقل المدبر: تحديد الجودة (AI Quality Manager)
# =======================================================================

class مدير_الجودة:
    @staticmethod
    def افضل_صيغة(video=False):
        """تحديد أفضل صيغة بناءً على نوع الطلب وموارد النظام"""
        if not video:
            # للصوت فقط: أفضل جودة صوت مع تحويل سريع
            return "bestaudio/best"
        
        # للفيديو: نوازن بين الجودة والسرعة
        if نظام_المراقبة:
            ram = psutil.virtual_memory().percent
            if ram > 80:
                return "bestvideo[height<=480]+bestaudio/best[height<=480]"
        
        return "bestvideo[height<=720]+bestaudio/best[height<=720]"

# =======================================================================
# 🚀 الكلاس الرئيسي (YouTubeAPI)
# =======================================================================

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        self.pool = ThreadPoolExecutor(max_workers=اعدادات.عدد_المعالجات)
        self.cookie_file = "cookies.txt" if os.path.exists("cookies.txt") else None
        
        # فحص وجود Aria2c
        self.has_aria2 = os.system("which aria2c > /dev/null 2>&1") == 0
        if self.has_aria2:
            سجل.info("🚀 تم تفعيل المحرك التوربيني (Aria2c) بنجاح!")
        else:
            سجل.warning("⚠️ لم يتم العثور على Aria2c، العمل بالوضع العادي.")

        self._تنظيف_تلقائي()

    def _تنظيف_تلقائي(self):
        # حذف الملفات القديمة جداً فقط عند التشغيل
        try:
            now = time.time()
            for f in os.listdir(اعدادات.مسار_التحميل):
                fp = os.path.join(اعدادات.مسار_التحميل, f)
                if os.stat(fp).st_mtime < now - 3600: os.remove(fp)
        except: pass

    # -----------------------------------------------------------------
    # 🔥 إعدادات التيربو (Aria2 Integration)
    # -----------------------------------------------------------------
    def _get_opts(self, out_path, video=False):
        opts = {
            "outtmpl": out_path,
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "user_agent": random.choice(اعدادات.وكلاء_المتصفح),
            "cookiefile": self.cookie_file,
            "noplaylist": True,
            "format": مدير_الجودة.افضل_صيغة(video),
        }

        # تفعيل السرعة القصوى لو Aria2 موجود
        if self.has_aria2:
            opts.update({
                "external_downloader": "aria2c",
                "external_downloader_args": [
                    "-x", "16",  # 16 خط متوازي
                    "-s", "16",  # تقسيم الملف
                    "-k", "1M",  # حجم القطعة
                ]
            })

        # إعدادات ما بعد المعالجة (تحويل الصيغ)
        if not video:
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            opts["merge_output_format"] = "mp4"

        return opts

    # -----------------------------------------------------------------
    # 🔍 البحث واستخراج الروابط
    # -----------------------------------------------------------------
    async def url(self, message: Message) -> Union[str, None]:
        msgs = [message]
        if message.reply_to_message: msgs.append(message.reply_to_message)
        for m in msgs:
            txt = m.text or m.caption
            if not txt: continue
            if m.entities:
                for e in m.entities:
                    if e.type == MessageEntityType.URL: return txt[e.offset:e.offset+e.length]
            match = re.search(self.regex, txt)
            if match: return match.group(0)
        return None

    # -----------------------------------------------------------------
    # 📥 محرك التحميل النووي (Nuclear Downloader)
    # -----------------------------------------------------------------
    async def download(
        self, link: str, mystic, video: bool = False, videoid: bool = False,
        songaudio: bool = False, songvideo: bool = False, format_id: str = None, title: str = None
    ) -> str:
        
        if videoid: link = self.base + link
        
        # استخراج المعرف لضمان عدم التكرار
        if "v=" in link:
            vid_id = link.split("v=")[1].split("&")[0]
        elif "youtu.be/" in link:
            vid_id = link.split("youtu.be/")[1].split("?")[0]
        else:
            vid_id = str(int(time.time()))

        ext = "mp4" if (video or songvideo) else "mp3"
        filename = f"{vid_id}.{ext}"
        filepath = os.path.join(اعدادات.مسار_التحميل, filename)

        # ✅ الكاش الذكي: فحص الوجود والحجم
        if os.path.exists(filepath):
            if os.path.getsize(filepath) > 1024 * 50: # أكبر من 50KB
                return filepath, False

        def _execute_download():
            # إعداد اسم الملف المؤقت (يستخدم ID)
            temp_path = os.path.join(اعدادات.مسار_التحميل, f"{vid_id}.%(ext)s")
            opts = self._get_opts(temp_path, video=(video or songvideo))
            
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([link])
                return filepath, False
            except Exception as e:
                # محاولة ثانية بدون Aria2 لو فشل
                if "external_downloader" in opts:
                    del opts["external_downloader"]
                    del opts["external_downloader_args"]
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([link])
                    return filepath, False
                raise e

        try:
            await asyncio.get_event_loop().run_in_executor(self.pool, _execute_download)
            
            # التأكد من الملف النهائي (قد يغير ffmpeg الامتداد)
            if not os.path.exists(filepath):
                for f in os.listdir(اعدادات.مسار_التحميل):
                    if f.startswith(vid_id):
                        return os.path.join(اعدادات.مسار_التحميل, f), False
            
            return filepath, False

        except Exception as e:
            s = LOGGER("Downloader")
            s.error(f"Download Error: {e}")
            return None, False

    # -----------------------------------------------------------------
    # 📡 البيانات والمعلومات (Metadata)
    # -----------------------------------------------------------------
    async def details(self, link: str, videoid: bool = None):
        if videoid: link = self.base + link
        try:
            opts = {"quiet": True, "cookiefile": self.cookie_file, "extract_flat": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(link, download=False)
                )
            
            title = info.get("title", "Unknown")
            duration = info.get("duration", 0)
            vidid = info.get("id", "")
            thumb = f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg"
            
            if duration:
                m, s = divmod(duration, 60)
                dur_str = f"{int(m)}:{int(s):02d}"
            else:
                dur_str = "Live"

            return title, dur_str, duration, thumb, vidid
        except:
            return None, None, None, None, None

    async def title(self, link: str, videoid: bool = None):
        d = await self.details(link, videoid)
        return d[0] if d else None

    async def duration(self, link: str, videoid: bool = None):
        d = await self.details(link, videoid)
        return d[1] if d else None

    async def thumbnail(self, link: str, videoid: bool = None):
        d = await self.details(link, videoid)
        return d[3] if d else None

    async def video(self, link: str, videoid: bool = None):
        if videoid: link = self.base + link
        # فحص سريع للبث المباشر
        opts = {"quiet": True, "format": "best"}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(link, download=False)
                )
            return 1, info.get("url", link)
        except:
            return 0, None

    async def playlist(self, link, limit, user_id, videoid: bool = True):
        if videoid: link = f"https://www.youtube.com/playlist?list={link}"
        cmd = [
            "yt-dlp", "--flat-playlist", "--print", "id",
            "--playlist-end", str(limit), "--skip-download", "--no-warnings", link
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        out, _ = await proc.communicate()
        return [x.strip() for x in out.decode().split("\n") if x.strip()]

    async def slider(self, link: str, query_type: int, videoid: bool = None):
        if videoid: link = self.base + link
        try:
            a = VideosSearch(link, limit=10)
            res = (await a.next()).get("result")[query_type]
            return res["title"], res["duration"], res["thumbnails"][0]["url"].split("?")[0], res["id"]
        except: return None
    
    async def formats(self, link: str, videoid: bool = None):
        # دالة احتياطية للحفاظ على توافق الكود القديم
        return [], link

# =======================================================================
# 🏁 التصدير
# =======================================================================
YouTube = YouTubeAPI()
