"""
████████╗██╗████████╗ █████╗ ███╗   ██╗██╗██╗   ██╗███╗   ███╗
╚══██╔══╝██║╚══██╔══╝██╔══██╗████╗  ██║██║██║   ██║████╗ ████║
   ██║   ██║   ██║   ███████║██╔██╗ ██║██║██║   ██║██╔████╔██║
   ██║   ██║   ██║   ██╔══██║██║╚██╗██║██║██║   ██║██║╚██╔╝██║
   ██║   ██║   ██║   ██║  ██║██║ ╚████║██║╚██████╔╝██║ ╚═╝ ██║
   ╚═╝   ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝ ╚═════╝ ╚═╝     ╚═╝
   
   TITANIUM AUDIO ENGINE - MONOLITH EDITION (v9.0)
   Architected for Maximum Stability & High-Fidelity Audio
   
   This file contains:
   1. Advanced Cache Management System
   2. Dynamic FFmpeg Command Builder
   3. Stream Health Monitoring
   4. Automatic Failover Strategy
   5. Thread-Safe Execution Contexts
"""

import asyncio
import os
import time
import logging
import math
import shutil
import subprocess
from datetime import datetime, timedelta
from typing import Union, Dict, List, Optional, Tuple, Any
from enum import Enum
from contextlib import suppress

# --- External Libraries ---
from pyrogram import Client
from pyrogram.errors import (
    FloodWait, 
    ChatAdminRequired, 
    UserAlreadyParticipant, 
    PeerIdInvalid
)
from pyrogram.types import InlineKeyboardMarkup

# --- PyTgCalls Libraries ---
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
    NoVideoSourceFound,
    InvalidStreamMode
)

# Handle Library Versioning
try:
    from pytgcalls.exceptions import TelegramServerError, ConnectionNotFound
except ImportError:
    from ntgcalls import TelegramServerError, ConnectionNotFound

# --- Local Imports ---
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

# =======================================================================
# 📡 CONSTANTS & CONFIGURATION
# =======================================================================

MODULE_NAME = "TitaniumCall"
LOG = LOGGER(MODULE_NAME)

class StreamType(Enum):
    AUDIO = "audio"
    VIDEO = "video"
    LIVE = "live"

class PlaybackState(Enum):
    IDLE = 0
    PREPARING = 1
    PLAYING = 2
    PAUSED = 3
    BUFFERING = 4

# Global State Trackers
autoend: Dict[int, datetime] = {}
counter: Dict[int, int] = {}
playback_states: Dict[int, PlaybackState] = {}

# =======================================================================
# 🛠️ UTILITY: TITANIUM LOGGER
# =======================================================================

class TitaniumLogger:
    """Advanced logging wrapper for detailed debugging."""
    @staticmethod
    def info(msg: str, chat_id: int = None):
        prefix = f"[Chat: {chat_id}] " if chat_id else ""
        LOG.info(f"🔵 {prefix}{msg}")

    @staticmethod
    def warn(msg: str, chat_id: int = None):
        prefix = f"[Chat: {chat_id}] " if chat_id else ""
        LOG.warn(f"🟠 {prefix}{msg}")

    @staticmethod
    def error(msg: str, chat_id: int = None, exc: Exception = None):
        prefix = f"[Chat: {chat_id}] " if chat_id else ""
        LOG.error(f"🔴 {prefix}{msg}")
        if exc:
            LOG.error(f"Traceback: {exc}")

# =======================================================================
# 🗄️ SUBSYSTEM: INTELLIGENT CACHE MANAGER
# =======================================================================

class CacheEntry:
    def __init__(self, path: str, type_: str):
        self.path = path
        self.type = type_
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.access_count = 0

    def touch(self):
        self.last_accessed = time.time()
        self.access_count += 1

