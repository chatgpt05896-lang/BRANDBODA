import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from config import YOUTUBE_IMG_URL, START_IMG_URL

# إعداد فلتر الجودة
if hasattr(Image, "Resampling"):
    LANCZOS = Image.Resampling.LANCZOS
else:
    LANCZOS = Image.LANCZOS

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

def truncate_text(draw, text, font, max_width):
    try:
        w = draw.textlength(text, font=font)
    except AttributeError:
        w = draw.textsize(text, font=font)[0]
    if w <= max_width:
        return text
    for i in range(len(text), 0, -1):
        temp_text = text[:i] + "..."
        try:
            w_temp = draw.textlength(temp_text, font=font)
        except AttributeError:
            w_temp = draw.textsize(temp_text, font=font)[0]
        if w_temp <= max_width:
            return temp_text
    return "..."

async def get_video_info(videoid):
    image_url = f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg"
    title = "Unknown Track"
    duration = "00:00"
    views = "Views"
    channel = "Music Bot"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(f"cache/temp{videoid}.jpg", mode="wb")
                await f.write(await resp.read())
                await f.close()
                return f"cache/temp{videoid}.jpg", title, duration, views, channel
            else:
                async with session.get(f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg") as resp2:
                    if resp2.status == 200:
                        f = await aiofiles.open(f"cache/temp{videoid}.jpg", mode="wb")
                        await f.write(await resp2.read())
                        await f.close()
                        return f"cache/temp{videoid}.jpg", title, duration, views, channel
    return YOUTUBE_IMG_URL, title, duration, views, channel

# --- الدالة الرئيسية للتصميم ---
async def gen_thumb(videoid, user_id=None, theme=None):
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"

    thumbnail_path, title, duration, views, channel = await get_video_info(videoid)

    try:
        if os.path.isfile(thumbnail_path):
            source_art = Image.open(thumbnail_path).convert("RGBA")
        else:
            source_art = Image.open(await aiofiles.open(START_IMG_URL, "rb")).convert("RGBA")

        # الخلفية
        background = source_art.resize((1280, 720), resample=LANCZOS)
        background = background.filter(ImageFilter.GaussianBlur(10))
        dark_layer = Image.new('RGBA', (1280, 720), (0, 0, 0, 100))
        background = Image.alpha_composite(background, dark_layer)

        # الدائرة
        circle_x, circle_y = 53, 148 
        circle_diam = 416
        art_for_circle = ImageOps.fit(source_art, (circle_diam, circle_diam), centering=(0.5, 0.5), method=LANCZOS)
        mask = Image.new('L', (circle_diam, circle_diam), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, circle_diam, circle_diam), fill=255)
        final_circle_art = Image.new('RGBA', (circle_diam, circle_diam), (0,0,0,0))
        final_circle_art.paste(art_for_circle, (0, 0), mask)
        background.paste(final_circle_art, (circle_x, circle_y), final_circle_art)

        # القالب (Overlay)
        overlay_path = "BrandrdXMusic/assets/overlay.png"
        if os.path.isfile(overlay_path):
            overlay = Image.open(overlay_path).convert("RGBA")
            overlay = overlay.resize((1280, 720), resample=LANCZOS)
            background = Image.alpha_composite(background, overlay)

        # الكتابة
        draw = ImageDraw.Draw(background)
        f_title = get_font(40)
        f_info = get_font(30)
        f_time = get_font(25)

        text_start_x = 730 
        
        draw.text((text_start_x, 185), "Music Audio Track", font=f_title, fill="white")
        draw.text((text_start_x, 255), f"Added By: {user_id or 'User'}", font=f_info, fill="#dddddd")
        draw.text((text_start_x, 320), "Views: Like", font=f_info, fill="#bbbbbb")

        bar_start_x = 500
        bar_end_x = 1150
        time_y = 390
        draw.text((bar_start_x, time_y), "00:00", font=f_time, fill="white")
        draw.text((bar_end_x - 60, time_y), "Live", font=f_time, fill="white")

        output_path = f"cache/{videoid}.png"
        background.convert("RGB").save(output_path)
        
        if os.path.exists(thumbnail_path) and "temp" in thumbnail_path:
            os.remove(thumbnail_path)
            
        return output_path

    except Exception as e:
        print(f"Error generating thumb: {e}")
        return YOUTUBE_IMG_URL

# --- الدالة القديمة (عشان call.py ميضربش) ---
async def get_thumb(videoid):
    # بنخليها تنادي على الدالة الجديدة وخلاص
    return await gen_thumb(videoid, user_id="Bot")
