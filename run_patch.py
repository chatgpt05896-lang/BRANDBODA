#!/usr/bin/env python3
# run_patch.py
"""
Script to:
1) Ensure a compatible py-tgcalls version is installed (e.g. 2.2.8).
2) Patch pytgcalls.exceptions to include TelegramServerError if missing.
3) Remove core/pytgcalls_patch.py from the repo if exists (optional).
4) Exec the given command (e.g. python3 run.py).

Usage:
    python3 run_patch.py python3 run.py
or in Dockerfile entrypoint:
    ENTRYPOINT ["python3", "/app/run_patch.py", "python3", "run.py"]
"""

import sys
import subprocess
import importlib
import site
import os
import shutil
import time
import traceback

PYTGCALLS_VERSION = "2.2.8"  # change if you want other version
BACKUP_SUFFIX = f".bak-{int(time.time())}"

def run(cmd, check=True):
    print(">>> Running:", " ".join(cmd))
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print(res.stdout)
    if res.stderr:
        print("ERR>", res.stderr)
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)} (exit {res.returncode})")
    return res

def pip_install(version):
    # Use sys.executable to ensure pip for current python
    run([sys.executable, "-m", "pip", "install", f"py-tgcalls=={version}", "--no-cache-dir"])

def find_pytgcalls_path():
    try:
        import pytgcalls
        pkg_file = getattr(pytgcalls, "__file__", None)
        if pkg_file:
            pkg_dir = os.path.dirname(pkg_file)
            print(f"Found installed pytgcalls at: {pkg_dir}")
            return pkg_dir
    except Exception as e:
        print("pytgcalls import failed (not installed yet):", e)

    # fallback: scan site-packages
    for p in site.getsitepackages() + [site.getusersitepackages()]:
        candidate = os.path.join(p, "pytgcalls")
        if os.path.isdir(candidate):
            print(f"Found pytgcalls at site-packages: {candidate}")
            return candidate
    return None

def patch_exceptions(pytgcalls_dir):
    exc_path = os.path.join(pytgcalls_dir, "exceptions.py")
    if not os.path.exists(exc_path):
        print(f"[WARN] exceptions.py not found at expected location: {exc_path}")
        return False

    with open(exc_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if TelegramServerError already defined
    if "class TelegramServerError" in content or "TelegramServerError =" in content:
        print("TelegramServerError already present in exceptions.py — skipping patch.")
        return True

    # Create backup
    backup = exc_path + BACKUP_SUFFIX
    print(f"Backing up exceptions.py -> {backup}")
    shutil.copy2(exc_path, backup)

    # We'll append a small compatibility shim at end of file
    shim = """

# --- Compatibility shim injected by run_patch.py ---
class TelegramServerError(Exception):
    \"\"\"Compatibility alias for older code expecting TelegramServerError in pytgcalls.exceptions.\"\"\"
    pass

# End of compatibility shim
"""
    try:
        with open(exc_path, "a", encoding="utf-8") as f:
            f.write(shim)
        print("Patched exceptions.py: added TelegramServerError shim.")
        return True
    except Exception as e:
        print("Failed to write patch to exceptions.py:", e)
        # restore backup
        try:
            shutil.copy2(backup, exc_path)
            print("Restored from backup after failed write.")
        except Exception as e2:
            print("Failed to restore backup:", e2)
        return False

def remove_repo_patch_file(repo_core_path="BrandrdXMusic/core", filename="pytgcalls_patch.py"):
    target = os.path.join(repo_core_path, filename)
    if os.path.exists(target):
        try:
            print(f"Removing repo-level patch file: {target}")
            os.remove(target)
            return True
        except Exception as e:
            print("Failed to remove repo patch file:", e)
            return False
    else:
        print("No repo-level pytgcalls_patch.py found — nothing to remove.")
        return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 run_patch.py <command...>")
        print("e.g. python3 run_patch.py python3 run.py")
        sys.exit(1)

    command = sys.argv[1:]
    print("Will run application command after patch:", " ".join(command))

    try:
        # 1) install expected py-tgcalls version
        print(f"Installing py-tgcalls=={PYTGCALLS_VERSION} ...")
        pip_install(PYTGCALLS_VERSION)

        # 2) find package path
        pytgcalls_dir = find_pytgcalls_path()
        if not pytgcalls_dir:
            print("[ERROR] Could not find pytgcalls package dir after installation.")
        else:
            # 3) patch exceptions.py
            ok = patch_exceptions(pytgcalls_dir)
            if not ok:
                print("[WARN] Patching exceptions.py failed. Check permissions.")
            else:
                print("[OK] exceptions.py patched (TelegramServerError shim added).")

        # 4) remove repo-level patch file so logs don't warn about missing file,
        #    or to avoid conflicting behavior. (Optional as requested)
        remove_repo_patch_file()

    except Exception as e:
        print("=== ERROR during patch steps ===")
        traceback.print_exc()
        print("Proceeding to run the command anyway (patch may have failed).")

    # Finally: exec the real command (replace process)
    print("Executing application command now...")
    try:
        os.execvp(command[0], command)
    except Exception:
        print("Failed to exec command via execvp, falling back to subprocess.run...")
        subprocess.run(command)

if __name__ == "__main__":
    main()
