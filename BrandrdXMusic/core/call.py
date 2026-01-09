import asyncio
import os
import traceback
from datetime import datetime, timedelta
from typing import Union, Dict, List
from functools import wraps

from pyrogram import Client
from pyrogram.errors import (
    FloodWait, 
    ChatAdminRequired, 
    UserAlreadyParticipant, 
    RPCError
)
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
# ✅ استيراد الغلاف الضروري (أساسي لمنع الإغلاق)
from pytgcalls.mtproto.data.update import UpdateGroupCallWrapper

# =======================================================================
# 🩹 PATCH: إصلاح دائم لمشكلة chat_id (Critical Fix)
# =======================================================================
try:
    from pytgcalls.types import UpdateGroupCall
    if not hasattr(UpdateGroupCall, 'chat_id'):
        UpdateGroupCall.chat_id = property(lambda self: getattr(getattr(self, "chat", None), "id", 0))
except ImportError:
    pass

# =======================================================================
# 🧱 جدار الحماية والاستثناءات (Exception Firewall)
# =======================================================================
# هنا بنعرف أخطاء وهمية عشان لو المكتبة اتحدثت واسماء الأخطاء اتغيرت الكود ميموتش
class _DummyException(Exception): pass
try: from pytgcalls.exceptions import NoActiveGroupCall
except ImportError: NoActiveGroupCall = _DummyException
try: from pytgcalls.exceptions import NoAudioSourceFound
except ImportError: NoAudioSourceFound = _DummyException
try: from pytgcalls.exceptions import NotConnected
except ImportError: NotConnected = _DummyException
try: from ntgcalls import TelegramServerError, ConnectionNotFound
except ImportError: TelegramServerError, ConnectionNotFound = _DummyException, _DummyException

# =======================================================================
# ⚙️ الإعدادات والمكتبات
# =======================================================================
import config
from strings import get_string
from BrandrdXMusic import LOGGER, YouTube, app
from BrandrdXMusic.misc import db
from BrandrdXMusic.utils.database import (
    add_active_chat, add_active_video_chat,
    get_lang, get_loop,
    group_assistant, is_autoend,
    music_on, remove_active_chat,
    remove_active_video_chat, set_loop,
)
from BrandrdXMusic.utils.exceptions import AssistantErr
from BrandrdXMusic.utils.formatters import check_duration, seconds_to_min, speed_converter
from BrandrdXMusic.utils.inline.play import stream_markup
from BrandrdXMusic.utils.stream.autoclear import auto_clean
from BrandrdXMusic.utils.thumbnails import get_thumb

# متغيرات تتبع الحالة
autoend = {}
counter = {}

