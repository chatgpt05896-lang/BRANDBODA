"""
███████╗██╗   ██╗███████╗████████╗███████╗███╗   ███╗
██╔════╝╚██╗ ██╔╝██╔════╝╚══██╔══╝██╔════╝████╗ ████║
███████╗ ╚████╔╝ ███████╗   ██║   █████╗  ██╔████╔██║
╚════██║  ╚██╔╝  ╚════██║   ██║   ██╔══╝  ██║╚██╔╝██║
███████║   ██║   ███████║   ██║   ███████╗██║ ╚═╝ ██║
╚══════╝   ╚═╝   ╚══════╝   ╚═╝   ╚══════╝╚═╝     ╚═╝

[النظام: النواة المطلقة - الإصدار الماسي]
[المعمارية: الهيكل العربي الموحد]
[الوظيفة: تحميل 4K ذكي + حماية قصوى]
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
import traceback
import sys
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

# استيرادات البوت الداخلية
try:
    from BrandrdXMusic.utils.database import is_on_off
    from BrandrdXMusic.utils.formatters import time_to_seconds
    from BrandrdXMusic import LOGGER
except ImportError:
    logging.basicConfig(level=logging.INFO)
    def LOGGER(name): return logging.getLogger(name)
    async def is_on_off(x): return True
    def time_to_seconds(t): return 0

# =======================================================================
# ⚙️ الإعدادات المركزية (The Core Config)
# =======================================================================

class اعدادات:
    مسار_التحميل = "downloads"
    عدد_المعالجات = 12
    وقت_انتظار_الشبكة = 30
    
    # قائمة السيرفرات (الجوكر + الاحتياطي)
    السيرفرات = [
        {"url": "https://shrutibots.site", "weight": 10},
        {"url": "https://myapi-i-bwca.fly.dev", "weight": 100}, # السيرفر الخاص
        {"url": "https://api.violet-bot.site", "weight": 5},
    ]

    وكلاء_المتصفح = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36"
    ]

# تهيئة المجلدات
if not os.path.exists(اعدادات.مسار_التحميل):
    os.makedirs(اعدادات.مسار_التحميل)

سجل = LOGGER("النواة_العربية")

# =======================================================================
# 🛡️ الحماية من الانهيار (Anti-Crash Patch)
# =======================================================================

try:
    import pytgcalls
    from pytgcalls import types as pt
    
    def اصلاح_الدردشة(self):
        for attr in ["chat", "chat_id", "message", "call"]:
            val = getattr(self, attr, None)
            if val:
                if isinstance(val, int): return val
                if hasattr(val, "id"): return val.id
                if hasattr(val, "chat_id"): return val.chat_id
        return 0

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
    def افضل_صيغة():
        """
        الخوارزمية الذكية:
        1. لو الرامات مستريحة (< 20%) -> 4K Ultra
        2. لو الرامات متوسطة (< 70%) -> 1080p FHD
        3. لو الرامات مضغوطة (> 70%) -> 720p HD
        """
        if not نظام_المراقبة:
            return مدير_الجودة._جودة_عالية()

        ram = psutil.virtual_memory().percent
        cpu = psutil.cpu_percent()
        
        سجل.info(f"📊 فحص النظام: RAM {ram}% | CPU {cpu}%")

        if ram < 20:
            سجل.info("🚀 النظام خارق: تفعيل وضع 4K")
            return [
                "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160]", # 4K
                "bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/best[height<=1440]", # 2K
            ] + مدير_الجودة._جودة_عالية()
        
        elif ram < 70:
            سجل.info("⚖️ النظام مستقر: تفعيل وضع 1080p")
            return مدير_الجودة._جودة_عالية()
        
        else:
            سجل.warning("⚠️ النظام مضغوط: تفعيل وضع التوفير 720p")
            return [
                "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
                "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
            ]

    @staticmethod
    def _جودة_عالية():
        return [
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
        ]

# =======================================================================
# 🌐 مدير الشبكة (Network Manager)
# =======================================================================

class الشبكة:
    def __init__(self):
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    async def فحص_السيرفر(self):
        # يختار أفضل سيرفر بناءً على الوزن والعمل
        sorted_srv = sorted(اعدادات.السيرفرات, key=lambda x: x["weight"], reverse=True)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=self.ctx)) as s:
            for srv in sorted_srv:
                try:
                    async with s.head(srv["url"], timeout=2) as r:
                        if r.status < 500: return srv["url"]
                except: continue
        return None

    def رؤوس(self):
        return {"User-Agent": random.choice(اعدادات.وكلاء_المتصفح)}

NET = الشبكة()

# =======================================================================
# 🍪 أدوات مساعدة (Helpers)
# =======================================================================

def جلب_كوكيز():
    path = os.path.join(os.getcwd(), "cookies")
    if not os.path.exists(path): return None
    files = glob.glob(os.path.join(path, "*.txt"))
    return random.choice(files) if files else None

def تنظيف_الاسم(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

# =======================================================================
# 🚀 الكلاس الرئيسي (YouTubeAPI)
# =======================================================================

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        self.pool = ThreadPoolExecutor(max_workers=اعدادات.عدد_المعالجات)
        self._تنظيف_تلقائي()

    def _تنظيف_تلقائي(self):
        try:
            now = time.time()
            for f in os.listdir(اعدادات.مسار_التحميل):
                fp = os.path.join(اعدادات.مسار_التحميل, f)
                if os.stat(fp).st_mtime < now - 3600: os.remove(fp)
        except: pass

    async def exists(self, link: str, videoid: bool = False):
        if videoid: link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Union[str, None]:
        msgs = [message]
        if message.reply_to_message: msgs.append(message.reply_to_message)
        for m in msgs:
            txt = m.text or m.caption
            if not txt: continue
            if m.entities:
                for e in m.entities:
                    if e.type == MessageEntityType.URL: return txt[e.offset:e.offset+e.length]
            if m.caption_entities:
                for e in m.caption_entities:
                    if e.type == MessageEntityType.TEXT_LINK: return e.url
        return None

    # -----------------------------------------------------------------
    # 🔍 البحث (Track Engine)
    # -----------------------------------------------------------------
    async def track(self, link: str, videoid: bool = False):
        if videoid: link = self.base + link
        link = link.split("&")[0]

        # 1. مكتبة البحث
        try:
            res = await self._search_lib(link)
            if res: return res
        except: pass

        # 2. استخراج yt-dlp
        try:
            res = await self._search_ytdlp(link)
            if res: return res
        except: pass

        return {"title": "Error", "link": link, "vidid": "error", "duration_min": "0:00", "thumb": ""}, "error"

    async def _search_lib(self, link):
        s = VideosSearch(link, limit=1)
        r = (await s.next())["result"][0]
        return {
            "title": r["title"], "link": r["link"], "vidid": r["id"],
            "duration_min": r["duration"], "thumb": r["thumbnails"][0]["url"].split("?")[0]
        }, r["id"]

    async def _search_ytdlp(self, link):
        c = جلب_كوكيز()
        cmd = ["yt-dlp", "-J", "--skip-download", link]
        if c: cmd.extend(["--cookies", c])
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        if out:
            d = json.loads(out.decode())
            dur = d.get("duration", 0)
            return {
                "title": d.get("title"), "link": link, "vidid": d.get("id"),
                "duration_min": f"{int(dur//60)}:{int(dur%60):02d}", "thumb": d.get("thumbnail")
            }, d.get("id")
        return None

    # -----------------------------------------------------------------
    # 📥 التحميل (Download Engine)
    # -----------------------------------------------------------------
    async def download(
        self, link: str, mystic, video: bool = False, videoid: bool = False,
        songaudio: bool = False, songvideo: bool = False, format_id: str = None, title: str = None
    ) -> str:
        
        if videoid: link = self.base + link
        loop = asyncio.get_running_loop()
        vid_id = link.split("v=")[-1].split("&")[0] if "v=" in link else str(int(time.time()))
        
        ext = "mp4" if (video or songvideo) else "mp3"
        fname = تنظيف_الاسم(title if title else vid_id)
        final_path = os.path.join(اعدادات.مسار_التحميل, f"{fname}.{ext}")

        if os.path.exists(final_path) and os.path.getsize(final_path) > 1024:
            return final_path, True

        # استراتيجية 1: السيرفرات (للبث فقط)
        if not (songaudio or songvideo):
            srv = await NET.فحص_السيرفر()
            if srv:
                is_priv = "fly.dev" in srv
                q = link if is_priv else vid_id
                if await self._download_api(srv, q, final_path, video, is_priv):
                    return final_path, True

        # استراتيجية 2: محلي (مع 4K Adaptive)
        try:
            res = await loop.run_in_executor(
                self.pool,
                lambda: self._download_local(link, final_path, video, songaudio, songvideo, format_id)
            )
            if res and os.path.exists(res): return res, True
        except Exception as e:
            سجل.error(f"DL Error: {e}")

        return None, False

    def _download_local(self, link, path, video, songaudio, songvideo, format_id):
        c = جلب_كوكيز()
        opts = {
            "quiet": True, "no_warnings": True, "nocheckcertificate": True,
            "geo_bypass": True, "cookiefile": c, "outtmpl": path,
            "socket_timeout": 30,
        }

        formats = []
        if songvideo:
            formats = [f"{format_id}+140"]
            opts["merge_output_format"] = "mp4"
        elif songaudio:
            formats = [format_id]
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio","preferredcodec": "mp3","preferredquality": "192"}]
        elif video:
            formats = مدير_الجودة.افضل_صيغة()
        else:
            formats = ["bestaudio/best"]

        for f in formats:
            try:
                opts["format"] = f
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([link])
                if os.path.exists(path) and os.path.getsize(path) > 1024:
                    return path
            except: continue
        return None

    async def _download_api(self, url, q, path, video, direct):
        try:
            t = "video" if video else "audio"
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=NET.ctx)) as s:
                async with s.get(f"{url}/download", params={"url": q, "type": t}, headers=NET.رؤوس(), timeout=15) as r:
                    if r.status != 200: return False
                    d = await r.json()
                    l = d.get("url")
                    if not l and not direct:
                        tok = d.get("download_token")
                        if tok: l = f"{url}/stream/{q}?type={t}&token={tok}"
                    if not l: return False
                    async with s.get(l, timeout=600) as st:
                        if st.status == 200:
                            with open(path, "wb") as f:
                                async for ch in st.content.iter_chunked(65536): f.write(ch)
                            return True
        except: return False
        return False

    # -----------------------------------------------------------------
    # 📡 المعلومات والبيانات (Metadata & Utils)
    # -----------------------------------------------------------------
    
    # دالة هامة جداً للبوتات لفحص الملفات
    async def video(self, link: str, videoid: bool = None):
        if videoid: link = self.base + link
        # نحاول نحمل الملف (أو نتأكد من وجوده)
        f, _ = await self.download(link, None, video=True)
        if f: return 1, f
        return 0, "Failed"

    async def details(self, link: str, videoid: bool = None):
        d, i = await self.track(link, videoid)
        if i == "error": return None
        return d["title"], d["duration_min"], time_to_seconds(d["duration_min"]), d["thumb"], i

    async def title(self, link: str, videoid: bool = None):
        d, _ = await self.track(link, videoid)
        return d.get("title")

    async def duration(self, link: str, videoid: bool = None):
        d, _ = await self.track(link, videoid)
        return d.get("duration_min")

    async def thumbnail(self, link: str, videoid: bool = None):
        d, _ = await self.track(link, videoid)
        return d.get("thumb")

    async def playlist(self, link, limit, user_id, videoid: bool = None):
        if videoid: link = self.listbase + link
        c = جلب_كوكيز()
        cmd = ["yt-dlp", "-i", "--get-id", "--flat-playlist", "--playlist-end", str(limit), "--skip-download", link]
        if c: cmd.extend(["--cookies", c])
        p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await p.communicate()
        return [x for x in out.decode().split("\n") if x]

    async def formats(self, link: str, videoid: bool = None):
        if videoid: link = self.base + link
        c = جلب_كوكيز()
        try:
            with yt_dlp.YoutubeDL({"quiet":True, "cookiefile":c}) as ydl:
                r = ydl.extract_info(link, download=False)
                return [{"format": f["format"], "filesize": f.get("filesize"), "format_id": f["format_id"], "ext": f["ext"], "format_note": f.get("format_note"), "yturl": link} for f in r.get("formats", []) if "dash" not in str(f.get("format")).lower()], link
        except: return [], link

    async def slider(self, link: str, query_type: int, videoid: bool = None):
        if videoid: link = self.base + link
        try:
            a = VideosSearch(link, limit=10)
            res = (await a.next()).get("result")[query_type]
            return res["title"], res["duration"], res["thumbnails"][0]["url"].split("?")[0], res["id"]
        except: return None

# =======================================================================
# 🏁 التشغيل (Instantiation)
# =======================================================================
# هذا السطر مهم جداً عشان باقي الملفات تشوف الكلاس
YouTube = YouTubeAPI()
