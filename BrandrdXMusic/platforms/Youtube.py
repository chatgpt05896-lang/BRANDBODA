"""
███████╗███████╗██████╗ ██╗  ██╗██╗███╗   ██╗███████╗████████╗███████╗██╗███╗   ██╗
██╔════╝██╔════╝██╔══██╗██║  ██║██║████╗  ██║██╔════╝╚══██╔══╝██╔════╝██║████╗  ██║
███████╗█████╗  ██████╔╝███████║██║██╔██╗ ██║███████╗   ██║   █████╗  ██║██╔██╗ ██║
╚════██║██╔══╝  ██╔══██╗██╔══██║██║██║╚██╗██║╚════██║   ██║   ██╔══╝  ██║██║╚██╗██║
███████║███████╗██║  ██║██║  ██║██║██║ ╚████║███████║   ██║   ███████╗██║██║ ╚████║
╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚══════╝╚═╝╚═╝  ╚═══╝

[النظام: المدمرة الشاملة - The Destroyer Edition]
[المكونات: Annie Cache System + Alexa Advanced Parser + Brandrd Hybrid Downloader]
[الحالة: Full Logic - No Compression]
"""

import asyncio
import os
import re
import json
import time
import random
import logging
import ssl
import aiohttp
import shutil
from typing import Union, List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch, Playlist
from yt_dlp import YoutubeDL

# =======================================================================
# ⚙️ 1. إعدادات السيرفر واللوج (Configuration & Logging)
# =======================================================================
try:
    from BrandrdXMusic.utils.database import is_on_off
    from BrandrdXMusic.utils.formatters import time_to_seconds
    from BrandrdXMusic import LOGGER
except ImportError:
    # إعدادات افتراضية في حالة التشغيل المنفصل
    logging.basicConfig(level=logging.ERROR)
    def LOGGER(name): return logging.getLogger(name)
    async def is_on_off(x): return True
    def time_to_seconds(t): return 0

# إخفاء تحذيرات المكتبات المزعجة
logging.getLogger("yt_dlp").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

class Config:
    DOWNLOAD_PATH = "downloads"
    MAX_WORKERS = 10
    # سيرفرات احتياطية من سورس Brandrd
    SERVERS = [
        {"url": "https://shrutibots.site", "weight": 10},
        {"url": "https://myapi-i-bwca.fly.dev", "weight": 100},
    ]

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH)

# =======================================================================
# 🧠 2. نظام الكاش المتطور (Annie X Memory System)
# =======================================================================
# المتغيرات دي بتخزن نتائج البحث عشان البوت ميبحثش مرتين عن نفس الحاجة
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
_formats_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_formats_lock = asyncio.Lock()

YOUTUBE_META_TTL = 3600  # مدة حفظ الذاكرة (ساعة)
YOUTUBE_META_MAX = 1000  # أقصى عدد لنتائج البحث المحفوظة

# =======================================================================
# 🛠️ 3. الأدوات المساعدة (Helpers & Parsers)
# =======================================================================
def get_cookie():
    """جلب ملف الكوكيز بذكاء من أي مكان محتمل"""
    if os.path.exists("cookies.txt"): return "cookies.txt"
    if os.path.exists("cookies"):
        files = [f for f in os.listdir("cookies") if f.endswith(".txt")]
        if files: return os.path.join("cookies", random.choice(files))
    return None

def clean_file(path):
    """تنظيف شامل للملفات التالفة ومخلفات التحميل"""
    try:
        if os.path.exists(path): os.remove(path)
        if os.path.exists(path + ".aria2"): os.remove(path + ".aria2")
        if os.path.exists(path + ".part"): os.remove(path + ".part")
        if os.path.exists(path + ".ytdl"): os.remove(path + ".ytdl")
    except: pass

async def shell_cmd(cmd):
    """تشغيل أوامر النظام (من كود Alexa)"""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

