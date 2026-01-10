import asyncio
import os
import time
import importlib
from datetime import datetime, timedelta
from typing import Union, Dict

from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired, UserAlreadyParticipant
from pyrogram.types import InlineKeyboardMarkup

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality, StreamEnded, ChatUpdate, Update
from pytgcalls.exceptions import (
    NoActiveGroupCall,
    NoAudioSourceFound,
    NoVideoSourceFound
)

# =======================================================================
# 🔧 HANDLING LIBRARY ERRORS (Patching)
# تصحيح أخطاء المكتبة الداخلية لمنع الـ AttributeError
# =======================================================================
try:
    # محاولة استيراد الاستثناءات حسب إصدار المكتبة
    from pytgcalls.exceptions import TelegramServerError, ConnectionNotFound, NotInCallError
except ImportError:
    try:
        from ntgcalls import TelegramServerError, ConnectionNotFound, NotInCallError
    except:
        TelegramServerError = Exception
        ConnectionNotFound = Exception
        NotInCallError = Exception

# تطبيق الحماية الإجبارية لمنع توقف البوت بسبب تحديثات بايثون
try:
    pyrogram_client_module = importlib.import_module("pytgcalls.mtproto.pyrogram_client")
    TargetClient = pyrogram_client_module.PyrogramClient
    original_on_update = TargetClient.on_update

    async def patched_on_update(self, client, update):
        # إذا التحديث مفيهوش chat_id، نتجاهله فوراً بدلاً من الانهيار
        if not hasattr(update, 'chat_id'):
            return
        try:
            await original_on_update(self, client, update)
        except AttributeError:
            # صيد الخطأ المحدد في اللوج
            pass
        except Exception:
            pass

    TargetClient.on_update = patched_on_update
except ImportError:
    pass

# =======================================================================
# 📦 IMPORTS
# =======================================================================
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
    music_off,
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
# 🚀 SMART CACHE SYSTEM
# =======================================================================

class SmartCache:
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.ttl = 3600

    def get(self, video_id: str) -> str:
        self.cleanup()
        if video_id in self.cache:
            entry = self.cache[video_id]
            if time.time() - entry['timestamp'] < self.ttl:
                if os.path.exists(entry['path']):
                    return entry['path']
        return None

    def store(self, video_id: str, path: str):
        self.cache[video_id] = {
            'path': os.path.abspath(path),
            'timestamp': time.time()
        }

    def cleanup(self):
        now = time.time()
        to_remove = []
        for vid, entry in self.cache.items():
            if now - entry['timestamp'] > self.ttl:
                to_remove.append(vid)
        for vid in to_remove:
            del self.cache[vid]

music_cache = SmartCache()

# =======================================================================
# 🔊 STEREO CONFIGURATION
# =======================================================================

REMOTE_FFMPEG = (
    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
    "-ac 2 -ar 48000 "
    "-analyzeduration 15000000 -probesize 100000000 "
    "-dn -sn "
    "-preset veryfast"
)

LOCAL_FFMPEG = (
    "-ac 2 -ar 48000 "
    "-analyzeduration 0 -probesize 32 "
    "-dn -sn "
    "-preset veryfast"
)

