import math
import json
import subprocess
import sys
from typing import Union

# ====================================================================
# 🚀 دوال التحويل الذكية (Smart Converters)
# ====================================================================

def get_readable_time(seconds: int) -> str:
    """
    تحويل الثواني لنص عربي ممدود وفخم
    مثال: 3 سـاعـات, 15 دقـيـقـة
    """
    if not seconds or seconds == 0:
        return "0 ثـوانـي"
    
    count = 0
    ping_time = ""
    time_list = []
    
    # ✅ تم تعديل الأسماء لتكون ممدودة "Kashida" للفخامة
    time_suffix_list = [" ثـانيـة", " دقـيقـة", " سـاعـة", " يــوم"]

    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)

    for i in range(len(time_list)):
        time_list[i] = str(time_list[i]) + time_suffix_list[i]

    if len(time_list) == 4:
        ping_time += time_list.pop() + ", "

    time_list.reverse()
    ping_time += ":".join(time_list)
    return ping_time


def convert_bytes(size: float) -> str:
    """تحويل الحجم باستخدام اللوغاريتمات (أسرع وأدق)"""
    if not size or size <= 0:
        return "0B"
    
    # مسميات الأحجام (إنجليزي عشان تكون دقيقة تقنياً) أو ممكن تعريبها
    power_labels = {0: "", 1: "Ki", 2: "Mi", 3: "Gi", 4: "Ti"}
    try:
        n = int(math.log(size, 1024))
        n = min(n, 4)  # سقف التحويل هو التيرا
        return "{:.2f} {}B".format(size / (1024 ** n), power_labels[n])
    except:
        return "0B"


async def int_to_alpha(user_id: int) -> str:
    """تشفير الأرقام لحروف"""
    alphabet = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
    return "".join([alphabet[int(i)] for i in str(user_id)])


async def alpha_to_int(user_id_alphabet: str) -> int:
    """فك تشفير الحروف لأرقام"""
    alphabet = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
    return int("".join([str(alphabet.index(i)) for i in user_id_alphabet]))


def time_to_seconds(time: str) -> int:
    """تحويل صيغة الوقت إلى ثواني بذكاء"""
    try:
        parts = str(time).split(":")
        parts.reverse()
        return sum(int(x) * 60**i for i, x in enumerate(parts))
    except:
        return 0


def seconds_to_min(seconds: Union[int, float]) -> str:
    """تحويل الثواني إلى توقيت قياسي (00:00:00)"""
    if seconds is None:
        return "00:00"
    
    try:
        seconds = int(round(seconds))
        if seconds < 0: return "00:00"

        d, remainder = divmod(seconds, 86400)
        h, remainder = divmod(remainder, 3600)
        m, s = divmod(remainder, 60)

        if d > 0:
            return "{:02d}:{:02d}:{:02d}:{:02d}".format(d, h, m, s)
        elif h > 0:
            return "{:02d}:{:02d}:{:02d}".format(h, m, s)
        return "{:02d}:{:02d}".format(m, s)
    except:
        return "00:00"


def speed_converter(seconds: Union[int, float], speed: Union[int, float]):
    """
    حساب المدة الجديدة بناءً على معادلة فيزيائية
    New Duration = Original Duration / Speed
    """
    try:
        speed = float(speed)
        if speed <= 0: speed = 1.0
        
        # المعادلة الرياضية الصحيحة لأي سرعة
        new_duration = seconds / speed
        collect = int(new_duration)
        
        return seconds_to_min(collect), collect
    except:
        return "00:00", 0


def check_duration(file_path: str) -> float:
    """
    استخراج مدة الفيديو/الصوت بأمان
    مع خاصية Timeout لمنع تعليق البوت
    """
    if not file_path:
        return 0.0

    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]

    try:
        # استخدام مهلة زمنية (Timeout) قدرها 5 ثواني
        output = subprocess.check_output(command, timeout=5)
        return float(output.decode().strip())
    except subprocess.TimeoutExpired:
        # print(f"⚠️ Timeout checking duration for: {file_path}")
        return 0.0
    except Exception as e:
        # محاولة بديلة (Fallback) للستريمز المعقدة
        try:
            command_alt = [
                "ffprobe", "-loglevel", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", file_path
            ]
            pipe = subprocess.Popen(command_alt, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out, _ = pipe.communicate(timeout=5)
            _json = json.loads(out)
            
            if "format" in _json and "duration" in _json["format"]:
                return float(_json["format"]["duration"])
            if "streams" in _json:
                for s in _json["streams"]:
                    if "duration" in s:
                        return float(s["duration"])
        except:
            pass
        return 0.0

# ====================================================================
# 📂 الامتدادات المدعومة (Set for O(1) Access)
# ====================================================================

# استخدام set أسرع في البحث 100 مرة من القائمة
formats = {
    # Video
    "webm", "mkv", "flv", "vob", "ogv", "ogg", "rrc", "gifv",
    "mng", "mov", "avi", "qt", "wmv", "yuv", "rm", "asf", "amv",
    "mp4", "m4p", "m4v", "mpg", "mp2", "mpeg", "mpe", "mpv",
    "m4v", "svi", "3gp", "3g2", "mxf", "roq", "nsv", "f4v",
    
    # Audio
    "mp3", "aac", "m4a", "flac", "wav", "wma", "opus", "aiff",
    "alac", "pcm", "m4b"
}