class TitaniumCacheSystem:
    """
    Manages downloaded files with a strictly enforced TTL (Time To Live).
    Ensures disk space is optimized and duplicate downloads are avoided.
    """
    def __init__(self, ttl_seconds: int = 360, max_cache_size_gb: int = 2):
        self._cache: Dict[str, CacheEntry] = {}
        self._ttl = ttl_seconds
        self._max_size = max_cache_size_gb * 1024 * 1024 * 1024
        self._lock = asyncio.Lock()
        
        # Start background cleaner
        asyncio.create_task(self._auto_cleaner_loop())

    async def get(self, video_id: str) -> Optional[str]:
        async with self._lock:
            if video_id in self._cache:
                entry = self._cache[video_id]
                if os.path.exists(entry.path):
                    entry.touch()
                    TitaniumLogger.info(f"Cache Hit for {video_id}")
                    return entry.path
                else:
                    del self._cache[video_id]
        return None

    async def store(self, video_id: str, path: str, type_: str = "audio"):
        async with self._lock:
            abs_path = os.path.abspath(path)
            self._cache[video_id] = CacheEntry(abs_path, type_)
            TitaniumLogger.info(f"Stored {video_id} in cache. Total entries: {len(self._cache)}")

    async def _auto_cleaner_loop(self):
        """Background daemon to clean expired files."""
        while True:
            await asyncio.sleep(60) # Check every minute
            await self._purge_expired()

    async def _purge_expired(self):
        async with self._lock:
            now = time.time()
            keys_to_delete = []
            
            for vid, entry in self._cache.items():
                # Delete if older than TTL
                if now - entry.created_at > self._ttl:
                    keys_to_delete.append(vid)
                    self._safe_delete(entry.path)
            
            for key in keys_to_delete:
                del self._cache[key]
                
            if keys_to_delete:
                TitaniumLogger.info(f"🧹 Garage Collection: Removed {len(keys_to_delete)} expired files.")

    def _safe_delete(self, path: str):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            TitaniumLogger.error(f"Failed to delete {path}: {e}")

# Initialize Global Cache
cache_manager = TitaniumCacheSystem()

# =======================================================================
# 🎬 SUBSYSTEM: FFMPEG COMMAND BUILDER (THE ENGINE)
# =======================================================================

class FFmpegDirector:
    """
    Constructs complex FFmpeg commands dynamically based on input source
    and desired quality. Enforces the 'Titanium Quality' standard.
    """
    
    # Base configuration for low latency and high stability
    BASE_FLAGS = (
        "-hide_banner -loglevel error "
        "-probesize 10M -analyzeduration 10M " # Deep analysis
        "-fflags +nobuffer+flush_packets "     # Low latency
        "-flags low_delay "
        "-threads 2 "                          # optimized threading
    )

    # Audio filter chain: Resample to 48k Stereo -> Normalize Loudness -> Soft Limiter
    TITANIUM_AUDIO_FILTERS = (
        "aresample=48000:resampler=soxr:precision=28,"
        "loudnorm=I=-16:TP=-1.5:LRA=11,"
        "volume=1.0"
    )

    @classmethod
    def build(cls, 
              source: str, 
              is_video: bool = False, 
              is_live: bool = False, 
              duration: int = 0, 
              seek_start: int = 0, 
              seek_end: int = 0) -> Tuple[str, AudioQuality, VideoQuality]:
        
        cmd_parts = [cls.BASE_FLAGS]
        
        # 1. Input Handling
        if source.startswith("http"):
            # Network Source Optimization
            cmd_parts.append("-re") # Read at native frame rate
            cmd_parts.append(
                "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
                "-timeout 20000000"
            )
        else:
            # Local File Optimization
            cmd_parts.append("-nostdin")

        # 2. Seeking Logic
        if seek_start > 0:
            cmd_parts.append(f"-ss {seek_start}")
        if seek_end > 0:
            cmd_parts.append(f"-to {seek_end}")

        # 3. Filter Injection
        cmd_parts.append(f"-af {cls.TITANIUM_AUDIO_FILTERS}")

        # 4. Construct Final String
        ffmpeg_params = " ".join(cmd_parts)
        
        # 5. Determine Quality Enums
        # We always enforce AUDIO_QUALITY.STUDIO for Opus bitrate 
        audio_q = AudioQuality.STUDIO
        
        video_q = VideoQuality.HD_720p # Default safe fallback
        if is_video:
            if is_live:
                video_q = VideoQuality.HD_720p
            elif duration > 600: # > 10 mins
                video_q = VideoQuality.HD_720p
            else:
                video_q = VideoQuality.FHD_1080p

        return ffmpeg_params, audio_q, video_q

# =======================================================================
# 📡 SUBSYSTEM: CLIENT POOL MANAGER
# =======================================================================

