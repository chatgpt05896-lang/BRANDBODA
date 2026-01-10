import os
import zipfile
import urllib.request
import shutil
import sys

def setup_library():
    # اسم المجلد اللي هنحط فيه المكتبة
    LIB_NAME = "pytgcalls"
    
    # لو المكتبة موجودة، خلاص منعملش حاجة
    if os.path.exists(LIB_NAME):
        print(f"✅ Library {LIB_NAME} is already installed locally.")
        sys.path.insert(0, os.getcwd())
        return

    print("⏳ Downloading PyTgCalls v2.2.8 (Source Code)...")
    
    # 1. تحميل الملف المضغوط
    url = "https://github.com/pytgcalls/pytgcalls/archive/refs/tags/v2.2.8.zip"
    zip_path = "v2.2.8.zip"
    
    try:
        urllib.request.urlretrieve(url, zip_path)
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return

    # 2. فك الضغط
    print("📦 Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("temp_extract")
    
    # 3. نقل الفولدر لمكانه الصحيح
    # في الملف المضغوط الفولدر اسمه pytgcalls-2.2.8 وجواه فولدر اسمه pytgcalls
    extracted_path = os.path.join("temp_extract", "pytgcalls-2.2.8", "pytgcalls")
    
    if os.path.exists(extracted_path):
        shutil.move(extracted_path, LIB_NAME)
        print("✅ Library moved to root folder.")
    else:
        print("❌ Could not find library folder inside zip.")
    
    # 4. تنظيف الملفات المؤقتة
    if os.path.exists(zip_path): os.remove(zip_path)
    if os.path.exists("temp_extract"): shutil.rmtree("temp_extract")

    # 5. الإصلاح (Fix chat_id error)
    print("🔧 Applying Fix for chat_id...")
    file_to_fix = os.path.join(LIB_NAME, "mtproto", "pyrogram_client.py")
    
    if os.path.exists(file_to_fix):
        with open(file_to_fix, "r") as f:
            content = f.read()
        
        # استبدال الكود الخطأ بالكود الصحيح
        old_code = "chat_id = self.chat_id(chats[update.chat_id])"
        new_code = "chat_id = self.chat_id(chats[update.chat.id])"
        
        if old_code in content:
            content = content.replace(old_code, new_code)
            with open(file_to_fix, "w") as f:
                f.write(content)
            print("✅ FIX APPLIED SUCCESSFULLY!")
        else:
            print("⚠️ Fix not needed or code changed.")
    
    # إضافة المجلد الحالي للمسارات عشان البوت يشوفه
    sys.path.insert(0, os.getcwd())

if __name__ == "__main__":
    setup_library()
