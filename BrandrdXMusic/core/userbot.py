import sys
import asyncio
from pyrogram import Client
import config
from ..logging import LOGGER

assistants = []
assistantids = []

class Userbot(Client):
    def __init__(self):
        self.one = Client(
            "BrandrdXMusic1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
            no_updates=True,
        )
        self.two = Client(
            "BrandrdXMusic2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
            no_updates=True,
        )
        self.three = Client(
            "BrandrdXMusic3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
            no_updates=True,
        )
        self.four = Client(
            "BrandrdXMusic4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
            no_updates=True,
        )
        self.five = Client(
            "BrandrdXMusic5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
            no_updates=True,
        )

    async def start(self):
        LOGGER(__name__).info("⚡ جـاري إقـلاع كـتـيـبـة الـمـسـاعـديـن...")
        
        clients = [
            (self.one, config.STRING1, 1, "☔"),
            (self.two, config.STRING2, 2, "🤍"),
            (self.three, config.STRING3, 3, "🧚"),
            (self.four, config.STRING4, 4, "✨"),
            (self.five, config.STRING5, 5, "🎸")
        ]

        for client, session, index, emoji in clients:
            if not session:
                continue

            try:
                await client.start()
                
                me = await client.get_me()
                client.id = me.id
                client.name = me.first_name
                client.username = me.username
                client.mention = me.mention
                
                assistants.append(index)
                assistantids.append(me.id)

                try:
                    await client.send_message(
                        config.LOGGER_ID, 
                        f"تـم تـفـعـيـل الـمـسـاعـد {index} يـا عـزيـزي {emoji}\n🤍 الأســم : {me.mention}"
                    )
                except Exception:
                    LOGGER(__name__).warning(f"الـمـسـاعـد {index} شـغـال بـس مـش عـارف يـبـعـت فـي جـروب الـسـجـل.")

                LOGGER(__name__).info(f"تـم تـفـعـيـل الـمـسـاعـد {index} بـاسـم: {client.name}")
            
            except Exception as e:
                LOGGER(__name__).error(f"فـشـل تـشـغـيـل الـمـسـاعـد {index}: {e}")

        LOGGER(__name__).info(f"تـم تـشـغـيـل {len(assistants)} مـسـاعـديـن بـنـجـاح.")

    async def stop(self):
        LOGGER(__name__).info("جـاري إيـقـاف الـمـسـاعـديـن...")
        clients = [self.one, self.two, self.three, self.four, self.five]
        try:
            await asyncio.gather(
                *[c.stop() for c in clients if c.is_connected]
            )
        except:
            pass
