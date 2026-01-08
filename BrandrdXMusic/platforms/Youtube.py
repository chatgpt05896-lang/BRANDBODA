import asyncio
import os
import re
import json
import glob
import random
import logging
import aiohttp
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from BrandrdXMusic.utils.database import is_on_off
from BrandrdXMusic.utils.formatters import time_to_seconds
from BrandrdXMusic import LOGGER

# =======================================================================
# 🔧 1. إصلاح Chat ID (Monkey Patch)
# =======================================================================
try:
    from pytgcalls.types import Update
    if not hasattr(Update, "chat_id"):
        @property
        def chat_id_patch(self):
            return self.chat.id if hasattr(self, "chat") else getattr(self, "chat_id", None)
        setattr(Update, "chat_id", chat_id_patch)
except ImportError:
    pass
except Exception as e:
    logging.error(f"Patch Error: {e}")

# =======================================================================
# 🌐 2. إعدادات الـ APIs (نظام التوفير الذكي)
# =======================================================================

# رابطك الخاص (سيستخدم فقط كبديل للحفاظ على الرصيد)
MY_FLY_API = "https://myapi-i-bwca.fly.dev"

# المتغيرات الخاصة بالرابط العام
PUBLIC_API_URL = "https://shrutibots.site" # قيمة افتراضية

async def load_public_api():
    """تحميل الرابط العام من Pastebin"""
    global PUBLIC_API_URL
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://pastebin.com/raw/rLsBhAQa", timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    PUBLIC_API_URL = (await response.text()).strip()
    except:
        PUBLIC_API_URL = "https://shrutibots.site"

# تحميل الرابط العام عند بدء التشغيل
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.create_task(load_public_api())
    else:
        loop.run_until_complete(load_public_api())
except RuntimeError:
    pass