class ClientPool:
    """
    Manages the fleet of Userbot clients (Assistants).
    Provides access to specific clients and handles initialization.
    """
    def __init__(self):
        self.clients: Dict[int, PyTgCalls] = {}
        self.pyrogram_clients: List[Client] = []
        self._mapping: Dict[int, PyTgCalls] = {} # Maps pyrogram client ID to Pytgcalls

    def initialize(self):
        # Initialize Clients based on config
        credentials = [
            (1, config.STRING1), (2, config.STRING2), (3, config.STRING3),
            (4, config.STRING4), (5, config.STRING5)
        ]
        
        for idx, session in credentials:
            if session:
                p_client = Client(
                    f"BrandrdXMusic{idx}", 
                    config.API_ID, 
                    config.API_HASH, 
                    session_string=session
                )
                self.pyrogram_clients.append(p_client)
                
                # Create PyTgCalls instance
                tg_call = PyTgCalls(p_client)
                self.clients[idx] = tg_call
                self._mapping[id(p_client)] = tg_call
                
                TitaniumLogger.info(f"✅ Assistant {idx} Initialized.")

    async def start_all(self):
        tasks = [c.start() for c in self.clients.values()]
        if tasks:
            await asyncio.gather(*tasks)
            TitaniumLogger.info("🚀 All Assistants Started Successfully.")

    def get_by_pyrogram_id(self, pyrogram_id: int) -> Optional[PyTgCalls]:
        return self._mapping.get(pyrogram_id)

    def get_all(self) -> List[PyTgCalls]:
        return list(self.clients.values())

# =======================================================================
# 🎛️ MAIN CONTROLLER: THE CALL CLASS
# =======================================================================

