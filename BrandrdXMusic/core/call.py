"""
██████╗ ██████╗  █████╗ ███╗   ██╗██████╗ ██████╗ ██████╗ ██╗  ██╗
██╔══██╗██╔══██╗██╔══██╗████╗  ██║██╔══██╗██╔══██╗██╔══██╗╚██╗██╔╝
██████╔╝██████╔╝███████║██╔██╗ ██║██║  ██║██████╔╝██║  ██║ ╚███╔╝ 
██╔══██╗██╔══██╗██╔══██║██║╚██╗██║██║  ██║██╔══██╗██║  ██║ ██╔██╗ 
██████╔╝██║  ██║██║  ██║██║ ╚████║██████╔╝██║  ██║██████╔╝██╔╝ ██╗
╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝

[ SYSTEM: NEXT GEN CORE - v3.0 ]
[ ARCHITECTURE: FORCED STABILITY WRAPPER ]
[ COMPATIBILITY: UNIVERSAL (v2.x - v3.x Bridges) ]
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Union
from functools import wraps

# =======================================================================
# ☢️ NUCLEAR PATCH: حقن الكود داخل قلب المكتبة
# هذا الجزء يقوم بإعادة كتابة طريقة استقبال التحديثات لمنع الكراش
# =======================================================================
try:
    import pytgcalls.mtproto.pyrogram_client
    
    # نحتفظ بالدالة الأصلية
    _original_update = pytgcalls.mtproto.pyrogram_client.PyrogramClient.on_update

    async def _safe_update_handler(self, client, update):
        # 1. فلترة التحديثات التالفة
        if not update or not hasattr(update, 'chat_id'):
            return
        # 2. فلترة القيم الفارغة (NoneType Crash Fix)
        if update.chat_id is None:
            return
        
        try:
            await _original_update(self, client, update)
        except (AttributeError, KeyError, TypeError):
            # تجاهل الأخطاء البنيوية في المكتبة القديمة
            pass
        except Exception:
            pass

    # استبدال الدالة
    pytgcalls.mtproto.pyrogram_client.PyrogramClient.on_update = _safe_update_handler
except ImportError:
    pass
# =======================================================================

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup
from ntgcalls import TelegramServerError
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import (
    AlreadyJoinedError,
    NoActiveGroupCall,
    GroupCallNotFound
)
from pytgcalls.types import (
    MediaStream,
    AudioQuality,
    VideoQuality,
    Update,
)
from pytgcalls.types.stream import StreamAudioEnded

import config
from BrandrdXMusic import LOGGER, YouTube, app
from BrandrdXMusic.misc import db
from BrandrdXMusic.utils.database import (
    add_active_chat, add_active_video_chat, get_lang, get_loop, group_assistant,
    is_autoend, music_on, remove_active_chat, remove_active_video_chat, set_loop,
)
from BrandrdXMusic.utils.exceptions import AssistantErr
from BrandrdXMusic.utils.formatters import check_duration, seconds_to_min, speed_converter
from BrandrdXMusic.utils.stream.autoclear import auto_clean
from BrandrdXMusic.utils.thumbnails import get_thumb
from strings import get_string

# استيراد آمن للماركوب
try: from BrandrdXMusic.utils.inline.play import stream_markup2
except: stream_markup2 = None
from BrandrdXMusic.utils.inline.play import stream_markup

autoend = {}
counter = {}
loop = asyncio.get_event_loop_policy().get_event_loop()

# =======================================================================
# 🛡️ THE FORTRESS: دوال الحماية والتنظيف
# =======================================================================

def run_safe(func):
    """ديكوريتور لتشغيل الدوال داخل غلاف آمن يمنع توقف البوت"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            LOGGER(__name__).error(f"⚠️ [AUTO-FIX] Handled error in {func.__name__}: {e}")
            return None
    return wrapper

def build_stream(path, video=False, ffmpeg=None):
    """
    مولد الستريم الذكي: يقوم بإنشاء إعدادات لا يمكن أن ترفضها المكتبة
    """
    # نستخدم جودة متوسطة للفيديو لضمان الثبات والسرعة (طلقة)
    # ونرسل الجودة دائمًا حتى لو الفيديو مغلق لتفادي NoneType
    video_q = VideoQuality.SD_480p 
    
    flags = MediaStream.Flags.REQUIRED if video else MediaStream.Flags.IGNORE
    
    return MediaStream(
        path,
        audio_parameters=AudioQuality.HIGH,
        video_parameters=video_q,
        video_flags=flags,
        ffmpeg_parameters=ffmpeg
    )

