import os
import re
import asyncio
import aiofiles
import aiohttp
import traceback
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

# 🟢 محاولة استيراد مكتبات العربي
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    print("⚠️ Arabic libraries missing. Installing fallback...")
    def get_display(text): return str(text)
    class arabic_reshaper:
        @staticmethod
        def reshape(text): return str(text)

# ==================================================================
# ⚙️ الإحداثيات والإعدادات
# ==================================================================

# إحداثيات الدائرة
BOX_LEFT = 115
BOX_TOP = 122
BOX_RIGHT = 453
BOX_BOTTOM = 394

ART_POS = (BOX_LEFT, BOX_TOP)
ART_WIDTH = BOX_RIGHT - BOX_LEFT   
ART_HEIGHT = BOX_BOTTOM - BOX_TOP  
ART_SIZE = (ART_WIDTH, ART_HEIGHT)

# إحداثيات النصوص
TEXT_X_AXIS = 520
POS_NAME = (TEXT_X_AXIS, 170)
POS_BY = (TEXT_X_AXIS, 240)
POS_VIEWS = (TEXT_X_AXIS, 310)

# إحداثيات الوقت
TIME_Y_AXIS = 500
POS_TIME_START = (60, TIME_Y_AXIS)
POS_TIME_END = (1160, TIME_Y_AXIS)

# الألوان
COLOR_VIEWS = "#00d4ff"
COLOR_BY = "#cccccc"
COLOR_NAME = "white"
COLOR_GLOW = "#00d4ff"

# ==================================================================
# 🛠️ معالجة الخطوط (الحل الجذري)
# ==================================================================

if hasattr(Image, "Resampling"):
    LANCZOS = Image.Resampling.LANCZOS
else:
    LANCZOS = Image.LANCZOS

# مسار الخط الإجباري
FORCED_FONT_PATH = "cache/Cairo-Bold.ttf"

