import os
import re
import asyncio
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

# ==================================================================
# ⚙️ CONFIGURATION & COORDINATES
# ==================================================================

# 1. Album Art Dimensions (Smart Box)
# الإحداثيات اللي انت حددتها بالظبط
BOX_LEFT = 115
BOX_TOP = 120
BOX_RIGHT = 453
BOX_BOTTOM = 392

# حساب العرض والارتفاع والمكان أوتوماتيكياً
ART_POS = (BOX_LEFT, BOX_TOP)
ART_WIDTH = BOX_RIGHT - BOX_LEFT   # النتيجة: 338
ART_HEIGHT = BOX_BOTTOM - BOX_TOP  # النتيجة: 272
ART_SIZE = (ART_WIDTH, ART_HEIGHT)

# 2. Text Coordinates
TEXT_X_AXIS = 520
POS_NAME = (TEXT_X_AXIS, 170)
POS_BY = (TEXT_X_AXIS, 240)
POS_VIEWS = (TEXT_X_AXIS, 310)

# 3. Time Coordinates
TIME_Y_AXIS = 504
POS_TIME_START = (60, TIME_Y_AXIS)
POS_TIME_END = (1160, TIME_Y_AXIS)

# 4. Colors
COLOR_VIEWS = "#00d4ff"   # Cyan Neon
COLOR_BY = "#cccccc"      # Light Gray
COLOR_NAME = "white"
COLOR_GLOW = "#00d4ff"    # Time Glow Color

# ==================================================================
# 🛠️ HELPER FUNCTIONS
# ==================================================================

# حل مشكلة اختلاف إصدارات Pillow
if hasattr(Image, "Resampling"):
    LANCZOS = Image.Resampling.LANCZOS
else:
    LANCZOS = Image.LANCZOS

def get_font(size):
    """
    دالة ذكية بتدور على ملف الخط في كذا مسار محتمل.
    لو ملقتهوش، بترجع الخط الافتراضي عشان الكود ميقفش.
    """
    potential_paths = [
        "BrandrdXMusic/assets/font.ttf",
        "assets/font.ttf",
        "font.ttf",
        "files/font.ttf"
    ]
    for path in potential_paths:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def smart_truncate(draw, text, font, max_width):
    """
    لو النص طويل جداً، بيقصه ويحط (...) في الآخر بحيث ميبوظش التصميم.
    """
    text = str(text)
    try:
        # Modern Pillow
        w = draw.textlength(text, font=font)
    except:
        # Old Pillow
        w = draw.textsize(text, font=font)[0]

    if w <= max_width:
        return text

    for i in range(len(text), 0, -1):
        temp_text = text[:i] + "..."
        try:
            w_temp = draw.textlength(temp_text, font=font)
        except:
            w_temp = draw.textsize(temp_text, font=font)[0]
        if w_temp <= max_width:
            return temp_text
    return "..."

def format_views(views):
    """
    تحويل الأرقام الكبيرة لـ K و M
    Example: 1500000 -> 1.5M
    """
    try:
        v = str(views).lower().replace("views", "").strip()
        if "m" in v or "k" in v:
            return v.upper()
        
        val = int(re.sub(r'\D', '', v))
        
        if val >= 1_000_000:
            return f"{val/1_000_000:.1f}M"
        elif val >= 1_000:
            return f"{val/1_000:.1f}K"
        else:
            return str(val)
    except:
        return str(views)

def draw_shadowed_text(draw, pos, text, font, color="white", shadow_color="black"):
    """
    رسم نص بظل خفيف للقراءة بوضوح.
    """
    x, y = pos
    # Shadow Layer
    draw.text((x + 2, y + 2), str(text), font=font, fill=shadow_color)
    # Main Layer
    draw.text((x, y), str(text), font=font, fill=color)

def draw_neon_text(base_img, pos, text, font):
    """
    Time Embedded in Glass Effect
    بيرسم طبقة مضيئة (Blur) وبعدين النص الحاد فوقها.
    """
    text = str(text)
    # 1. Create a transparent layer for the glow
    glow_layer = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    
    # 2. Draw the text with the glow color
    glow_draw.text(pos, text, font=font, fill=COLOR_GLOW)
    
    # 3. Apply Gaussian Blur to create the neon effect
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=6))
    
    # 4. Merge glow with background
    base_img.alpha_composite(glow_layer)
    
    # 5. Draw the sharp white text on top (slightly transparent)
    final_draw = ImageDraw.Draw(base_img)
    final_draw.text(pos, text, font=font, fill=(255, 255, 255, 230))

# ==================================================================
# 🎨 MAIN DRAWING FUNCTION (THE ARTIST)
# ==================================================================

