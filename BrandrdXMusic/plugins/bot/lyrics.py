import sys
import typing
import random
import re
import string
import asyncio

# --- Compatibility Patch for Python 3.10 ---
try:
    from typing import Self
except ImportError:
    Self = typing.TypeVar("Self")
    typing.Self = Self
    sys.modules["typing"].Self = Self
# -------------------------------------------

try:
    import lyricsgenius as lg
except ImportError:
    lg = None

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from BrandrdXMusic import app
from BrandrdXMusic.utils.decorators.language import language
from config import BANNED_USERS, lyrical

# Genius API Key
api_key = "JVv8pud-25QRBYyRwcH34AlAygySsSAU3owRNGBw6hXO96x0JiTMn-3R4PvsjcTf"

if lg:
    y = lg.Genius(
        api_key,
        skip_non_songs=True,
        excluded_terms=["(Remix)", "(Live)"],
        remove_section_headers=True,
    )
    y.verbose = False
else:
    y = None

# Command Filter: Supports "lyrics", "lyric", "كلمات" with /, !, or no prefix at all
@app.on_message(filters.command(["lyrics", "lyric", "كلمات"], prefixes=["/", "!", "", "•"]) & ~BANNED_USERS)
@language
async def lrsearch(client, message: Message, _):
    if not y:
        return await message.reply_text("Genius library is not installed correctly.")

    if len(message.command) < 2:
        return await message.reply_text(_["lyrics_1"])

    title = message.text.split(None, 1)[1]
    m = await message.reply_text(_["lyrics_2"])
    
    loop = asyncio.get_event_loop()
    try:
        S = await loop.run_in_executor(None, lambda: y.search_song(title, get_full_info=False))
    except Exception:
        return await m.edit(_["lyrics_3"].format(title))

    if S is None:
        return await m.edit(_["lyrics_3"].format(title))

    ran_hash = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    lyric = S.lyrics
    
    if "Embed" in lyric:
        lyric = re.sub(r"\d*Embed", "", lyric)
    
    lyrical[ran_hash] = lyric

    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_["L_B_1"],
                    url=f"https://t.me/{app.username}?start=lyrics_{ran_hash}",
                ),
            ]
        ]
    )
    
    await m.edit(_["lyrics_4"], reply_markup=upl)
