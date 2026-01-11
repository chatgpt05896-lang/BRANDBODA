# -*- coding: utf-8 -*-
"""
call.py
إصدار مُحصّن ومُعاد البناء للعمل مع:
 - py-tgcalls >= 2.2.8
 - ntgcalls >= 2.0.6
يحتوي:
 - دعم حتى 5 مساعدين
 - حماية من CHAT_ADMIN_REQUIRED
 - حماية ضد UpdateGroupCall (chat_id missing) عبر معالجة ذكية وتغليف المُعلّقات
 - استرداد المكالمات الميتة (Zombie Call recovery)
 - queue، loop، seek، speedup، pause/resume، mute/unmute
 - تعليقات تفصيلية
"""

import asyncio
import os
import random
import inspect
import contextlib
from datetime import datetime, timedelta
from typing import Union, Optional, Dict

from pyrogram import Client
from pyrogram.errors import UserAlreadyParticipant
from pyrogram.types import InlineKeyboardMarkup

# PyTgCalls / NTgCalls imports
from pytgcalls import PyTgCalls
from pytgcalls.types import (
    MediaStream,
    AudioQuality,
    VideoQuality,
    StreamEnded,
    ChatUpdate,
    Update,
)

# ===========================
# استيراد الاستثناءات بشكل مرن
# ===========================
try:
    from pytgcalls.exceptions import (
        NoActiveGroupCall,
        NoAudioSourceFound,
        NoVideoSourceFound,
        ConnectionNotFound,
        AlreadyJoinedError,
        GroupCallNotFound,
    )
except Exception:
    class NoActiveGroupCall(Exception): pass
    class NoAudioSourceFound(Exception): pass
    class NoVideoSourceFound(Exception): pass
    class ConnectionNotFound(Exception): pass
    class AlreadyJoinedError(Exception): pass
    class GroupCallNotFound(Exception): pass

# TelegramServerError قد تكون في pytgcalls أو ntgcalls — نعمل fallback
try:
    from pytgcalls.exceptions import TelegramServerError
except Exception:
    try:
        from ntgcalls import TelegramServerError  # بعض النسخ توفره هنا
    except Exception:
        class TelegramServerError(Exception): pass

# ===========================
# raw functions
# ===========================
from pyrogram.raw import functions as raw_functions

# ===========================
# مشروعك: استيراد الأدوات الداخلية
# ===========================
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
except Exception:
    stream_markup2 = None

# ===========================
# Global states
# ===========================
autoend: Dict[int, datetime] = {}
counter: Dict[int, dict] = {}
locks: Dict[int, asyncio.Lock] = {}  # lock per chat to avoid concurrent change_stream
watchdog_task: Optional[asyncio.Task] = None

# ===========================
# Defensive monkeypatch for pytgcalls on_update decorator
# (Purpose: if pytgcalls internal processing raises unexpected AttributeError for certain Update types,
#  wrap handlers to avoid crashing dispatcher)
# ===========================
def _safe_patch_pytgcalls():
    try:
        import pytgcalls.mtproto.pyrogram_client as _pc
    except Exception:
        return

    for name, obj in inspect.getmembers(_pc):
        if inspect.isclass(obj) and hasattr(obj, "on_update"):
            try:
                orig = getattr(obj, "on_update")

                def make_safe(orig_func):
                    def safe_on_update(self, *dargs, **dkwargs):
                        orig_decorator = orig_func(self, *dargs, **dkwargs)

                        def new_decorator(func):
                            # create safe wrapper around func
                            async def safe_handler(*h_args, **h_kwargs):
                                try:
                                    return await func(*h_args, **h_kwargs)
                                except Exception as e:
                                    # swallow handler errors but log them
                                    try:
                                        LOGGER(__name__).warning(f"Suppressed update handler error: {e}")
                                    except Exception:
                                        pass
                                    return None
                            # return original decorator applied to wrapped function
                            return orig_decorator(safe_handler)
                        return new_decorator
                    return safe_on_update

                setattr(obj, "on_update", make_safe(orig))
            except Exception:
                # best-effort patch: ignore if can't patch
                continue

# apply patch immediately
_safe_patch_pytgcalls()