# =======================================================================
# 🛡️ مزخرف الأخطاء المتقدم (Advanced Error Decorator)
# =======================================================================
def capture_internal_err(func):
    """
    يقوم بالتقاط أي خطأ داخل الدوال وتسجيله بالتفصيل الممل
    بدلاً من إيقاف البوت.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # تسجيل الخطأ بالتفصيل مع السطر المتسبب
            err_trace = traceback.format_exc()
            LOGGER(__name__).error(f"⚠️ Error in {func.__name__}: {e}")
            LOGGER(__name__).debug(f"🔍 Traceback: {err_trace}")
            return None
    return wrapper

# =======================================================================
# 🚀 إعدادات البث الاحترافية (Professional Stream Config)
# =======================================================================
def dynamic_media_stream(path: str, video: bool = False, image: str = None, ffmpeg_params: str = None) -> MediaStream:
    """
    يقوم ببناء كائن البث بإعدادات مخصصة للأداء العالي.
    تم إضافة bufsize و maxrate لتقليل التقطيع.
    """
    audio_q = AudioQuality.HIGH
    video_q = VideoQuality.HD_720p if video else VideoQuality.SD_480p
    
    # إعدادات متقدمة للـ Buffer عشان النت الضعيف
    # -preset ultrafast: أسرع تشفير
    # -tune zerolatency: استجابة فورية
    # -bufsize 5000k: مخزن مؤقت للبيانات
    base_params = "-preset ultrafast -tune zerolatency -maxrate 3000k -bufsize 6000k"
    
    final_params = f"{base_params} {ffmpeg_params}" if ffmpeg_params else base_params

    if video:
        return MediaStream(
            media_path=path,
            audio_parameters=audio_q,
            video_parameters=video_q,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.REQUIRED,
            ffmpeg_parameters=final_params
        )
    else:
        return MediaStream(
            media_path=path,
            audio_parameters=audio_q,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.IGNORE,
            ffmpeg_parameters=final_params
        )

async def _clear_(chat_id: int) -> None:
    """
    تنظيف شامل لقاعدة البيانات الخاصة بالمحادثة
    """
    try:
        popped = db.pop(chat_id, None)
        if popped: await auto_clean(popped)
        if chat_id in db: del db[chat_id]
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await set_loop(chat_id, 0)
    except Exception as e:
        LOGGER(__name__).error(f"Clear Error {chat_id}: {e}")

# =======================================================================
# 📞 الكلاس الرئيسي (The Ultimate Engine)
# =======================================================================
class Call:
    def __init__(self):
        # تهيئة العملاء والمساعدين بشكل منفصل لسهولة التحكم
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
        
        # تتبع المكالمات النشطة لمنع التداخل
        self.active_calls: set[int] = set()

    async def get_call_engine(self, chat_id: int) -> PyTgCalls:
        """
        تحديد المساعد المناسب للجروب.
        """
        try:
            userbot = await group_assistant(self, chat_id)
            if userbot:
                if self.userbot1 and userbot.me.id == self.userbot1.me.id: return self.one
                if self.userbot2 and userbot.me.id == self.userbot2.me.id: return self.two
                if self.userbot3 and userbot.me.id == self.userbot3.me.id: return self.three
                if self.userbot4 and userbot.me.id == self.userbot4.me.id: return self.four
                if self.userbot5 and userbot.me.id == self.userbot5.me.id: return self.five
            return self.one
        except Exception: 
            return self.one

    async def start(self) -> None:
        """
        تشغيل كافة العملاء في آن واحد.
        """
        LOGGER(__name__).info("🚀 Starting All Assistant Clients...")
        clients = [c for c in [self.one, self.two, self.three, self.four, self.five] if c]
        if clients:
            await asyncio.gather(*[cli.start() for cli in clients])
        LOGGER(__name__).info(f"✅ Started {len(clients)} Assistant Clients.")

    # ===================================================================
    # 🕵️ فحص الحالة والاتصال (Helper Methods)
    # ===================================================================
    async def is_connected(self, chat_id: int) -> bool:
        """فحص ما إذا كان المساعد متصل بالفعل في المكالمة"""
        assistant = await self.get_call_engine(chat_id)
        try:
            # طريقة ذكية للتأكد من التواجد عبر فحص المشاركين
            participants = await assistant.get_participants(chat_id)
            return True
        except (NotConnected, NoActiveGroupCall):
            return False
        except Exception:
            return False

    # ===================================================================
    # 🥊 دالة الانضمام المدرعة (Armored Join Logic)
    # ===================================================================
    async def join_call_robust(self, assistant: PyTgCalls, chat_id: int, stream: MediaStream) -> None:
        """
        تحاول الانضمام للمكالمة بقوة، مع التعامل مع كافة أخطاء التيليجرام المحتملة.
        """
        attempts = 4 # زيادة عدد المحاولات
        retry_delay = 1
        
        while attempts > 0:
            try:
                LOGGER(__name__).info(f"🔄 Connecting to {chat_id}...")
                await assistant.play(chat_id, stream)
                LOGGER(__name__).info(f"✅ Successfully connected to {chat_id}")
                return 
            
            except UserAlreadyParticipant:
                LOGGER(__name__).info(f"ℹ️ Assistant already in {chat_id}, updating stream.")
                return 
                
            except FloodWait as e:
                # التعامل الذكي مع حظر التكرار
                wait_time = e.value + 1
                if wait_time < 30:
                    LOGGER(__name__).warning(f"⏳ FloodWait {wait_time}s detected. Sleeping...")
                    await asyncio.sleep(wait_time)
                    continue # إعادة المحاولة بعد الانتظار
                else:
                    raise AssistantErr(f"Heavy FloodWait: {wait_time}s. Aborting.")
            
            except (NoActiveGroupCall, ChatAdminRequired):
                # أخطاء لا يمكن تخطيها
                raise AssistantErr("Voice Chat not started or Assistant lacks permissions.")
            
            except ConnectionNotFound:
                LOGGER(__name__).warning("⚠️ Connection lost, retrying...")
            
            except Exception as e:
                LOGGER(__name__).warning(f"⚠️ Unknown Join Error in {chat_id}: {e}")
                
            attempts -= 1
            await asyncio.sleep(retry_delay)
            retry_delay += 1 # زيادة وقت الانتظار تدريجياً (Exponential Backoff)
            
        raise AssistantErr("Failed to connect after multiple attempts.")

    # ===================================================================
    # 🎮 التحكم في البث (Stream Control)
    # ===================================================================
    @capture_internal_err
    async def join_call(self, chat_id: int, original_chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None) -> None:
        assistant = await self.get_call_engine(chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)
        
        # بناء الستريم بالإعدادات الجديدة
        stream = dynamic_media_stream(path=link, video=bool(video), image=image)
        
        # تنفيذ الانضمام
        await self.join_call_robust(assistant, chat_id, stream)
        
        # تحديث الحالات في قاعدة البيانات
        self.active_calls.add(chat_id)
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video: await add_active_video_chat(chat_id)

        # التحقق من الإغلاق التلقائي (Auto-End Logic)
        if await is_autoend():
            counter[chat_id] = {}
            try:
                participants = await assistant.get_participants(chat_id)
                users = len(participants)
                if users == 1: 
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except: pass

    @capture_internal_err
    async def stop_stream(self, chat_id: int) -> None:
        assistant = await self.get_call_engine(chat_id)
        await _clear_(chat_id)
        
        # محاولة الخروج الآمن
        try:
            await assistant.leave_call(chat_id)
        except (NotConnected, NoActiveGroupCall):
            pass # مش مشكلة لو مش متصل
        except Exception as e:
            LOGGER(__name__).debug(f"Stop Stream Error: {e}")
        finally:
            self.active_calls.discard(chat_id)

    @capture_internal_err
    async def force_stop_stream(self, chat_id: int) -> None:
        """إيقاف إجباري وتنظيف كامل للداتا"""
        assistant = await self.get_call_engine(chat_id)
        try:
            check = db.get(chat_id)
            if check: check.pop(0)
        except: pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await _clear_(chat_id)
        
        try: await assistant.leave_call(chat_id)
        except: pass
        finally: self.active_calls.discard(chat_id)

    @capture_internal_err
    async def pause_stream(self, chat_id: int) -> None:
        assistant = await self.get_call_engine(chat_id)
        await assistant.pause(chat_id)

    @capture_internal_err
    async def resume_stream(self, chat_id: int) -> None:
        assistant = await self.get_call_engine(chat_id)
        await assistant.resume(chat_id)

    @capture_internal_err
    async def mute_stream(self, chat_id: int) -> None:
        assistant = await self.get_call_engine(chat_id)
        await assistant.mute(chat_id)

    @capture_internal_err
    async def unmute_stream(self, chat_id: int) -> None:
        assistant = await self.get_call_engine(chat_id)
        await assistant.unmute(chat_id)

    @capture_internal_err
    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None) -> None:
        """تخطي الأغنية الحالية وتشغيل التالية"""
        assistant = await self.get_call_engine(chat_id)
        stream = dynamic_media_stream(path=link, video=bool(video), image=image)
        # نستخدم نفس دالة الانضمام لضمان الاستقرار
        await self.join_call_robust(assistant, chat_id, stream)

    @capture_internal_err
    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str) -> None:
        assistant = await self.get_call_engine(chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        stream = dynamic_media_stream(path=file_path, video=(mode == "video"), ffmpeg_params=ffmpeg_params)
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def speedup_stream(self, chat_id: int, file_path: str, speed: float, playing: list) -> None:
        """معالجة وتسريع الملف الصوتي"""
        assistant = await self.get_call_engine(chat_id)
        base = os.path.basename(file_path)
        chatdir = os.path.join(os.getcwd(), "playback", str(speed))
        os.makedirs(chatdir, exist_ok=True)
        out = os.path.join(chatdir, base)
        
        # معالجة الملف بـ FFMPEG لو مش موجود
        if not os.path.exists(out):
            vs = str(2.0 / float(speed))
            cmd = f'ffmpeg -i "{file_path}" -filter:v "setpts={vs}*PTS" -filter:a atempo={speed} -y "{out}"'
            proc = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()
            
        dur = int(await asyncio.get_event_loop().run_in_executor(None, check_duration, out))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration_min = seconds_to_min(dur)
        ffmpeg_params = f"-ss {played} -to {duration_min}"
        
        stream = dynamic_media_stream(path=out, video=(playing[0]["streamtype"] == "video"), ffmpeg_params=ffmpeg_params)
        
        if chat_id in db and db[chat_id] and db[chat_id][0].get("file") == file_path:
            await assistant.play(chat_id, stream)
            db[chat_id][0].update({"played": con_seconds, "dur": duration_min, "seconds": dur, "speed_path": out, "speed": speed})

    # ===================================================================
    # 🎵 نظام إدارة الطابور والتشغيل (Queue & Play Manager)
    # ===================================================================
    @capture_internal_err
    async def play(self, client, chat_id: int) -> None:
        """
        الدالة المسؤولة عن جلب الأغنية التالية من الطابور وتشغيلها.
        """
        if isinstance(client, Client): client = await self.get_call_engine(chat_id)
        
        # 1. إدارة الطابور (Loop & Pop)
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        
        try:
            if loop == 0: popped = check.pop(0)
            else:
                loop -= 1
                await set_loop(chat_id, loop)
            if popped: await auto_clean(popped)
            
            # إذا انتهى الطابور
            if not check:
                await _clear_(chat_id)
                return await self.stop_stream(chat_id)
        except Exception:
            await _clear_(chat_id)
            return await self.stop_stream(chat_id)

        # 2. تجهيز معلومات الملف
        queued = check[0]["file"]
        language = await get_lang(chat_id)
        _ = get_string(language)
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        db[chat_id][0]["played"] = 0
        video = (str(streamtype) == "video")
        
        # 3. التشغيل الفعلي
        try:
            try: img = await get_thumb(videoid)
            except: img = config.STREAM_IMG_URL
            
            stream = None
            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0: raise Exception("Live Failed")
                stream = dynamic_media_stream(path=link, video=video, image=img)
            elif "vid_" in queued:
                # منطق التحميل للفيديو
                mystic = await app.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, _ = await YouTube.download(videoid, mystic, videoid=True, video=video)
                except:
                    await mystic.delete()
                    return await app.send_message(original_chat_id, text=_["call_6"])
                stream = dynamic_media_stream(path=file_path, video=video, image=img)
                await mystic.delete()
            else:
                stream = dynamic_media_stream(path=queued, video=video, image=img)
            
            # استخدام دالة الانضمام القوية
            await self.join_call_robust(client, chat_id, stream)
            
            # إرسال رسالة التشغيل في الخلفية لعدم تعطيل البوت
            asyncio.create_task(self._send_playing_message(original_chat_id, videoid, title, check[0]["dur"], user, video, _, chat_id))
            
        except Exception as e:
            LOGGER(__name__).error(f"❌ Play Error in {chat_id}: {e}")
            await _clear_(chat_id)

    async def _send_playing_message(self, chat_id, videoid, title, dur, user, video, _, original_chat_id_for_markup):
        try:
            img = await get_thumb(videoid)
            button = stream_markup(_, videoid, original_chat_id_for_markup)
            
            if videoid == "telegram":
                 photo = config.TELEGRAM_VIDEO_URL if video else config.TELEGRAM_AUDIO_URL
                 link = config.SUPPORT_CHAT
            elif videoid == "soundcloud":
                 photo = config.SOUNCLOUD_IMG_URL
                 link = config.SUPPORT_CHAT
            else:
                 photo = img
                 link = f"https://t.me/{app.username}?start=info_{videoid}"
                 
            run = await app.send_photo(
                chat_id=chat_id, photo=photo,
                caption=_["stream_1"].format(link, title[:23], dur, user),
                reply_markup=InlineKeyboardMarkup(button),
            )
            if original_chat_id_for_markup in db:
                db[original_chat_id_for_markup][0]["mystic"] = run
                db[original_chat_id_for_markup][0]["markup"] = "tg"
        except: pass

    @capture_internal_err
    async def ping(self) -> str:
        """حساب متوسط البنج لجميع المساعدين"""
        pings = []
        clients = [c for c in [self.one, self.two, self.three, self.four, self.five] if c]
        for cli in clients:
            if cli.ping: pings.append(cli.ping)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    # ===================================================================
    # ⚠️ معالج التحديثات (Update Handler)
    # ===================================================================
    @capture_internal_err
    async def decorators(self) -> None:
        assistants = [c for c in [self.one, self.two, self.three, self.four, self.five] if c]
        
        async def unified_update_handler(client, update: Update) -> None:
            try:
                # 1. تصحيح الغلاف (UpdateGroupCallWrapper)
                # هذا الشرط ضروري جداً لمنع الانهيار عند تحديث حالة المكالمة
                if isinstance(update, UpdateGroupCallWrapper):
                    await self.stop_stream(update.chat_id)
                    return
                
                # 2. التعامل مع انتهاء الأغنية
                elif isinstance(update, StreamEnded):
                    if update.stream_type == StreamEnded.Type.AUDIO:
                        LOGGER(__name__).info(f"Stream Ended in {update.chat_id}, Playing next...")
                        await self.play(client, update.chat_id)
                
                # 3. التعامل مع الخروج الاجباري
                elif isinstance(update, ChatUpdate):
                    if update.status in [ChatUpdate.Status.KICKED, ChatUpdate.Status.LEFT_GROUP, ChatUpdate.Status.CLOSED_VOICE_CHAT]:
                        LOGGER(__name__).info(f"Chat Update {update.status} in {update.chat_id}, Stopping...")
                        await self.stop_stream(update.chat_id)
                        
            except Exception as e:
                LOGGER(__name__).error(f"Update Handler Exception: {e}")

        for assistant in assistants:
            assistant.on_update()(unified_update_handler)

Hotty = Call()