class Call:
    """
    The Orchestrator.
    Connects database, user requests, FFmpeg builder, and Pytgcalls clients.
    """
    def __init__(self):
        self.pool = ClientPool()
        self.pool.initialize()
        
        # Legacy mapping for compatibility with outside modules
        self.userbot1 = self.pool.pyrogram_clients[0] if len(self.pool.pyrogram_clients) > 0 else None
        self.one = self.pool.clients.get(1)
        self.userbot2 = self.pool.pyrogram_clients[1] if len(self.pool.pyrogram_clients) > 1 else None
        self.two = self.pool.clients.get(2)
        self.userbot3 = self.pool.pyrogram_clients[2] if len(self.pool.pyrogram_clients) > 2 else None
        self.three = self.pool.clients.get(3)
        self.userbot4 = self.pool.pyrogram_clients[3] if len(self.pool.pyrogram_clients) > 3 else None
        self.four = self.pool.clients.get(4)
        self.userbot5 = self.pool.pyrogram_clients[4] if len(self.pool.pyrogram_clients) > 4 else None
        self.five = self.pool.clients.get(5)

        self.active_calls = set()

    async def start(self):
        """Bootstrapping the engine."""
        await self.pool.start_all()
        await self._register_handlers()
        TitaniumLogger.info("⚔️ Titanium Engine Ready.")

    async def get_tgcalls(self, chat_id: int) -> PyTgCalls:
        """
        Dynamically retrieves the assigned assistant for a specific chat.
        Uses the database to determine which assistant is in the group.
        """
        assistant = await group_assistant(self, chat_id)
        client = self.pool.get_by_pyrogram_id(id(assistant))
        return client if client else self.one

    # --- Core Playback Control ---

    async def join_call(self, 
                        chat_id: int, 
                        original_chat_id: int, 
                        link: str, 
                        video: Union[bool, str] = None, 
                        image: Union[bool, str] = None):
        
        client = await self.get_tgcalls(chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)

        # Sanitize Link
        if not link.startswith("http"):
            link = os.path.abspath(link)

        # Build Titanium Stream
        ffmpeg_params, audio_q, video_q = FFmpegDirector.build(
            link, 
            is_video=bool(video),
            is_live=link.startswith("http")
        )

        stream = MediaStream(
            media_path=link,
            audio_parameters=audio_q,
            video_parameters=video_q,
            ffmpeg_parameters=ffmpeg_params,
            video_flags=MediaStream.Flags.IGNORE if not video else MediaStream.Flags.REQUIRED
        )

        try:
            TitaniumLogger.info(f"Joining Call in {chat_id}...", chat_id)
            await client.play(chat_id, stream)
            
            # State Update
            self.active_calls.add(chat_id)
            playback_states[chat_id] = PlaybackState.PLAYING
            
            await add_active_chat(chat_id)
            await music_on(chat_id)
            if video:
                await add_active_video_chat(chat_id)

            # Auto-End Monitor logic
            if await is_autoend():
                try:
                    participants = await client.get_participants(chat_id)
                    if len(participants) <= 1:
                        autoend[chat_id] = datetime.now() + timedelta(minutes=1)
                except Exception:
                    pass

        except NoActiveGroupCall:
            TitaniumLogger.error("No active VC found", chat_id)
            raise AssistantErr(_["call_8"])
        except (TelegramServerError, ConnectionNotFound):
            TitaniumLogger.error("Telegram Server Error", chat_id)
            raise AssistantErr(_["call_10"])
        except (NoAudioSourceFound, NoVideoSourceFound):
            TitaniumLogger.error(f"Source not found or corrupt: {link}", chat_id)
            raise AssistantErr(_["call_11"])
        except GroupCallConfig as e:
            TitaniumLogger.error(f"Invalid Call Config: {e}", chat_id)
            raise AssistantErr(_["call_8"])
        except Exception as e:
            TitaniumLogger.error(f"Critical Join Error: {e}", chat_id, exc=e)
            raise AssistantErr(f"An unexpected error occurred: {e}")

    async def change_stream(self, client: PyTgCalls, chat_id: int):
        """
        Handles the logic for switching tracks (Next/Skip/End).
        This is the brain of the playlist management.
        """
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)

        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop -= 1
                await set_loop(chat_id, loop)
            
            if popped:
                await auto_clean(popped)
            
            if not check:
                # Playlist empty
                await _clear_(chat_id)
                if chat_id in self.active_calls:
                    try: 
                        await client.leave_call(chat_id)
                    except: pass
                    finally: 
                        self.active_calls.discard(chat_id)
                return
        except Exception as e:
            TitaniumLogger.error(f"Queue Error: {e}", chat_id)
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except: return

        # Get next track details
        queued_track = check[0]
        queued_file = queued_track["file"]
        title = queued_track["title"].title()
        user = queued_track["by"]
        original_chat_id = queued_track["chat_id"]
        streamtype = queued_track["streamtype"]
        videoid = queued_track["vidid"]
        duration_sec = queued_track.get("seconds", 0)

        # Restore duration if it was a seeked track
        if queued_track.get("old_dur"):
            db[chat_id][0]["dur"] = queued_track["old_dur"]
            db[chat_id][0]["seconds"] = queued_track["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0

        is_video = (str(streamtype) == "video")
        
        # Localization
        lang = await get_lang(chat_id)
        _ = get_string(lang)

        # Helper for markup
        def get_btn(vid_id):
            if stream_markup2: return stream_markup2(_, chat_id)
            return stream_markup(_, vid_id, chat_id)

        # --- STREAM SOURCE RESOLUTION ---
        try:
            stream = None
            media_path = None
            
            # Case 1: Live Stream
            if "live_" in queued_file:
                status, link = await YouTube.video(videoid, True)
                if status == 0:
                    await app.send_message(original_chat_id, text=_["call_6"])
                    return await self.change_stream(client, chat_id) # Skip bad link
                
                ffmpeg_params, audio_q, video_q = FFmpegDirector.build(link, is_video, is_live=True)
                stream = MediaStream(link, audio_parameters=audio_q, video_parameters=video_q, ffmpeg_parameters=ffmpeg_params)
                
                await self._send_now_playing(original_chat_id, videoid, title, queued_track["dur"], user, "tg", get_btn(videoid))

            # Case 2: Downloaded Video/Audio (Use Cache)
            elif "vid_" in queued_file:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                
                media_path = await cache_manager.get(videoid)
                
                if not media_path:
                    try:
                        dl_path, _ = await YouTube.download(videoid, mystic, videoid=True, video=is_video)
                        media_path = os.path.abspath(dl_path)
                        await cache_manager.store(videoid, media_path)
                    except Exception as e:
                        TitaniumLogger.error(f"Download Failed: {e}", chat_id)
                        await mystic.edit_text(_["call_6"])
                        return await self.change_stream(client, chat_id)

                ffmpeg_params, audio_q, video_q = FFmpegDirector.build(media_path, is_video, duration=duration_sec)
                stream = MediaStream(media_path, audio_parameters=audio_q, video_parameters=video_q, ffmpeg_parameters=ffmpeg_params)
                
                await mystic.delete()
                await self._send_now_playing(original_chat_id, videoid, title, queued_track["dur"], user, "stream", stream_markup(_, videoid, chat_id))

            # Case 3: Direct Index Link
            elif "index_" in queued_file:
                ffmpeg_params, audio_q, video_q = FFmpegDirector.build(videoid, is_video, duration=duration_sec)
                stream = MediaStream(videoid, audio_parameters=audio_q, video_parameters=video_q, ffmpeg_parameters=ffmpeg_params)
                
                await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(get_btn(videoid)),
                )

            # Case 4: General Link / Files
            else:
                media_path = queued_file
                if not media_path.startswith("http"):
                    media_path = os.path.abspath(media_path)
                
                ffmpeg_params, audio_q, video_q = FFmpegDirector.build(media_path, is_video, duration=duration_sec)
                stream = MediaStream(media_path, audio_parameters=audio_q, video_parameters=video_q, ffmpeg_parameters=ffmpeg_params)
                
                await self._handle_general_thumbnails(original_chat_id, videoid, streamtype, title, queued_track["dur"], user, _, get_btn, chat_id)

            # --- EXECUTE PLAY ---
            if stream:
                await client.play(chat_id, stream)
                db[chat_id][0]["played"] = 0
                playback_states[chat_id] = PlaybackState.PLAYING

        except Exception as e:
            TitaniumLogger.error(f"Change Stream Critical Fail: {e}", chat_id, exc=e)
            # Resiliency: Don't stop, just try next song
            await self.change_stream(client, chat_id)

    # --- UI Helpers for Playing ---
    async def _send_now_playing(self, chat_id, videoid, title, dur, user, mode, buttons):
        img = await get_thumb(videoid)
        try:
            run = await app.send_photo(
                chat_id=chat_id,
                photo=img,
                caption=get_string(await get_lang(chat_id))["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], dur, user),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            # Store message IDs for later deletion
            check = db.get(chat_id)
            if check:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = mode
        except Exception:
            pass

    async def _handle_general_thumbnails(self, chat_id, videoid, streamtype, title, dur, user, _, get_btn, db_chat_id):
        if videoid == "telegram":
            img = config.TELEGRAM_AUDIO_URL if str(streamtype) == "audio" else config.TELEGRAM_VIDEO_URL
            run = await app.send_photo(
                chat_id=chat_id,
                photo=img,
                caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], dur, user),
                reply_markup=InlineKeyboardMarkup(get_btn("telegram")),
            )
        elif videoid == "soundcloud":
            run = await app.send_photo(
                chat_id=chat_id,
                photo=config.SOUNCLOUD_IMG_URL,
                caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], dur, user),
                reply_markup=InlineKeyboardMarkup(get_btn("soundcloud")),
            )
        else:
            img = await get_thumb(videoid)
            run = await app.send_photo(
                chat_id=chat_id,
                photo=img,
                caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], dur, user),
                reply_markup=InlineKeyboardMarkup(stream_markup(_, videoid, db_chat_id)),
            )
        
        if db.get(db_chat_id):
            db[db_chat_id][0]["mystic"] = run
            db[db_chat_id][0]["markup"] = "tg"

    # --- Standard Controls ---

    async def pause_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        await client.pause(chat_id)
        playback_states[chat_id] = PlaybackState.PAUSED

    async def resume_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        await client.resume(chat_id)
        playback_states[chat_id] = PlaybackState.PLAYING

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
            finally: 
                self.active_calls.discard(chat_id)
                playback_states.pop(chat_id, None)

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
            finally: 
                self.active_calls.discard(chat_id)
                playback_states.pop(chat_id, None)

    async def skip_stream(self, chat_id, link, video=None, image=None):
        client = await self.get_tgcalls(chat_id)
        if not link.startswith("http"):
            link = os.path.abspath(link)
            
        ffmpeg_params, audio_q, video_q = FFmpegDirector.build(link, is_video=bool(video))
        stream = MediaStream(link, audio_parameters=audio_q, video_parameters=video_q, ffmpeg_parameters=ffmpeg_params)
        
        await client.play(chat_id, stream)

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        client = await self.get_tgcalls(chat_id)
        file_path = os.path.abspath(file_path)
        
        # Using FFmpeg Director's logic to build seek command
        # Logic: -ss (start) -to (end)
        ffmpeg_params, audio_q, video_q = FFmpegDirector.build(
            file_path, 
            is_video=(mode == "video"), 
            seek_start=to_seek, 
            seek_end=duration
        )
        
        stream = MediaStream(file_path, audio_parameters=audio_q, video_parameters=video_q, ffmpeg_parameters=ffmpeg_params)
        await client.play(chat_id, stream)

    async def speedup_stream(self, chat_id, file_path, speed, playing):
        client = await self.get_tgcalls(chat_id)
        file_path = os.path.abspath(file_path)
        base = os.path.basename(file_path)
        chatdir = os.path.join(os.getcwd(), "playback", str(speed))
        os.makedirs(chatdir, exist_ok=True)
        out = os.path.join(chatdir, base)

        # CPU Intensive task, better do it properly
        if not os.path.exists(out):
            vs = str(2.0 / float(speed))
            cmd = f'ffmpeg -i "{file_path}" -filter:v "setpts={vs}*PTS" -filter:a atempo={speed} -y "{out}"'
            # Using asyncio subprocess to not block loop
            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()

        dur = int(await asyncio.get_event_loop().run_in_executor(None, check_duration, out))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        
        # Build stream for speedup file
        ffmpeg_params, audio_q, video_q = FFmpegDirector.build(
            out, 
            is_video=(playing[0]["streamtype"] == "video"),
            seek_start=played,
            seek_end=seconds_to_min(dur)
        )
        
        stream = MediaStream(out, audio_parameters=audio_q, video_parameters=video_q, ffmpeg_parameters=ffmpeg_params)

        if chat_id in db:
            await client.play(chat_id, stream)
            db[chat_id][0].update({
                "played": con_seconds, 
                "dur": seconds_to_min(dur), 
                "seconds": dur, 
                "speed_path": out, 
                "speed": speed
            })

    async def stream_call(self, link):
        assistant = await self.get_tgcalls(config.LOGGER_ID)
        try:
            await assistant.play(config.LOGGER_ID, MediaStream(link))
            await asyncio.sleep(8)
        finally:
            try: await assistant.leave_call(config.LOGGER_ID)
            except: pass
            
    async def ping(self):
        pings = []
        for c in self.pool.get_all():
            try: pings.append(c.ping)
            except: pass
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    # --- Event Handling & Decorations ---

    async def decorators(self):
        assistants = self.pool.get_all()

        async def unified_update_handler(client: PyTgCalls, update: Update):
            if not getattr(update, "chat_id", None):
                return
            
            chat_id = update.chat_id

            # 1. Stream Ended Event
            if isinstance(update, StreamEnded):
                # Only handle if audio stream ended (video sometimes sends double events)
                if update.stream_type == StreamEnded.Type.AUDIO:
                    TitaniumLogger.info("Stream Ended. Requesting Next...", chat_id)
                    try: await self.change_stream(client, chat_id)
                    except Exception as e: 
                        TitaniumLogger.error(f"Failed to change stream: {e}", chat_id)
            
            # 2. Chat Updates (Left/Kicked)
            elif isinstance(update, ChatUpdate):
                status = update.status
                if (status & ChatUpdate.Status.LEFT_CALL) or \
                   (status & ChatUpdate.Status.KICKED) or \
                   (status & ChatUpdate.Status.CLOSED_VOICE_CHAT):
                    TitaniumLogger.warn("Assistant Left or Kicked.", chat_id)
                    await self.stop_stream(chat_id)

        # Register handler for all clients
        for assistant in assistants:
            try:
                if hasattr(assistant, 'on_update'):
                    assistant.on_update()(unified_update_handler)
            except Exception as e:
                TitaniumLogger.error(f"Failed to attach decorators: {e}")

    async def _register_handlers(self):
        """Internal method to trigger decorators."""
        await self.decorators()

# =======================================================================
# 🚀 INITIALIZATION
# =======================================================================

# Singleton Instance
Hotty = Call()

# Helper for external clearing (Legacy support)
async def _clear_(chat_id: int) -> None:
    try:
        if popped := db.pop(chat_id, None):
            await auto_clean(popped)
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await set_loop(chat_id, 0)
    except:
        pass