# ===========================
# Helper: build MediaStream
# ===========================
def build_stream(path: str, video: bool = False, ffmpeg: str = None, duration: int = 0) -> MediaStream:
    # add reconnect options for http sources to avoid mid-stream drop
    is_url = isinstance(path, str) and path.startswith("http")
    base_ffmpeg = " -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ac 2"
    final_ffmpeg = ffmpeg or ""
    if is_url:
        final_ffmpeg += base_ffmpeg
    else:
        final_ffmpeg += " -ac 2"

    audio_params = AudioQuality.HIGH
    video_params = VideoQuality.SD_480p if video else VideoQuality.SD_480p

    return MediaStream(
        media_path=path,
        audio_parameters=audio_params,
        audio_flags=MediaStream.Flags.REQUIRED,
        video_parameters=video_params,
        video_flags=MediaStream.Flags.REQUIRED if video else MediaStream.Flags.IGNORE,
        ffmpeg_parameters=final_ffmpeg if final_ffmpeg else None,
    )

# ===========================
# Helper: lock per chat
# ===========================
def get_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in locks:
        locks[chat_id] = asyncio.Lock()
    return locks[chat_id]

# ===========================
# Helper: robust get chat id from update (try multiple shapes)
# ===========================
def extract_chat_id_from_update(update) -> Optional[int]:
    # try many shapes to extract chat id safely
    try:
        # common attribute
        if hasattr(update, "chat_id"):
            cid = getattr(update, "chat_id")
            if isinstance(cid, int): return cid
        # some updates include chat object
        if hasattr(update, "chat"):
            chat = getattr(update, "chat")
            if hasattr(chat, "id"):
                return getattr(chat, "id")
        # raw group call shapes
        if hasattr(update, "group_call"):
            gc = getattr(update, "group_call")
            # sometimes group_call has full_chat or peer
            if hasattr(gc, "full_chat"):
                return getattr(gc, "full_chat")
            if hasattr(gc, "id") and isinstance(getattr(gc, "id"), int):
                return getattr(gc, "id")
        # some updates have "call" or "peer"
        for attr in ("call", "peer", "from_id"):
            if hasattr(update, attr):
                v = getattr(update, attr)
                if isinstance(v, int):
                    return v
                if hasattr(v, "chat_id"):
                    return getattr(v, "chat_id")
                if hasattr(v, "id"):
                    return getattr(v, "id")
    except Exception:
        return None
    return None

# ===========================
# Clear/cleanup helper
# ===========================
async def _clear_(chat_id: int) -> None:
    try:
        if popped := db.pop(chat_id, None):
            await auto_clean(popped)
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await set_loop(chat_id, 0)
    except Exception as e:
        try:
            LOGGER(__name__).warning(f"_clear_ failed for {chat_id}: {e}")
        except Exception:
            pass

