import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Union, Dict

from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired, UserAlreadyParticipant
from pyrogram.types import InlineKeyboardMarkup

from pytgcalls import PyTgCalls
from pytgcalls.types import (
    MediaStream, 
    AudioQuality, 
    VideoQuality, 
    StreamEnded, 
    ChatUpdate, 
    Update,
    GroupCallConfig
)
from pytgcalls.exceptions import (
    NoActiveGroupCall,
    NoAudioSourceFound,
    NoVideoSourceFound
)

# محاولة استيراد الاستثناءات حسب إصدار المكتبة
try:
    from pytgcalls.exceptions import TelegramServerError, ConnectionNotFound
except ImportError:
    # Fallback للإصدارات القديمة أو المعدلة
    class TelegramServerError(Exception): pass
    class ConnectionNotFound(Exception): pass

import config
from strings import get_string
from BrandrdXMusic import LOGGER, YouTube, app
from BrandrdXMusic.misc import db
from BrandrdXMusic.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from BrandrdXMusic.utils.exceptions import AssistantErr
from BrandrdXMusic.utils.formatters import check_duration, seconds_to_min, speed_converter
from BrandrdXMusic.utils.stream.autoclear import auto_clean
from BrandrdXMusic.utils.thumbnails import get_thumb
from BrandrdXMusic.utils.inline.play import stream_markup

try:
    from BrandrdXMusic.utils.inline.play import stream_markup2
except ImportError:
    stream_markup2 = None

autoend = {}
counter = {}

# =======================================================================
# 🗂️ 1. SMART CACHE SYSTEM (Fixed Duration & Path)
# =======================================================================

class SmartCache:
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.ttl = 420  # 7 Minutes as requested

    def get(self, video_id: str) -> str:
        self.cleanup()
        if video_id in self.cache:
            entry = self.cache[video_id]
            # التأكد من وجود الملف فعلياً
            if time.time() - entry['timestamp'] < self.ttl:
                if os.path.exists(entry['path']):
                    return entry['path']
        return None

    def store(self, video_id: str, path: str):
        # تخزين المسار المطلق دائماً لتجنب مشاكل المسارات النسبية
        abs_path = os.path.abspath(path)
        self.cache[video_id] = {
            'path': abs_path,
            'timestamp': time.time()
        }

    def cleanup(self):
        now = time.time()
        to_remove = []
        for vid, entry in self.cache.items():
            if now - entry['timestamp'] > self.ttl:
                to_remove.append(vid)
                if os.path.exists(entry['path']):
                    try:
                        os.remove(entry['path'])
                    except: pass
        for vid in to_remove:
            del self.cache[vid]

music_cache = SmartCache()

# =======================================================================
# ⚙️ 2. FFmpeg & STREAM CONFIGURATION (Studio Quality)
# =======================================================================

# إعدادات الروابط الخارجية (Live/URL) مع منع التقطيع
REMOTE_FFMPEG = (
    "-reconnect 1 "
    "-reconnect_streamed 1 "
    "-reconnect_delay_max 5 "
    "-probesize 32M "       # حجم متوسط لضمان التحليل الجيد وسرعة البدء
    "-analyzeduration 10M " # مدة تحليل متوسطة
    "-ac 2 "                # Stereo حقيقي
    "-ar 48000 "            # جودة صوت عالية
    "-nostdin "
    "-fflags nobuffer "
    "-flags low_delay "
    "-loglevel error"
)

# إعدادات الملفات المحلية
LOCAL_FFMPEG = (
    "-ac 2 "
    "-ar 48000 "
    "-nostdin "
    "-fflags nobuffer "
    "-flags low_delay "
    "-loglevel error"
)