def build_stream(path: str, video: bool = False, ffmpeg: str = None, duration: int = 0) -> MediaStream:
    is_url = path.startswith("http")
    base_ffmpeg = REMOTE_FFMPEG if is_url else LOCAL_FFMPEG
    
    final_ffmpeg = f"{base_ffmpeg} {ffmpeg}" if ffmpeg else base_ffmpeg

    if video:
        video_q = VideoQuality.HD_720p if is_url or duration > 600 else VideoQuality.FHD_1080p
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.STUDIO,
            video_parameters=video_q,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.REQUIRED,
            ffmpeg_parameters=final_ffmpeg,
        )
    else:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.STUDIO,
            video_parameters=VideoQuality.HD_720p,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.IGNORE,
            ffmpeg_parameters=final_ffmpeg,
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
# 💎 CORE CLASS
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

    async def start(self):
        LOGGER(__name__).info("🚀 Starting Music Engine (Final Fix)...")
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

    # ===================================================================
    # 🛠️ Safe Control Methods (Protected against NotInCallError)
    # ===================================================================

    async def pause_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        try:
            await client.pause(chat_id)
        except (NotInCallError, NoActiveGroupCall):
            # إذا لم يكن في المكالمة، نعتبرها تم إيقافها بالفعل
            pass
        except Exception as e:
            LOGGER(__name__).error(f"Pause Error: {e}")

    async def resume_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        try:
            await client.resume(chat_id)
        except (NotInCallError, NoActiveGroupCall):
            pass
        except Exception as e:
            LOGGER(__name__).error(f"Resume Error: {e}")

    async def mute_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        try:
            await client.mute(chat_id)
        except (NotInCallError, NoActiveGroupCall):
            pass

    async def unmute_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        try:
            await client.unmute(chat_id)
        except (NotInCallError, NoActiveGroupCall):
            pass

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
        try: _ = get_string(lang)
        except: _ = {}
        
        if not link.startswith("http"):
            link = os.path.abspath(link)

        stream = build_stream(link, video=bool(video))

        try:
            await client.play(chat_id, stream)
            await asyncio.sleep(0.5)

        except (NoActiveGroupCall, ChatAdminRequired):
            raise AssistantErr(_.get("call_8", "قم بفتح المكالمة الصوتية أولاً."))
        except (NoAudioSourceFound, NoVideoSourceFound):
            raise AssistantErr(_.get("call_11", "ملف الصوت غير صالح."))
        except (TelegramServerError, ConnectionNotFound):
            raise AssistantErr(_.get("call_10", "مشكلة في الاتصال بسيرفر تيليجرام."))
        except UserAlreadyParticipant:
            pass
        except Exception as e:
            # تجاهل خطأ TelegramServerError لأنه غالباً كاذب
            if "TelegramServerError" in str(e):
                pass
            else:
                LOGGER(__name__).error(f"Join Call Error: {e}")
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
        try: _ = get_string(lang)
        except: _ = {}
        
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
                if n == 0: return await app.send_message(original_chat_id, text=_.get("call_6", "خطأ في البث"))

                stream = build_stream(link, video, duration=0) 
                await client.play(chat_id, stream)
                
                img = await get_thumb(videoid)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_.get("stream_1", "{0}").format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                    reply_markup=InlineKeyboardMarkup(get_btn(videoid)),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _.get("call_7", "جاري التحميل..."))
                
                file_path = music_cache.get(videoid)
                if not file_path:
                    try: 
                        file_path, direct = await YouTube.download(videoid, mystic, videoid=True, video=video)
                        file_path = os.path.abspath(file_path)
                        music_cache.store(videoid, file_path)
                    except: 
                        return await mystic.edit_text(_.get("call_6", "فشل التحميل"))
                
                stream = build_stream(file_path, video, duration=duration_sec)
                await client.play(chat_id, stream)

                img = await get_thumb(videoid)
                await mystic.delete()
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_.get("stream_1", "{0}").format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                    reply_markup=InlineKeyboardMarkup(stream_markup(_, videoid, chat_id)),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

            elif "index_" in queued:
                stream = build_stream(videoid, video, duration=duration_sec)
                await client.play(chat_id, stream)

                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=_.get("stream_2", "{0}").format(user),
                    reply_markup=InlineKeyboardMarkup(get_btn(videoid)),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            else:
                stream = build_stream(queued, video, duration=duration_sec)
                await client.play(chat_id, stream)

                if videoid == "telegram":
                    img = config.TELEGRAM_AUDIO_URL if str(streamtype) == "audio" else config.TELEGRAM_VIDEO_URL
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=img,
                        caption=_.get("stream_1", "{0}").format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user),
                        reply_markup=InlineKeyboardMarkup(get_btn("telegram")),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                elif videoid == "soundcloud":
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=config.SOUNCLOUD_IMG_URL,
                        caption=_.get("stream_1", "{0}").format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user),
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
                            caption=_.get("stream_1", "{0}").format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                            reply_markup=InlineKeyboardMarkup(stream_markup(_, videoid, chat_id)),
                        )
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_.get("stream_1", "{0}").format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                            reply_markup=InlineKeyboardMarkup(stream_markup(_, videoid, chat_id)),
                        )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
                    
        except Exception as e:
            LOGGER(__name__).error(f"Play Error: {e}")
            try:
                await self.change_stream(client, chat_id)
            except:
                pass

    async def skip_stream(self, chat_id, link, video=None, image=None):
        client = await self.get_tgcalls(chat_id)
        if not link.startswith("http"):
            link = os.path.abspath(link)
        stream = build_stream(link, video=bool(video))
        await client.play(chat_id, stream)

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        client = await self.get_tgcalls(chat_id)
        file_path = os.path.abspath(file_path)
        ffmpeg = f"-ss {to_seek} -to {duration}"
        stream = build_stream(file_path, video=(mode == "video"), ffmpeg=ffmpeg)
        await client.play(chat_id, stream)

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
        try:
            played, con_seconds = speed_converter(playing[0]["played"], speed)
        except:
            played, con_seconds = 0, 0
            
        ffmpeg = f"-ss {played} -to {seconds_to_min(dur)}"
        
        stream = build_stream(out, video=(playing[0]["streamtype"] == "video"), ffmpeg=ffmpeg)

        if chat_id in db:
            db[chat_id][0].update({"played": con_seconds, "dur": seconds_to_min(dur), "seconds": dur, "speed_path": out, "speed": speed})
            await client.play(chat_id, stream)

    async def stream_call(self, link):
        assistant = await self.get_tgcalls(config.LOGGER_ID)
        try:
            await assistant.play(config.LOGGER_ID, MediaStream(link))
            await asyncio.sleep(8)
        finally:
            try: await assistant.leave_call(config.LOGGER_ID)
            except: pass

    async def decorators(self):
        assistants = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))

        async def unified_update_handler(client, update: Update):
            if not getattr(update, "chat_id", None):
                return
            
            chat_id = update.chat_id

            if isinstance(update, StreamEnded):
                try: 
                    await self.change_stream(client, chat_id)
                except Exception: 
                    pass
            
            elif isinstance(update, ChatUpdate):
                status = update.status
                if (status & ChatUpdate.Status.LEFT_CALL) or \
                   (status & ChatUpdate.Status.KICKED) or \
                   (status & ChatUpdate.Status.CLOSED_VOICE_CHAT):
                    await self.stop_stream(chat_id)

        for assistant in assistants:
            try:
                if hasattr(assistant, 'on_update'):
                    assistant.on_update()(unified_update_handler)
                elif hasattr(assistant, 'on_stream_end'):
                    assistant.on_stream_end()(unified_update_handler)
                    assistant.on_chat_update()(unified_update_handler)
            except: pass

Hotty = Call()
