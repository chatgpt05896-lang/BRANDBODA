import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

# تعريف فلتر الجودة العالية (LANCZOS) المتوافق مع كل الإصدارات
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

async def draw_thumb(thumbnail, title, userid, theme, duration, views, videoid):
    try:
        # تجهيز الصورة
        if os.path.isfile(thumbnail):
            source_art = Image.open(thumbnail).convert("RGBA")
        else:
            source_art = Image.new('RGBA', (500, 500), (30, 30, 30))

        # 1. الخلفية (تم إضافة LANCZOS للجودة العالية)
        background = source_art.resize((1280, 720), resample=LANCZOS)
        background = background.filter(ImageFilter.GaussianBlur(10))
        
        dark_layer = Image.new('RGBA', (1280, 720), (0, 0, 0, 40))
        background = Image.alpha_composite(background, dark_layer)

        # 2. الدائرة (بنفس إحداثياتك المظبوطة + جودة عالية)
        circle_x, circle_y = 53, 148 
        circle_diam = 416
        
        # استخدام LANCZOS هنا عشان صورة الألبوم جوه الدائرة تبقى HD
        art_for_circle = ImageOps.fit(source_art, (circle_diam, circle_diam), centering=(0.5, 0.5), method=LANCZOS)
        
        mask = Image.new('L', (circle_diam, circle_diam), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, circle_diam, circle_diam), fill=255)
        
        final_circle_art = Image.new('RGBA', (circle_diam, circle_diam), (0,0,0,0))
        final_circle_art.paste(art_for_circle, (0, 0), mask)
        
        background.paste(final_circle_art, (circle_x, circle_y), final_circle_art)

        # 3. القالب الشفاف (Overlay)
        overlay_path = "BrandrdXMusic/assets/overlay.png"
        if os.path.isfile(overlay_path):
            overlay = Image.open(overlay_path).convert("RGBA")
            # تغيير حجم القالب بجودة عالية
            overlay = overlay.resize((1280, 720), resample=LANCZOS)
            background = Image.alpha_composite(background, overlay)

        # 4. النصوص (بنفس إحداثياتك)
        draw = ImageDraw.Draw(background)
        
        f_title = get_font(42)
        f_info = get_font(32)
        f_time = get_font(24)

        # العنوان
        title_x = 601
        safe_title = truncate_text(draw, title, f_title, 1180 - title_x)
        draw.text((title_x, 180), safe_title, font=f_title, fill="white")

        # الفنان
        artist_x = 550
        artist_y = 250
        safe_user = truncate_text(draw, userid, f_info, 1180 - artist_x)
        draw.text((artist_x, artist_y), safe_user, font=f_info, fill="#cccccc")

        # المشاهدات
        views_x = 600
        draw.text((views_x, 315), views, font=f_info, fill="#aaaaaa")

        # الوقت
        bar_start_x = 500
        bar_end_x = 1150
        time_y = 390
        
        draw.text((bar_start_x, time_y), "00:00", font=f_time, fill="white")
        
        try:
            dur_width = draw.textlength(duration, font=f_time)
        except AttributeError:
            dur_width = draw.textsize(duration, font=f_time)[0]
            
        draw.text((bar_end_x - dur_width, time_y), duration, font=f_time, fill="white")

        output = f"cache/{videoid}.png"
        background.convert("RGB").save(output)
        return output
        
    except Exception as e:
        print(f"Error in draw_thumb: {e}")
        return thumbnail

async def get_thumb(videoid):
    if not os.path.exists("cache"):
        os.makedirs("cache")
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"
    url = f"https://www.youtube.com/watch?v={videoid}"
    try:
        results = VideosSearch(url, limit=1)
        for result in (await results.next())["result"]:
            try: title = result["title"]; title = re.sub("\W+", " ", title); title = title.title()
            except: title = "Unsupported Title"
            try: duration = result["duration"]
            except: duration = "Unknown"
            thumbnail = result["thumbnails"][0]["url"]
            try: views = result["viewCount"]["short"]
            except: views = "Unknown Views"
            try: channel = result["channel"]["name"]
            except: channel = "Unknown Channel"

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(f"cache/temp{videoid}.png", mode="wb")
                    await f.write(await resp.read())
                    await f.close()

        final_image = await draw_thumb(f"cache/temp{videoid}.png", title, channel, "#ff0000", duration, views, videoid)
        try: os.remove(f"cache/temp{videoid}.png")
        except: pass     
        return final_image
    except Exception as e:
        print(e)
        return YOUTUBE_IMG_URL
