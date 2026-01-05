import os
import re
import asyncio
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

# ==========================================
# 🛑 الإحداثيات المقدسة (بدون تعديل)
# ==========================================
CIRCLE_POS = (160, 146)   # (X, Y)
CIRCLE_SIZE = (385, 355)  # (Width, Height)

NAME_POS = (715, 190)
BY_POS = (650, 255)
VIEWS_POS = (711, 310)
TIME_START = (580, 368)
TIME_END = (1055, 368)
# ==========================================

if hasattr(Image, "Resampling"):
    LANCZOS = Image.Resampling.LANCZOS
else:
    LANCZOS = Image.LANCZOS

def get_font(size):
    fonts = ["BrandrdXMusic/assets/font.ttf", "assets/font.ttf", "font.ttf"]
    for font in fonts:
        if os.path.isfile(font): return ImageFont.truetype(font, size)
    return ImageFont.load_default()

def smart_truncate(draw, text, font, max_width):
    try: w = draw.textlength(text, font=font)
    except: w = draw.textsize(text, font=font)[0]
    if w <= max_width: return text
    for i in range(len(text), 0, -1):
        if draw.textlength(text[:i] + "...", font=font) <= max_width: return text[:i] + "..."
    return "..."

def format_views(views):
    try:
        v = str(views).lower().replace("views","").strip()
        if "m" in v or "k" in v: return v.upper()
        val = int(re.sub(r'\D', '', v))
        return f"{val/1_000_000:.1f}M" if val >= 1e6 else (f"{val/1_000:.1f}K" if val >= 1e3 else str(val))
    except: return str(views)

def draw_shadowed_text(draw, pos, text, font, color="white"):
    x, y = pos
    draw.text((x+2, y+2), text, font=font, fill="black") # ظل
    draw.text((x, y), text, font=font, fill=color)       # أساسي

# ============================================================
# 🎨 الرسام الذكي (Smart Renderer)
# ============================================================
async def draw_thumb(thumbnail_path, title, userid, theme, duration, views, videoid):
    try:
        # تجهيز البيانات
        title = str(title or "Unknown Track")
        userid = str(userid or "Unknown Artist")
        views = str(views or "0")

        # 1. فتح الصورة الأصلية
        try: source = Image.open(thumbnail_path).convert("RGBA")
        except: source = Image.new('RGBA', (1280, 720), (30, 30, 30))

        # 2. الخلفية (Background) -> Blur = 3
        # بنعمل ريسيز لـ 1280x720 وبعدين تغبيش خفيف
        background = source.resize((1280, 720), resample=LANCZOS)
        background = background.filter(ImageFilter.GaussianBlur(3))

        # 3. القالب (Overlay)
        # بيتحط الأول عشان الدائرة تيجي فوقه وتغطيه لو هو مش مفرغ
        if os.path.isfile("BrandrdXMusic/assets/overlay.png"):
            try:
                overlay = Image.open("BrandrdXMusic/assets/overlay.png").convert("RGBA")
                overlay = overlay.resize((1280, 720), resample=LANCZOS)
                background.paste(overlay, (0, 0), overlay)
            except: pass

        # 4. الدائرة الذكية (Smart Circle Fill)
        # هنا بنقص الصورة بذكاء عشان تملا المربع المحدد (385x355) من غير مط
        try:
            # تكبير 3 أضعاف عشان النعومة
            big_w, big_h = CIRCLE_SIZE[0] * 3, CIRCLE_SIZE[1] * 3
            
            # Smart Fit: دي بتاخد منتصف الصورة وتحافظ على الأبعاد
            smart_circle = ImageOps.fit(source, (big_w, big_h), centering=(0.5, 0.5), method=LANCZOS)
            
            # عمل الماسك الدائري
            mask = Image.new('L', (big_w, big_h), 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.ellipse((0, 0, big_w, big_h), fill=255)
            
            # تصغير للحجم المطلوب
            smart_circle = smart_circle.resize(CIRCLE_SIZE, resample=LANCZOS)
            mask = mask.resize(CIRCLE_SIZE, resample=LANCZOS)
            
            # اللصق في الإحداثيات المحددة (فوق القالب)
            background.paste(smart_circle, CIRCLE_POS, mask)
        except Exception as e:
            print(f"Circle Error: {e}")

        # 5. الكتابة
        draw = ImageDraw.Draw(background)
        f_45 = get_font(45)
        f_30 = get_font(30)
        f_26 = get_font(26)

        draw_shadowed_text(draw, NAME_POS, smart_truncate(draw, title, f_45, 500), f_45, "white")
        draw_shadowed_text(draw, BY_POS, smart_truncate(draw, userid, f_30, 450), f_30, "#dddddd")
        draw_shadowed_text(draw, VIEWS_POS, format_views(views), f_30, "#cccccc")
        
        draw_shadowed_text(draw, TIME_START, "00:00", f_26, "white")
        draw_shadowed_text(draw, TIME_END, duration, f_26, "white")

        output = f"cache/{videoid}_final.png"
        background.save(output)
        return output

    except Exception as e:
        print(f"Render Error: {e}")
        return thumbnail_path

# ============================================================
# 🦅 الصياد (Fetching Logic)
# ============================================================
async def gen_thumb(videoid, user_id=None):
    if not os.path.exists("cache"): os.makedirs("cache")
    if os.path.isfile(f"cache/{videoid}_final.png"): return f"cache/{videoid}_final.png"

    temp_path = f"cache/temp_{videoid}.png"
    url = f"https://www.youtube.com/watch?v={videoid}"

    try:
        search = VideosSearch(url, limit=1)
        res = (await search.next())["result"][0]
        
        title = res.get("title", "Unknown")
        title = re.sub(r"\W+", " ", title).title()
        duration = res.get("duration", "00:00")
        views = res.get("viewCount", {}).get("short", "0")
        channel = res.get("channel", {}).get("name", "Unknown Artist")
        
        # الروابط المحتملة
        candidates = [
            f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg", # الأفضل
            f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg",     # الجيد
            f"https://img.youtube.com/vi/{videoid}/sddefault.jpg"      # المقبول
        ]
        if res.get("thumbnails"): candidates.append(res["thumbnails"][-1]["url"])

        # التحميل مع الإلحاح (Retry)
        downloaded = False
        async with aiohttp.ClientSession() as session:
            for img_url in candidates:
                try:
                    async with session.get(img_url, timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) > 1000: # تأكد إن الملف سليم
                                async with aiofiles.open(temp_path, mode="wb") as f:
                                    await f.write(data)
                                downloaded = True
                                break
                except: pass
                if downloaded: break
        
        if not downloaded: return YOUTUBE_IMG_URL

        final_img = await draw_thumb(temp_path, title, channel, None, duration, views, videoid)
        
        if os.path.exists(temp_path): os.remove(temp_path)
        return final_img

    except Exception as e:
        print(f"Gen Error: {e}")
        return YOUTUBE_IMG_URL

get_thumb = gen_thumb