def build_stream(path: str, video: bool = False, ffmpeg: str = None, duration: int = 0, quality_mode: str = "studio") -> MediaStream:
    is_url = path.startswith("http")
    base_ffmpeg = REMOTE_FFMPEG if is_url else LOCAL_FFMPEG
    
    combined_ffmpeg = f"{base_ffmpeg} {ffmpeg}" if ffmpeg else base_ffmpeg

    # تحديد جودة الصوت ديناميكياً
    if quality_mode == "studio":
        audio_params = AudioQuality.STUDIO
    else:
        audio_params = AudioQuality.HIGH
    
    # تحديد جودة الفيديو
    video_params = VideoQuality.HD_720p if (is_url or duration > 600) else VideoQuality.FHD_1080p

    if video:
        return MediaStream(
            media_path=path,
            audio_parameters=audio_params,
            video_parameters=video_params,
            ffmpeg_parameters=combined_ffmpeg,
        )
    else:
        return MediaStream(
            media_path=path,
            audio_parameters=audio_params,
            video_flags=MediaStream.Flags.IGNORE, # تعطيل الفيديو لتوفير الباندويث
            ffmpeg_parameters=combined_ffmpeg,
        )

async def _clear_(chat_id: int) -> None:
    try:
        if popped := db.pop(chat_id, None):
            await auto_clean(popped)
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await set_loop(chat_id, 0)
    except:
        pass

# =======================================================================
# 🚀 3. CORE CLASS (With Fallback Mechanism)
# =======================================================================

