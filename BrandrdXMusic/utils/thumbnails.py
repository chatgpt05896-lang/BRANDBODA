import os
import re
import asyncio
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

# 🟢 مكتبات دعم اللغة العربية
import arabic_reshaper
from bidi.algorithm import get_display

# ==================================================================
# ⚙️ الإحداثيات والإعدادات
# ==================================================================

# إحداثيات الدائرة (مكان الصورة)
BOX_LEFT = 115
BOX_TOP = 120
BOX_RIGHT = 453
BOX_BOTTOM = 392

ART_POS = (BOX_LEFT, BOX_TOP)
ART_WIDTH = BOX_RIGHT - BOX_LEFT   
ART_HEIGHT = BOX_BOTTOM - BOX_TOP  
ART_SIZE = (ART_WIDTH, ART_HEIGHT)

# إحداثيات النصوص
TEXT_X_AXIS = 520
POS_NAME = (TEXT_X_AXIS, 170)
POS_BY = (TEXT_X_AXIS, 240)
POS_VIEWS = (TEXT_X_AXIS, 310)

# إحداثيات الوقت (تم الرفع 6 بكسل: 504 -> 498) ⬆️
TIME_Y_AXIS = 498
POS_TIME_START = (60, TIME_Y_AXIS)
POS_TIME_END = (1160, TIME_Y_AXIS)

# الألوان
COLOR_VIEWS = "#00d4ff"
COLOR_BY = "#cccccc"
COLOR_NAME = "white"
COLOR_GLOW = "#00d4ff"

# ==================================================================
# 🛠️ الدوال المساعدة
# ==================================================================

if hasattr(Image, "Resampling"):
    LANCZOS = Image.Resampling.LANCZOS
else:
    LANCZOS = Image.LANCZOS

def get_font(size):
    potential_paths = [
        "font.ttf",                      # الأولوية للملف الرئيسي
        "BrandrdXMusic/assets/font.ttf",
        "assets/font.ttf",
        "files/font.ttf"
    ]
    for path in potential_paths:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def fix_text(text):
    text = str(text)
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text
    except:
        return text

def smart_truncate(draw, text, font, max_width):
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
    x, y = pos
    draw.text((x + 2, y + 2), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=color)

def draw_neon_text(base_img, pos, text, font):
    text = fix_text(text)
    glow_layer = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.text(pos, text, font=font, fill=COLOR_GLOW)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=6))
    base_img.alpha_composite(glow_layer)
    final_draw = ImageDraw.Draw(base_img)
    final_draw.text(pos, text, font=font, fill=(255, 255, 255, 230))

# ==================================================================
# 🎨 دالة الرسم الرئيسية
# ==================================================================

async def draw_thumb(thumbnail_path, title, userid, theme, duration, views, videoid):
    try:
        # تجهيز البيانات
        title = str(title or "Unknown Track")
        userid = str(userid or "Unknown Artist")
        views = str(views or "0")
        duration = str(duration or "00:00")

        # 1. الخلفية (Background)
        if os.path.exists(thumbnail_path):
            try:
                source = Image.open(thumbnail_path).convert("RGBA")
            except:
                source = Image.new('RGBA', (1280, 720), (30, 30, 30))
        else:
            source = Image.new('RGBA', (1280, 720), (30, 30, 30))

        background = source.resize((1280, 720), resample=LANCZOS)
        background = background.filter(ImageFilter.GaussianBlur(40))
        dark_layer = Image.new('RGBA', (1280, 720), (0, 0, 0, 180))
        background = Image.alpha_composite(background, dark_layer)

        # 2. وضع صورة الألبوم (Art) - الخطوة دي الأول عشان تبقى "ورا"
        try:
            art_cropped = ImageOps.fit(source, ART_SIZE, centering=(0.5, 0.5), method=LANCZOS)
            mask = Image.new('L', ART_SIZE, 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.ellipse((0, 0, ART_WIDTH, ART_HEIGHT), fill=255)
            # اللصق
            background.paste(art_cropped, ART_POS, mask)
        except Exception as e:
            print(f"[Thumb] Art Error: {e}")

        # 3. وضع القالب (Overlay) - الخطوة دي التانية عشان يبقى "قدام"
        overlay_path = "BrandrdXMusic/assets/overlay.png"
        if not os.path.isfile(overlay_path):
            overlay_path = "assets/overlay.png"

        if os.path.isfile(overlay_path):
            try:
                overlay = Image.open(overlay_path).convert("RGBA")
                overlay = overlay.resize((1280, 720), resample=LANCZOS)
                # لصق القالب فوق الصورة
                background.paste(overlay, (0, 0), overlay)
            except: pass

        # 4. الكتابة
        draw = ImageDraw.Draw(background)
        f_50 = get_font(50)
        f_35 = get_font(35)
        f_30 = get_font(30)

        safe_title = smart_truncate(draw, title, f_50, 600)
        draw_shadowed_text(draw, POS_NAME, f"Name: {safe_title}", f_50, COLOR_NAME)
        
        safe_artist = smart_truncate(draw, userid, f_35, 550)
        draw_shadowed_text(draw, POS_BY, f"By: {safe_artist}", f_35, COLOR_BY)
        
        fmt_views = format_views(views)
        full_views = fix_text(f"Views: {fmt_views}")
        draw_shadowed_text(draw, POS_VIEWS, full_views, f_30, COLOR_VIEWS)

        draw_neon_text(background, POS_TIME_START, "00:00", f_30)
        draw_neon_text(background, POS_TIME_END, duration, f_30)

        # 5. الحفظ
        if not os.path.exists("cache"): os.makedirs("cache")
        final_path = f"cache/{videoid}_final.png"
        background.save(final_path, format="PNG")
        return final_path

    except Exception as e:
        print(f"[Thumb] Error: {e}")
        return thumbnail_path

async def gen_thumb(videoid, user_id=None):
    if not os.path.exists("cache"): os.makedirs("cache")
    final_path = f"cache/{videoid}_final.png"
    if os.path.isfile(final_path): return final_path

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
        if data.get("thumbnails"): candidates.append(data["thumbnails"][-1]["url"])

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
        if os.path.exists(temp_path): os.remove(temp_path)
        return final

    except Exception as e:
        print(f"[Gen] Error: {e}")
        return YOUTUBE_IMG_URL

get_thumb = gen_thumb
