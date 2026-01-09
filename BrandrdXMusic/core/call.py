import asyncio
import os
import gc
import sys
import traceback
from datetime import datetime, timedelta
from typing import Union, List, Dict, Any

from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired, UserAlreadyParticipant
from pyrogram.types import InlineKeyboardMarkup

# ============================================================
# 🛡️ IMPORT SAFETY SYSTEM
# ============================================================
try:
    from pytgcalls import PyTgCalls
    from pytgcalls.types import (
        MediaStream, AudioQuality, VideoQuality,
        StreamEnded, ChatUpdate, Update
    )
    from pytgcalls.exceptions import (
        NoActiveGroupCall, NoAudioSourceFound, NoVideoSourceFound,
        AlreadyJoined
    )
except ImportError as e:
    print(f"CRITICAL ERROR: PyTgCalls not installed correctly! {e}")
    sys.exit(1)

# Fallback for Network Exceptions
try:
    from pytgcalls.exceptions import TelegramServerError, ConnectionNotFound
except ImportError:
    try:
        from ntgcalls import TelegramServerError, ConnectionNotFound
    except:
        TelegramServerError = Exception
        ConnectionNotFound = Exception

import config
from strings import get_string
from BrandrdXMusic import LOGGER, YouTube, app
from BrandrdXMusic.misc import db
from BrandrdXMusic.utils.database import (
    add_active_chat, add_active_video_chat, get_lang, get_loop,
    group_assistant, is_autoend, music_on, remove_active_chat,
    remove_active_video_chat, set_loop,
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
# 🛠️ UTILS & FFMPEG (ENHANCED VALIDATION)
# =======================================================================

def get_ffmpeg_flags(live: bool = False) -> str:
    """Returns optimized FFMPEG flags."""
    return (
        "-re -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
        "-reconnect_on_network_error 1 "
        "-bg 0 "
        "-max_muxing_queue_size 4096 "
        "-headers 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)' "
        f"{'-tune zerolatency -preset ultrafast' if live else '-preset veryfast'}"
    )

def build_stream(path: str, video: bool = False, live: bool = False) -> MediaStream:
    """Builds a MediaStream object safely with ABSOLUTE PATHS & SIZE CHECK."""
    if not path:
        raise ValueError("Stream Path is Empty!")
    
    # 🌟 FIX: Convert to Absolute Path if it's a local file
    if not path.startswith("http"):
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise ValueError(f"File not found: {path}")
        # 🛡️ PROTECTION: Check if file is corrupt (too small)
        if os.path.getsize(path) < 1024: # Less than 1KB
            raise ValueError(f"File is corrupt/empty: {path}")

    flags = get_ffmpeg_flags(live)
    
    if video:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.STUDIO,
            video_parameters=VideoQuality.HD_720p,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.REQUIRED,
            ffmpeg_parameters=flags,
        )
    return MediaStream(
        media_path=path,
        audio_parameters=AudioQuality.STUDIO,
        audio_flags=MediaStream.Flags.REQUIRED,
        video_flags=MediaStream.Flags.IGNORE,
        ffmpeg_parameters=flags,
    )

async def _safe_clean(chat_id: int):
    """Safely cleans chat data without crashing."""
    try:
        popped = db.pop(chat_id, None)
        if popped: await auto_clean(popped)
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await set_loop(chat_id, 0)
    except Exception as e:
        LOGGER(__name__).warning(f"Cleanup warning for {chat_id}: {e}")
    finally:
        gc.collect()

# =======================================================================
# 🏰 THE FORTRESS ENGINE v3.0 (ARMORED EDITION)
# =======================================================================

