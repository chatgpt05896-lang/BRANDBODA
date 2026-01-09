import asyncio
import shlex
from typing import Tuple

# شلنا السطر ده عشان هو سبب المشكلة 👇
# from BrandrdXMusic import LOGGER

def install_req(cmd: str) -> Tuple[str, str, int, int]:
    async def install_requirements():
        args = shlex.split(cmd)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return (
            stdout.decode("utf-8", "replace").strip(),
            stderr.decode("utf-8", "replace").strip(),
            process.returncode,
            process.pid,
        )

    return asyncio.get_event_loop().run_until_complete(install_requirements())

def git():
    """
    نسخة خفيفة جداً لكسر الـ Circular Import
    """
    # استخدمنا print بدل LOGGER عشان نحل المشكلة
    print("[INFO] ✅ Git Update Skipped: Running on Cloud Platform.")
    return
