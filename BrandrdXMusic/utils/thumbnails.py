import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance, ImageChops
from config import YOUTUBE_IMG_URL, START_IMG_URL

# ==========================================
# 🧠 إعدادات الذكاء (Smart Config)
# ==========================================
OVAL_X, OVAL_Y = 160, 146
OVAL_W, OVAL_H = 385, 355

# إحداثيات النصوص
TEXT_X = 730
BAR_START = 500
BAR_END = 1150
TIME_Y = 390

if hasattr(Image, "Resampling"):
    LANCZOS = Image.Resampling.LANCZOS
else:
    LANCZOS = Image.LANCZOS

def get_font(size):
    possible_fonts = ["BrandrdXMusic/assets/font.ttf", "BrandrdXMusic/font.ttf", "assets/font.ttf", "font.ttf"]
    for font_path in possible_fonts:
        if os.path.isfile(font_path): return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()

# 🧠 دالة ذكية: استخراج اللون الغالب من الصورة
def get_dominant_color(pil_img):
    img = pil_img.copy()
    img = img.convert("RGBA")
    img = img.resize((1, 1), resample=0)
    dominant_color = img.getpixel((0, 0))
    return dominant_color

# 🧠 دالة ذكية: تنسيق الأرقام
def smart_views(views):
    try:
        if isinstance(views, str) and not views.isdigit(): return views
        count = int(views)
        if count >= 1_000_000: return f"{count / 1_000_000:.1f}M"
        if count >= 1_000: return f"{count / 1_000:.1f}K"
        return str(count)
    except: return str(views)

# 🧠 دالة ذكية: رسم نص مع ظل (عشان الوضوح)
def draw_text_with_shadow(draw, pos, text, font, fill="white", shadow_color="black", offset=(2, 2)):
    x, y = pos
    # رسم الظل أولاً
    draw.text((x + offset[0], y + offset[1]), text, font=font, fill=shadow_color)
    # رسم النص الأصلي
    draw.text((x, y), text, font=font, fill=fill)

# 🧠 دالة ذكية: تصغير الخط
def fit_text(draw, text, initial_size, max_width):
    size = initial_size
    font = get_font(size)
    while size > 20:
        try: w = draw.textlength(text, font=font)
        except: w = draw.textsize(text, font=font)[0]
        if w <= max_width: return font, text
        size -= 2
        font = get_font(size)
    
    truncated = text
    while len(truncated) > 0:
        truncated = truncated[:-1]
        try: w = draw.textlength(truncated + "...", font=font)
        except: w = draw.textsize(truncated + "...", font=font)[0]
        if w <= max_width: return font, truncated + "..."
    return font, text

async def get_video_info(videoid):
    image_url = f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg"
    title, duration, views, channel = "Unknown Track", "00:00", "0", "Music Bot"
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(f"cache/temp{videoid}.jpg", mode="wb")
                await f.write(await resp.read()); await f.close()
                return f"cache/temp{videoid}.jpg", title, duration, views, channel
            else:
                async with session.get(f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg") as resp2:
                    if resp2.status == 200:
                        f = await aiofiles.open(f"cache/temp{videoid}.jpg", mode="wb")
                        await f.write(await resp2.read()); await f.close()
                        return f"cache/temp{videoid}.jpg", title, duration, views, channel
    return YOUTUBE_IMG_URL, title, duration, views, channel

async def gen_thumb(videoid, user_id=None, theme=None):
    if os.path.isfile(f"cache/{videoid}.png"): return f"cache/{videoid}.png"
    thumbnail_path, title, duration, views, channel = await get_video_info(videoid)

    try:
        if os.path.isfile(thumbnail_path):
            source_art = Image.open(thumbnail_path).convert("RGBA")
        else:
            source_art = Image.open(await aiofiles.open(START_IMG_URL, "rb")).convert("RGBA")

        # 1. 🧠 تحسين ألوان الصورة (Enhance)
        enhancer = ImageEnhance.Color(source_art)
        source_art = enhancer.enhance(1.3) # تزويد التشبع اللوني 30%

        # 2. 🧠 استخراج لون الثيم (Theme Color)
        dom_color = get_dominant_color(source_art)
        # نخلي اللون غامق شوية عشان الخلفية
        theme_tint = (dom_color[0]//2, dom_color[1]//2, dom_color[2]//2, 200)

        # 3. تجهيز الخلفية
        background = source_art.resize((1280, 720), resample=LANCZOS)
        background = background.filter(ImageFilter.GaussianBlur(15)) # Blur background
        
        # إضافة طبقة لونية مقتبسة من الصورة (بدل الأسود السادة)
        tint_layer = Image.new('RGBA', (1280, 720), theme_tint)
        background = Image.alpha_composite(background, tint_layer)

        # 4. قص وتركيب الصورة البيضاوية (الوزنة)
        art_for_circle = ImageOps.fit(source_art, (OVAL_W, OVAL_H), centering=(0.5, 0.5), method=LANCZOS)
        mask = Image.new('L', (OVAL_W, OVAL_H), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, OVAL_W, OVAL_H), fill=255)
        
        # إضافة توهج (Glow) خفيف حول الصورة البيضاوية
        glow_size = 10
        glow_mask = mask.filter(ImageFilter.GaussianBlur(glow_size))
        background.paste(dom_color, (OVAL_X - glow_size, OVAL_Y - glow_size), mask.resize((OVAL_W + glow_size*2, OVAL_H + glow_size*2)))
        
        # لصق الصورة
        background.paste(art_for_circle, (OVAL_X, OVAL_Y), mask)

        # 5. القالب
        overlay_path = "mydesign.png"
        if os.path.isfile(overlay_path):
            overlay = Image.open(overlay_path).convert("RGBA")
            overlay = overlay.resize((1280, 720), resample=LANCZOS)
            background = Image.alpha_composite(background, overlay)

        # 6. الكتابة الذكية
        draw = ImageDraw.Draw(background)
        
        # العنوان
        smart_font_title, smart_title_text = fit_text(draw, title, 40, 500)
        draw_text_with_shadow(draw, (TEXT_X, 185), smart_title_text, smart_font_title)

        # المعلومات (Added By + Views)
        f_info = get_font(30)
        draw_text_with_shadow(draw, (TEXT_X, 255), f"Added By: {user_id or 'Bot'}", f_info, fill="#eeeeee")
        draw_text_with_shadow(draw, (TEXT_X, 320), f"Views: {smart_views(views)}", f_info, fill="#cccccc")

        # 7. 🧠 رسم شريط التشغيل (Progress Bar)
        # رسم خط خلفي باهت
        draw.line([(BAR_START, TIME_Y - 10), (BAR_END, TIME_Y - 10)], fill=(255, 255, 255, 50), width=4)
        # رسم نقطة بداية (وهمية كأنها مشغل)
        draw.ellipse([(BAR_START - 5, TIME_Y - 15), (BAR_START + 5, TIME_Y - 5)], fill="white")

        # التوقيت
        f_time = get_font(25)
        draw_text_with_shadow(draw, (BAR_START, TIME_Y), "00:00", f_time)
        draw_text_with_shadow(draw, (BAR_END - 60, TIME_Y), duration, f_time)

        output_path = f"cache/{videoid}.png"
        background.convert("RGB").save(output_path)
        
        if os.path.exists(thumbnail_path) and "temp" in thumbnail_path: os.remove(thumbnail_path)
        return output_path

    except Exception as e:
        print(f"Error generating thumb: {e}")
        return YOUTUBE_IMG_URL

async def get_thumb(videoid):
    return await gen_thumb(videoid, user_id="Bot")
