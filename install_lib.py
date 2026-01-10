import os
import sys
import subprocess
import shutil

def setup_library():
    # اسم المجلد اللي المفروض المكتبة تنزل فيه
    LIB_NAME = "pytgcalls"
    cwd = os.getcwd()

    # 1. تنظيف أي محاولة فاشلة قديمة (عشان نبدأ على نضافة)
    # لو المجلد موجود بس فاضي أو بايظ، هنمسحه
    if os.path.exists(LIB_NAME):
        try:
            # اختبار بسيط لو المكتبة شغالة
            import pytgcalls
            print("✅ Library is already installed and working.")
            return
        except ImportError:
            print("⚠️ Found broken library folder, removing...")
            shutil.rmtree(LIB_NAME, ignore_errors=True)

    print("⏳ Installing PyTgCalls v2.2.8 from Official PyPI...")
    
    # 2. التنزيل باستخدام PIP (المتجر الرسمي)
    # --target . : معناها نزلها هنا جنبي في ملفات البوت
    # --no-deps : نزل المكتبة دي بس من غير ما تبوظ باقي المكتبات
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "py-tgcalls==2.2.8", 
            "--target", cwd,
            "--no-deps"
        ])
        print("✅ Install successful via PIP.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install via PIP: {e}")
        return

    # 3. التأكد إن المسار الحالي مقروء
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    # 4. عملية الإصلاح (Fix chat_id error)
    print("🔧 Applying Fix for chat_id...")
    # المسار المتوقع للملف جوه المكتبة
    file_path = os.path.join(cwd, LIB_NAME, "mtproto", "pyrogram_client.py")
    
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            code = f.read()
        
        # الكود القديم (البايظ)
        old = "chat_id = self.chat_id(chats[update.chat_id])"
        # الكود الجديد (السليم)
        new = "chat_id = self.chat_id(chats[update.chat.id])"
        
        if old in code:
            code = code.replace(old, new)
            with open(file_path, "w") as f:
                f.write(code)
            print("✅ FIX APPLIED: chat_id bug resolved.")
        else:
            print("⚠️ Fix not needed (code already patched or different).")
    else:
        print(f"❌ Critical: Could not find {file_path} to patch!")

if __name__ == "__main__":
    setup_library()