async def api_download(link: str, is_video: bool = False):
    """
    محاولة التحميل بالترتيب:
    1. الرابط العام (توفير للرصيد)
    2. رابطك الخاص (بديل للطوارئ)
    """
    global PUBLIC_API_URL, MY_FLY_API
    
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link
    if not video_id or len(video_id) < 3: return None

    ext = "mp4" if is_video else "mp3"
    type_str = "video" if is_video else "audio"
    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

    if os.path.exists(file_path): return file_path

    async with aiohttp.ClientSession() as session:
        # ---------------------------------------------------------
        # المحاولة 1: استخدام API العام (Shruit/Pastebin)
        # ---------------------------------------------------------
        try:
            if not PUBLIC_API_URL: await load_public_api()
            
            params = {"url": video_id, "type": type_str}
            async with session.get(f"{PUBLIC_API_URL}/download", params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    token = data.get("download_token")
                    if token:
                        stream_url = f"{PUBLIC_API_URL}/stream/{video_id}?type={type_str}&token={token}"
                        async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=300)) as f_resp:
                            if f_resp.status in [200, 302]:
                                target = f_resp.headers.get('Location') if f_resp.status == 302 else stream_url
                                async with session.get(target, timeout=aiohttp.ClientTimeout(total=300)) as final:
                                    if final.status == 200:
                                        with open(file_path, "wb") as f:
                                            async for chunk in final.content.iter_chunked(16384):
                                                f.write(chunk)
                                        return file_path
        except Exception:
            pass # فشل العام، ننتقل للخاص بصمت

        # ---------------------------------------------------------
        # المحاولة 2: استخدام API الخاص بك (Fly.io) - المنقذ
        # ---------------------------------------------------------
        try:
            # نبعت الرابط كامل عشان الكود بتاعك يفهمه
            full_link = f"https://www.youtube.com/watch?v={video_id}"
            params = {"url": full_link}
            
            # ملاحظة: API الخاص بك يرجع URL مباشر ولا يحتاج توكن
            async with session.get(f"{MY_FLY_API}/download", params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    direct_url = data.get("url")
                    
                    if direct_url:
                        async with session.get(direct_url, timeout=aiohttp.ClientTimeout(total=600)) as final:
                            if final.status == 200:
                                with open(file_path, "wb") as f:
                                    async for chunk in final.content.iter_chunked(16384):
                                        f.write(chunk)
                                return file_path
        except Exception:
            pass

    return None

# =======================================================================
# 🍪 3. أدوات مساعدة (Cookies & Shell)
# =======================================================================
def cookie_txt_file():
    folder_path = f"{os.getcwd()}/cookies"
    if not os.path.exists(folder_path): return None
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files: return None
    return random.choice(txt_files)

async def check_file_size(link):
    cookies = cookie_txt_file()
    cmd = ["yt-dlp", "-J", link]
    if cookies: cmd.extend(["--cookies", cookies])
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    if proc.returncode != 0: return None
    try:
        info = json.loads(stdout.decode())
        return sum(f['filesize'] for f in info.get('formats', []) if 'filesize' in f)
    except: return None

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos" in (errorz.decode("utf-8")).lower(): return out.decode("utf-8")
        return errorz.decode("utf-8")
    return out.decode("utf-8")

# =======================================================================
# 🎬 4. كلاس YouTubeAPI
# =======================================================================

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message: messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        return (message.text or message.caption)[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]:
                return (result["title"], result["duration"], 
                        int(time_to_seconds(result["duration"])) if result["duration"] else 0,
                        result["thumbnails"][0]["url"].split("?")[0], result["id"])
        except: return None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]: return result["title"]
        except: return None

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]: return result["duration"]
        except: return None

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]: return result["thumbnails"][0]["url"].split("?")[0]
        except: return None

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        
        # 1. المحاولة عبر APIs
        api_file = await api_download(link, is_video=True)
        if api_file: return 1, api_file

        # 2. المحاولة المحلية
        cookies = cookie_txt_file()
        cmd = ["yt-dlp", "-g", "-f", "best[height<=?720][width<=?1280]", link]
        if cookies: cmd.extend(["--cookies", cookies])

        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        if stdout: return 1, stdout.decode().split("\n")[0]
        return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid: link = self.listbase + link
        if "&" in link: link = link.split("&")[0]
        cookies = cookie_txt_file()
        cmd_str = f"yt-dlp -i --get-id --flat-playlist --playlist-end {limit} --skip-download {link}"
        if cookies: cmd_str += f" --cookies {cookies}"
        playlist = await shell_cmd(cmd_str)
        return [key for key in playlist.split("\n") if key]

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]:
                return {"title": result["title"], "link": result["link"], "vidid": result["id"], 
                        "duration_min": result["duration"], "thumb": result["thumbnails"][0]["url"].split("?")[0]}, result["id"]
        except: return None, None

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        cookies = cookie_txt_file()
        opts = {"quiet": True}
        if cookies: opts["cookiefile"] = cookies
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                r = ydl.extract_info(link, download=False)
                formats = [{"format": f["format"], "filesize": f.get("filesize"), "format_id": f["format_id"], 
                            "ext": f["ext"], "format_note": f.get("format_note"), "yturl": link} 
                           for f in r.get("formats", []) if "dash" not in str(f.get("format")).lower()]
            return formats, link
        except: return [], link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            a = VideosSearch(link, limit=10)
            result = (await a.next()).get("result")[query_type]
            return result["title"], result["duration"], result["thumbnails"][0]["url"].split("?")[0], result["id"]
        except: return None

    async def download(self, link: str, mystic, video: Union[bool, str] = None, videoid: Union[bool, str] = None, 
                       songaudio: Union[bool, str] = None, songvideo: Union[bool, str] = None, 
                       format_id: Union[bool, str] = None, title: Union[bool, str] = None) -> str:
        if videoid: link = self.base + link
        loop = asyncio.get_running_loop()

        # أولوية للـ API (للتحميل العادي فقط)
        if not songvideo and not songaudio and not format_id:
            api_file = await api_download(link, is_video=bool(video))
            if api_file: return api_file, True

        # إعدادات التحميل المحلي
        cookies = cookie_txt_file()
        def get_opts(tmpl, fmt, pp=None):
            opts = {"format": fmt, "outtmpl": tmpl, "geo_bypass": True, "nocheckcertificate": True, "quiet": True, "no_warnings": True}
            if cookies: opts["cookiefile"] = cookies
            if pp: opts.update(pp)
            return opts

        def local_dl(func_type):
            if func_type == "video":
                opts = get_opts("downloads/%(id)s.%(ext)s", "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])")
            elif func_type == "audio":
                opts = get_opts("downloads/%(id)s.%(ext)s", "bestaudio/best")
            elif func_type == "song_video":
                opts = get_opts(f"downloads/{title}", f"{format_id}+140")
                opts["merge_output_format"] = "mp4"
            elif func_type == "song_audio":
                opts = get_opts(f"downloads/{title}.%(ext)s", format_id, 
                                {"prefer_ffmpeg": True, "postprocessors": [{"key": "FFmpegExtractAudio","preferredcodec": "mp3","preferredquality": "192"}]})
            
            with yt_dlp.YoutubeDL(opts) as x:
                info = x.extract_info(link, download=(func_type in ["song_video", "song_audio"]))
                if func_type in ["video", "audio"]:
                    path = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                    if not os.path.exists(path): x.download([link])
                    return path
            return None

        try:
            if songvideo:
                await loop.run_in_executor(None, lambda: local_dl("song_video"))
                return f"downloads/{title}.mp4", False
            elif songaudio:
                await loop.run_in_executor(None, lambda: local_dl("song_audio"))
                return f"downloads/{title}.mp3", False
            elif video:
                if await is_on_off(1):
                    return await loop.run_in_executor(None, lambda: local_dl("video")), True
                else:
                    cmd = ["yt-dlp", "-g", "-f", "best[height<=?720][width<=?1280]", link]
                    if cookies: cmd.extend(["--cookies", cookies])
                    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    stdout, _ = await proc.communicate()
                    if stdout: return stdout.decode().split("\n")[0], False
                    return await loop.run_in_executor(None, lambda: local_dl("video")), True
            else:
                return await loop.run_in_executor(None, lambda: local_dl("audio")), True
        except:
            return None, False
