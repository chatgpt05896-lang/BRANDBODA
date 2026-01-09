"""
██████╗ ██████╗  █████╗ ███╗   ██╗██████╗ ██████╗ ██████╗ ██╗  ██╗
██╔══██╗██╔══██╗██╔══██╗████╗  ██║██╔══██╗██╔══██╗██╔══██╗╚██╗██╔╝
██████╔╝██████╔╝███████║██╔██╗ ██║██║  ██║██████╔╝██║  ██║ ╚███╔╝ 
██╔══██╗██╔══██╗██╔══██║██║╚██╗██║██║  ██║██╔══██╗██║  ██║ ██╔██╗ 
██████╔╝██║  ██║██║  ██║██║ ╚████║██████╔╝██║  ██║██████╔╝██╔╝ ██╗
╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝

[ SYSTEM: ADVANCED CALL ENGINE - REBUILT ]
[ VERSION: 5.0.0 STABLE ]
[ DEVELOPER: GEMINI AI ]
"""

import asyncio
import os
import sys
import random
import traceback
import typing
from datetime import datetime, timedelta
from typing import Union, List, Dict, Optional, Any
from functools import wraps
from time import time

# =======================================================================
# 🩹 1. MONKEY PATCHING SECTION (CRITICAL FIXES)
# =======================================================================
def _apply_critical_patches():
    """
    تطبيق إصلاحات إجبارية للمكتبات لضمان التوافقية
    يتم استدعاء هذه الدالة قبل أي عملية استيراد أخرى
    """
    # Patch 1: UpdateGroupCall.chat_id Fix
    # يقوم هذا الباتش بحقن خاصية chat_id في كائنات التحديث التي تفتقدها
    targets = [
        "pyrogram.raw.types", 
        "pyrogram.types", 
        "pytgcalls.types"
    ]
    
    for module_name in targets:
        try:
            mod = __import__(module_name, fromlist=["UpdateGroupCall"])
            if hasattr(mod, "UpdateGroupCall"):
                cls = getattr(mod, "UpdateGroupCall")
                if not hasattr(cls, "chat_id"):
                    # إنشاء خاصية ديناميكية
                    def _get_chat_id(self):
                        # المحاولة 1: من كائن chat
                        if hasattr(self, "chat") and getattr(self.chat, "id", None):
                            return self.chat.id
                        # المحاولة 2: إذا كانت الخاصية موجودة ولكن مخفية
                        if hasattr(self, "_chat_id"):
                            return self._chat_id
                        return 0
                    
                    setattr(cls, "chat_id", property(_get_chat_id))
        except Exception:
            pass

_apply_critical_patches()

# =======================================================================
# 📚 2. LIBRARY IMPORTS
# =======================================================================
from pyrogram import Client
from pyrogram.errors import (
    FloodWait,
    ChatAdminRequired,
    UserAlreadyParticipant,
    UserNotParticipant,
    RPCError,
    ChatWriteForbidden,
    PeerIdInvalid
)
from pyrogram.types import (
    InlineKeyboardMarkup, 
    Message,
    ChatMember
)

from pytgcalls import PyTgCalls
from pytgcalls.types import (
    AudioQuality,
    VideoQuality,
    ChatUpdate,
    MediaStream,
    StreamEnded,
    Update,
    GroupCallConfig
)
from pytgcalls.exceptions import (
    NoActiveGroupCall,
    NoAudioSourceFound,
    NoVideoSourceFound,
    NotConnected,
    GroupCallNotFound,
    InvalidStreamMode
)

# استيراد إعدادات المشروع
try:
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
        is_active_chat
    )
    from BrandrdXMusic.utils.exceptions import AssistantErr
    from BrandrdXMusic.utils.formatters import check_duration, seconds_to_min, speed_converter
    from BrandrdXMusic.utils.inline.play import stream_markup
    from BrandrdXMusic.utils.stream.autoclear import auto_clean
    from BrandrdXMusic.utils.thumbnails import get_thumb
    
    # محاولة استيراد stream_markup2 بشكل آمن
    try:
        from BrandrdXMusic.utils.inline.play import stream_markup2
    except ImportError:
        stream_markup2 = None
        
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)


# =======================================================================
# ⚙️ 3. CONFIGURATION & CONSTANTS
# =======================================================================

# إعدادات الـ Buffer لضمان عدم التقطيع
FFMPEG_BUFFER_SIZE = "4096k"
FFMPEG_MAX_RATE = "2048k"