async def force_download_font():
    """يحمل الخط بأي طريقة ممكنة (Python أو System)"""
    if os.path.exists(FORCED_FONT_PATH):
        return

    if not os.path.exists("cache"):
        try: os.makedirs("cache")
        except: pass

    url = "https://github.com/google/fonts/raw/main/ofl/cairo/Cairo-Bold.ttf"
    print(f"⏳ Attempting to download font to {FORCED_FONT_PATH}...")

    # الطريقة 1: باستخدام Python aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    async with aiofiles.open(FORCED_FONT_PATH, "wb") as f:
                        await f.write(data)
                    print("✅ Font downloaded via Python!")
                    return
    except Exception as e:
        print(f"⚠️ Python download failed: {e}")

    # الطريقة 2: باستخدام أوامر النظام (wget/curl) - حل الطوارئ
    try:
        print("🔄 Trying system download (wget/curl)...")
        subprocess.run(["wget", "-O", FORCED_FONT_PATH, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(FORCED_FONT_PATH): return
        
        subprocess.run(["curl", "-o", FORCED_FONT_PATH, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(FORCED_FONT_PATH): return
    except Exception as e:
        print(f"⚠️ System download failed: {e}")

def get_font(size):
    # 1. الأولوية القصوى للخط اللي حملناه
    if os.path.exists(FORCED_FONT_PATH):
        try:
            return ImageFont.truetype(FORCED_FONT_PATH, size)
        except: pass

    # 2. خطوط احتياطية
    backups = [
        "BrandrdXMusic/assets/font.ttf",
        "assets/font.ttf",
        "font.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "C:\\Windows\\Fonts\\arial.ttf" # لو شغال على ويندوز
    ]
    
    for path in backups:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except: continue
            
    # 3. لو كله فشل، ده اللي بيطلع مربعات (للأسف مفيش حل غيره لو مفيش خطوط)
    return ImageFont.load_default()

def fix_text(text):
    text = str(text)
    try:
        # تبسيط المعالجة
        reshaped = arabic_reshaper.reshape(text)
        bidi = get_display(reshaped)
        return bidi
    except:
        return text

def smart_truncate(draw, text, font, max_width):
    try:
        display_text = fix_text(text)
        try:
            w = draw.textlength(display_text, font=font)
        except:
            w = draw.textsize(display_text, font=font)[0]
        
        if w <= max_width:
            return display_text
        
        text = str(text)
        for i in range(len(text), 0, -1):
            temp_text = text[:i] + "..."
            temp_display = fix_text(temp_text)
            try:
                w_temp = draw.textlength(temp_display, font=font)
            except:
                w_temp = draw.textsize(temp_display, font=font)[0]
            if w_temp <= max_width:
                return temp_display
        return "..."
    except:
        return "..."

def format_views(views):
    try:
        v = str(views).lower().replace("views", "").strip()
        if "m" in v or "k" in v: return v.upper()
        val = int(re.sub(r'\D', '', v))
        if val >= 1_000_000: return f"{val/1_000_000:.1f}M"
        elif val >= 1_000: return f"{val/1_000:.1f}K"
        else: return str(val)
    except: return str(views)

def draw_shadowed_text(draw, pos, text, font, color="white", shadow_color="black"):
    try:
        x, y = pos
        draw.text((x + 2, y + 2), text, font=font, fill=shadow_color)
        draw.text((x, y), text, font=font, fill=color)
    except: pass

def draw_neon_text(base_img, pos, text, font):
    try:
        text = fix_text(text)
        glow_layer = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        glow_draw.text(pos, text, font=font, fill=COLOR_GLOW)
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=8))
        base_img.alpha_composite(glow_layer)
        final_draw = ImageDraw.Draw(base_img)
        final_draw.text(pos, text, font=font, fill=(255, 255, 255, 240))
    except: pass

# ==================================================================
# 🎨 دالة الرسم (الكلاسيكية)
# ==================================================================

async def draw_thumb(thumbnail_path, title, userid, theme, duration, views, videoid):
    try:
        # تحميل الخلفية
        if os.path.exists(thumbnail_path):
            try:
                source = Image.open(thumbnail_path).convert("RGBA")
            except:
                source = Image.new('RGBA', (1280, 720), (30, 30, 30))
        else:
            source = Image.new('RGBA', (1280, 720), (30, 30, 30))

        try:
            background = source.resize((1280, 720), resample=LANCZOS)
            background = background.filter(ImageFilter.GaussianBlur(3))
            dark_layer = Image.new('RGBA', (1280, 720), (0, 0, 0, 100))
            background = Image.alpha_composite(background, dark_layer)
        except:
            background = Image.new('RGBA', (1280, 720), (0, 0, 0))

        # رسم الدائرة
        try:
            art_cropped = ImageOps.fit(source, ART_SIZE, centering=(0.5, 0.5), method=LANCZOS)
            mask = Image.new('L', ART_SIZE, 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.ellipse((0, 0, ART_WIDTH, ART_HEIGHT), fill=255)
            background.paste(art_cropped, ART_POS, mask)
        except: pass

        # القالب
        try:
            overlay_path = "BrandrdXMusic/assets/overlay.png"
            if not os.path.isfile(overlay_path):
                overlay_path = "assets/overlay.png"
            if os.path.isfile(overlay_path):
                overlay = Image.open(overlay_path).convert("RGBA")
                overlay = overlay.resize((1280, 720), resample=LANCZOS)
                bg_rgb = background.convert("RGB")
                ov_rgb = overlay.convert("RGB")
                merged = ImageChops.screen(bg_rgb, ov_rgb)
                background = merged.convert("RGBA")
        except: pass

        # الكتابة
        try:
            draw = ImageDraw.Draw(background)
            # استدعاء الخط (هيستخدم الخط الإجباري)
            f_50 = get_font(50)
            f_35 = get_font(35)
            f_30 = get_font(30)

            safe_title = smart_truncate(draw, str(title), f_50, 600)
            draw_shadowed_text(draw, POS_NAME, f"Name: {safe_title}", f_50, COLOR_NAME)
            
            safe_artist = smart_truncate(draw, str(userid), f_35, 550)
            draw_shadowed_text(draw, POS_BY, f"By: {safe_artist}", f_35, COLOR_BY)
            
            full_views = fix_text(f"Views: {format_views(views)}")
            draw_shadowed_text(draw, POS_VIEWS, full_views, f_30, COLOR_VIEWS)

            draw_neon_text(background, POS_TIME_START, "00:00", f_30)
            draw_neon_text(background, POS_TIME_END, str(duration), f_30)
        except Exception as e:
            print(f"Draw Text Error: {e}")

        if not os.path.exists("cache"):
            try: os.makedirs("cache")
            except: pass
            
        final_path = f"cache/{videoid}_final.png"
        background.save(final_path, format="PNG")
        return final_path

    except Exception as e:
        print(f"Draw Thumb Error: {e}")
        return thumbnail_path if os.path.exists(thumbnail_path) else YOUTUBE_IMG_URL

# ==================================================================
# 🌐 دالة التوليد
# ==================================================================

async def gen_thumb(videoid, user_id=None):
    if not os.path.exists("cache"):
        try: os.makedirs("cache")
        except: pass
        
    final_path = f"cache/{videoid}_final.png"
    if os.path.isfile(final_path): return final_path

    # 🔥🔥 تحميل الخط بالإجبار 🔥🔥
    await force_download_font()

    temp_path = f"cache/temp_{videoid}.png"
    url = f"https://www.youtube.com/watch?v={videoid}"

    try:
        search = VideosSearch(url, limit=1)
        res = await search.next()
        data = res["result"][0]
        
        title = re.sub(r"\W+", " ", data.get("title", "Unknown")).title()
        duration = data.get("duration", "00:00")
        views = data.get("viewCount", {}).get("short", "0")
        channel = data.get("channel", {}).get("name", "Unknown Artist")
        
        candidates = [
            f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg",
            f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg"
        ]
        if data.get("thumbnails"):
            candidates.append(data["thumbnails"][-1]["url"])

        downloaded = False
        async with aiohttp.ClientSession() as session:
            for u in candidates:
                try:
                    async with session.get(u, timeout=5) as r:
                        if r.status == 200:
                            d = await r.read()
                            if len(d) > 1000:
                                async with aiofiles.open(temp_path, "wb") as f:
                                    await f.write(d)
                                downloaded = True
                                break
                except: continue
                if downloaded: break
        
        if not downloaded: return YOUTUBE_IMG_URL

        final = await draw_thumb(temp_path, title, channel, None, duration, views, videoid)
        
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
            
        return final

    except Exception as e:
        print(f"Gen Thumb Error: {e}")
        return YOUTUBE_IMG_URL

get_thumb = gen_thumb
