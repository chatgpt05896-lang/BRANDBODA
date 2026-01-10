# call.py
# نسخة محسّنة من Call manager مع حماية من GROUPCALL_INVALID و UpdateGroupCall
# ومهمة hard-reset لإعادة تشغيل الـ userbots و pytgcalls بأمان.

import asyncio
import os
import random
from datetime import datetime, timedelta
from typing import Union

# المهم جداً: استدعاء الباتش قبل أي تحميل لـ PyTgCalls أو Pyrogram internals
from . import pytgcalls_patch  # تأكد المسار صحيح داخل مشروعك

from pyrogram import Client
from pyrogram.errors import UserAlreadyParticipant
from pyrogram.types import InlineKeyboardMarkup

from pytgcalls import PyTgCalls
from pytgcalls.types import (
    MediaStream,
    AudioQuality,
    VideoQuality,
    StreamEnded,
    ChatUpdate,
    Update
)

# استيراد raw functions لو احتجنا لإنشاء مكالمة كخيار بديل (best-effort)
from pyrogram.raw import functions as raw_functions

# استيراد الاستثناءات من pytgcalls إن كانت متاحة
try:
    from pytgcalls.exceptions import (
        NoActiveGroupCall,
        NoAudioSourceFound,
        NoVideoSourceFound,
        TelegramServerError,
        ConnectionNotFound,
        AlreadyJoinedError,
    )
except Exception:
    class NoActiveGroupCall(Exception): pass
    class NoAudioSourceFound(Exception): pass
    class NoVideoSourceFound(Exception): pass
    class TelegramServerError(Exception): pass
    class ConnectionNotFound(Exception): pass
    class AlreadyJoinedError(Exception): pass

# =======================================================================
# استورد وظائف المشروع (تأكد أن هذه المسارات موجودة في مشروعك)
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

# =======================================================================
# حالات autoend per chat
# =======================================================================
autoend = {}
counter = {}

# =======================================================================
# مساعدة لبناء stream مع تحسينات ffmpeg
# =======================================================================
def build_stream(path: str, video: bool = False, ffmpeg: str = None, duration: int = 0) -> MediaStream:
    is_url = isinstance(path, str) and path.startswith("http")
    base_ffmpeg = " -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ac 2"

    final_ffmpeg = ffmpeg if ffmpeg else ""
    if is_url:
        final_ffmpeg += base_ffmpeg
    else:
        final_ffmpeg += " -ac 2"

    audio_params = AudioQuality.HIGH
    video_params = VideoQuality.SD_480p if video else VideoQuality.SD_480p

    return MediaStream(
        media_path=path,
        audio_parameters=audio_params,
        video_parameters=video_params,
        video_flags=MediaStream.Flags.IGNORE if not video else MediaStream.Flags.REQUIRED,
        ffmpeg_parameters=final_ffmpeg if final_ffmpeg else None,
    )

# =======================================================================
# تنظيف queue / حذف حالات الفيديو/الموسيقى
# =======================================================================
async def _clear_(chat_id: int) -> None:
    try:
        if popped := db.pop(chat_id, None):
            await auto_clean(popped)
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await set_loop(chat_id, 0)
    except Exception:
        pass