class Call:
    def __init__(self):
        self.active_calls = set()
        self.clients = []
        self.pytgcalls_map = {}
        # 🛡️ PROTECTION: Locks to prevent Race Conditions
        self.chat_locks: Dict[int, asyncio.Lock] = {}
        self._init_clients()

    def _init_clients(self):
        configs = [
            (config.STRING1, 1), (config.STRING2, 2), 
            (config.STRING3, 3), (config.STRING4, 4), (config.STRING5, 5)
        ]
        for session, idx in configs:
            if session:
                try:
                    ub = Client(f"Assistant{idx}", config.API_ID, config.API_HASH, session_string=session)
                    pc = PyTgCalls(ub, cache_duration=100)
                    self.clients.append(pc)
                    setattr(self, f"userbot{idx}", ub)
                    # Mapping helper
                    name = ["one", "two", "three", "four", "five"][idx-1]
                    setattr(self, name, pc)
                except Exception as e:
                    LOGGER(__name__).error(f"Failed to initialize Assistant {idx}: {e}")

    async def get_lock(self, chat_id: int):
        if chat_id not in self.chat_locks:
            self.chat_locks[chat_id] = asyncio.Lock()
        return self.chat_locks[chat_id]

    async def run_diagnostics(self):
        LOGGER(__name__).info("🔍 RUNNING SYSTEM DIAGNOSTICS...")
        if not self.clients:
            LOGGER(__name__).error("❌ No Assistant Clients Loaded! Check config.")
        else:
            LOGGER(__name__).info(f"✅ {len(self.clients)} Assistants Loaded.")
            
        # Check Directories & Permissions
        try:
            if not os.path.exists("downloads"):
                os.makedirs("downloads")
            # Test write permissions
            with open("downloads/test.txt", "w") as f: f.write("ok")
            os.remove("downloads/test.txt")
            LOGGER(__name__).info("✅ Downloads Directory: Writable & Ready.")
        except Exception as e:
            LOGGER(__name__).error(f"❌ Downloads Directory Error: {e}")

    async def start(self):
        await self.run_diagnostics()
        LOGGER(__name__).info("🚀 Starting PyTgCalls...")
        if self.clients:
            await asyncio.gather(*[c.start() for c in self.clients])
            for c in self.clients:
                if hasattr(c, 'app'): self.pytgcalls_map[id(c.app)] = c
            await self.decorators()
        LOGGER(__name__).info("✅ Call System Online.")

    async def get_tgcalls(self, chat_id: int) -> PyTgCalls:
        assistant = await group_assistant(self, chat_id)
        for client in self.clients:
            if hasattr(client, 'app') and client.app.me.id == assistant.me.id:
                return client
        return self.clients[0]

    # ================= 🛡️ ROBUST JOIN (ANTI-FLOOD) =================

    async def join_call(self, chat_id: int, original_chat_id: int, link: str, video: bool = False, image: str = None):
        client = await self.get_tgcalls(chat_id)
        
        try:
            is_live = "live" in link or "m3u8" in link
            stream = build_stream(link, video, is_live)
            
            # 🛡️ PROTECTION: FloodWait Handler
            try:
                await client.play(chat_id, stream)
            except AlreadyJoined:
                LOGGER(__name__).info(f"Already in call {chat_id}, restarting stream...")
            except FloodWait as f:
                LOGGER(__name__).warning(f"FloodWait detected! Sleeping {f.value}s")
                await asyncio.sleep(f.value)
                await client.play(chat_id, stream)

            await asyncio.sleep(1) 

            self.active_calls.add(chat_id)
            await add_active_chat(chat_id)
            await music_on(chat_id)
            if video: await add_active_video_chat(chat_id)

            if await is_autoend():
                try:
                    if len(await client.get_participants(chat_id)) <= 1:
                        autoend[chat_id] = datetime.now() + timedelta(minutes=1)
                except: pass

        except NoActiveGroupCall:
            raise AssistantErr("المكالمة الصوتية مغلقة! يرجى فتحها.")
        except (NoAudioSourceFound, NoVideoSourceFound) as e:
            LOGGER(__name__).error(f"Stream failed for {link}: {e}")
            raise AssistantErr("فشل قراءة الملف (Source Error).")
        except Exception as e:
            LOGGER(__name__).error(f"Unknown Join Error: {e}")
            raise AssistantErr(f"خطأ غير متوقع: {e}")

    # ================= 🛡️ ROBUST CHANGE STREAM (LOCKED) =================

    async def change_stream(self, client, chat_id: int):
        # 🛡️ PROTECTION: Use Lock to prevent double-skipping
        lock = await self.get_lock(chat_id)
        async with lock:
            try:
                check = db.get(chat_id)
            except Exception:
                return await self.stop_stream(chat_id)

            if not check:
                return await self.stop_stream(chat_id)

            try:
                loop = await get_loop(chat_id)
                if loop == 0:
                    popped = check.pop(0)
                    if popped: await auto_clean(popped)
                else:
                    loop -= 1
                    await set_loop(chat_id, loop)
                
                if not check:
                    return await self.stop_stream(chat_id)
            except Exception as e:
                LOGGER(__name__).error(f"Queue Error: {e}")
                return await self.stop_stream(chat_id)

            # Data Extraction
            track = check[0]
            queued_file = track.get("file")
            vidid = track.get("vidid")
            title = track.get("title", "Unknown Track")
            user = track.get("by", "Unknown")
            streamtype = track.get("streamtype", "audio")
            original_chat_id = track.get("chat_id", chat_id)
            duration = track.get("dur", "00:00")
            
            if not queued_file or not vidid:
                LOGGER(__name__).warning(f"Corrupt track data in {chat_id}, skipping...")
                # Release lock and recurse (conceptually), but better to just stop/next
                # To avoid recursion depth, we just stop if data bad, or try next via Task
                return await self.stop_stream(chat_id)

            is_video = str(streamtype) == "video"
            is_live = False
            final_path = queued_file

            try:
                if "live_" in queued_file:
                    n, link = await YouTube.video(vidid, True)
                    if n == 0:
                        await app.send_message(original_chat_id, "فشل الحصول على رابط البث.")
                        return # Should try next really
                    final_path = link
                    is_live = True
                
                elif "vid_" in queued_file:
                    # 🌟 ABSOLUTE PATH CHECK + CORRUPTION CHECK
                    abs_path = os.path.abspath(queued_file)
                    file_ok = os.path.exists(abs_path) and os.path.getsize(abs_path) > 1024
                    
                    if not file_ok:
                        LOGGER(__name__).info(f"File missing/bad ({abs_path}), attempting re-download.")
                        msg = await app.send_message(original_chat_id, "🔄 الملف تالف أو مفقود، جاري التحميل...")
                        try:
                            final_path, _ = await YouTube.download(vidid, msg, videoid=True, video=is_video)
                            check[0]["file"] = final_path 
                            await msg.delete()
                        except Exception as e:
                            LOGGER(__name__).error(f"Redownload failed: {e}")
                            await msg.edit("❌ فشل التحميل.")
                            return await self.stop_stream(chat_id)

                # Playback with FloodWait Protection
                stream = build_stream(final_path, is_video, is_live)
                try:
                    await client.play(chat_id, stream)
                except FloodWait as f:
                    LOGGER(__name__).warning(f"FloodWait in ChangeStream: {f.value}s")
                    await asyncio.sleep(f.value)
                    await client.play(chat_id, stream)

            except Exception as e:
                LOGGER(__name__).error(f"Playback failed: {e}. Trying Force Download.")
                try:
                    new_path, _ = await YouTube.download(vidid, None, videoid=True, video=is_video)
                    stream = build_stream(new_path, is_video, False)
                    await client.play(chat_id, stream)
                except:
                    return await self.stop_stream(chat_id)

            # UI Update
            asyncio.create_task(self.safe_send_ui(chat_id, original_chat_id, vidid, title, user, duration, streamtype, is_live))

    async def safe_send_ui(self, chat_id, original_chat_id, vidid, title, user, duration, streamtype, is_live):
        try:
            lang = await get_lang(chat_id)
            _ = get_string(lang)
            
            btn = None
            try:
                if stream_markup2: btn = stream_markup2(_, chat_id)
                else: btn = stream_markup(_, vidid, chat_id)
            except Exception: pass
            
            markup = InlineKeyboardMarkup(btn) if btn else None
            
            try:
                caption = _["stream_1"].format(title[:25], duration, user, config.SUPPORT_CHAT)
            except (KeyError, IndexError):
                caption = f"🎶 **Playing:** {title}\n👤 **By:** {user}"

            img = await get_thumb(vidid)
            
            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                caption=caption,
                reply_markup=markup
            )
            
            if chat_id in db:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

        except Exception as e:
            LOGGER(__name__).error(f"UI Error (Ignored): {e}")

    # ================= STANDARD CONTROLS =================

    async def stop_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        await _safe_clean(chat_id)
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
        await self.stop_stream(chat_id)

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
        # 🛡️ PROTECTION: Validate file exists before seek
        if not os.path.exists(file_path):
             return # Fail silently or log
        
        if mode == "video":
             stream = MediaStream(file_path, audio_parameters=AudioQuality.STUDIO, video_parameters=VideoQuality.HD_720p, ffmpeg_parameters=ffmpeg)
        else:
             stream = MediaStream(file_path, audio_parameters=AudioQuality.STUDIO, video_flags=MediaStream.Flags.IGNORE, ffmpeg_parameters=ffmpeg)
        await client.play(chat_id, stream)

    async def speedup_stream(self, chat_id, file_path, speed, playing):
        client = await self.get_tgcalls(chat_id)
        try:
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
            is_video = playing[0]["streamtype"] == "video"
            
            if is_video:
                stream = MediaStream(out, audio_parameters=AudioQuality.STUDIO, video_parameters=VideoQuality.HD_720p, ffmpeg_parameters=ffmpeg)
            else:
                stream = MediaStream(out, audio_parameters=AudioQuality.STUDIO, video_flags=MediaStream.Flags.IGNORE, ffmpeg_parameters=ffmpeg)

            if chat_id in db:
                await client.play(chat_id, stream)
                db[chat_id][0].update({"played": con_seconds, "dur": seconds_to_min(dur), "seconds": dur, "speed_path": out, "speed": speed})
        except Exception as e:
             LOGGER(__name__).error(f"Speedup Error: {e}")

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
            if not getattr(update, "chat_id", None): return
            chat_id = update.chat_id

            if isinstance(update, StreamEnded):
                if update.stream_type == StreamEnded.Type.AUDIO:
                    asyncio.create_task(self.change_stream(client, chat_id))
            
            elif isinstance(update, ChatUpdate):
                if update.status in [ChatUpdate.Status.LEFT_CALL, ChatUpdate.Status.KICKED, ChatUpdate.Status.CLOSED_VOICE_CHAT]:
                    await self.stop_stream(chat_id)

        for c in self.clients:
            if hasattr(c, 'on_update'): c.on_update()(unified_handler)

Hotty = Call()