# أوامر FFMPEG المحسنة للأداء العالي
FFMPEG_BASE_OPTIONS = (
    "-preset ultrafast "      # أقصى سرعة تشفير
    "-tune zerolatency "      # أقل تأخير ممكن
    "-f flv "                 # الصيغة الافتراضية
)

# متغيرات الحالة
autoend = {}
counter = {}

# =======================================================================
# 🛡️ 4. ERROR HANDLING DECORATORS
# =======================================================================

def capture_internal_err(func):
    """
    مزخرف (Decorator) وظيفته التقاط أي خطأ يحدث داخل الدوال الحساسة
    ومنع البوت من التوقف (Crash) مع تسجيل الخطأ بشكل مفصل.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # استخراج تفاصيل الخطأ
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            
            error_message = f"⚠️ [CallEngine Error] -> {e}"
            debug_info = f"   File: {fname}, Line: {exc_tb.tb_lineno}, Func: {func.__name__}"
            
            LOGGER(__name__).error(error_message)
            LOGGER(__name__).debug(debug_info)
            
            # في حالة الضرورة القصوى، يمكن إعادة رفع الخطأ، ولكن هنا نكتفي بالتسجيل
            return None
    return wrapper

# =======================================================================
# 🎬 5. MEDIA STREAM FACTORY
# =======================================================================

def create_media_stream(
    path: str, 
    video: bool = False, 
    image: str = None, 
    ffmpeg_params: str = None
) -> MediaStream:
    """
    يقوم بإنشاء كائن MediaStream مع إعدادات FFMPEG المتقدمة.
    """
    
    # 1. إعدادات الصوت (ثابتة للأداء العالي)
    audio_q = AudioQuality.HIGH  # أو STUDIO لو السيرفر قوي
    
    # 2. إعدادات الفيديو (تعتمد على الطلب)
    if video:
        video_q = VideoQuality.HD_720p
        video_flags = MediaStream.Flags.REQUIRED
    else:
        video_q = VideoQuality.SD_480p # قيمة افتراضية لتجنب الأخطاء
        video_flags = MediaStream.Flags.IGNORE
        
    # 3. بناء أوامر FFMPEG
    # إضافة تحسينات الشبكة
    base_cmd = (
        f"{FFMPEG_BASE_OPTIONS} "
        f"-maxrate {FFMPEG_MAX_RATE} "
        f"-bufsize {FFMPEG_BUFFER_SIZE} "
    )
    
    # إذا كان هناك باراميترات إضافية (مثل Seek)
    final_cmd = f"{base_cmd} {ffmpeg_params}" if ffmpeg_params else base_cmd
    
    # 4. إنشاء الكائن
    stream = MediaStream(
        media_path=path,
        audio_parameters=audio_q,
        video_parameters=video_q,
        audio_flags=MediaStream.Flags.REQUIRED,
        video_flags=video_flags,
        ffmpeg_parameters=final_cmd
    )
    
    return stream

# =======================================================================
# 📞 6. THE CALL MANAGER CLASS (CORE ENGINE)
# =======================================================================

class Call:
    """
    الكلاس المسؤول عن إدارة المكالمات، التبديل بين المساعدين، وتشغيل الوسائط.
    """
    
    def __init__(self):
        self.active_calls: set[int] = set()
        
        # تهيئة العملاء (Clients)
        # يتم استخدام قائمة لتسهيل الإدارة بدلاً من المتغيرات المنفصلة
        self.clients_list = []
        self.pytgcalls_list = []
        
        # تحميل الجلسات من ملف Config
        self._load_clients()

    def _load_clients(self):
        """تحميل وتجهيز جميع المساعدين المتاحين"""
        sessions = [
            (config.STRING1, "BrandrdXMusic1"),
            (config.STRING2, "BrandrdXMusic2"),
            (config.STRING3, "BrandrdXMusic3"),
            (config.STRING4, "BrandrdXMusic4"),
            (config.STRING5, "BrandrdXMusic5"),
        ]
        
        for session_str, name in sessions:
            if session_str:
                try:
                    client = Client(
                        name=name,
                        api_id=config.API_ID,
                        api_hash=config.API_HASH,
                        session_string=session_str
                    )
                    tg_call = PyTgCalls(client)
                    
                    self.clients_list.append(client)
                    self.pytgcalls_list.append(tg_call)
                except Exception as e:
                    LOGGER(__name__).error(f"Failed to initialize assistant {name}: {e}")

        # تعيين اختصارات للمساعدين (للتوافق مع الكود القديم)
        self.one = self.pytgcalls_list[0] if len(self.pytgcalls_list) > 0 else None
        self.two = self.pytgcalls_list[1] if len(self.pytgcalls_list) > 1 else None
        self.three = self.pytgcalls_list[2] if len(self.pytgcalls_list) > 2 else None
        self.four = self.pytgcalls_list[3] if len(self.pytgcalls_list) > 3 else None
        self.five = self.pytgcalls_list[4] if len(self.pytgcalls_list) > 4 else None

        self.userbot1 = self.clients_list[0] if len(self.clients_list) > 0 else None
        self.userbot2 = self.clients_list[1] if len(self.clients_list) > 1 else None
        self.userbot3 = self.clients_list[2] if len(self.clients_list) > 2 else None
        self.userbot4 = self.clients_list[3] if len(self.clients_list) > 3 else None
        self.userbot5 = self.clients_list[4] if len(self.clients_list) > 4 else None

    async def start(self) -> None:
        """تشغيل جميع المساعدين دفعة واحدة"""
        LOGGER(__name__).info("🚀 Starting Assistant Clients...")
        if not self.pytgcalls_list:
            LOGGER(__name__).error("❌ No Assistant Clients Found! Check Config.")
            return

        tasks = [cli.start() for cli in self.pytgcalls_list]
        await asyncio.gather(*tasks)
        LOGGER(__name__).info(f"✅ Successfully started {len(self.pytgcalls_list)} assistants.")

    async def get_call_engine(self, chat_id: int) -> PyTgCalls:
        """تحديد المساعد المناسب للمجموعة"""
        try:
            # نحاول جلب المساعد المخصص للمجموعة من قاعدة البيانات
            assistant = await group_assistant(self, chat_id)
            if assistant:
                # البحث عن كائن PyTgCalls المطابق للعميل
                for i, client in enumerate(self.clients_list):
                    if client.me.id == assistant.me.id:
                        return self.pytgcalls_list[i]
            
            # الافتراضي هو المساعد الأول
            return self.one
        except Exception:
            return self.one

    # ===================================================================
    # 🔌 Connection Handler (Robust Join)
    # ===================================================================
    
    async def join_call_robust(self, assistant: PyTgCalls, chat_id: int, stream: MediaStream) -> None:
        """
        دالة الانضمام الذكية والمعالجة للأخطاء.
        تحاول الانضمام عدة مرات مع معالجة FloodWait وأخطاء الصلاحيات.
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(1, max_retries + 1):
            try:
                # محاولة التشغيل
                await assistant.play(chat_id, stream)
                LOGGER(__name__).info(f"✅ Joined call in {chat_id} successfully.")
                return

            except UserAlreadyParticipant:
                # إذا كان المساعد موجوداً بالفعل، فهذا جيد
                LOGGER(__name__).info(f"ℹ️ Assistant already in {chat_id}, checking stream...")
                try:
                    # نحاول عمل تحديث للبث فقط للتأكد
                    await assistant.play(chat_id, stream)
                except: pass
                return

            except FloodWait as e:
                # التعامل مع حظر التكرار من تيليجرام
                wait_sec = e.value
                if wait_sec > 45:
                    LOGGER(__name__).warning(f"⚠️ Heavy FloodWait ({wait_sec}s) in {chat_id}. Aborting.")
                    raise AssistantErr(f"FloodWait: {wait_sec}s")
                
                LOGGER(__name__).warning(f"⏳ FloodWait {wait_sec}s in {chat_id}. Sleeping...")
                await asyncio.sleep(wait_sec + 1)
                # إعادة المحاولة في اللفة القادمة

            except (NoActiveGroupCall, GroupCallNotFound):
                # لا توجد مكالمة جارية
                LOGGER(__name__).error(f"❌ No active call in {chat_id}.")
                raise AssistantErr("No Active Group Call. Please start a video chat.")

            except ChatAdminRequired:
                # المساعد يحتاج صلاحيات
                LOGGER(__name__).error(f"❌ Permissions missing in {chat_id}.")
                raise AssistantErr("Assistant missing permissions (Invite Users/Manage Call).")

            except Exception as e:
                LOGGER(__name__).warning(f"⚠️ Join Attempt {attempt} failed in {chat_id}: {e}")
                if attempt == max_retries:
                    raise AssistantErr(f"Failed to join after {max_retries} attempts.")
                
                await asyncio.sleep(retry_delay)
                retry_delay += 2  # زيادة وقت الانتظار تدريجياً (Exponential Backoff)

    # ===================================================================
    # 🎮 Playback Controls
    # ===================================================================

    @capture_internal_err
    async def stop_stream(self, chat_id: int) -> None:
        """إيقاف البث وتنظيف البيانات"""
        assistant = await self.get_call_engine(chat_id)
        await _clear_(chat_id)
        if chat_id in self.active_calls:
            try:
                await assistant.leave_call(chat_id)
            except Exception:
                pass
            finally:
                self.active_calls.discard(chat_id)

    @capture_internal_err
    async def force_stop_stream(self, chat_id: int) -> None:
        """إيقاف إجباري (لأوامر الأدمن)"""
        assistant = await self.get_call_engine(chat_id)
        try:
            check = db.get(chat_id)
            if check: check.pop(0)
        except: pass
        
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await _clear_(chat_id)
        
        if chat_id in self.active_calls:
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
        """تخطي الأغنية الحالية وتشغيل الرابط التالي"""
        assistant = await self.get_call_engine(chat_id)
        stream = create_media_stream(path=link, video=bool(video), image=image)
        await self.join_call_robust(assistant, chat_id, stream)

    @capture_internal_err
    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str) -> None:
        """تقديم أو تأخير الأغنية"""
        assistant = await self.get_call_engine(chat_id)
        # باراميترات FFMPEG للتقديم
        params = f"-ss {to_seek} -to {duration}"
        stream = create_media_stream(path=file_path, video=(mode == "video"), ffmpeg_params=params)
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def speedup_stream(self, chat_id: int, file_path: str, speed: float, playing: list) -> None:
        """تغيير سرعة التشغيل"""
        if not playing or not isinstance(playing, list): return
        
        assistant = await self.get_call_engine(chat_id)
        
        # إنشاء ملف مؤقت للسرعة الجديدة
        base = os.path.basename(file_path)
        playback_dir = os.path.join(os.getcwd(), "playback", str(speed))
        if not os.path.exists(playback_dir):
            os.makedirs(playback_dir, exist_ok=True)
            
        out_file = os.path.join(playback_dir, base)

        # معالجة الملف باستخدام FFMPEG إذا لم يكن موجوداً
        if not os.path.exists(out_file):
            video_speed = str(2.0 / float(speed)) # معادلة عكسية للفيديو
            
            # أمر معالجة الصوت والفيديو
            cmd = (
                f'ffmpeg -i "{file_path}" '
                f'-filter:v "setpts={video_speed}*PTS" '
                f'-filter:a "atempo={speed}" '
                f'-y "{out_file}"'
            )
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

        # حساب المدة الجديدة
        dur = int(await asyncio.get_event_loop().run_in_executor(None, check_duration, out_file))
        played_time, con_seconds = speed_converter(playing[0]["played"], speed)
        duration_min = seconds_to_min(dur)
        
        # تشغيل الملف الجديد
        params = f"-ss {played_time} -to {duration_min}"
        stream = create_media_stream(
            path=out_file, 
            video=(playing[0]["streamtype"] == "video"), 
            ffmpeg_params=params
        )

        if chat_id in db and db[chat_id] and db[chat_id][0].get("file") == file_path:
            await assistant.play(chat_id, stream)
            # تحديث قاعدة البيانات بالمعلومات الجديدة
            db[chat_id][0].update({
                "played": con_seconds,
                "dur": duration_min,
                "seconds": dur,
                "speed_path": out_file,
                "speed": speed,
                "old_dur": db[chat_id][0].get("dur"),
                "old_second": db[chat_id][0].get("seconds"),
            })

    # ===================================================================
    # ▶️ Main Play Function
    # ===================================================================
    
    @capture_internal_err
    async def join_call(self, chat_id: int, original_chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None) -> None:
        """الانضمام الأولي للمكالمة وتشغيل الرابط"""
        assistant = await self.get_call_engine(chat_id)
        stream = create_media_stream(path=link, video=bool(video), image=image)
        await self.join_call_robust(assistant, chat_id, stream)
        
        self.active_calls.add(chat_id)
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video: await add_active_video_chat(chat_id)
        
        # تفعيل خاصية الخروج التلقائي إذا كان المساعد وحده
        if await is_autoend():
            counter[chat_id] = {}
            try:
                participants = await assistant.get_participants(chat_id)
                if len(participants) <= 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except: pass

    @capture_internal_err
    async def play(self, client, chat_id: int) -> None:
        """
        محرك التشغيل الرئيسي: يجلب الأغنية التالية من الطابور (Queue) ويشغلها.
        """
        # التأكد من العميل
        if isinstance(client, Client):
            client = await self.get_call_engine(chat_id)
            
        # 1. جلب حالة الطابور (Queue)
        queue = db.get(chat_id)
        if not queue:
            # الطابور فارغ
            await _clear_(chat_id)
            return await self.stop_stream(chat_id)
            
        # 2. إدارة التكرار (Loop)
        loop_count = await get_loop(chat_id)
        popped_track = None
        
        try:
            if loop_count == 0:
                # إزالة الأغنية المنتهية
                popped_track = queue.pop(0)
            else:
                # تكرار الأغنية
                loop_count -= 1
                await set_loop(chat_id, loop_count)
            
            # تنظيف الملفات المؤقتة للأغنية السابقة
            if popped_track:
                await auto_clean(popped_track)
                
            # التحقق مرة أخرى بعد الحذف
            if not queue:
                await _clear_(chat_id)
                return await self.stop_stream(chat_id)
                
        except IndexError:
            await _clear_(chat_id)
            return await self.stop_stream(chat_id)

        # 3. تجهيز بيانات الأغنية التالية
        next_track = queue[0]
        file_path = next_track["file"]
        title = (next_track["title"]).title()
        user = next_track["by"]
        original_chat_id = next_track["chat_id"]
        streamtype = next_track["streamtype"]
        videoid = next_track["vidid"]
        duration_txt = next_track["dur"]
        
        # إعادة تعيين عداد التشغيل
        db[chat_id][0]["played"] = 0
        
        # تحديد نوع الوسائط
        is_video = (str(streamtype) == "video")
        
        # استعادة المدة الأصلية (في حالة تم تسريع الأغنية سابقاً)
        old_dur = next_track.get("old_dur")
        if old_dur:
            db[chat_id][0]["dur"] = old_dur
            db[chat_id][0]["seconds"] = next_track.get("old_second")
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0

        # 4. محاولة التشغيل حسب النوع
        try:
            # جلب الصورة المصغرة
            try: 
                img = await get_thumb(videoid)
            except: 
                img = config.STREAM_IMG_URL

            stream_obj = None

            # --- النوع A: بث مباشر (Live) ---
            if "live_" in file_path:
                status, link = await YouTube.video(videoid, True)
                if status == 0:
                    # فشل في جلب الرابط المباشر
                    return await app.send_message(original_chat_id, text=_["call_6"])
                
                stream_obj = create_media_stream(path=link, video=is_video, image=img)
                await self.join_call_robust(client, chat_id, stream_obj)
                
                # إرسال رسالة التشغيل
                await self._send_play_message(original_chat_id, videoid, title, duration_txt, user, is_video, _, chat_id, img, "live")

            # --- النوع B: يوتيوب فيديو/صوت (Vid/Aud) ---
            elif "vid_" in file_path:
                mystic = await app.send_message(original_chat_id, _["call_7"]) # "جاري التحميل..."
                try:
                    # تحميل الملف
                    downloaded_file, _ = await YouTube.download(
                        videoid, 
                        mystic, 
                        videoid=True, 
                        video=is_video
                    )
                except Exception as e:
                    LOGGER(__name__).error(f"Download failed: {e}")
                    return await mystic.edit_text(_["call_6"])
                
                stream_obj = create_media_stream(path=downloaded_file, video=is_video, image=img)
                await self.join_call_robust(client, chat_id, stream_obj)
                await mystic.delete()
                
                await self._send_play_message(original_chat_id, videoid, title, duration_txt, user, is_video, _, chat_id, img, "vid")

            # --- النوع C: روابط خارجية (Index) ---
            elif "index_" in file_path:
                # videoid هنا يحتوي على الرابط المباشر
                stream_obj = create_media_stream(path=videoid, video=is_video, image=img)
                await self.join_call_robust(client, chat_id, stream_obj)
                
                await self._send_play_message(original_chat_id, videoid, title, duration_txt, user, is_video, _, chat_id, img, "index")

            # --- النوع D: ملفات محلية أو أخرى ---
            else:
                stream_obj = create_media_stream(path=file_path, video=is_video, image=img)
                await self.join_call_robust(client, chat_id, stream_obj)
                
                await self._send_play_message(original_chat_id, videoid, title, duration_txt, user, is_video, _, chat_id, img, streamtype)

        except Exception as e:
            LOGGER(__name__).error(f"❌ Critical Play Error in {chat_id}: {e}")
            await _clear_(chat_id)

    # -------------------------------------------------------------------
    # Helper: Send Playing Message
    # -------------------------------------------------------------------
    async def _send_play_message(self, chat_id, videoid, title, duration, user, is_video, lang_str, db_chat_id, img, stream_type):
        """دالة مساعدة لإرسال رسالة 'يعمل الآن' بشكل موحد"""
        try:
            # تحديد الأزرار (Buttons)
            if stream_markup2:
                buttons = stream_markup2(lang_str, db_chat_id)
            else:
                buttons = stream_markup(lang_str, videoid, db_chat_id)

            # تحديد الصورة والرابط
            photo = img
            link = f"https://t.me/{app.username}?start=info_{videoid}"
            markup_type = "stream"

            if videoid == "telegram":
                photo = config.TELEGRAM_VIDEO_URL if is_video else config.TELEGRAM_AUDIO_URL
                link = config.SUPPORT_CHAT
            elif videoid == "soundcloud":
                photo = config.SOUNCLOUD_IMG_URL
                link = config.SUPPORT_CHAT
            elif stream_type == "index":
                photo = config.STREAM_IMG_URL
                markup_type = "tg"

            # النص
            caption = lang_str["stream_1"].format(link, title[:23], duration, user)
            if stream_type == "index":
                caption = lang_str["stream_2"].format(user)

            # الإرسال
            msg = await app.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            # تحديث قاعدة البيانات بمعرف الرسالة (للتحكم بها لاحقاً)
            if db_chat_id in db:
                db[db_chat_id][0]["mystic"] = msg
                db[db_chat_id][0]["markup"] = markup_type

        except Exception as e:
            LOGGER(__name__).warning(f"Failed to send playing message: {e}")

    @capture_internal_err
    async def ping(self) -> str:
        """قياس سرعة استجابة المساعدين (Ping)"""
        pings = []
        for cli in self.pytgcalls_list:
            try:
                # التحقق مما إذا كانت خاصية ping مدعومة
                if hasattr(cli, "ping"):
                    pings.append(cli.ping)
            except: pass
            
        if not pings:
            return "0.0"
        
        avg_ping = sum(pings) / len(pings)
        return str(round(avg_ping, 3))

    # ===================================================================
    # 🔄 Updates Decorator (Event Listener)
    # ===================================================================
    @capture_internal_err
    async def decorators(self) -> None:
        """
        يقوم بتسجيل معالج التحديثات لجميع المساعدين.
        يستمع لانتهاء الأغاني أو خروج البوت من المكالمة.
        """
        
        async def unified_update_handler(client: PyTgCalls, update: Update):
            try:
                # 1. حالة انتهاء البث (Stream Ended)
                if isinstance(update, StreamEnded):
                    # التحقق من أن الانتهاء للصوت (وليس الفيديو فقط) لتجنب التكرار
                    if update.stream_type == StreamEnded.Type.AUDIO:
                        chat_id = update.chat_id
                        LOGGER(__name__).info(f"🎵 Stream ended in {chat_id}. Playing next...")
                        # تشغيل التالي
                        await self.play(client, chat_id)
                
                # 2. حالة تحديث المجموعة (Chat Update)
                elif isinstance(update, ChatUpdate):
                    chat_id = update.chat_id
                    
                    # إذا تم طرد المساعد أو إغلاق المكالمة
                    if update.status in [
                        ChatUpdate.Status.KICKED,
                        ChatUpdate.Status.LEFT_GROUP,
                        ChatUpdate.Status.CLOSED_VOICE_CHAT
                    ]:
                        LOGGER(__name__).info(f"⚠️ Assistant kicked/left from {chat_id}. Stopping.")
                        await self.stop_stream(chat_id)
                        
            except Exception as e:
                LOGGER(__name__).error(f"Update Handler Error: {e}")

        # ربط المعالج بجميع العملاء
        for assistant in self.pytgcalls_list:
            try:
                assistant.on_update()(unified_update_handler)
            except Exception as e:
                LOGGER(__name__).error(f"Failed