# =======================================================================
# Call manager class
# =======================================================================
class Call:
    def __init__(self):
        # أنشئ الـ userbots ثم PyTgCalls لكلٍ منهم (إذا كانت session strings موجودة)
        self.userbot1 = Client("BrandrdXMusic1", config.API_ID, config.API_HASH, session_string=config.STRING1) if getattr(config, "STRING1", None) else None
        self.one = PyTgCalls(self.userbot1) if self.userbot1 else None

        self.userbot2 = Client("BrandrdXMusic2", config.API_ID, config.API_HASH, session_string=config.STRING2) if getattr(config, "STRING2", None) else None
        self.two = PyTgCalls(self.userbot2) if self.userbot2 else None

        self.userbot3 = Client("BrandrdXMusic3", config.API_ID, config.API_HASH, session_string=config.STRING3) if getattr(config, "STRING3", None) else None
        self.three = PyTgCalls(self.userbot3) if self.userbot3 else None

        self.userbot4 = Client("BrandrdXMusic4", config.API_ID, config.API_HASH, session_string=config.STRING4) if getattr(config, "STRING4", None) else None
        self.four = PyTgCalls(self.userbot4) if self.userbot4 else None

        self.userbot5 = Client("BrandrdXMusic5", config.API_ID, config.API_HASH, session_string=config.STRING5) if getattr(config, "STRING5", None) else None
        self.five = PyTgCalls(self.userbot5) if self.userbot5 else None

        self.active_calls = set()

        # خريطة id(assistant) -> pytgcalls instance
        self.pytgcalls_map = {
            id(self.userbot1) if self.userbot1 else None: self.one,
            id(self.userbot2) if self.userbot2 else None: self.two,
            id(self.userbot3) if self.userbot3 else None: self.three,
            id(self.userbot4) if self.userbot4 else None: self.four,
            id(self.userbot5) if self.userbot5 else None: self.five,
        }

    async def get_tgcalls(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        return self.pytgcalls_map.get(id(assistant), self.one)

    # ===================================================================
    # Hard reset: إعادة تشغيل userbot و pytgcalls آمنة
    # ===================================================================
    async def _hard_reset(self, chat_id: int):
        LOGGER(__name__).warning(f"Performing hard reset for chat {chat_id}...")

        # حاول تنظيف الحالة محليًا
        try:
            await _clear_(chat_id)
        except Exception as e:
            LOGGER(__name__).error(f"Error clearing db state for {chat_id}: {e}")

        assistants = [self.userbot1, self.userbot2, self.userbot3, self.userbot4, self.userbot5]
        calls = [self.one, self.two, self.three, self.four, self.five]

        # leave_call attempt
        for c in calls:
            if c:
                try:
                    await c.leave_call(chat_id)
                except Exception:
                    pass

        # Stop all PyTgCalls
        for c in calls:
            if c:
                try:
                    await c.stop()
                except Exception:
                    try:
                        c.stop()
                    except Exception:
                        pass

        # Stop clients (userbots)
        for bot in assistants:
            if bot:
                try:
                    await bot.stop()
                except Exception:
                    try:
                        bot.stop()
                    except Exception:
                        pass

        # small delay to allow sockets to close
        await asyncio.sleep(2)

        # Start clients and pytgcalls again
        for bot, call in zip(assistants, calls):
            if bot:
                try:
                    await bot.start()
                except Exception as e:
                    LOGGER(__name__).error(f"Failed to start assistant {bot}: {e}")
            if call:
                try:
                    await call.start()
                except Exception as e:
                    LOGGER(__name__).error(f"Failed to start pytgcalls instance: {e}")

        # remove chat from active_calls
        try:
            self.active_calls.discard(chat_id)
        except Exception:
            pass

        LOGGER(__name__).info(f"Hard reset finished for chat {chat_id}")

    # ===================================================================
    # Safe play: معالجات لخطأ GROUPCALL_INVALID و NOACTIVEGROUPCALL
    # ===================================================================
    async def _play_stream_safe(self, client, chat_id, path, video, duration_sec=0, ffmpeg=None):
        stream = build_stream(path, video, ffmpeg, duration_sec)
        try:
            await client.play(chat_id, stream)
            return
        except NoActiveGroupCall:
            raise NoActiveGroupCall()
        except Exception as e:
            err_str = str(e)
            LOGGER(__name__).error(f"_play_stream_safe error for {chat_id}: {err_str}")

            if "GROUPCALL_INVALID" in err_str or "GROUPCALL_FORBIDDEN" in err_str:
                LOGGER(__name__).warning(f"⚠️ Invalid Group Call in {chat_id}, performing hard reset...")
                try:
                    await self._hard_reset(chat_id)
                except Exception as re:
                    LOGGER(__name__).error(f"Hard reset failed for {chat_id}: {re}")
                raise Exception("GROUPCALL_INVALID")

            if "Call not found" in err_str or "not found" in err_str:
                try:
                    await self._hard_reset(chat_id)
                except Exception:
                    pass
                raise Exception("CALL_NOT_FOUND")

            # تصاعد الاستثناءات الأخرى لمعالجتها في مكان أعلى
            raise e

    # ===================================================================
    # Startup helpers
    # ===================================================================
    async def start(self):
        LOGGER(__name__).info("🚀 Starting Audio Engine...")
        clients = [c for c in [self.one, self.two, self.three, self.four, self.five] if c]
        tasks = [c.start() for c in clients]
        if tasks:
            await asyncio.gather(*tasks)
        await self.decorators()

    async def ping(self):
        pings = []
        clients = [c for c in [self.one, self.two, self.three, self.four, self.five] if c]
        for c in clients:
            try:
                pings.append(c.ping)
            except Exception:
                pass
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
            try:
                await client.leave_call(chat_id)
            except Exception:
                pass
            finally:
                self.active_calls.discard(chat_id)

    async def force_stop_stream(self, chat_id: int):
        client = await self.get_tgcalls(chat_id)
        try:
            check = db.get(chat_id)
            if check: check.pop(0)
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

    # ===================================================================
    # join_call مع محاولة إنشاء مكالمة لو لم تكن موجودة (best-effort)
    # ===================================================================
    async def join_call(self, chat_id: int, original_chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None):
        client = await self.get_tgcalls(chat_id)
        assistant = await group_assistant(self, chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)

        if not link.startswith("http"):
            link = os.path.abspath(link)

        try:
            # ensure assistant in chat (best-effort)
            try:
                await assistant.join_chat(chat_id)
            except UserAlreadyParticipant:
                pass
            except Exception:
                pass

            try:
                await self._play_stream_safe(client, chat_id, link, bool(video))
            except NoActiveGroupCall:
                # لا توجد مكالمة نشطة — محاولة إنشاء مكالمة جديدة عبر Raw API كـ best-effort
                try:
                    try:
                        peer = await assistant.resolve_peer(chat_id)
                        random_id = random.getrandbits(32)
                        await assistant.send(raw_functions.phone.CreateGroupCall(peer=peer, random_id=random_id))
                        await asyncio.sleep(1.5)
                    except Exception as create_ex:
                        LOGGER(__name__).warning(f"CreateGroupCall attempt failed for {chat_id}: {create_ex}")
                        await self._hard_reset(chat_id)
                        raise AssistantErr(_["call_8"])

                    # بعد الإنشاء، حاول التشغيل مرة ثانية
                    await self._play_stream_safe(client, chat_id, link, bool(video))
                except Exception as inner_e:
                    LOGGER(__name__).error(f"Join Call after create attempt failed: {inner_e}")
                    raise AssistantErr(_["call_8"])

        except NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except (NoAudioSourceFound, NoVideoSourceFound):
            raise AssistantErr(_["call_11"])
        except (TelegramServerError, ConnectionNotFound):
            raise AssistantErr(_["call_10"])
        except Exception as e:
            if "GROUPCALL_INVALID" in str(e) or "CALL_NOT_FOUND" in str(e):
                raise AssistantErr(_["call_8"])
            LOGGER(__name__).error(f"Join Call Error: {e}")
            raise AssistantErr(str(e))

        # لو نجحت الإضافة:
        self.active_calls.add(chat_id)
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)

        # autoend handling
        if await is_autoend():
            try:
                if await assistant.get_chat_members_count(chat_id) <= 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except Exception:
                pass

    # ===================================================================
    # تغيير المسار/التراك بعد انتهاء مقطع
    # ===================================================================
    async def change_stream(self, client, chat_id: int):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)

        try:
            if not check:
                await _clear_(chat_id)
                if chat_id in self.active_calls:
                    try:
                        await client.leave_call(chat_id)
                    except Exception:
                        pass
                    finally:
                        self.active_calls.discard(chat_id)
                return

            if loop == 0:
                popped = check.pop(0)
            else:
                loop -= 1
                await set_loop(chat_id, loop)

            if popped:
                await auto_clean(popped)

            if not check:
                await _clear_(chat_id)
                if chat_id in self.active_calls:
                    try:
                        await client.leave_call(chat_id)
                    except Exception:
                        pass
                    finally:
                        self.active_calls.discard(chat_id)
                return
        except Exception:
            try:
                await _clear_(chat_id)
                await client.leave_call(chat_id)
            except Exception:
                pass
            return

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
        except Exception:
            duration_sec = 0

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
            LOGGER(__name__).error(f"Play Error: {e}")
            try:
                await self.change_stream(client, chat_id)
            except Exception:
                pass

    # ===================================================================
    # skip / seek / speedup helpers
    # ===================================================================
    async def skip_stream(self, chat_id, link, video=None, image=None):
        client = await self.get_tgcalls(chat_id)
        if not link.startswith("http"):
            link = os.path.abspath(link)
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
            db[chat_id][0].update({
                "played": con_seconds,
                "dur": seconds_to_min(dur),
                "seconds": dur,
                "speed_path": out,
                "speed": speed
            })

    # ===================================================================
    # diagnostic stream (logger)
    # ===================================================================
    async def stream_call(self, link):
        assistant = await self.get_tgcalls(config.LOGGER_ID)
        try:
            await assistant.play(config.LOGGER_ID, MediaStream(link))
            await asyncio.sleep(8)
        finally:
            try:
                await assistant.leave_call(config.LOGGER_ID)
            except Exception:
                pass

    # ===================================================================
    # decorators: unified update handler مع حماية إضافية
    # ===================================================================
    async def decorators(self):
        assistants = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))

        async def unified_update_handler(client, update: Update):
            try:
                # حماية: إذا تحديث بدون chat_id => تجاهله
                if not hasattr(update, "chat_id"):
                    return

                chat_id = update.chat_id

                if isinstance(update, StreamEnded):
                    try:
                        await self.change_stream(client, chat_id)
                    except Exception as e:
                        LOGGER(__name__).error(f"Error handling StreamEnded for {chat_id}: {e}")

                elif isinstance(update, ChatUpdate):
                    status = update.status
                    if (status == ChatUpdate.Status.LEFT_CALL) or \
                       (status == ChatUpdate.Status.KICKED) or \
                       (status == ChatUpdate.Status.CLOSED_VOICE_CHAT):
                        await self.stop_stream(chat_id)

            except Exception as e:
                LOGGER(__name__).error(f"Decorator Error: {e}")
                return

        for assistant in assistants:
            try:
                if hasattr(assistant, 'on_update'):
                    assistant.on_update()(unified_update_handler)
            except Exception as e:
                LOGGER(__name__).error(f"Failed to attach decorators: {e}")

# instance جاهز للاستخدام
Hotty = Call()
