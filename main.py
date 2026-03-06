# main.py

import telebot
from telebot import types
import time
import random

# استيراد الملفات الأخرى
import config
import strings
from database import db

# ---------------------------------
# تهيئة البوت
# ---------------------------------
bot = telebot.TeleBot(config.API_TOKEN)

print("🚀 --- البوت يعمل الآن على Termux ---")

# ---------------------------------
# دالة شريط التقدم
# ---------------------------------
def progress_bar(chat_id, text="⏳ جاري المعالجة..."):
    msg = bot.send_message(chat_id, text)

    steps = [
        "🔎 فحص الحساب...",
        "📡 الاتصال بالسيرفر...",
        "📂 قراءة السجلات...",
        "⚙️ تنفيذ العملية...",
        "✅ اكتملت العملية"
    ]

    for step in steps:
        time.sleep(1.5)
        bot.edit_message_text(step, chat_id, msg.message_id)

    return msg


# ---------------------------------
# أمر البداية
# ---------------------------------
@bot.message_handler(commands=['start'])
def start_command(message):

    user_id = message.from_user.id
    name = message.from_user.first_name

    # إضافة المستخدم
    db.add_user(user_id, name)

    # إنشاء الأزرار
    markup = types.InlineKeyboardMarkup(row_width=2)

    btn1 = types.InlineKeyboardButton(
        "🧬 فك البند (ID)",
        callback_data="unban"
    )

    btn2 = types.InlineKeyboardButton(
        "🛡️ تنظيف البلاك ليست",
        callback_data="blacklist"
    )

    btn3 = types.InlineKeyboardButton(
        "📊 حالة الطلب",
        callback_data="status"
    )

    btn4 = types.InlineKeyboardButton(
        "👤 حسابي",
        callback_data="profile"
    )

    markup.add(btn1, btn2)
    markup.add(btn3, btn4)

    bot.send_message(
        message.chat.id,
        strings.WELCOME_MSG,
        parse_mode="Markdown",
        reply_markup=markup
    )


# ---------------------------------
# التعامل مع الأزرار
# ---------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):

    chat_id = call.message.chat.id

    # ----------------------------
    # فك بند
    # ----------------------------
    if call.data == "unban":

        msg = bot.send_message(
            chat_id,
            "🆔 أرسل الـ ID المراد فك البند عنه:"
        )

        bot.register_next_step_handler(msg, process_unban)


    # ----------------------------
    # تنظيف البلاك ليست
    # ----------------------------
    elif call.data == "blacklist":

        progress_bar(chat_id)

        bot.send_message(
            chat_id,
            "🛡️ تم تنظيف سجلات البلاك ليست بنجاح!"
        )


    # ----------------------------
    # حالة الطلب
    # ----------------------------
    elif call.data == "status":

        ticket = random.randint(10000, 99999)

        bot.send_message(
            chat_id,
            f"""
📊 **حالة الطلب**

🆔 رقم الطلب : `{ticket}`
📡 الحالة : قيد المراجعة
⏳ الوقت المتوقع : 1 - 5 دقائق
""",
            parse_mode="Markdown"
        )


    # ----------------------------
    # الملف الشخصي
    # ----------------------------
    elif call.data == "profile":

        user = call.from_user

        bot.send_message(
            chat_id,
            f"""
👤 **معلومات حسابك**

🆔 ID : `{user.id}`
📛 الاسم : {user.first_name}
🤖 مستخدم البوت : نعم
""",
            parse_mode="Markdown"
        )


# ---------------------------------
# معالجة فك البند
# ---------------------------------
def process_unban(message):

    chat_id = message.chat.id
    player_id = message.text.strip()

    # تحقق من الـ ID
    if not player_id.isdigit():

        bot.send_message(
            chat_id,
            strings.ERROR_ID
        )
        return


    # تسجيل الطلب
    db.log_unban_request(player_id, message.from_user.id)

    # عرض تقدم العملية
    progress_bar(chat_id)

    # رسالة النجاح
    bot.send_message(
        chat_id,
        strings.SUCCESS_UNBAN,
        parse_mode="Markdown"
    )


# ---------------------------------
# أمر إداري لفك البلاك ليست
# ---------------------------------
@bot.message_handler(commands=['unblacklist'])
def admin_unblacklist(message):

    args = message.text.split()

    if len(args) < 2:
        bot.reply_to(
            message,
            "❗ استخدم الأمر هكذا:\n/unblacklist 123456"
        )
        return

    player_id = args[1]

    if not player_id.isdigit():
        bot.reply_to(message, "⚠️ الـ ID غير صالح")
        return


    progress_bar(message.chat.id)

    bot.send_message(
        message.chat.id,
        f"""
🛡️ **تم فك البلاك ليست**

🆔 ID : `{player_id}`
📡 الحالة : تمت الإزالة
""",
        parse_mode="Markdown"
    )


# ---------------------------------
# تشغيل البوت
# ---------------------------------
bot.infinity_polling()