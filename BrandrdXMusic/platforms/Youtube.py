"""
███████╗██╗   ██╗███████╗████████╗███████╗███╗   ███╗
██╔════╝╚██╗ ██╔╝██╔════╝╚══██╔══╝██╔════╝████╗ ████║
███████╗ ╚████╔╝ ███████╗   ██║   █████╗  ██╔████╔██║
╚════██║  ╚██╔╝  ╚════██║   ██║   ██╔══╝  ██║╚██╔╝██║
███████║   ██║   ███████║   ██║   ███████╗██║ ╚═╝ ██║
╚══════╝   ╚═╝   ╚══════╝   ╚═╝   ╚══════╝╚═╝     ╚═╝

[النظام: السرعة القصوى - Nitro Edition]
[التقنية: Multi-Threaded Aria2 + Concurrent Fragments]
[الهدف: تحميل فوري بدون انتظار]
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
import gc
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

# معالجة مكتبة البحث
try:
    from youtubesearchpython.future import VideosSearch
except ImportError:
    from youtubesearchpython.__future__ import VideosSearch

# استيرادات البوت للحفاظ على التوافق
try:
    from BrandrdXMusic.utils.database import is_on_off
    from BrandrdXMusic.utils.formatters import time_to_seconds
    from BrandrdXMusic import LOGGER
except ImportError:
    logging.basicConfig(level=logging.ERROR)
    def LOGGER(name): return logging.getLogger(name)
    async def is_on_off(x): return True
    def time_to_seconds(t): return 0

سجل = LOGGER("Nitro_Core")
logging.getLogger("yt_dlp").setLevel(logging.ERROR)

# =======================================================================
# ⚡ إعدادات السرعة القصوى (Overclock Config)
# =======================================================================
class Config:
    DOWNLOAD_PATH = "downloads"
    MAX_WORKERS = 20  # زيادة عدد العمال للسرعة
    DISK_THRESHOLD = 90
    
    # خوادم API السريعة
    SERVERS = [
        {"url": "https://shrutibots.site", "weight": 10},
        {"url": "https://myapi-i-bwca.fly.dev", "weight": 100},
        {"url": "https://api.violet-bot.site", "weight": 5},
    ]

    # وكلاء متصفح سريعة
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH)

# =======================================================================
# 🛠️ أدوات النظام (System Tools)
# =======================================================================
def get_random_cookie():
    # تدوير الكوكيز لتجنب الإبطاء من يوتيوب
    if os.path.exists("cookies") and os.path.isdir("cookies"):
        files = glob.glob(os.path.join("cookies", "*.txt"))
        if files: return random.choice(files)
    if os.path.exists("cookies.txt"): return "cookies.txt"
    return None

def smart_cleaner():
    # تنظيف سريع جداً
    try:
        now = time.time()
        # حذف الملفات الأقدم من 30 دقيقة (بدل ساعة) لتوفير المساحة للسرعة
        for f in os.listdir(Config.DOWNLOAD_PATH):
            fp = os.path.join(Config.DOWNLOAD_PATH, f)
            if os.stat(fp).st_mtime < now - 1800: 
                os.remove(fp)
    except: pass

# =======================================================================
# 🌐 مدير الشبكة
# =======================================================================
class NetworkManager:
    def __init__(self):
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    async def get_best_server(self):
        # البحث عن أسرع سيرفر استجابة
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=self.ctx)) as s:
            for srv in sorted(Config.SERVERS, key=lambda x: x["weight"], reverse=True):
                try:
                    async with s.head(srv["url"], timeout=1.5) as r: # وقت انتظار قليل جداً
                        if r.status < 500: return srv["url"]
                except: continue
        return None
    
    def get_headers(self):
        return {"User-Agent": random.choice(Config.USER_AGENTS)}

NET = NetworkManager()

# =======================================================================
# 🚀 الكلاس الرئيسي (YouTubeAPI)
# =======================================================================
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)
        
        self.has_aria2 = os.system("which aria2c > /dev/null 2>&1") == 0
        if self.has_aria2:
            سجل.info("🚀 Nitro Mode Active: Aria2c detected.")
        
        smart_cleaner()

    # -----------------------------------------------------------------
    # 🔍 محرك البحث (Optimized Track Engine)
    # -----------------------------------------------------------------
    async def track(self, link: str, videoid: bool = False):
        if videoid: link = self.base + link
        link = link.split("&")[0]

        # البحث السريع أولاً (VideosSearch)
        try:
            res = await self._search_lib(link)
            if res: return res
        except: pass

        # البحث العميق ثانياً (yt-dlp JSON)
        try:
            res = await self._search_ytdlp(link)
            if res: return res
        except: pass

        return {"title": "Unknown", "link": link, "vidid": "error", "duration_min": "0:00", "thumb": ""}, "error"

    async def _search_lib(self, link):
        s = VideosSearch(link, limit=1)
        r = (await s.next())["result"][0]
        # جلب صورة عالية الجودة فوراً
        thumb = r["thumbnails"][0]["url"].split("?")[0].replace("hqdefault", "maxresdefault")
        return {
            "title": r["title"], "link": r["link"], "vidid": r["id"],
            "duration_min": r["duration"], "thumb": thumb
        }, r["id"]

    async def _search_ytdlp(self, link):
        cookie = get_random_cookie()
        cmd = ["yt-dlp", "-J", "--skip-download", "--no-warnings", link] # تقليل المخرجات للسرعة
        if cookie: cmd.extend(["--cookies", cookie])
        
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=8) # وقت انتظار أقل
        
        if out:
            d = json.loads(out.decode())
            dur = d.get("duration", 0)
            return {
                "title": d.get("title"), "link": link, "vidid": d.get("id"),
                "duration_min": f"{int(dur//60)}:{int(dur%60):02d}", "thumb": d.get("thumbnail")
            }, d.get("id")
        return None

    # -----------------------------------------------------------------
    # 📥 محرك التحميل الصاروخي (Nitro Downloader)
    # -----------------------------------------------------------------
    async def download(self, link: str, mystic, video: bool = False, videoid: bool = False, songaudio: bool = False, songvideo: bool = False, format_id: str = None, title: str = None) -> str:
        
        if videoid: link = self.base + link
        if "v=" in link: vid_id = link.split("v=")[1].split("&")[0]
        elif "youtu.be/" in link: vid_id = link.split("youtu.be/")[1].split("?")[0]
        else: vid_id = str(int(time.time()))

        safe_title = re.sub(r'[\\/*?:"<>|]', "", title if title else vid_id)
        ext = "mp4" if (video or songvideo) else "mp3"
        filename = f"{safe_title}.{ext}"
        filepath = os.path.join(Config.DOWNLOAD_PATH, filename)

        # 1. فحص الكاش (0 ثانية)
        if os.path.exists(filepath) and os.path.getsize(filepath) > 50000:
            return filepath, True

        smart_cleaner()

        # 2. تشغيل التوربينات (Aria2 Local)
        # تشغيل في Thread منفصل عشان البوت ميهنجش
        loop = asyncio.get_running_loop()
        local_res = await loop.run_in_executor(
            self.pool,
            lambda: self._download_nitro_local(link, vid_id, filepath, video, songaudio, songvideo)
        )
        
        gc.collect() # تنظيف الرامات فوراً
        
        if local_res and os.path.exists(local_res):
            return local_res, True

        # 3. خطة الطوارئ السريعة (API Fallback)
        srv = await NET.get_best_server()
        if srv:
            is_priv = "fly.dev" in srv
            q = link if is_priv else vid_id
            if await self._download_nitro_api(srv, q, filepath, video, is_priv):
                gc.collect()
                return filepath, True

        return None, False

    def _download_nitro_local(self, link, vid_id, target_path, video, songaudio, songvideo):
        """تحميل محلي بإعدادات كسر السرعة"""
        temp_out = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id}.%(ext)s")
        cookie = get_random_cookie()
        
        # اختيار الصيغة: نضحي بالجودة القليلة مقابل السرعة لو الفيديو، أو أفضل صوت
        fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]" if (video or songvideo) else "bestaudio/best"
        
        opts = {
            "outtmpl": temp_out,
            "quiet": True, 
            "no_warnings": True, 
            "nocheckcertificate": True, # سرعة
            "geo_bypass": True, 
            "user_agent": random.choice(Config.USER_AGENTS),
            "cookiefile": cookie,
            "format": fmt,
            "writethumbnail": False,
            
            # 🔥 إعدادات السرعة القصوى 🔥
            "concurrent_fragment_downloads": 5, # تحميل 5 أجزاء في نفس الوقت
            "buffersize": 16384, # بافر 16 ميجا
            "http_chunk_size": 10485760, # 10 ميجا للقطعة
        }

        if self.has_aria2:
            opts.update({
                "external_downloader": "aria2c",
                "external_downloader_args": [
                    "-x", "16", # 16 اتصال
                    "-s", "16", # تقسيم الملف
                    "-k", "1M", # حجم التقسيم
                    "--file-allocation=none" # توفير وقت حجز المساحة
                ]
            })

        if not (video or songvideo):
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
        else:
            opts["merge_output_format"] = "mp4"

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([link])
            
            # نقل الملف النهائي بسرعة
            files = glob.glob(os.path.join(Config.DOWNLOAD_PATH, f"{vid_id}.*"))
            if files:
                actual = files[0]
                if os.path.exists(actual):
                    if os.path.exists(target_path): os.remove(target_path)
                    os.rename(actual, target_path)
                    return target_path
        except: return None
        return None

    async def _download_nitro_api(self, url, q, final_path, video, direct):
        if not self.has_aria2: return False
        try:
            t = "video" if video else "audio"
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=NET.ctx)) as s:
                # طلب التحميل (Timeout 8 ثواني بس)
                async with s.get(f"{url}/download", params={"url": q, "type": t}, headers=NET.get_headers(), timeout=8) as r:
                    if r.status != 200: return False
                    d = await r.json()
                    dl_url = d.get("url")
                    if not dl_url and not direct:
                        tok = d.get("download_token")
                        if tok: dl_url = f"{url}/stream/{q}?type={t}&token={tok}"
                    if not dl_url: return False
                    
                    # تحميل صاروخي بـ Aria2c
                    dirname = os.path.dirname(final_path)
                    filename = os.path.basename(final_path)
                    cmd = [
                        "aria2c", "-x", "16", "-s", "16", "-k", "1M",
                        "-d", dirname, "-o", filename,
                        "--allow-overwrite=true", "--file-allocation=none",
                        "--user-agent", random.choice(Config.USER_AGENTS),
                        dl_url
                    ]
                    
                    proc = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    await asyncio.wait_for(proc.communicate(), timeout=600)
                    
                    if os.path.exists(final_path) and os.path.getsize(final_path) > 1024:
                        return True
        except: return False
        return False

    # -----------------------------------------------------------------
    # 📡 أدوات المعلومات (Utilities)
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

    async def details(self, link: str, videoid: bool = None):
        d, i = await self.track(link, videoid)
        if i == "error": return None
        return d["title"], d["duration_min"], d["thumb"], i

    async def title(self, link: str, videoid: bool = None):
        d, _ = await self.track(link, videoid)
        return d.get("title")

    async def duration(self, link: str, videoid: bool = None):
        d, _ = await self.track(link, videoid)
        return d.get("duration_min")

    async def thumbnail(self, link: str, videoid: bool = None):
        d, _ = await self.track(link, videoid)
        return d.get("thumb")

    async def slider(self, link: str, query_type: int, videoid: bool = None):
        if videoid: link = self.base + link
        try:
            a = VideosSearch(link, limit=10)
            res = (await a.next()).get("result")[query_type]
            return res["title"], res["duration"], res["thumbnails"][0]["url"].split("?")[0], res["id"]
        except: return None
        
    async def playlist(self, link, limit, user_id, videoid: bool = None):
        if videoid: link = self.listbase + link
        cookie = get_random_cookie()
        cmd = ["yt-dlp", "-i", "--get-id", "--flat-playlist", "--playlist-end", str(limit), "--skip-download", link]
        if cookie: cmd.extend(["--cookies", cookie])
        
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
        return [x for x in out.decode().split("\n") if x]

    async def formats(self, link: str, videoid: bool = None):
        return [], link

# =======================================================================
# 🏁 التصدير
# =======================================================================
YouTube = YouTubeAPI()
