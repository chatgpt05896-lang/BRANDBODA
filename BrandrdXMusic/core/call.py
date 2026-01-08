"""
██████╗ ██████╗ ██████╗ ███████╗    ██████╗ ███████╗██╗     ██╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝    ██╔══██╗██╔════╝██║     ██║
██║     ██║   ██║██████╔╝█████╗      ██████╔╝█████╗  ██║     ██║
██║     ██║   ██║██╔══██╗██╔══╝      ██╔══██╗██╔══╝  ██║     ██║
╚██████╗╚██████╔╝██║  ██║███████╗    ██║  ██║███████╗███████╗███████╗
 ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝

[النظام: وحدة الاتصال المركزي - الإصدار البلاتيني]
[الميزة: دمج ذكي + حماية ضد تحديثات المكتبات + معالجة تلقائية]
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls
from pytgcalls.types import (
    AudioQuality, 
    ChatUpdate, 
    MediaStream, 
    StreamEnded, 
    Update, 
    VideoQuality
)

# -----------------------------------------------------------
# 🛡️ منطقة الحماية الذكية (Smart Import Patch)
# -----------------------------------------------------------
# هذا الكود يمنع البوت من الانهيار بسبب اختلاف إصدارات pytgcalls
try:
    from pytgcalls.exceptions import (
        NoActiveGroupCall,
        NoAudioSourceFound,
        NoVideoSourceFound,
        NotConnected, # الإصدارات القديمة
    )
except ImportError:
    # معالجة الإصدارات الجديدة
    from pytgcalls.exceptions import (
        NoActiveGroupCall,
        NoAudioSourceFound,
        NoVideoSourceFound,
    )
    # حيلة برمجية: نعتبر NotConnected هي نفسها NoActiveGroupCall لتجنب الخطأ
    NotConnected = NoActiveGroupCall

# محاولة استيراد أخطاء الاتصال الإضافية بأمان
try:
    from ntgcalls import TelegramServerError, ConnectionNotFound
except ImportError:
    try:
        from pytgcalls.exceptions import TelegramServerError, ConnectionNotFound
    except ImportError:
        # تعريف فئات وهمية في أسوأ الحالات لمنع الانهيار
        class TelegramServerError(Exception): pass
        class ConnectionNotFound(Exception): pass

# -----------------------------------------------------------
# ⚙️ استيراد إعدادات البوت والملحقات
# -----------------------------------------------------------
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
from BrandrdXMusic.utils.inline.play import stream_markup
from BrandrdXMusic.utils.stream.autoclear import auto_clean
from BrandrdXMusic.utils.thumbnails import get_thumb
from BrandrdXMusic.utils.errors import capture_internal_err

autoend = {}
counter = {}

def dynamic_media_stream(path: str, video: bool = False, ffmpeg_params: str = None) -> MediaStream:
    """تجهيز جودة البث (Audio/Video) بناءً على الطلب"""
    if video:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.HIGH,
            video_parameters=VideoQuality.HD_720p,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.REQUIRED,
            ffmpeg_parameters=ffmpeg_params,
        )
    else:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.HIGH,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.IGNORE,
            ffmpeg_parameters=ffmpeg_params,
        )

async def _clear_(chat_id: int) -> None:
    """تنظيف بيانات المحادثة بعد انتهاء التشغيل"""
    popped = db.pop(chat_id, None)
    if popped:
        await auto_clean(popped)
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    await set_loop(chat_id, 0)

# =======================================================================
# 📞 الكلاس الرئيسي (Call Manager)
# =======================================================================

class Call:
    def __init__(self):
        # تهيئة عملاء PyTgCalls مع ربطهم بجلسات Pyrogram من الكونفج
        self.userbot1 = Client("BrandrdXAssis1", config.API_ID, config.API_HASH, session_string=config.STRING1) if config.STRING1 else None
        self.one = PyTgCalls(self.userbot1) if self.userbot1 else None

        self.userbot2 = Client("BrandrdXAssis2", config.API_ID, config.API_HASH, session_string=config.STRING2) if config.STRING2 else None
        self.two = PyTgCalls(self.userbot2) if self.userbot2 else None

        self.userbot3 = Client("BrandrdXAssis3", config.API_ID, config.API_HASH, session_string=config.STRING3) if config.STRING3 else None
        self.three = PyTgCalls(self.userbot3) if self.userbot3 else None

        self.userbot4 = Client("BrandrdXAssis4", config.API_ID, config.API_HASH, session_string=config.STRING4) if config.STRING4 else None
        self.four = PyTgCalls(self.userbot4) if self.userbot4 else None

        self.userbot5 = Client("BrandrdXAssis5", config.API_ID, config.API_HASH, session_string=config.STRING5) if config.STRING5 else None
        self.five = PyTgCalls(self.userbot5) if self.userbot5 else None

        self.active_calls: set[int] = set()

    # ---------------------------------------------------
    # ⏸️ أدوات التحكم الأساسية
    # ---------------------------------------------------
    @capture_internal_err
    async def pause_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    @capture_internal_err
    async def resume_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    @capture_internal_err
    async def mute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    @capture_internal_err
    async def unmute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    @capture_internal_err
    async def stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return
        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass
        finally:
            self.active_calls.discard(chat_id)

    @capture_internal_err
    async def force_stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            if check:
                check.pop(0)
        except (IndexError, KeyError):
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return
        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass
        finally:
            self.active_calls.discard(chat_id)

    # ---------------------------------------------------
    # ⏩ أدوات التشغيل المتقدمة (Seek, Skip, Join)
    # ---------------------------------------------------
    @capture_internal_err
    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None) -> None:
        assistant = await group_assistant(self, chat_id)
        stream = dynamic_media_stream(path=link, video=bool(video))
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str) -> None:
        assistant = await group_assistant(self, chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        is_video = mode == "video"
        stream = dynamic_media_stream(path=file_path, video=is_video, ffmpeg_params=ffmpeg_params)
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def speedup_stream(self, chat_id: int, file_path: str, speed: float, playing: list) -> None:
        if not isinstance(playing, list) or not playing or not isinstance(playing[0], dict):
            raise AssistantErr("بيانات التشغيل غير صحيحة.")

        assistant = await group_assistant(self, chat_id)
        base = os.path.basename(file_path)
        chatdir = os.path.join(os.getcwd(), "playback", str(speed))
        os.makedirs(chatdir, exist_ok=True)
        out = os.path.join(chatdir, base)

        if not os.path.exists(out):
            vs = str(2.0 / float(speed))
            cmd = f'ffmpeg -i "{file_path}" -filter:v "setpts={vs}*PTS" -filter:a atempo={speed} -y "{out}"'
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdin=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        dur = int(await asyncio.get_event_loop().run_in_executor(None, check_duration, out))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration_min = seconds_to_min(dur)
        is_video = playing[0]["streamtype"] == "video"
        ffmpeg_params = f"-ss {played} -to {duration_min}"
        stream = dynamic_media_stream(path=out, video=is_video, ffmpeg_params=ffmpeg_params)

        if chat_id in db and db[chat_id] and db[chat_id][0].get("file") == file_path:
            await assistant.play(chat_id, stream)
            db[chat_id][0].update({
                "played": con_seconds,
                "dur": duration_min,
                "seconds": dur,
                "speed_path": out,
                "speed": speed,
                "old_dur": db[chat_id][0].get("dur"),
                "old_second": db[chat_id][0].get("seconds"),
            })

    @capture_internal_err
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ) -> None:
        assistant = await group_assistant(self, chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)
        stream = dynamic_media_stream(path=link, video=bool(video))

        try:
            await assistant.play(chat_id, stream)
        except (NoActiveGroupCall, ChatAdminRequired):
            raise AssistantErr(_["call_8"])
        except NoAudioSourceFound:
            raise AssistantErr(_["call_11"])
        except NoVideoSourceFound:
            raise AssistantErr(_["call_12"])
        except (ConnectionNotFound, TelegramServerError):
            raise AssistantErr(_["call_10"])
        except NotConnected:
             raise AssistantErr(_["call_8"])
        except Exception as e:
            raise AssistantErr(f"فشل الانضمام للمكالمة.\nالسبب: {e}")
        
        self.active_calls.add(chat_id)
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)

        if await is_autoend():
            counter[chat_id] = {}
            try:
                users = len(await assistant.get_participants(chat_id))
                if users == 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except: pass

    # ---------------------------------------------------
    # 🎵 وحدة التشغيل الرئيسية (The Core Play Function)
    # ---------------------------------------------------
    @capture_internal_err
    async def play(self, client, chat_id: int) -> None:
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)
            if not check:
                await _clear_(chat_id)
                if chat_id in self.active_calls:
                    try:
                        await client.leave_call(chat_id)
                    except: pass
                    finally:
                        self.active_calls.discard(chat_id)
                return
        except:
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except: return

        queued = check[0]["file"]
        language = await get_lang(chat_id)
        _ = get_string(language)
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        db[chat_id][0]["played"] = 0

        # استعادة بيانات السرعة
        exis = (check[0]).get("old_dur")
        if exis:
            db[chat_id][0]["dur"] = exis
            db[chat_id][0]["seconds"] = check[0]["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0

        video = True if str(streamtype) == "video" else False

        # Live Stream
        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                return await app.send_message(original_chat_id, text=_["call_6"])
            stream = dynamic_media_stream(path=link, video=video)
            try:
                await client.play(chat_id, stream)
            except:
                return await app.send_message(original_chat_id, text=_["call_6"])
            img = await get_thumb(videoid)
            button = stream_markup(_, videoid, chat_id)
            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

        # Downloaded Media
        elif "vid_" in queued:
            mystic = await app.send_message(original_chat_id, _["call_7"])
            try:
                # تكامل مع دالة التحميل الجديدة
                file_path, _ = await YouTube.download(
                    videoid,
                    mystic,
                    videoid=True,
                    video=True if str(streamtype) == "video" else False,
                )
            except:
                return await mystic.edit_text(_["call_6"], disable_web_page_preview=True)
            stream = dynamic_media_stream(path=file_path, video=video)
            try:
                await client.play(chat_id, stream)
            except:
                return await app.send_message(original_chat_id, text=_["call_6"])
            img = await get_thumb(videoid)
            button = stream_markup(_, videoid, chat_id)
            await mystic.delete()
            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

        # Other Files
        else:
            stream = dynamic_media_stream(path=queued, video=video)
            try:
                await client.play(chat_id, stream)
            except:
                return await app.send_message(original_chat_id, text=_["call_6"])
            
            if videoid == "telegram":
                button = stream_markup(_, "telegram", chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.TELEGRAM_VIDEO_URL if video else config.TELEGRAM_AUDIO_URL,
                    caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
            elif videoid == "soundcloud":
                button = stream_markup(_, "soundcloud", chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.SOUNCLOUD_IMG_URL,
                    caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                img = await get_thumb(videoid)
                button = stream_markup(_, videoid, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    # ---------------------------------------------------
    # 🔄 تهيئة وإدارة المساعدين
    # ---------------------------------------------------
    async def start(self) -> None:
        LOGGER(__name__).info("Starting PyTgCalls Clients...")
        clients = [self.one, self.two, self.three, self.four, self.five]
        for cli in clients:
            if cli: await cli.start()

    @capture_internal_err
    async def ping(self) -> str:
        pings = []
        clients = [self.one, self.two, self.three, self.four, self.five]
        for cli in clients:
            if cli and cli.ping:
                pings.append(cli.ping)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    @capture_internal_err
    async def decorators(self) -> None:
        assistants = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))

        async def unified_update_handler(client, update: Update) -> None:
            if isinstance(update, StreamEnded):
                if update.stream_type == StreamEnded.Type.AUDIO:
                    assistant = await group_assistant(self, update.chat_id)
                    await self.play(assistant, update.chat_id)
            
            elif isinstance(update, ChatUpdate):
                status = update.status
                # التعامل مع الخروج الاجباري او التوقف
                if status in [ChatUpdate.Status.KICKED, ChatUpdate.Status.LEFT_GROUP, ChatUpdate.Status.CLOSED_VOICE_CHAT]:
                    await self.stop_stream(update.chat_id)

        for assistant in assistants:
            assistant.on_update()(unified_update_handler)

Hotty = Call()