# =======================================================================
# 🚀 4. الكلاس الرئيسي (The Monster Class)
# =======================================================================
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)
        self.has_aria2 = os.system("which aria2c > /dev/null 2>&1") == 0

        # تنظيف أولي عند الإقلاع
        try:
            for f in os.listdir(Config.DOWNLOAD_PATH):
                if os.stat(os.path.join(Config.DOWNLOAD_PATH, f)).st_mtime < time.time() - 3600:
                    os.remove(os.path.join(Config.DOWNLOAD_PATH, f))
        except: pass

    # -----------------------------------------------------------------
    # 🔗 معالجة الروابط (Alexa Advanced Logic)
    # -----------------------------------------------------------------
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        """دالة استخراج الروابط الأكثر دقة (من Alexa)"""
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset: break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None if offset in (None,) else text[offset : offset + length]

    # -----------------------------------------------------------------
    # 🔍 البحث والمعلومات (Annie Caching System)
    # -----------------------------------------------------------------
    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        link = link.split("&")[0]

        # 1. البحث في الذاكرة (الكاش) لسرعة خرافية
        async with _cache_lock:
            if link in _cache:
                ts, val = _cache[link]
                if time.time() - ts < YOUTUBE_META_TTL:
                    return val[0], val[1] # إرجاع البيانات المخزنة

        # 2. البحث الفعلي باستخدام VideosSearch
        try:
            results = VideosSearch(link, limit=1)
            data = (await results.next())["result"][0]
            
            track_details = {
                "title": data["title"],
                "link": data["link"],
                "vidid": data["id"],
                "duration_min": data["duration"],
                "thumb": data["thumbnails"][0]["url"].split("?")[0],
                "cookiefile": get_cookie(),
            }
            
            # 3. تخزين النتيجة في الذاكرة
            async with _cache_lock:
                _cache[link] = (time.time(), (track_details, data["id"]))
            
            return track_details, data["id"]
        except Exception:
            # لو فشل البحث، نرجع قيم افتراضية بدل ما البوت يوقف
            return {"title": "Error", "link": link, "vidid": "error", "duration_min": "0:00", "thumb": ""}, "error"

    # دوال مساعدة لجلب البيانات الفردية
    async def details(self, link: str, videoid: Union[bool, str] = None):
        d, i = await self.track(link, videoid)
        if i == "error": return None
        return d["title"], d["duration_min"], time_to_seconds(d["duration_min"]), d["thumb"], i

    async def title(self, link: str, videoid: Union[bool, str] = None):
        d, _ = await self.track(link, videoid)
        return d.get("title")

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        d, _ = await self.track(link, videoid)
        return d.get("duration_min")

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        d, _ = await self.track(link, videoid)
        return d.get("thumb")

    # -----------------------------------------------------------------
    # 📥 محرك التحميل العملاق (The Ultimate Downloader)
    # -----------------------------------------------------------------
    # يدمج منطق Alexa للتنسيقات المحددة + منطق Aria2 للسرعة + منطق API للطوارئ
    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid: link = self.base + link
        loop = asyncio.get_running_loop()

        # استخراج ID لاستخدامه في التسمية
        if "v=" in link: vid_id = link.split("v=")[1].split("&")[0]
        elif "youtu.be/" in link: vid_id = link.split("youtu.be/")[1].split("?")[0]
        else: vid_id = str(int(time.time()))

        # تحديد المسار النهائي للملف
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title if title else vid_id)
        
        # === الدوال الداخلية (من منطق Alexa) ===
        def audio_dl():
            ydl_optssx = {
                "cookiefile": get_cookie(),
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "outtmpl": f"downloads/%(id)s.%(ext)s",
                "geo_bypass": True, "nocheckcertificate": True,
                "quiet": True, "no_warnings": True,
            }
            with YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link, False)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz): return xyz
                x.download([link])
                return xyz

        def video_dl():
            ydl_optssx = {
                "cookiefile": get_cookie(),
                "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]",
                "outtmpl": f"downloads/%(id)s.%(ext)s",
                "geo_bypass": True, "nocheckcertificate": True,
                "quiet": True, "no_warnings": True,
            }
            with YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link, False)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz): return xyz
                x.download([link])
                return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{safe_title}"
            ydl_optssx = {
                "format": formats, "outtmpl": fpath,
                "geo_bypass": True, "nocheckcertificate": True,
                "quiet": True, "no_warnings": True,
                "cookiefile": get_cookie(),
                "prefer_ffmpeg": True, "merge_output_format": "mp4",
            }
            x = YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            fpath = f"downloads/{safe_title}.%(ext)s"
            ydl_optssx = {
                "format": format_id, "outtmpl": fpath,
                "geo_bypass": True, "nocheckcertificate": True,
                "quiet": True, "no_warnings": True,
                "cookiefile": get_cookie(),
                "prefer_ffmpeg": True,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
            }
            x = YoutubeDL(ydl_optssx)
            x.download([link])

        # === 1. التعامل مع طلبات التنسيق الخاص (Format Specific) ===
        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            return f"downloads/{safe_title}.mp4"
        elif songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            return f"downloads/{safe_title}.mp3"

        # === 2. التحميل العادي (Waterfall Strategy: Aria2 -> Native -> API) ===
        final_path = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id}.mp4" if video else f"{vid_id}.m4a")
        
        # أ) محاولة Aria2 (الأسرع)
        if self.has_aria2:
            try:
                # محاولة التحميل باستخدام Aria2c
                res = await loop.run_in_executor(
                    self.pool,
                    lambda: self._aria2_download(link, final_path, video)
                )
                if res: return res, True
            except:
                clean_file(final_path)

        # ب) محاولة Native yt-dlp (الأكثر استقراراً)
        if video:
            if await is_on_off(1):
                downloaded_file = await loop.run_in_executor(None, video_dl)
                return downloaded_file, True
        else:
            downloaded_file = await loop.run_in_executor(None, audio_dl)
            return downloaded_file, True

        # ج) محاولة API (الطوارئ القصوى)
        if not (songaudio or songvideo):
            try:
                res = await self._api_download_fallback(link, vid_id, final_path, video)
                if res: return res, True
            except:
                pass
        
        return None, False

    # دوال المساعدة الداخلية للتحميل
    def _aria2_download(self, link, path, is_video):
        opts = {
            "outtmpl": path,
            "cookiefile": get_cookie(),
            "geo_bypass": True, "nocheckcertificate": True,
            "quiet": True, "no_warnings": True,
            "external_downloader": "aria2c",
            "external_downloader_args": ["-x", "16", "-s", "16", "-k", "1M"],
        }
        if is_video:
            opts["format"] = "bestvideo[height<=720]+bestaudio/best[height<=720]"
            opts["merge_output_format"] = "mp4"
        else:
            opts["format"] = "bestaudio/best"
        
        with YoutubeDL(opts) as ydl:
            ydl.download([link])
        if os.path.exists(path): return path
        return None

    async def _api_download_fallback(self, link, vid_id, path, is_video):
        """تحميل من سيرفرات خارجية لو يوتيوب محظور"""
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        url = None
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ctx)) as s:
            for srv in sorted(Config.SERVERS, key=lambda x: x["weight"], reverse=True):
                try:
                    async with s.head(srv["url"], timeout=2) as r:
                        if r.status < 500: url = srv["url"]; break
                except: continue
        
        if not url: return None
        t = "video" if is_video else "audio"
        q = vid_id
        
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ctx)) as s:
            async with s.get(f"{url}/download", params={"url": q, "type": t}, timeout=10) as r:
                if r.status != 200: return None
                d = await r.json()
                dl_url = d.get("url")
                if not dl_url: return None
                
                async with s.get(dl_url, timeout=600) as stream:
                    if stream.status == 200:
                        with open(path, "wb") as f:
                            async for chunk in stream.content.iter_chunked(65536):
                                f.write(chunk)
                        return path
        return None

    # -----------------------------------------------------------------
    # 📺 وظائف إضافية (Playlist, Stream, Formats)
    # -----------------------------------------------------------------
    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        # استخراج رابط بث مباشر (Direct Stream URL)
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", get_cookie(),
            "-g", "-f", "best[height<=?720][width<=?1280]",
            f"{link}",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid: link = self.listbase + link
        if "&" in link: link = link.split("&")[0]
        # استخدام yt-dlp لجلب القائمة بسرعة
        cmd = (
            f"yt-dlp -i --compat-options no-youtube-unavailable-videos "
            f"--get-id --flat-playlist --playlist-end {limit} --skip-download '{link}' "
            f"2>/dev/null"
        )
        playlist = await shell_cmd(cmd)
        try:
            result = [key for key in playlist.split("\n") if key]
        except Exception:
            result = []
        return result

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        
        ytdl_opts = {"quiet": True, "cookiefile": get_cookie()}
        ydl = YoutubeDL(ytdl_opts)
        
        # استخراج صيغ التحميل (Quality Options)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    if "dash" in str(format["format"]).lower(): continue
                    if not format.get("filesize"): continue
                    
                    formats_available.append({
                        "format": format["format"],
                        "filesize": format["filesize"],
                        "format_id": format["format_id"],
                        "ext": format["ext"],
                        "format_note": format.get("format_note", ""),
                        "yturl": link,
                        "cookiefile": get_cookie(),
                    })
                except: continue
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        a = VideosSearch(link, limit=10)
        try:
            result = (await a.next()).get("result")
            r = result[query_type]
            return r["title"], r["duration"], r["thumbnails"][0]["url"].split("?")[0], r["id"]
        except:
            return "Error", "0", "", "error"

# =======================================================================
# 🏁 التصدير النهائي
# =======================================================================
YouTube = YouTubeAPI()
