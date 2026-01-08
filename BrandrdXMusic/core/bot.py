import sys
from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus

import config
from ..logging import LOGGER


class Hotty(Client):
    def __init__(self):
        super().__init__(
            name="BrandrdXMusic",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            workers=50,
            max_concurrent_transmissions=7,
        )
        LOGGER(__name__).info("Bot client initialized...")

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.username, self.id = me.username, me.id
        self.name = f"{me.first_name} {me.last_name or ''}".strip()
        self.mention = me.mention

        try:
            await self.send_message(
                config.LOGGER_ID,
                (
                    f"<u><b>» {self.mention} الـبـوت اشـتـغـل يـا عـزيـزي ✯ :</b></u>\n\n"
                    f"✯ الآيـدي : <code>{self.id}</code>\n"
                    f"✯ الأســم : {self.name}\n"
                    f"✯ اليـوزر : @{self.username}"
                ),
            )
        except (errors.ChannelInvalid, errors.PeerIdInvalid):
            LOGGER(__name__).error("❌ Bot cannot access the log group/channel – add & promote it first!")
            sys.exit()
        except Exception as exc:
            LOGGER(__name__).error(f"❌ Bot has failed to access the log group.\nReason: {type(exc).__name__}")
            sys.exit()

        try:
            member = await self.get_chat_member(config.LOGGER_ID, self.id)
            if member.status != ChatMemberStatus.ADMINISTRATOR:
                LOGGER(__name__).error("❌ Promote the bot as admin in the log group/channel.")
                sys.exit()
        except Exception as e:
            LOGGER(__name__).error(f"❌ Could not check admin status: {e}")
            sys.exit()

        # عربتلك رسالة اللوج هنا 👇
        LOGGER(__name__).info(f"✅ تم تشغيل بوت الميوزك بنجاح : {self.name} (@{self.username})")

    async def stop(self):
        await super().stop()
