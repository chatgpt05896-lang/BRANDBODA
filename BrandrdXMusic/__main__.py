# BrandrdXMusic/__main__.py
"""
Entry point that ensures run_patch is executed BEFORE any pytgcalls import.
It tries multiple candidate locations for run_patch.py and runs it with --patch-only.
If patch succeeds, it continues to import the app and start normally.
"""

import os
import sys
import subprocess

def run_patcher():
    candidates = []
    env_path = os.environ.get("RUN_PATCH_PATH")
    if env_path:
        candidates.append(env_path)
    # parent of this file (project root)
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(here)
        candidates.append(os.path.join(repo_root, "run_patch.py"))
    except Exception:
        pass
    # cwd
    candidates.append(os.path.join(os.getcwd(), "run_patch.py"))
    # two levels up (safety)
    try:
        two_up = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates.append(os.path.join(two_up, "run_patch.py"))
    except Exception:
        pass

    for p in candidates:
        if not p:
            continue
        if os.path.isfile(p):
            print(f"[PATCH] Found run_patch at: {p} — running --patch-only")
            try:
                res = subprocess.run([sys.executable, p, "--patch-only"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=900)
                if res.stdout:
                    print(res.stdout)
                if res.stderr:
                    print("PATCH-ERR>", res.stderr)
                if res.returncode == 0:
                    print("[PATCH] run_patch --patch-only finished successfully.")
                    return True
                else:
                    print(f"[PATCH] run_patch returned non-zero exit code: {res.returncode}")
                    # continue to try other candidates
            except subprocess.TimeoutExpired:
                print("[PATCH] run_patch timed out.")
                continue
            except Exception as e:
                print(f"[PATCH] Error running run_patch at {p}: {e}")
                continue
    print("[PATCH] Failed to run run_patch --patch-only from any candidate.")
    return False

# Execute patcher before importing pytgcalls or call
patched_ok = run_patcher()
if not patched_ok:
    print("[ERROR] Patching step failed. Exiting to avoid ImportError conflicts.")
    sys.exit(1)

# Now safe to import the rest
import asyncio
import importlib
from sys import exit

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from BrandrdXMusic import LOGGER, app, userbot
from BrandrdXMusic.core.call import Hotty
from BrandrdXMusic.misc import sudo
from BrandrdXMusic.plugins import ALL_MODULES
from BrandrdXMusic.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS

async def init():
    # 1 - check assistant strings
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()

    # 2 - sudo
    await sudo()

    # 3 - load banned
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass

    # 4 - start app
    await app.start()

    # 5 - import plugins
    for module in ALL_MODULES:
        importlib.import_module("BrandrdXMusic.plugins" + module)

    LOGGER("BrandrdXMusic.plugins").info("Successfully Imported Modules...")

    # 6 - start userbot
    await userbot.start()

    # 7 - start Hotty
    await Hotty.start()
    try:
        await Hotty.stream_call("https://telegra.ph/file/b60b80ccb06f7a48f68b5.mp4")
    except Exception as e:
        # handle gracefully
        print("[INFO] stream_call test failed (may be no log group voice chat):", e)
    # 8 - decorators
    await Hotty.decorators()

    LOGGER("BrandrdXMusic").info(f"Bot Started Successfully: @{app.username}")

    # 9 - idle
    await idle()

    # 10 - shutdown
    await app.stop()
    await userbot.stop()
    LOGGER("BrandrdXMusic").info("Stopping Bot...")
