# BrandrdXMusic/__main__.py
"""
Entry point that ensures run_patch is executed BEFORE any pytgcalls import.
Provides a local fallback injection (TelegramServerError + chat_id alias) in case the external patch fails or is not applied yet.
"""

import os
import sys
import subprocess
import traceback

def run_patcher():
    candidates = []
    env_path = os.environ.get("RUN_PATCH_PATH")
    if env_path:
        candidates.append(env_path)
    # parent of this file (project root)
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(here)
        candidates.append(os.path.join(repo_root, "run_patch_clean.py"))
        candidates.append(os.path.join(repo_root, "run_patch.py"))
    except Exception:
        pass
    # cwd
    candidates.append(os.path.join(os.getcwd(), "run_patch_clean.py"))
    candidates.append(os.path.join(os.getcwd(), "run_patch.py"))
    # two levels up (safety)
    try:
        two_up = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates.append(os.path.join(two_up, "run_patch_clean.py"))
        candidates.append(os.path.join(two_up, "run_patch.py"))
    except Exception:
        pass

    for p in candidates:
        if not p:
            continue
        if os.path.isfile(p):
            print(f"[PATCH] Found patcher at: {p} — running --patch-only")
            try:
                # run with a reasonably long timeout (15 minutes)
                res = subprocess.run([sys.executable, p, "--patch-only"],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, timeout=900)
                if res.stdout:
                    print(res.stdout)
                if res.stderr:
                    print("PATCH-ERR>", res.stderr)
                if res.returncode == 0:
                    print("[PATCH] run_patch --patch-only finished successfully.")
                    return True
                else:
                    print(f"[PATCH] run_patch returned non-zero exit code: {res.returncode}")
                    # try next candidate
            except subprocess.TimeoutExpired:
                print("[PATCH] run_patch timed out.")
                continue
            except Exception as e:
                print(f"[PATCH] Error running run_patch at {p}: {e}")
                traceback.print_exc()
                continue
    print("[PATCH] Failed to run run_patch --patch-only from any candidate.")
    return False


def inject_local_compat():
    """
    Fallback injection run inside the process:
    - add TelegramServerError to pytgcalls.exceptions if missing
    - add Update.chat_id property aliasing to chat.id if missing
    This is defensive: if the external patch didn't run for any reason,
    this will prevent immediate ImportError / AttributeError crashes.
    """
    try:
        import pytgcalls
    except Exception:
        # If pytgcalls is not importable, nothing to inject here.
        print("[FALLBACK] pytgcalls not importable yet; skipping local injection.")
        return

    # Inject TelegramServerError in exceptions module if necessary
    try:
        import pytgcalls.exceptions as _exc
        if not hasattr(_exc, "TelegramServerError"):
            class TelegramServerError(Exception):
                """Injected fallback TelegramServerError"""
                pass
            _exc.TelegramServerError = TelegramServerError
            print("[FALLBACK] Injected TelegramServerError into pytgcalls.exceptions")
    except Exception as e:
        print(f"[FALLBACK] Could not inject TelegramServerError: {e}")

    # Inject chat_id alias into pytgcalls.types.Update if necessary
    try:
        # import types module
        from pytgcalls import types as _types
        Update = getattr(_types, "Update", None)
        if Update is None:
            # try direct import
            try:
                from pytgcalls.types import Update as Update
            except Exception:
                Update = None

        if Update is not None and not getattr(Update, "_chat_id_injected", False):
            def _chat_id(self):
                # prefer existing attribute if present
                if hasattr(self, "chat_id") and getattr(self, "chat_id") is not None:
                    return getattr(self, "chat_id")
                if hasattr(self, "chat") and getattr(self, "chat") is not None:
                    return getattr(getattr(self, "chat"), "id", None)
                return None
            try:
                setattr(Update, "chat_id", property(_chat_id))
                setattr(Update, "_chat_id_injected", True)
                print("[FALLBACK] Injected Update.chat_id alias -> chat.id")
            except Exception as e:
                print(f"[FALLBACK] Failed to set property on Update: {e}")
    except Exception as e:
        print(f"[FALLBACK] Chat_id injection step failed: {e}")


# 1) Run external patcher first (best-effort)
patched_ok = run_patcher()
if not patched_ok:
    print("[WARN] External patch did not run successfully. Will attempt in-process fallback injection and then continue.")
else:
    print("[OK] External patch completed. Proceeding.")

# 2) Attempt in-process fallback injection (defensive)
inject_local_compat()

# Now safe to import remaining modules (pytgcalls exceptions should exist or be patched)
import asyncio
import importlib
from sys import exit

from pyrogram import idle
# Import NoActiveGroupCall after patch/injection
try:
    from pytgcalls.exceptions import NoActiveGroupCall
except Exception as e:
    print(f"[WARN] Could not import NoActiveGroupCall: {e}. Continuing, but calls may fail if pytgcalls missing.")
    NoActiveGroupCall = None  # keep name available

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

    # Safe optional stream test: only call if Hotty actually implements stream_call
    try:
        if hasattr(Hotty, "stream_call") and callable(getattr(Hotty, "stream_call")):
            try:
                await Hotty.stream_call("https://telegra.ph/file/b60b80ccb06f7a48f68b5.mp4")
            except Exception as e:
                print("[INFO] stream_call test failed (may be no log group voice chat):", e)
        else:
            print("[INFO] Hotty.stream_call not available on this implementation; skipping test.")
    except Exception as e:
        print("[WARN] Unexpected error during optional stream test:", e)

    # 8 - decorators
    try:
        await Hotty.decorators()
    except Exception as e:
        print(f"[WARN] Hotty.decorators() raised: {e}")

    LOGGER("BrandrdXMusic").info(f"Bot Started Successfully: @{app.username}")

    # 9 - idle
    await idle()

    # 10 - shutdown
    await app.stop()
    await userbot.stop()
    LOGGER("BrandrdXMusic").info("Stopping Bot...")