class Call:
    def __init__(self):
        self.userbot1 = Client("BrandrdXMusic1", config.API_ID, config.API_HASH, session_string=config.STRING1) if config.STRING1 else None
        self.one = PyTgCalls(self.userbot1) if self.userbot1 else None

        self.userbot2 = Client("BrandrdXMusic2", config.API_ID, config.API_HASH, session_string=config.STRING2) if config.STRING2 else None
        self.two = PyTgCalls(self.userbot2) if self.userbot2 else None

        self.userbot3 = Client("BrandrdXMusic3", config.API_ID, config.API_HASH, session_string=config.STRING3) if config.STRING3 else None
        self.three = PyTgCalls(self.userbot3) if self.userbot3 else None

        self.userbot4 = Client("BrandrdXMusic4", config.API_ID, config.API_HASH, session_string=config.STRING4) if config.STRING4 else None
        self.four = PyTgCalls(self.userbot4) if self.userbot4 else None

        self.userbot5 = Client("BrandrdXMusic5", config.API_ID, config.API_HASH, session_string=config.STRING5) if config.STRING5 else None
        self.five = PyTgCalls(self.userbot5) if self.userbot5 else None

        self.active_calls = set()
        
        self.pytgcalls_map = {
            id(self.userbot1): self.one,
            id(self.userbot2): self.two,
            id(self.userbot3): self.three,
            id(self.userbot4): self.four,
            id(self.userbot5): self.five,
        }

    async def get_tgcalls(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        return self.pytgcalls_map.get(id(assistant), self.one)

    # دالة ذكية للتشغيل الآمن مع الـ Fallback
    async def _play_stream_safe(self, client, chat_id, path, video, duration_sec=0, ffmpeg=None):
        # المحاولة الأولى: Studio Quality
        try:
            stream = build_stream(path, video, ffmpeg, duration_sec, quality_mode="studio")
            await client.play(chat_id, stream)
        except Exception as e:
            LOGGER(__name__).warning(f"Studio Quality Failed for {chat_id}, falling back to HIGH. Error: {e}")
            # المحاولة الثانية: High Quality (Fallback)
            try:
                stream = build_stream(path, video, ffmpeg, duration_sec, quality_mode="high")
                await client.play(chat_id, stream)
            except Exception as final_e:
                LOGGER(__name__).error(f"FATAL: All streams failed for {chat_id}. Error: {final_e}")
                raise final_e

    async def start(self):
        LOGGER(__name__).info("🚀 Starting Studio Audio Engine...")
        clients = [self.one, self.two, self.three, self.four, self.five]
        tasks = [c.start() for c in clients if c]
        if tasks:
            await asyncio.gather(*tasks)
        await self.decorators()

    async def ping(self):
        pings = []
        clients = [self.one, self.two, self.three, self.four, self.five]
        for c in clients:
            if c:
                try: pings.append(c.ping)
                except: pass
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    async def pause_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        await client.pause(chat_id)

    async def resume_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        await client.resume(chat_id)

    async def mute_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        await client.mute(chat_id)

    async def unmute_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        await client.unmute(chat_id)

    async def stop_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        await _clear_(chat_id)
        if chat_id in self.active_calls:
            try: await client.leave_call(chat_id)
            except: pass
            finally: self.active_calls.discard(chat_id)

    async def force_stop_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        try:
            check = db.get(chat_id)
            if check: check.pop(0)
        except: pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await _clear_(chat_id)
        if chat_id in self.active_calls:
            try: await client.leave_call(chat_id)
            except: pass
            finally: self.active_calls.discard(chat_id)

    async def join_call(self, chat_id: int, original_chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None):
        client = await self.get_tgcalls(chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)
        
        if not link.startswith("http"):
            link = os.path.abspath(link)

        try:
            # نستخدم الدالة الآمنة هنا
            await self._play_stream_safe(client, chat_id, link, bool(video))
            
        except (NoActiveGroupCall, ChatAdminRequired):
            raise AssistantErr(_["call_8"])
        except (NoAudioSourceFound, NoVideoSourceFound):
            raise AssistantErr(_["call_11"])
        except (TelegramServerError, ConnectionNotFound):
            raise AssistantErr(_["call_10"])
        except Exception as e:
            raise AssistantErr(f"{e}")
            
        self.active_calls.add(chat_id)
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video: await add_active_video_chat(chat_id)

        if await is_autoend():
            try:
                if len(await client.get_participants(chat_id)) <= 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except: pass

    async def change_stream(self, client, chat_id: int):
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
                if chat_id in self.active_calls:
                    try: await client.leave_call(chat_id)
                    except: pass
                    finally: self.active_calls.discard(chat_id)
                return
        except:
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except: return
        
        queued = check[0]["file"]
        lang = await get_lang(chat_id)
        _ = get_string(lang)
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        
        try:
            duration_sec = check[0].get("seconds", 0)
        except:
            duration_sec = 0
            
        db[chat_id][0]["played"] = 0

        if check[0].get("old_dur"):
            db[chat_id][0]["dur"] = check[0]["old_dur"]
            db[chat_id][0]["seconds"] = check[0]["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0

        video = True if str(streamtype) == "video" else False

        def get_btn(vid_id):
            if stream_markup2: return stream_markup2(_, chat_id)
            return stream_markup(_, vid_id, chat_id)

        try:
            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0: return await app.send_message(original_chat_id, text=_["call_6"])

                await self._play_stream_safe(client, chat_id, link, video, 0)
                
                img = await get_thumb(videoid)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                    reply_markup=InlineKeyboardMarkup(get_btn(videoid)),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                
                file_path = music_cache.get(videoid)
                if not file_path:
                    try: 
                        file_path, direct = await YouTube.download(videoid, mystic, videoid=True, video=video)
                        file_path = os.path.abspath(file_path)
                        music_cache.store(videoid, file_path)
                    except: 
                        return await mystic.edit_text(_["call_6"])
                
                await self._play_stream_safe(client, chat_id, file_path, video, duration_sec)

                img = await get_thumb(videoid)
                await mystic.delete()
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                    reply_markup=InlineKeyboardMarkup(stream_markup(_, videoid, chat_id)),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

            elif "index_" in queued:
                await self._play_stream_safe(client, chat_id, videoid, video, duration_sec)

                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(get_btn(videoid)),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            else:
                await self._play_stream_safe(client, chat_id, queued, video, duration_sec)

                if videoid == "telegram":
                    img = config.TELEGRAM_AUDIO_URL if str(streamtype) == "audio" else config.TELEGRAM_VIDEO_URL
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=img,
                        caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user),
                        reply_markup=InlineKeyboardMarkup(get_btn("telegram")),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                elif videoid == "soundcloud":
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=config.SOUNCLOUD_IMG_URL,
                        caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user),
                        reply_markup=InlineKeyboardMarkup(get_btn("soundcloud")),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                else:
                    img = await get_thumb(videoid)
                    try:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                            reply_markup=InlineKeyboardMarkup(stream_markup(_, videoid, chat_id)),
                        )
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                            reply_markup=InlineKeyboardMarkup(stream_markup(_, videoid, chat_id)),
                        )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
                    
        except Exception as e:
            LOGGER(__name__).error(f"Play Error: {e}")
            try:
                # Zero-Downtime: الانتقال الفوري للتالي عند الخطأ
                await self.change_stream(client, chat_id)
            except:
                pass

    async def skip_stream(self, chat_id, link, video=None, image=None):
        client = await self.get_tgcalls(chat_id)
        if not link.startswith("http"):
            link = os.path.abspath(link)
        # استخدام نفس آلية الـ Fallback هنا أيضاً
        await self._play_stream_safe(client, chat_id, link, bool(video))

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        client = await self.get_tgcalls(chat_id)
        file_path = os.path.abspath(file_path)
        ffmpeg = f"-ss {to_seek} -to {duration}"
        await self._play_stream_safe(client, chat_id, file_path, (mode == "video"), ffmpeg=ffmpeg)

    async def speedup_stream(self, chat_id, file_path, speed, playing):
        client = await self.get_tgcalls(chat_id)
        file_path = os.path.abspath(file_path)
        base = os.path.basename(file_path)
        chatdir = os.path.join(os.getcwd(), "playback", str(speed))
        os.makedirs(chatdir, exist_ok=True)
        out = os.path.join(chatdir, base)

        if not os.path.exists(out):
            vs = str(2.0 / float(speed))
            cmd = f'ffmpeg -i "{file_path}" -filter:v "setpts={vs}*PTS" -filter:a atempo={speed} -y "{out}"'
            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()

        dur = int(await asyncio.get_event_loop().run_in_executor(None, check_duration, out))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        ffmpeg = f"-ss {played} -to {seconds_to_min(dur)}"
        
        if chat_id in db:
            await self._play_stream_safe(client, chat_id, out, (playing[0]["streamtype"] == "video"), ffmpeg=ffmpeg)
            db[chat_id][0].update({"played": con_seconds, "dur": seconds_to_min(dur), "seconds": dur, "speed_path": out, "speed": speed})

    async def stream_call(self, link):
        assistant = await self.get_tgcalls(config.LOGGER_ID)
        try:
            await assistant.play(config.LOGGER_ID, MediaStream(link))
            await asyncio.sleep(8)
        finally:
            try: await assistant.leave_call(config.LOGGER_ID)
            except: pass

    # =======================================================================
    # 🧩 4. UPDATED DECORATORS (v2.x Syntax)
    # =======================================================================
    async def decorators(self):
        assistants = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))

        async def unified_update_handler(client, update: Update):
            # التأكد من أن التحديث يخص شات معين
            if not getattr(update, "chat_id", None):
                return
            
            chat_id = update.chat_id

            # التعامل مع انتهاء الأغنية
            if isinstance(update, StreamEnded):
                # يمكنك هنا إضافة فلتر إذا أردت تجاهل بعض الحالات
                # مثلاً تجاهل الفيديو إذا كنت مهتماً بالصوت فقط
                try: 
                    await self.change_stream(client, chat_id)
                except Exception as e: 
                    LOGGER(__name__).error(f"Error handling StreamEnded for {chat_id}: {e}")

            # التعامل مع تحديثات المكالمة (الخروج، الطرد، الإغلاق)
            elif isinstance(update, ChatUpdate):
                status = update.status
                # إذا خرج المساعد أو انغلقت المكالمة
                if (status == ChatUpdate.Status.LEFT_CALL) or \
                   (status == ChatUpdate.Status.KICKED) or \
                   (status == ChatUpdate.Status.CLOSED_VOICE_CHAT):
                    await self.stop_stream(chat_id)

        # ربط الـ Handler الموحد بكل المساعدين
        for assistant in assistants:
            try:
                if hasattr(assistant, 'on_update'):
                    assistant.on_update()(unified_update_handler)
            except Exception as e:
                LOGGER(__name__).error(f"Failed to attach decorators: {e}")

Hotty = Call()