async def _clear_(chat_id):
    try:
        db[chat_id] = []
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
    except: pass

# =======================================================================
# 🚀 ENGINE CLASS
# =======================================================================

class Call(PyTgCalls):
    def __init__(self):
        self.userbot1 = Client("BrandrdXMusic1", config.API_ID, config.API_HASH, session_string=str(config.STRING1)) if config.STRING1 else None
        self.one = PyTgCalls(self.userbot1, cache_duration=100) if self.userbot1 else None

        self.userbot2 = Client("BrandrdXMusic2", config.API_ID, config.API_HASH, session_string=str(config.STRING2)) if config.STRING2 else None
        self.two = PyTgCalls(self.userbot2, cache_duration=100) if self.userbot2 else None

        self.userbot3 = Client("BrandrdXMusic3", config.API_ID, config.API_HASH, session_string=str(config.STRING3)) if config.STRING3 else None
        self.three = PyTgCalls(self.userbot3, cache_duration=100) if self.userbot3 else None

        self.userbot4 = Client("BrandrdXMusic4", config.API_ID, config.API_HASH, session_string=str(config.STRING4)) if config.STRING4 else None
        self.four = PyTgCalls(self.userbot4, cache_duration=100) if self.userbot4 else None

        self.userbot5 = Client("BrandrdXMusic5", config.API_ID, config.API_HASH, session_string=str(config.STRING5)) if config.STRING5 else None
        self.five = PyTgCalls(self.userbot5, cache_duration=100) if self.userbot5 else None

    # --- CONTROL METHODS ---
    @run_safe
    async def pause_stream(self, chat_id: int):
        await (await group_assistant(self, chat_id)).pause_stream(chat_id)

    @run_safe
    async def mute_stream(self, chat_id: int):
        await (await group_assistant(self, chat_id)).mute_stream(chat_id)

    @run_safe
    async def unmute_stream(self, chat_id: int):
        await (await group_assistant(self, chat_id)).unmute_stream(chat_id)

    @run_safe
    async def resume_stream(self, chat_id: int):
        await (await group_assistant(self, chat_id)).resume_stream(chat_id)

    @run_safe
    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await _clear_(chat_id)
        try: await assistant.leave_group_call(chat_id)
        except: pass

    @run_safe
    async def force_stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            if check: check.pop(0)
        except: pass
        await _clear_(chat_id)
        try: await assistant.leave_group_call(chat_id)
        except: pass

    @run_safe
    async def stop_stream_force(self, chat_id: int):
        # إيقاف شامل لكل المساعدين في حالة الطوارئ
        clients = [self.one, self.two, self.three, self.four, self.five]
        for c in clients:
            if c:
                try: await c.leave_group_call(chat_id)
                except: pass
        await _clear_(chat_id)

    # --- STREAMING METHODS ---
    @run_safe
    async def join_call(self, chat_id: int, original_chat_id: int, link, video=None, image=None):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)
        
        # استخدام المولد الذكي
        stream = build_stream(link, video=bool(video))

        try:
            await assistant.join_group_call(chat_id, stream)
        except NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except AlreadyJoinedError:
            raise AssistantErr(_["call_9"])
        except (TelegramServerError, GroupCallNotFound):
            raise AssistantErr(_["call_10"])
        except Exception as e:
            if "phone.CreateGroupCall" in str(e):
                raise AssistantErr(_["call_8"])
            LOGGER(__name__).error(f"Join Call Error: {e}")
            raise AssistantErr(f"⚠️ Error: {e}")

        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video: await add_active_video_chat(chat_id)
        
        if await is_autoend():
            counter[chat_id] = {}
            try:
                users = len(await assistant.get_participants(chat_id))
                if users == 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except: pass

    @run_safe
    async def change_stream(self, client, chat_id):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0: popped = check.pop(0)
            else:
                loop -= 1
                await set_loop(chat_id, loop)
            if popped: await auto_clean(popped)
            if not check:
                await _clear_(chat_id)
                return await client.leave_group_call(chat_id)
        except:
            await _clear_(chat_id)
            try: return await client.leave_group_call(chat_id)
            except: return

        queued = check[0]["file"]
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        db[chat_id][0]["played"] = 0
        
        if exis := (check[0]).get("old_dur"):
            db[chat_id][0]["dur"] = exis
            db[chat_id][0]["seconds"] = check[0]["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0

        video = str(streamtype) == "video"
        lang = await get_lang(chat_id)
        _ = get_string(lang)

        # UI Helper for cleaner code
        async def send_ui(img, btn_type, markup_type):
            try:
                btn = stream_markup2(_, chat_id) if btn_type == "tg" else stream_markup(_, videoid, chat_id)
                caption = _["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user)
                if videoid in ["telegram", "soundcloud"]:
                     caption = _["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user)

                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(btn),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = markup_type
            except: pass

        try:
            stream = None
            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0: return await app.send_message(original_chat_id, text=_["call_6"])
                stream = build_stream(link, video)
                await client.change_stream(chat_id, stream)
                img = await get_thumb(videoid)
                await send_ui(img, "tg", "tg")

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                try: file_path, direct = await YouTube.download(videoid, mystic, videoid=True, video=video)
                except: return await mystic.edit_text(_["call_6"])
                stream = build_stream(file_path, video)
                await client.change_stream(chat_id, stream)
                img = await get_thumb(videoid)
                await mystic.delete()
                await send_ui(img, "stream", "stream")

            elif "index_" in queued:
                stream = build_stream(videoid, video)
                await client.change_stream(chat_id, stream)
                button = stream_markup2(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            else:
                stream = build_stream(queued, video)
                await client.change_stream(chat_id, stream)
                if videoid == "telegram":
                    img = config.TELEGRAM_AUDIO_URL if str(streamtype) == "audio" else config.TELEGRAM_VIDEO_URL
                    await send_ui(img, "tg", "tg")
                elif videoid == "soundcloud":
                    await send_ui(config.SOUNCLOUD_IMG_URL, "tg", "tg")
                else:
                    img = await get_thumb(videoid)
                    await send_ui(img, "stream", "stream")

        except Exception as e:
            LOGGER(__name__).error(f"Change Stream Error: {e}")
            await app.send_message(original_chat_id, text=_["call_6"])

    @run_safe
    async def skip_stream(self, chat_id: int, link: str, video=None, image=None):
        assistant = await group_assistant(self, chat_id)
        stream = build_stream(link, video=bool(video))
        await assistant.change_stream(chat_id, stream)

    @run_safe
    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        ffmpeg = f"-ss {to_seek} -to {duration}"
        stream = build_stream(file_path, video=(mode == "video"), ffmpeg=ffmpeg)
        await assistant.change_stream(chat_id, stream)

    @run_safe
    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            os.makedirs(chatdir, exist_ok=True)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                vs = {"0.5": 2.0, "0.75": 1.35, "1.5": 0.68, "2.0": 0.5}.get(str(speed), 1.0)
                cmd = f'ffmpeg -i "{file_path}" -filter:v "setpts={vs}*PTS" -filter:a atempo={speed} -y "{out}"'
                proc = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await proc.communicate()
        else:
            out = file_path
            
        dur = int(await loop.run_in_executor(None, check_duration, out))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        ffmpeg = f"-ss {played} -to {duration}"
        
        stream = build_stream(out, video=(playing[0]["streamtype"] == "video"), ffmpeg=ffmpeg)

        if str(db[chat_id][0]["file"]) == str(file_path):
            await assistant.change_stream(chat_id, stream)
            db[chat_id][0].update({
                "played": con_seconds, "dur": duration, "seconds": dur,
                "speed_path": out, "speed": speed
            })
            if "old_dur" not in db[chat_id][0]:
                 db[chat_id][0]["old_dur"] = playing[0]["dur"]
                 db[chat_id][0]["old_second"] = playing[0]["seconds"]
        else:
            raise AssistantErr("Stream mismatch")

    @run_safe
    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOGGER_ID)
        await assistant.join_group_call(config.LOGGER_ID, build_stream(link))
        await asyncio.sleep(0.5)
        await assistant.leave_group_call(config.LOGGER_ID)

    async def ping(self):
        pings = []
        clients = [self.one, self.two, self.three, self.four, self.five]
        for c in clients:
            if c: pings.append(await c.ping)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    async def start(self):
        LOGGER(__name__).info("🚀 Initializing Next-Gen Audio Engine...")
        clients = [self.one, self.two, self.three, self.four, self.five]
        for c in clients:
            if c: await c.start()

    async def decorators(self):
        clients = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))
        
        for c in clients:
            @c.on_kicked()
            @c.on_closed_voice_chat()
            @c.on_left()
            async def stream_services_handler(_, chat_id: int):
                await self.stop_stream(chat_id)

            @c.on_stream_end()
            async def stream_end_handler(client, update: Update):
                if not isinstance(update, StreamAudioEnded):
                    return
                # الحماية هنا لمنع تداخل الأحداث
                try: await self.change_stream(client, update.chat_id)
                except: pass

Hotty = Call()
