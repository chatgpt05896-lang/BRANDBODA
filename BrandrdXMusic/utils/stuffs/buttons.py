from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram import Client, filters, enums 

class BUTTONS(object):
    MBUTTON = [
        [
            InlineKeyboardButton("ذكـاء اصطنـاعي", callback_data="mplus HELP_ChatGPT"),
            InlineKeyboardButton("الـسجـل", callback_data="mplus HELP_History"),
            InlineKeyboardButton("ريـلز", callback_data="mplus HELP_Reel")
        ],
        [
            InlineKeyboardButton("الـمنشـن", callback_data="mplus HELP_TagAll"),
            InlineKeyboardButton("معلـومـات", callback_data="mplus HELP_Info"),
            InlineKeyboardButton("إضـافيـة", callback_data="mplus HELP_Extra")
        ],
        [
            InlineKeyboardButton("نسبـة حـب", callback_data="mplus HELP_Couples"),
            InlineKeyboardButton("أفعـال", callback_data="mplus HELP_Action"),
            InlineKeyboardButton("بـحـث", callback_data="mplus HELP_Search")
        ],    
        [
            InlineKeyboardButton("خـطـوط", callback_data="mplus HELP_Font"),
            InlineKeyboardButton("بـوتـات", callback_data="mplus HELP_Bots"),
            InlineKeyboardButton("تليـجـراف", callback_data="mplus HELP_TG")
        ],
        [
            InlineKeyboardButton("الـسـورس", callback_data="mplus HELP_Source"),
            InlineKeyboardButton("صـراحـة", callback_data="mplus HELP_TD"),
            InlineKeyboardButton("اخـتبـار", callback_data="mplus HELP_Quiz")
        ], 
        [
            InlineKeyboardButton("الـنطـق", callback_data="mplus HELP_TTS"),
            InlineKeyboardButton("راديـو", callback_data="mplus HELP_Radio"),
            InlineKeyboardButton("اقـتبـاس", callback_data="mplus HELP_Q")
        ],          
        [
            InlineKeyboardButton("◁", callback_data=f"settings_back_helper"),
            InlineKeyboardButton("رجـوع", callback_data=f"mbot_cb"), 
            InlineKeyboardButton("▷", callback_data=f"managebot123 settings_back_helper"),
        ]
    ]
