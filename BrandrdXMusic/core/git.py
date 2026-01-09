import asyncio
import shlex
from typing import Tuple
from BrandrdXMusic import LOGGER

# --- دالة تسطيب المكتبات (سيبناها زي ما هي عشان لو احتجتها) ---
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

# --- دالة Git المعدلة (عطلناها عشان Fly.io) ---
def git():
    """
    تم تعطيل التحديث التلقائي لتجنب أخطاء Git على Fly.io.
    يتم رفع التحديثات يدوياً عبر 'fly deploy'.
    """
    LOGGER(__name__).info("✅ Git Update Skipped: Running on Cloud Platform.")
    return
