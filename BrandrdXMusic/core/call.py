import asyncio
import os
import gc
from datetime import datetime, timedelta
from typing import Union, Dict, List

from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired, UserAlreadyParticipant
from pyrogram.types import InlineKeyboardMarkup

# ============================================================
# ✅ PY-TGCALLS 2.2.8 COMPATIBLE IMPORTS
# ============================================================
from pytgcalls import PyTgCalls
from pytgcalls.types import (
    MediaStream,
    AudioQuality,
    VideoQuality,
    StreamEnded,
    ChatUpdate,
    Update,
)
from pytgcalls.exceptions import (
    NoActiveGroupCall,
    NoAudioSourceFound,
    NoVideoSourceFound
)

# Safe Imports Logic
try:
    from pytgcalls.exceptions import TelegramServerError, ConnectionNotFound
except ImportError:
    try:
        from ntgcalls import TelegramServerError, ConnectionNotFound
    except ImportError:
        TelegramServerError = Exception
        ConnectionNotFound = Exception

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
# ⚙️ DYNAMIC FFMPEG ENGINE (Titan Config)
# =======================================================================

def get_ffmpeg_flags(is_live: bool) -> str:
    # إعدادات قوية جداً لضمان عدم التقطيع
    base = (
        "-re -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
        "-reconnect_on_network_error 1 "
        "-bg 0 "
        "-max_muxing_queue_size 4096 "
        "-headers 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)' "
    )
    if is_live:
        return base + "-tune zerolatency -preset ultrafast -bufsize 512k -ar 48000 -ac 2 -f s16le"
    else:
        return base + "-preset veryfast -bufsize 8192k -ar 48000 -ac 2 -f s16le"

def build_stream(path: str, video: bool = False, live: bool = False, ffmpeg: str = None) -> MediaStream:
    custom_ffmpeg = ffmpeg if ffmpeg else get_ffmpeg_flags(live)
    
    if video:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.STUDIO,
            video_parameters=VideoQuality.HD_720p,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.REQUIRED,
            ffmpeg_parameters=custom_ffmpeg,
        )
    else:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.STUDIO,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.IGNORE,
            ffmpeg_parameters=custom_ffmpeg,
        )

# =======================================================================
# 🧹 SMART CLEANER
# =======================================================================
async def _aggressive_clean_(chat_id: int):
    try:
        popped = db.pop(chat_id, None)
        if popped:
            await auto_clean(popped)
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await set_loop(chat_id, 0)
    except:
        pass
    finally:
        gc.collect()

# =======================================================================
# 💎 THE TITAN ENGINE (Fixed for 2.2.8)
# =======================================================================

