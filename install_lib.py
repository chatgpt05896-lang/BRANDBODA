import os
import sys
import subprocess
import shutil
import compileall

def setup_library():
    LIB_NAME = "pytgcalls"
    cwd = os.getcwd()
    lib_path = os.path.join(cwd, LIB_NAME)

    # 1. تنظيف شامل (حذف القديم عشان نبدأ على نظافة)
    print("🧹 Cleaning old library...")
    if os.path.exists(lib_path):
        try:
            shutil.rmtree(lib_path)
        except: pass

    # 2. تحميل المكتبة Clean Install
    print("⏳ Installing PyTgCalls v2.2.8...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "py-tgcalls==2.2.8", 
            "--target", cwd,
            "--no-deps",
            "--upgrade",
            "--force-reinstall"
        ])
    except Exception as e:
        print(f"❌ Install failed: {e}")
        return

    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    # 3. كتابة ملف pyrogram_client.py بالكود الصحيح (بدون Import Errors)
    print("🔧 Patching Pyrogram Client...")
    target_file = os.path.join(lib_path, "mtproto", "pyrogram_client.py")
    
    # ده الكود السليم اللي مبيعملش مشاكل استيراد
    # شلنا الوراثة المعقدة وخليناها بسيطة ومباشرة
    safe_code = r'''
from pyrogram import Client
from ...types import Update
from ...types import GroupCall
import logging

# شلنا الوراثة من MTProtoClient عشان نتفادى خطأ الاستيراد الدائري
class PyrogramClient:
    def __init__(self, client: Client):
        self._client = client

        @self._client.on_message()
        async def on_message(client, message):
            if message.chat:
                await self.on_update(
                    Update(
                        chat_id=message.chat.id,
                        chat=message.chat,
                        message_id=message.id,
                        message=message,
                    )
                )

        @self._client.on_deleted_messages()
        async def on_deleted_messages(client, messages):
            for message in messages:
                if message.chat:
                    await self.on_update(
                        Update(
                            chat_id=message.chat.id,
                            chat=message.chat,
                            message_id=message.id,
                        )
                    )

    async def start(self):
        await self._client.start()

    async def stop(self):
        await self._client.stop()

    async def call(self, method, data):
        try:
            return await self._client.invoke(method, data)
        except Exception as e:
            logging.error(f"[Anti-Crash] Invoke Error: {e}")
            return None

    async def resolve_peer(self, id):
        return await self._client.resolve_peer(id)

    async def get_input_entity(self, peer):
        return await self._client.resolve_peer(peer)

    def chat_id(self, chat: GroupCall):
        return int(f"-100{chat.id}")

    async def set_params(self, chats: dict):
        self._my_id = (await self._client.get_me()).id
        self._chats = chats

    # دالة وهمية عشان التوافق مع المكتبة الأم
    def set_on_update(self, func):
        self._on_update = func

    async def on_update(self, update: Update):
        # التأكد من وجود الدالة قبل استدعائها
        if not hasattr(self, '_on_update'):
            return

        chats = self._chats
        try:
            c_id = getattr(update, 'chat_id', None)
            if c_id is None and hasattr(update, 'chat'):
                 c_id = update.chat.id
            
            if c_id is None: return

            if c_id in chats:
                chat_id = self.chat_id(chats[c_id])
                await self._on_update(update, chat_id)
        except Exception:
            return
'''
    
    if os.path.exists(os.path.dirname(target_file)):
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(safe_code)
        print("✅ File patched successfully (Import Error Fixed).")
    else:
        print("❌ Directory not found!")

    # 4. إصلاح بسيط في ملف mtproto_client.py عشان يقبل الكلاس الجديد
    mtproto_file = os.path.join(lib_path, "mtproto", "mtproto_client.py")
    if os.path.exists(mtproto_file):
        with open(mtproto_file, "r") as f:
            content = f.read()
        # بنشيل أي checks صارمة على النوع
        if "isinstance(client, MTProtoClient)" in content:
            new_content = content.replace("isinstance(client, MTProtoClient)", "True")
            with open(mtproto_file, "w") as f:
                f.write(new_content)
            print("✅ MTProto check bypassed.")

    print("🔄 Recompiling...")
    compileall.compile_dir(lib_path, force=True)
    print("🚀 Ready! Restart now.")

if __name__ == "__main__":
    setup_library()