# ===========================
# Main Call Controller
# ===========================
class Call:
    def __init__(self):
        # init up to 5 userbots (if strings provided)
        self.userbot1 = Client("BrandrdXMusic1", config.API_ID, config.API_HASH, session_string=getattr(config, "STRING1", None)) if getattr(config, "STRING1", None) else None
        self.one = PyTgCalls(self.userbot1) if self.userbot1 else None

        self.userbot2 = Client("BrandrdXMusic2", config.API_ID, config.API_HASH, session_string=getattr(config, "STRING2", None)) if getattr(config, "STRING2", None) else None
        self.two = PyTgCalls(self.userbot2) if self.userbot2 else None

        self.userbot3 = Client("BrandrdXMusic3", config.API_ID, config.API_HASH, session_string=getattr(config, "STRING3", None)) if getattr(config, "STRING3", None) else None
        self.three = PyTgCalls(self.userbot3) if self.userbot3 else None

        self.userbot4 = Client("BrandrdXMusic4", config.API_ID, config.API_HASH, session_string=getattr(config, "STRING4", None)) if getattr(config, "STRING4", None) else None
        self.four = PyTgCalls(self.userbot4) if self.userbot4 else None

        self.userbot5 = Client("BrandrdXMusic5", config.API_ID, config.API_HASH, session_string=getattr(config, "STRING5", None)) if getattr(config, "STRING5", None) else None
        self.five = PyTgCalls(self.userbot5) if self.userbot5 else None

        self.active_calls = set()
        # map id(pyrogram_client) -> pytgcalls instance
        self.pytgcalls_map = {
            id(self.userbot1) if self.userbot1 else None: self.one,
            id(self.userbot2) if self.userbot2 else None: self.two,
            id(self.userbot3) if self.userbot3 else None: self.three,
            id(self.userbot4) if self.userbot4 else None: self.four,
            id(self.userbot5) if self.userbot5 else None: self.five,
        }

        # cache for assistant own user ids {client: user_id}
        self._assistant_user_id_cache: Dict[Client, int] = {}

    # choose PyTgCalls instance for the chat via group_assistant helper
    async def get_tgcalls(self, chat_id: int) -> PyTgCalls:
        assistant = await group_assistant(self, chat_id)
        return self.pytgcalls_map.get(id(assistant), self.one)

    # get assistant user id for this client (cached)
    async def _get_assistant_self_id(self, assistant: Client) -> Optional[int]:
        if not assistant:
            return None
        if assistant in self._assistant_user_id_cache:
            return self._assistant_user_id_cache[assistant]
        try:
            me = await assistant.get_me()
            if me:
                self._assistant_user_id_cache[assistant] = getattr(me, "id", None)
                return self._assistant_user_id_cache[assistant]
        except Exception:
            # unable to get me
            return None
        return None

    # check if assistant client is admin in chat (must be admin to CreateGroupCall)
    async def _assistant_is_admin(self, assistant: Client, chat_id: int) -> bool:
        try:
            aid = await self._get_assistant_self_id(assistant)
            if not aid:
                return False
            member = await assistant.get_chat_member(chat_id, aid)
            # check status: 'creator' or 'administrator'
            status = getattr(member, "status", "")
            if status in ("administrator", "creator"):
                # try to be permissive: if privileges exist, ensure can_manage_voice_chats if present
                priv = getattr(member, "privileges", None)
                if priv is None:
                    return True
                # attribute may be can_manage_video_chats or can_manage_voice_chats
                for p in ("can_manage_voice_chats", "can_manage_video_chats", "can_manage_calls"):
                    if hasattr(priv, p):
                        if getattr(priv, p):
                            return True
                        else:
                            return False
                return True
            return False
        except Exception:
            # if any error: return False to be safe
            return False

    # robust play wrapper
    async def _play_stream_safe(self, client: PyTgCalls, chat_id: int, path: str, video: bool, duration_sec: int = 0, ffmpeg: Optional[str] = None):
        stream = build_stream(path, video, ffmpeg, duration_sec)
        last_exc = None
        # try couple attempts
        for attempt in range(1, 3):
            try:
                await client.play(chat_id, stream)
                return
            except (NoActiveGroupCall, GroupCallNotFound) as e:
                last_exc = e
                raise NoActiveGroupCall()
            except Exception as e:
                last_exc = e
                err_str = str(e)
                # detect zombie / interface error
                if "GROUPCALL_INVALID" in err_str or "call_interface" in err_str:
                    raise NoActiveGroupCall()
                try:
                    LOGGER(__name__).warning(f"_play_stream_safe attempt {attempt} error for {chat_id}: {err_str}")
                except Exception:
                    pass
                await asyncio.sleep(0.5 * attempt)
        # if reach here, raise last
        if last_exc:
            raise last_exc

    # start all call clients & attach handlers
    async def start(self):
        try:
            LOGGER(__name__).info("🚀 Starting Audio Engine...")
        except Exception:
            pass
        clients = [c for c in [self.one, self.two, self.three, self.four, self.five] if c]
        for c in clients:
            try:
                await c.start()
            except Exception as e:
                try:
                    LOGGER(__name__).warning(f"Failed to start PyTgCalls client: {e}")
                except Exception:
                    pass
        # attach decorators
        await self.decorators()
        # start watchdog
        self._start_watchdog()

    async def ping(self) -> str:
        pings = []
        for c in [self.one, self.two, self.three, self.four, self.five]:
            if c:
                try:
                    pings.append(c.ping)
                except Exception:
                    pass
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    # playback control
    async def pause_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        with contextlib.suppress(Exception):
            await client.pause(chat_id)

    async def resume_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        with contextlib.suppress(Exception):
            await client.resume(chat_id)

    async def mute_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        with contextlib.suppress(Exception):
            await client.mute(chat_id)

    async def unmute_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        with contextlib.suppress(Exception):
            await client.unmute(chat_id)

    # stop & force stop
    async def stop_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        await _clear_(chat_id)
        if chat_id in self.active_calls:
            try:
                await client.leave_call(chat_id)
            except Exception as e:
                try:
                    LOGGER(__name__).warning(f"stop_stream leave_call failed for {chat_id}: {e}")
                except Exception:
                    pass
            finally:
                self.active_calls.discard(chat_id)

    async def force_stop_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        try:
            check = db.get(chat_id)
            if check:
                check.pop(0)
        except Exception:
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await _clear_(chat_id)
        if chat_id in self.active_calls:
            try:
                await client.leave_call(chat_id)
            except Exception:
                pass
            finally:
                self.active_calls.discard(chat_id)

    # join call (robust): create group call only if assistant is admin
    async def join_call(self, chat_id: int, original_chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None):
        client = await self.get_tgcalls(chat_id)
        assistant = await group_assistant(self, chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)

        if not link.startswith("http"):
            link = os.path.abspath(link)

        # lock to avoid concurrent join attempts for same chat
        lock = get_lock(chat_id)
        async with lock:
            try:
                # ensure assistant in chat (best-effort)
                with contextlib.suppress(Exception):
                    await assistant.join_chat(chat_id)
            except Exception:
                pass

            try:
                # try initial play
                try:
                    await self._play_stream_safe(client, chat_id, link, bool(video))
                except NoActiveGroupCall:
                    # before trying CreateGroupCall, ensure assistant is admin in chat
                    try:
                        is_admin = await self._assistant_is_admin(assistant, chat_id)
                        if not is_admin:
                            # don't attempt to create group call - raise friendly error
                            raise AssistantErr(_["call_9"] if "call_9" in _ else "⚠️ البوت يحتاج أن يكون مشرفًا لبدء المكالمة.")
                        # create group call using raw function
                        try:
                            peer = await assistant.resolve_peer(chat_id)
                            random_id = random.getrandbits(32)
                            await assistant.send(raw_functions.phone.CreateGroupCall(peer=peer, random_id=random_id))
                            await asyncio.sleep(1.5)
                        except Exception as ce:
                            LOGGER(__name__).warning(f"CreateGroupCall attempt failed for {chat_id}: {ce}")
                        # second attempt
                        await self._play_stream_safe(client, chat_id, link, bool(video))
                except Exception as e:
                    LOGGER(__name__).error(f"Join call play error for {chat_id}: {e}")
                    raise AssistantErr(_["call_8"])
            except (NoAudioSourceFound, NoVideoSourceFound):
                raise AssistantErr(_["call_11"])
            except (TelegramServerError, ConnectionNotFound):
                raise AssistantErr(_["call_10"])
            except AssistantErr:
                raise
            except Exception as e:
                LOGGER(__name__).error(f"Join Call Error: {e}")
                raise AssistantErr(_["call_8"])

            # on success
            self.active_calls.add(chat_id)
            await add_active_chat(chat_id)
            await music_on(chat_id)
            if video:
                await add_active_video_chat(chat_id)

            # autoend handling
            if await is_autoend():
                try:
                    # use get_participants if available
                    if hasattr(assistant, "get_participants"):
                        parts = await assistant.get_participants(chat_id)
                        if parts is not None and len(parts) <= 1:
                            autoend[chat_id] = datetime.now() + timedelta(minutes=1)
                    else:
                        # fallback to chat members count
                        cnt = await assistant.get_chat_members_count(chat_id)
                        if cnt <= 1:
                            autoend[chat_id] = datetime.now() + timedelta(minutes=1)
                except Exception:
                    pass

    # change_stream: move to next track (robust)
    async def change_stream(self, client, chat_id: int):
        lock = get_lock(chat_id)
        async with lock:
            check = db.get(chat_id)
            popped = None
            try:
                loop = await get_loop(chat_id)
            except Exception:
                loop = 0

            try:
                if not check:
                    await _clear_(chat_id)
                    if chat_id in self.active_calls:
                        with contextlib.suppress(Exception):
                            await client.leave_call(chat_id)
                        self.active_calls.discard(chat_id)
                    return

                if loop == 0:
                    popped = check.pop(0)
                else:
                    loop -= 1
                    await set_loop(chat_id, loop)

                if popped:
                    with contextlib.suppress(Exception):
                        await auto_clean(popped)

                if not check:
                    await _clear_(chat_id)
                    if chat_id in self.active_calls:
                        with contextlib.suppress(Exception):
                            await client.leave_call(chat_id)
                        self.active_calls.discard(chat_id)
                    return
            except Exception as e:
                LOGGER(__name__).error(f"change_stream prepare failed for {chat_id}: {e}")
                with contextlib.suppress(Exception):
                    await _clear_(chat_id)
                    await client.leave_call(chat_id)
                return

            queued = check[0].get("file")
            lang = await get_lang(chat_id)
            _ = get_string(lang)
            title = (check[0].get("title") or "").title()
            user = check[0].get("by")
            original_chat_id = check[0].get("chat_id")
            streamtype = check[0].get("streamtype")
            videoid = check[0].get("vidid")
            duration_sec = check[0].get("seconds", 0)

            db[chat_id][0]["played"] = 0
            video = True if str(streamtype) == "video" else False

            def get_btn(vid_id):
                if stream_markup2:
                    return stream_markup2(_, chat_id)
                return stream_markup(_, vid_id, chat_id)

            try:
                if "live_" in queued:
                    n, link = await YouTube.video(videoid, True)
                    if n == 0:
                        return await app.send_message(original_chat_id, text=_["call_6"])
                    await self._play_stream_safe(client, chat_id, link, video, 0)
                    img = await get_thumb(videoid)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=img,
                        caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0].get("dur", ""), user),
                        reply_markup=InlineKeyboardMarkup(get_btn(videoid)),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                elif "vid_" in queued:
                    mystic = await app.send_message(original_chat_id, _["call_7"])
                    try:
                        file_path, direct = await YouTube.download(videoid, mystic, videoid=True, video=video)
                    except Exception:
                        return await mystic.edit_text(_["call_6"])
                    await self._play_stream_safe(client, chat_id, file_path, video, duration_sec)
                    img = await get_thumb(videoid)
                    with contextlib.suppress(Exception):
                        await mystic.delete()
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=img,
                        caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0].get("dur", ""), user),
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
                            caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0].get("dur", ""), user),
                            reply_markup=InlineKeyboardMarkup(get_btn("telegram")),
                        )
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "tg"

                    elif videoid == "soundcloud":
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=config.SOUNDCLOUD_IMG_URL,
                            caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0].get("dur", ""), user),
                            reply_markup=InlineKeyboardMarkup(get_btn("soundcloud")),
                        )
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "tg"

                    else:
                        img = await get_thumb(videoid)
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0].get("dur", ""), user),
                            reply_markup=InlineKeyboardMarkup(stream_markup(_, videoid, chat_id)),
                        )
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "stream"

            except Exception as e:
                LOGGER(__name__).error(f"Play Error in change_stream for {chat_id}: {e}")
                try:
                    await self.change_stream(client, chat_id)
                except Exception:
                    pass

    # skip / seek / speedup
    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None):
        client = await self.get_tgcalls(chat_id)
        if not link.startswith("http"):
            link = os.path.abspath(link)
        await self._play_stream_safe(client, chat_id, link, bool(video))

    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str):
        client = await self.get_tgcalls(chat_id)
        file_path = os.path.abspath(file_path)
        ffmpeg = f"-ss {to_seek} -to {duration}"
        await self._play_stream_safe(client, chat_id, file_path, (mode == "video"), ffmpeg=ffmpeg)

    async def speedup_stream(self, chat_id: int, file_path: str, speed: float, playing: list):
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
            db[chat_id][0].update({
                "played": con_seconds,
                "dur": seconds_to_min(dur),
                "seconds": dur,
                "speed_path": out,
                "speed": speed
            })

    # ===== Decorators / Update handlers =====
    async def decorators(self):
        assistants = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))

        # unified handler: robust extraction & actions
        async def unified_update_handler(client, update: Update):
            # protect everything here — never let it bubble up
            try:
                # try to get chat id in flexible ways
                chat_id = extract_chat_id_from_update(update)
                if not chat_id:
                    # fallback: some updates carry attribute 'group_call' with 'full_chat_id' or so
                    try:
                        chat_id = getattr(update, "chat_id", None)
                    except Exception:
                        chat_id = None
                if not chat_id:
                    return

                # Stream ended -> next track
                if isinstance(update, StreamEnded):
                    try:
                        await self.change_stream(client, chat_id)
                    except Exception as e:
                        LOGGER(__name__).error(f"Error handling StreamEnded for {chat_id}: {e}")

                # Chat updates: left/kicked/closed -> stop
                elif isinstance(update, ChatUpdate):
                    try:
                        status = update.status
                        if status in (ChatUpdate.Status.LEFT_CALL, ChatUpdate.Status.KICKED, ChatUpdate.Status.CLOSED_VOICE_CHAT):
                            await self.stop_stream(chat_id)
                    except Exception as e:
                        LOGGER(__name__).warning(f"ChatUpdate handling warning for {chat_id}: {e}")

            except Exception as e:
                # log and swallow
                try:
                    LOGGER(__name__).warning(f"unified_update_handler outer error: {e}")
                except Exception:
                    pass

        # attach handler to each assistant (safe because of earlier monkeypatch)
        for assistant in assistants:
            try:
                if hasattr(assistant, "on_update"):
                    assistant.on_update()(unified_update_handler)
            except Exception as e:
                try:
                    LOGGER(__name__).error(f"Failed to attach decorators: {e}")
                except Exception:
                    pass

    # ===== Watchdog: autoend & zombie recovery =====
    def _start_watchdog(self):
        global watchdog_task
        if watchdog_task and not watchdog_task.done():
            return
        watchdog_task = asyncio.create_task(self._watchdog_loop())

    async def _watchdog_loop(self):
        while True:
            try:
                active = list(self.active_calls)
                for chat_id in active:
                    try:
                        assistant = await group_assistant(self, chat_id)
                        if not assistant:
                            await _clear_(chat_id)
                            self.active_calls.discard(chat_id)
                            continue
                        # try to get participants length safely
                        participants_count = None
                        with contextlib.suppress(Exception):
                            if hasattr(assistant, "get_participants"):
                                parts = await assistant.get_participants(chat_id)
                                participants_count = len(parts) if parts is not None else None
                            else:
                                participants_count = await assistant.get_chat_members_count(chat_id)
                        # if only assistant alone -> schedule autoend or end now
                        if participants_count is not None and participants_count <= 1:
                            if await is_autoend():
                                if chat_id not in autoend:
                                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
                            else:
                                # no autoend: clean up immediately
                                await self.stop_stream(chat_id)
                                continue
                        # handle autoend timeout
                        if chat_id in autoend:
                            if datetime.now() >= autoend[chat_id]:
                                await self.stop_stream(chat_id)
                                autoend.pop(chat_id, None)
                        # Zombie detection: if ntgcalls says call not found but we have active_calls -> try recover
                        # We attempt a best-effort recovery: if queue exists, try re-join (only if assistant is admin)
                        with contextlib.suppress(Exception):
                            # check if we are actually in call by querying assistant.get_participants
                            in_call = False
                            try:
                                parts = await assistant.get_participants(chat_id)
                                if parts:
                                    in_call = True
                            except Exception:
                                in_call = False
                            if not in_call:
                                # try recovery only if there is something to play
                                q = db.get(chat_id)
                                if q and len(q) > 0:
                                    # attempt to re-join & resume playing first item
                                    try:
                                        # choose client & play first file
                                        client = await self.get_tgcalls(chat_id)
                                        first = q[0]
                                        file_path = first.get("file")
                                        video = True if str(first.get("streamtype")) == "video" else False
                                        # check admin before create
                                        is_admin = await self._assistant_is_admin(assistant, chat_id)
                                        if not is_admin:
                                            await self.stop_stream(chat_id)
                                            continue
                                        await self._play_stream_safe(client, chat_id, file_path, video, first.get("seconds", 0))
                                        # re-add active state
                                        self.active_calls.add(chat_id)
                                    except Exception as re:
                                        LOGGER(__name__).warning(f"Recovery attempt failed for {chat_id}: {re}")
                                        # if recovery fails repeatedly, force stop to avoid endless loop
                                        # schedule immediate cleanup next cycle
                                        await self.stop_stream(chat_id)
                    except Exception as inner:
                        LOGGER(__name__).warning(f"Watchdog inner error for {chat_id}: {inner}")
                await asyncio.sleep(20)
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER(__name__).error(f"Watchdog outer error: {e}")
                await asyncio.sleep(10)

# export instance
Hotty = Call()
