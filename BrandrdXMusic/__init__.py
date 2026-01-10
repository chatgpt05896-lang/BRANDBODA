# BrandrdXMusic/__main__.py
import asyncio
import importlib
import traceback
import config
from BrandrdXMusic import LOGGER, create_clients
from BrandrdXMusic.core.call import Call
from BrandrdXMusic.misc import sudo
from BrandrdXMusic.plugins import ALL_MODULES
from BrandrdXMusic.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS

# instance holders
call: Call | None = None
app = None
userbot = None
api = None

async def init():
    global call, app, userbot, api

    # check assistant strings
    if not any([
        getattr(config, "STRING1", None),
        getattr(config, "STRING2", None),
        getattr(config, "STRING3", None),
        getattr(config, "STRING4", None),
        getattr(config, "STRING5", None),
    ]):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        return

    await sudo()

    # load bans
    try:
        for uid in await get_gbanned():
            BANNED_USERS.add(uid)
        for uid in await get_banned_users():
            BANNED_USERS.add(uid)
    except Exception as e:
        LOGGER(__name__).warning(f"Failed loading bans: {e}")

    # create clients now (after loop & patch are set)
    try:
        app, userbot, api = create_clients()
    except Exception as e:
        LOGGER(__name__).error(f"Failed to create clients: {e}\n{traceback.format_exc()}")
        return

    # start the core bot (app) first
    try:
        await app.start()
    except Exception as e:
        LOGGER(__name__).error(f"Failed to start main bot (app): {e}\n{traceback.format_exc()}")
        # if start failed, try to stop any partially started resources
        try:
            await app.stop()
        except Exception:
            pass
        return

    # import plugins only AFTER app exists (so modules see BrandrdXMusic.app)
    modules_loaded = 0
    for all_module in ALL_MODULES:
        try:
            importlib.import_module("BrandrdXMusic.plugins" + all_module)
            modules_loaded += 1
        except Exception as e:
            LOGGER(__name__).error(f"Failed to import plugin {all_module}: {e}\n{traceback.format_exc()}")

    LOGGER("BrandrdXMusic.plugins").info(f"Imported modules: {modules_loaded}/{len(ALL_MODULES)}")

    # start userbot(s)
    try:
        await userbot.start()
    except Exception as e:
        LOGGER(__name__).error(f"Failed to start userbot: {e}\n{traceback.format_exc()}")
        # graceful stop app if userbot start is critical
        try:
            await app.stop()
        except Exception:
            pass
        return

    # start Voice engine (Call manager)
    try:
        call = Call()
        await call.start()
    except Exception as e:
        LOGGER(__name__).error(f"Failed to start Call engine: {e}\n{traceback.format_exc()}")
        # attempt to shutdown gracefully
        try:
            await userbot.stop()
        except Exception:
            pass
        try:
            await app.stop()
        except Exception:
            pass
        return

    print("-------------------------------------------------------")
    print("🚀 البوت يعمل الآن بنجاح (VOICE ENGINE READY)")
    print("-------------------------------------------------------")

    LOGGER("BrandrdXMusic").info(f"Bot Started: @{getattr(app, 'username', 'unknown')}")

    # keep alive and wait for signals
    from pyrogram import idle
    try:
        await idle()
    except Exception as e:
        LOGGER(__name__).error(f"Idle interrupted: {e}")

    # graceful shutdown
    try:
        if call:
            try:
                # stop call manager if it exposes a stop (best-effort)
                await call.force_stop_stream(-1)  # dummy to trigger cleanup if implemented
            except Exception:
                pass
    except Exception:
        pass

    try:
        await userbot.stop()
    except Exception:
        pass

    try:
        await app.stop()
    except Exception:
        pass