class Call:
    def __init__(self):
        self.active_calls = set()
        self.action_locks: Dict[int, asyncio.Lock] = {}
        self.init_lock = asyncio.Lock()
        
        self.clients = []
        self.pytgcalls_map = {}
        self._initialize_assistants()

    def _initialize_assistants(self):
        configs = [config.STRING1, config.STRING2, config.STRING3, config.STRING4, config.STRING5]
        for index, string in enumerate(configs, 1):
            if string:
                ub = Client(f"Assistant{index}", config.API_ID, config.API_HASH, session_string=string)
                pc = PyTgCalls(ub, cache_duration=100)
                self.clients.append(pc)
                setattr(self, f"userbot{index}", ub)
                setattr(self, f"one" if index==1 else f"two" if index==2 else f"three" if index==3 else f"four" if index==4 else "five", pc)

        for pc in self.clients:
            # Map based on userbot ID (Compatible way)
            # We wait for start to map correctly, or map lazily
            pass

    async def get_lock(self, chat_id: int) -> asyncio.Lock:
        async with self.init_lock:
            if chat_id not in self.action_locks:
                self.action_locks[chat_id] = asyncio.Lock()
            return self.action_locks[chat_id]

    async def get_tgcalls(self, chat_id: int) -> PyTgCalls:
        assistant = await group_assistant(self, chat_id)
        for client in self.clients:
            if hasattr(client, 'app') and client.app.me.id == assistant.me.id:
                return client
        return self.clients[0]

    async def start(self):
        LOGGER(__name__).info("🚀 Titan Engine v5.0 (Fixed) Starting...")
        await asyncio.gather(*[c.start() for c in self.clients])
        
        # Build map after start
        for pc in self.clients:
            if hasattr(pc, 'app'):
                self.pytgcalls_map[id(pc.app)] = pc
                
        await self.decorators()
        LOGGER(__name__).info("✅ Engine Online.")

    async def join_call(self, chat_id: int, original_chat_id: int, link: str, video: bool = False, image: str = None):
        client = await self.get_tgcalls(chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)
        
        is_live = "m3u8" in link or "live" in link
        stream = build_stream(link, video, is_live)
        
        async with await self.get_lock(chat_id):
            try:
                await client.play(chat_id, stream)
                await asyncio.sleep(1.5)
            except (NoActiveGroupCall, ChatAdminRequired):
                raise AssistantErr(_["call_8"])
            except (NoAudioSourceFound, NoVideoSourceFound, ConnectionNotFound):
                # Fallback Logic can be added here, but for join we report error
                raise AssistantErr(_["call_11"])
            except Exception as e:
                LOGGER(__name__).error(f"Join Error: {e}")
                raise AssistantErr(f"Error: {e}")

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
        async with await self.get_lock(chat_id):
            check = db.get(chat_id)
            if not check:
                return await self.stop_stream_internal(chat_id, client)

            loop = await get_loop(chat_id)
            try:
                if loop == 0:
                    popped = check.pop(0)
                else:
                    loop -= 1
                    await set_loop(chat_id, loop)
                
                if popped: await auto_clean(popped)
                if not check:
                    return await self.stop_stream_internal(chat_id, client)
            except:
                return await self.stop_stream_internal(chat_id, client)

            # Data Setup
            track = check[0]
            queued_file = track["file"]
            vidid = track["vidid"]
            title = track["title"]
            user = track["by"]
            streamtype = track["streamtype"]
            original_chat_id = track["chat_id"]
            is_video = (str(streamtype) == "video")
            lang = await get_lang(chat_id)
            _ = get_string(lang)

            # 🧠 SMART HANDOVER LOGIC
            final_path = queued_file
            is_live = False

            if "live_" in queued_file:
                n, link = await YouTube.video(vidid, True)
                if n == 0: 
                    await app.send_message(original_chat_id, _["call_6"])
                    return # Will trigger next
                final_path = link
                is_live = True
            elif "vid_" in queued_file or os.path.exists(queued_file):
                if not os.path.exists(queued_file):
                    # Auto-Redownload
                    msg = await app.send_message(original_chat_id, _["call_7"])
                    try:
                        final_path, _ = await YouTube.download(vidid, msg, videoid=True, video=is_video)
                        await msg.delete()
                    except:
                        await app.send_message(original_chat_id, _["call_6"])
                        return 

            stream = build_stream(final_path, is_video, is_live)
            
            try:
                await client.play(chat_id, stream)
            except Exception as e:
                # 🛑 FAILSAFE DOWNLOAD
                LOGGER(__name__).warning(f"Playback failed ({e}), forcing download...")
                try:
                    dl_msg = await app.send_message(original_chat_id, _["call_7"])
                    new_path, _ = await YouTube.download(vidid, dl_msg, videoid=True, video=is_video)
                    await dl_msg.delete()
                    check[0]["file"] = new_path # Update DB
                    stream = build_stream(new_path, is_video, False)
                    await client.play(chat_id, stream)
                except:
                    await app.send_message(original_chat_id, _["call_6"])
                    return await self.stop_stream_internal(chat_id, client)

            # Send UI
            asyncio.create_task(self.send_ui(chat_id, original_chat_id, vidid, title, user, track["dur"], streamtype, is_live, _))

    async def send_ui(self, chat_id, original_chat_id, vidid, title, user, duration, streamtype, is_live, _):
        try:
            def get_btn(vid_id):
                if stream_markup2: return stream_markup2(_, chat_id)
                return stream_markup(_, vid_id, chat_id)

            msg_stream1 = _["stream_1"]
            img = await get_thumb(vidid)
            caption = ""
            markup = None
            
            if vidid == "telegram":
                 img = config.TELEGRAM_AUDIO_URL if str(streamtype) == "audio" else config.TELEGRAM_VIDEO_URL
                 caption = msg_stream1.format(title[:23], duration, user, config.SUPPORT_CHAT)
                 markup = InlineKeyboardMarkup(get_btn("telegram"))
            elif vidid == "soundcloud":
                 img = config.SOUNCLOUD_IMG_URL
                 caption = msg_stream1.format(title[:23], duration, user, config.SUPPORT_CHAT)
                 markup = InlineKeyboardMarkup(get_btn("soundcloud"))
            else:
                 caption = msg_stream1.format(title[:23], duration, user, f"https://t.me/{app.username}?start=info_{vidid}")
                 markup = InlineKeyboardMarkup(get_btn(vidid) if is_live else stream_markup(_, vidid, chat_id))

            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                caption=caption,
                reply_markup=markup
            )
            if chat_id in db:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
        except: pass

    async def stop_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        await self.stop_stream_internal(chat_id, client)

    async def stop_stream_internal(self, chat_id: int, client):
        await _aggressive_clean_(chat_id)
        if chat_id in self.active_calls:
            try: await client.leave_call(chat_id)
            except: pass
            self.active_calls.discard(chat_id)

    async def force_stop_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        try:
            check = db.get(chat_id)
            if check: check.pop(0)
        except: pass
        await self.stop_stream_internal(chat_id, client)

    # Standard Commands
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

    async def skip_stream(self, chat_id, link, video=None, image=None):
        client = await self.get_tgcalls(chat_id)
        stream = build_stream(link, video=bool(video))
        await client.play(chat_id, stream)

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        client = await self.get_tgcalls(chat_id)
        ffmpeg = f"-ss {to_seek} -to {duration}"
        stream = build_stream(file_path, video=(mode == "video"), ffmpeg=ffmpeg)
        await client.play(chat_id, stream)

    async def speedup_stream(self, chat_id, file_path, speed, playing):
        client = await self.get_tgcalls(chat_id)
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
        stream = build_stream(out, video=(playing[0]["streamtype"] == "video"), ffmpeg=ffmpeg)

        if chat_id in db:
            await client.play(chat_id, stream)
            db[chat_id][0].update({"played": con_seconds, "dur": seconds_to_min(dur), "seconds": dur, "speed_path": out, "speed": speed})

    async def stream_call(self, link):
        assistant = await self.get_tgcalls(config.LOGGER_ID)
        try:
            await assistant.play(config.LOGGER_ID, MediaStream(link))
            await asyncio.sleep(8)
        finally:
            try: await assistant.leave_call(config.LOGGER_ID)
            except: pass

    async def decorators(self):
        async def unified_handler(client, update: Update):
            chat_id = getattr(update, "chat_id", None)
            if not chat_id: return

            if isinstance(update, StreamEnded):
                # Trigger Next using task
                asyncio.create_task(self.change_stream(client, chat_id))
            
            elif isinstance(update, ChatUpdate):
                if update.status in [ChatUpdate.Status.LEFT_CALL, ChatUpdate.Status.KICKED, ChatUpdate.Status.CLOSED_VOICE_CHAT]:
                    await _aggressive_clean_(chat_id)
                    if chat_id in self.active_calls:
                        self.active_calls.discard(chat_id)

        for assistant in self.clients:
            try:
                if hasattr(assistant, 'on_update'):
                    assistant.on_update()(unified_handler)
            except: pass

Hotty = Call()
