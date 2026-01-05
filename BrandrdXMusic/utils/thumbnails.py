import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

# ==========================================
# 🛑 إعدادات التصميم
# ==========================================
OVAL_X, OVAL_Y = 160, 146
OVAL_W, OVAL_H = 385, 355
TEXT_X = 730
BAR_START, BAR_END = 500, 1050 
TIME_Y = 385 
BLUR_VALUE = 3

if hasattr(Image, "Resampling"):
    LANCZOS = Image.Resampling.LANCZOS
else:
    LANCZOS = Image.LANCZOS

# ==========================================
# 🛠️ دوال مساعدة
# ==========================================
def get_font(size):
    possible_fonts = [
        "BrandrdXMusic/assets/font.ttf",
        "BrandrdXMusic/font.ttf",
        "assets/font.ttf",
        "font.ttf"
    ]
    for font_path in possible_fonts:
        if os.path.isfile(font_path):
            return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()

def smart_views(views):
    try:
        if isinstance(views, str) and not views.isdigit(): return views
        count = int(views)
        if count >= 1_000_000: return f"{count / 1_000_000:.1f}M"
        if count >= 1_000: return f"{count / 1_000:.1f}K"
        return str(count)
    except: return str(views)

def get_dominant_color(pil_img):
    img = pil_img.copy().convert("RGBA").resize((1, 1), resample=0)
    return img.getpixel((0, 0))

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

def draw_shadow_text(draw, pos, text, font, fill="white"):
    x, y = pos
    draw.text((x + 2, y + 2), str(text), font=font, fill="black")
    draw.text((x, y), str(text), font=font, fill=fill)

# ==========================================
# 🎨 دالة الرسم (Internal)
# ==========================================
async def draw_thumb(thumbnail, title, userid, theme, duration, views, videoid):
    try:
        if not userid: userid = "Music Bot"

        if os.path.isfile(thumbnail):
            source_art = Image.open(thumbnail).convert("RGBA")
        else:
            source_art = Image.new('RGBA', (500, 500), (30, 30, 30))

        # 1. Colors
        enhancer = ImageEnhance.Color(source_art)
        source_art = enhancer.enhance(1.3)
        dom_color = get_dominant_color(source_art)
        theme_tint = (dom_color[0]//2, dom_color[1]//2, dom_color[2]//2, 150)

        # 2. Background
        background = source_art.resize((1280, 720), resample=LANCZOS)
        background = background.filter(ImageFilter.GaussianBlur(BLUR_VALUE))
        tint_layer = Image.new('RGBA', (1280, 720), theme_tint)
        background = Image.alpha_composite(background, tint_layer)

        # 3. Circle/Oval
        art_for_circle = ImageOps.fit(source_art, (OVAL_W, OVAL_H), centering=(0.5, 0.5), method=LANCZOS)
        mask = Image.new('L', (OVAL_W, OVAL_H), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, OVAL_W, OVAL_H), fill=255)
        
        glow_size = 15
        glow_mask = mask.filter(ImageFilter.GaussianBlur(glow_size))
        background.paste(dom_color, (OVAL_X - glow_size, OVAL_Y - glow_size), mask.resize((OVAL_W + glow_size*2, OVAL_H + glow_size*2)))
        background.paste(art_for_circle, (OVAL_X, OVAL_Y), mask)

        # 4. Overlay (MyDesign)
        overlay = None
        possible_paths = [
            "mydesign.png",
            "BrandrdXMusic/assets/mydesign.png",
            "assets/mydesign.png"
        ]
        for path in possible_paths:
            if os.path.isfile(path):
                overlay = Image.open(path).convert("RGBA")
                break
        
        if overlay:
            overlay = overlay.resize((1280, 720), resample=LANCZOS)
            background = Image.alpha_composite(background, overlay)

        # 5. Text
        draw = ImageDraw.Draw(background)
        
        f_title, safe_title = fit_text(draw, title, 42, 500)
        draw_shadow_text(draw, (TEXT_X, 185), safe_title, f_title, fill="white")

        f_info = get_font(30)
        draw_shadow_text(draw, (TEXT_X, 255), f"Added By: {str(userid)}", f_info, fill="#cccccc")
        draw_shadow_text(draw, (TEXT_X, 320), f"Views: {smart_views(views)}", f_info, fill="#aaaaaa")

        f_time = get_font(26)
        draw.line([(BAR_START, TIME_Y + 10), (BAR_END, TIME_Y + 10)], fill=(255, 255, 255, 100), width=4)
        draw_shadow_text(draw, (BAR_START, TIME_Y), "00:00", f_time)
        draw_shadow_text(draw, (BAR_END - 50, TIME_Y), duration, f_time)

        output = f"cache/{videoid}.png"
        background.convert("RGB").save(output)
        return output
        
    except Exception as e:
        print(f"Error in draw_thumb: {e}")
        return thumbnail

# ==========================================
# 🚀 الدوال الأساسية (Required Functions)
# ==========================================

# 1. gen_thumb: دي الدالة اللي البوت بيسأل عليها
async def gen_thumb(videoid, userid="Music Bot"):
    if not os.path.exists("cache"):
        os.makedirs("cache")
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"
    
    url = f"https://www.youtube.com/watch?v={videoid}"
    try:
        results = VideosSearch(url, limit=1)
        for result in (await results.next())["result"]:
            try: title = result["title"]; title = re.sub("\W+", " ", title); title = title.title()
            except: title = "Unknown Track"
            try: duration = result["duration"]
            except: duration = "00:00"
            thumbnail = result["thumbnails"][0]["url"]
            try: views = result["viewCount"]["short"]
            except: views = "Unknown Views"

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(f"cache/temp{videoid}.png", mode="wb")
                    await f.write(await resp.read())
                    await f.close()

        final_image = await draw_thumb(f"cache/temp{videoid}.png", title, userid, "#ff0000", duration, views, videoid)
        
        try: os.remove(f"cache/temp{videoid}.png")
        except: pass     
        return final_image
        
    except Exception as e:
        print(e)
        return YOUTUBE_IMG_URL

# 2. get_thumb: دي عشان التوافق مع الملفات القديمة
async def get_thumb(videoid):
    return await gen_thumb(videoid, userid="Music Bot")