async def draw_thumb(thumbnail_path, title, userid, theme, duration, views, videoid):
    try:
        # Data Sanitization
        title = str(title or "Unknown Track")
        userid = str(userid or "Unknown Artist")
        views = str(views or "0")
        duration = str(duration or "00:00")

        # ------------------------------------------------
        # 1. PREPARE BACKGROUND
        # ------------------------------------------------
        if os.path.exists(thumbnail_path):
            try:
                source = Image.open(thumbnail_path).convert("RGBA")
            except:
                source = Image.new('RGBA', (1280, 720), (30, 30, 30))
        else:
            source = Image.new('RGBA', (1280, 720), (30, 30, 30))

        # Resize & Heavy Blur
        background = source.resize((1280, 720), resample=LANCZOS)
        background = background.filter(ImageFilter.GaussianBlur(40))
        
        # Darkening Layer (Opacity 180/255)
        dark_layer = Image.new('RGBA', (1280, 720), (0, 0, 0, 180))
        background = Image.alpha_composite(background, dark_layer)

        # ------------------------------------------------
        # 2. PROCESS ALBUM ART (ELLIPSE CROP)
        # ------------------------------------------------
        try:
            # Crop center of image to fit the aspect ratio of our box
            art_cropped = ImageOps.fit(source, ART_SIZE, centering=(0.5, 0.5), method=LANCZOS)
            
            # Create Ellipse Mask
            mask = Image.new('L', ART_SIZE, 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.ellipse((0, 0, ART_WIDTH, ART_HEIGHT), fill=255)
            
            # Paste onto background
            background.paste(art_cropped, ART_POS, mask)
        except Exception as e:
            print(f"[Thumb] Art Processing Error: {e}")

        # ------------------------------------------------
        # 3. APPLY GLASS OVERLAY
        # ------------------------------------------------
        overlay_path = "BrandrdXMusic/assets/overlay.png"
        if not os.path.isfile(overlay_path):
            overlay_path = "assets/overlay.png"

        if os.path.isfile(overlay_path):
            try:
                overlay = Image.open(overlay_path).convert("RGBA")
                overlay = overlay.resize((1280, 720), resample=LANCZOS)
                # Paste keeps transparency clean
                background.paste(overlay, (0, 0), overlay)
            except Exception as e:
                print(f"[Thumb] Overlay Error: {e}")

        # ------------------------------------------------
        # 4. DRAW TEXT & TIME
        # ------------------------------------------------
        draw = ImageDraw.Draw(background)
        
        # Load Fonts
        font_large = get_font(50)
        font_medium = get_font(35)
        font_small = get_font(30)

        # Draw Metadata
        # Name
        safe_title = smart_truncate(draw, title, font_large, 600)
        draw_shadowed_text(draw, POS_NAME, f"Name: {safe_title}", font_large, COLOR_NAME)
        
        # Artist
        safe_artist = smart_truncate(draw, userid, font_medium, 550)
        draw_shadowed_text(draw, POS_BY, f"By: {safe_artist}", font_medium, COLOR_BY)
        
        # Views
        formatted_views = format_views(views)
        draw_shadowed_text(draw, POS_VIEWS, f"Views: {formatted_views}", font_small, COLOR_VIEWS)

        # Time (Neon Effect)
        draw_neon_text(background, POS_TIME_START, "00:00", font_small)
        draw_neon_text(background, POS_TIME_END, duration, font_small)

        # ------------------------------------------------
        # 5. SAVE & RETURN
        # ------------------------------------------------
        if not os.path.exists("cache"):
            os.makedirs("cache")
            
        final_path = f"cache/{videoid}_final.png"
        background.save(final_path, format="PNG")
        return final_path

    except Exception as e:
        print(f"[Thumb] Critical Error: {e}")
        return thumbnail_path

# ==================================================================
# 🦅 DATA FETCHER (THE LOGIC)
# ==================================================================

async def gen_thumb(videoid, user_id=None):
    """
    Main entry point.
    1. Checks cache.
    2. Fetches YouTube data.
    3. Downloads thumbnail.
    4. Calls draw_thumb.
    """
    if not os.path.exists("cache"):
        os.makedirs("cache")
        
    # 1. Check Cache
    final_path = f"cache/{videoid}_final.png"
    if os.path.isfile(final_path):
        return final_path

    # 2. Setup Paths & URL
    temp_download_path = f"cache/temp_{videoid}.png"
    youtube_url = f"https://www.youtube.com/watch?v={videoid}"

    try:
        # 3. Fetch Info
        search = VideosSearch(youtube_url, limit=1)
        result = await search.next()
        data = result["result"][0]
        
        title = re.sub(r"\W+", " ", data.get("title", "Unknown")).title()
        duration = data.get("duration", "00:00")
        views = data.get("viewCount", {}).get("short", "0")
        channel = data.get("channel", {}).get("name", "Unknown Artist")
        
        # 4. Get High Quality Image
        thumbnails = data.get("thumbnails", [])
        candidates = [
            f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg",
            f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg"
        ]
        if thumbnails:
            candidates.append(thumbnails[-1]["url"])

        downloaded = False
        async with aiohttp.ClientSession() as session:
            for url in candidates:
                try:
                    async with session.get(url, timeout=5) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            # Ensure valid image size
                            if len(img_data) > 1000:
                                async with aiofiles.open(temp_download_path, mode="wb") as f:
                                    await f.write(img_data)
                                downloaded = True
                                break
                except:
                    continue
                if downloaded:
                    break
        
        if not downloaded:
            return YOUTUBE_IMG_URL

        # 5. Render
        final_image = await draw_thumb(
            temp_download_path, 
            title, 
            channel, 
            None, 
            duration, 
            views, 
            videoid
        )
        
        # Cleanup
        if os.path.exists(temp_download_path):
            os.remove(temp_download_path)
            
        return final_image

    except Exception as e:
        print(f"[GenThumb] Error: {e}")
        return YOUTUBE_IMG_URL

# Export function
get_thumb = gen_thumb
