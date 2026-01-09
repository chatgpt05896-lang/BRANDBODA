import os
import asyncio
from random import randint
from typing import Union

from pyrogram.types import InlineKeyboardMarkup
from pyrogram.errors import FloodWait

import config
from BrandrdXMusic import Carbon, YouTube, app
from BrandrdXMusic.core.call import Hotty
from BrandrdXMusic.misc import db
from BrandrdXMusic.utils.database import (
    add_active_video_chat,
    is_active_chat,
    add_active_chat,
)
from BrandrdXMusic.utils.exceptions import AssistantErr
from BrandrdXMusic.utils.inline import (
    aq_markup,
    close_markup,
    stream_markup,
)
from BrandrdXMusic.utils.pastebin import HottyBin
from BrandrdXMusic.utils.stream.queue import put_queue, put_queue_index
from BrandrdXMusic.utils.thumbnails import gen_thumb

# --- دالة حذف آمنة (من سورس ديف) ---
async def safe_delete(message):
    try:
        await message.delete()
    except:
        pass

async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
):
    if not result:
        return
    
    # التأكد إن الفيديو قيمة منطقية (True/False)
    is_video = True if video else False
    
    if forceplay:
        await Hotty.force_stop_stream(chat_id)
        
    # ==========================
    # 1. PLAYLIST MODE
    # ==========================
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0
        for search in result:
            if int(count) == config.PLAYLIST_FETCH_LIMIT:
                continue
            try:
                (
                    title,
                    duration_min,
                    duration_sec,
                    thumbnail,
                    vidid,
                ) = await YouTube.details(search, False if spotify else True)
            except:
                continue
            if str(duration_min) == "None":
                continue
            if duration_sec > config.DURATION_LIMIT:
                continue
            
            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if is_video else "audio",
                )
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            else:
                if not forceplay:
                    db[chat_id] = []
                try:
                    file_path, direct = await YouTube.download(
                        vidid, mystic, video=is_video, videoid=True
                    )
                except:
                    await mystic.edit_text(_["play_3"])
                    return
                
                await Hotty.join_call(
                    chat_id,
                    original_chat_id,
                    file_path,
                    video=is_video,
                    image=thumbnail,
                )
                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path if direct else f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if is_video else "audio",
                    forceplay=forceplay,
                )
                
                # محاولة جلب الصورة بأمان
                try:
                    img = await gen_thumb(vidid, user_id)
                except:
                    img = config.STREAM_IMG_URL

                button = stream_markup(_, vidid, chat_id)
                await safe_delete(mystic)

                # حماية FloodWait (ميزة السورس بتاعك) + تنسيق Alexa
                try:
                    run = await app.send_photo(
                        original_chat_id,
                        photo=img,
                        caption="🧚 " + _["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{vidid}",
                            title[:25],
                            duration_min,
                            user_name,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    run = await app.send_photo(
                        original_chat_id,
                        photo=img,
                        caption="🧚 " + _["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{vidid}",
                            title[:25],
                            duration_min,
                            user_name,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
                except Exception:
                    pass

        if count == 0:
            return
        else:
            link = await HottyBin(msg)
            lines = msg.count("\n")
            car = os.linesep.join(msg.split(os.linesep)[:17]) if lines >= 17 else msg
            carbon = await Carbon.generate(car, randint(100, 10000000))
            upl = close_markup(_)
            return await app.send_photo(
                original_chat_id,
                photo=carbon,
                caption="🧚 " + _["play_21"].format(position, link),
                reply_markup=upl,
            )

    # ==========================
    # 2. YOUTUBE MODE (Safe & Clean)
    # ==========================
    elif streamtype == "youtube":
        # استخدام .get لمنع KeyError (ميزة Annie)
        link = result.get("link")
        vidid = result.get("vidid")
        title = (result.get("title", "Unknown Track")).title()
        duration_min = result.get("duration_min", "00:00")
        thumbnail = result.get("thumb")
        
        try:
            file_path, direct = await YouTube.download(
                vidid, mystic, videoid=True, video=is_video
            )
        except:
            await mystic.edit_text(_["play_3"])
            return

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
            )
            
            try:
                img = await gen_thumb(vidid, user_id)
            except:
                img = config.STREAM_IMG_URL
                
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            
            await safe_delete(mystic)
            await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                caption="🧚 " + _["queue_4"].format(
                    position, title[:25], duration_min, user_name
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            
            await Hotty.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=is_video,
                image=thumbnail,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            
            try:
                img = await gen_thumb(vidid, user_id)
            except:
                img = config.STREAM_IMG_URL
                
            button = stream_markup(_, vidid, chat_id)
            await safe_delete(mystic)

            try:
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption="🧚 " + _["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{vidid}",
                        title[:25],
                        duration_min,
                        user_name,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            except FloodWait as e:
                await asyncio.sleep(e.value)
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption="🧚 " + _["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{vidid}",
                        title[:25],
                        duration_min,
                        user_name,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            except Exception: pass

    # ==========================
    # 3. SOUNDCLOUD MODE
    # ==========================
    elif streamtype == "soundcloud":
        file_path = result.get("filepath")
        title = result.get("title", "SoundCloud Track")
        duration_min = result.get("duration_min", "00:00")
        
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:25], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Hotty.join_call(chat_id, original_chat_id, file_path, video=False)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
                forceplay=forceplay,
            )
            button = stream_markup(_, "None", chat_id)
            await safe_delete(mystic)

            try:
                run = await app.send_photo(
                    original_chat_id,
                    photo=config.SOUNCLOUD_IMG_URL,
                    caption="🧚 " + _["stream_1"].format(
                        config.SUPPORT_CHAT, title[:25], duration_min, user_name
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            except Exception: pass

    # ==========================
    # 4. TELEGRAM FILES MODE
    # ==========================
    elif streamtype == "telegram":
        file_path = result.get("path")
        link = result.get("link")
        title = (result.get("title", "ملف تيليجرام")).title()
        # هنا كان سبب المشكلة غالباً (dur vs duration_min) - حليناها بالـ Get
        duration_min = result.get("dur", result.get("duration_min", "00:00"))
        
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:25], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Hotty.join_call(chat_id, original_chat_id, file_path, video=is_video)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            if is_video:
                await add_active_video_chat(chat_id)
            
            button = stream_markup(_, "None", chat_id)
            await safe_delete(mystic)

            try:
                run = await app.send_photo(
                    original_chat_id,
                    photo=config.TELEGRAM_VIDEO_URL if is_video else config.TELEGRAM_AUDIO_URL,
                    caption="🧚 " + _["stream_1"].format(link, title[:25], duration_min, user_name),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            except Exception: pass

    # ==========================
    # 5. LIVE MODE
    # ==========================
    elif streamtype == "live":
        link = result.get("link")
        vidid = result.get("vidid")
        title = (result.get("title", "Live Stream")).title()
        thumbnail = result.get("thumb")
        duration_min = "Live Track"
        
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:25], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            n, file_path = await YouTube.video(link)
            if n == 0:
                raise AssistantErr(_["str_3"])
            
            await Hotty.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=is_video,
                image=thumbnail if thumbnail else None,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            
            try:
                img = await gen_thumb(vidid, user_id)
            except:
                img = config.STREAM_IMG_URL

            button = stream_markup(_, vidid, chat_id)
            await safe_delete(mystic)

            try:
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption="🧚 " + _["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{vidid}",
                        title[:25],
                        duration_min,
                        user_name,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            except Exception: pass

    # ==========================
    # 6. INDEX / URL MODE
    # ==========================
    elif streamtype == "index":
        link = result
        title = "رابط خارجي أو M3u8"
        duration_min = "00:00"
        
        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await mystic.edit_text(
                text="🧚 " + _["queue_4"].format(position, title[:25], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Hotty.join_call(
                chat_id,
                original_chat_id,
                link,
                video=is_video,
            )
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            button = stream_markup(_, "None", chat_id)
            
            await safe_delete(mystic)

            try:
                run = await app.send_photo(
                    original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption="🧚 " + _["stream_2"].format(user_name),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            except Exception: pass
