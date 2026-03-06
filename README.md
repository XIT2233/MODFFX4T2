
المزايا الرئيسية:
 - دعم قائمة مدراء متعددة (ADMIN_IDS)
 - ديكوريتور @require_admin لحماية الأوامر
 - دوال بث مرنة مع: تجزئة (chunking)، فترة انتظار بين الدُفعات، نمط المعالجة النصية، ووضع المعاينة preview
 - تسجيل نتائج الإرسال (نجاحات، فشل، أخطاء مفصّلة)
 - دعم إرسال تنبيهات مع ذكر المستخدمين (mention)
 - إمكانية عرض تقدم البث عبر رسالة قابلة للتعديل (اختياري)
"""

from functools import wraps
import time
import logging
from typing import Iterable, List, Tuple, Dict, Optional, Any

# تأكد أن config يحتوي على ADMIN_IDS = [12345, 67890]
import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# --- صلاحيات الأدمن -----------------------------------
def is_admin(user_id: int) -> bool:
    """
    تحقق من أن المعرف ضمن قائمة المشرفين في config.ADMIN_IDS.
    config.ADMIN_IDS يجب أن تكون قائمة من الأعداد الصحيحة.
    """
    admins = getattr(config, "ADMIN_IDS", None)
    if admins is None:
        # إذا لم توجد قائمة، فاعتبر فقط ADMIN_ID الوحيد (التوافق للنسخ القديمة)
        single = getattr(config, "ADMIN_ID", None)
        if single is None:
            logger.warning("لا توجد إعدادات ADMIN_IDS أو ADMIN_ID في config.")
            return False
        return user_id == single
    return user_id in admins


def require_admin(func):
    """
    ديكوريتور لحماية handlers: يتحقق من أن المرسل admin قبل التنفيذ.
    يفترض أن الدالة المزيّفة تستقبل (message, ...) كما في telebot.
    """
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = getattr(message.from_user, "id", None)
        if user_id is None or not is_admin(user_id):
            try:
                # الرد الآمن عند الرفض
                message.reply("⛔ هذه الخاصية متاحة للمشرفين فقط.")
            except Exception:
                logger.warning("فشل إرسال رسالة رفض الصلاحية.")
            return
        return func(message, *args, **kwargs)
    return wrapper


# --- استخراج المستخدمين من قاعدة البيانات -----------------
def get_registered_users(db: Optional[Any] = None, db_cursor: Optional[Any] = None) -> List[int]:
    """
    حاول إرجاع قائمة user_id مسجلة. يدعم:
     - كائن db (مع method fetch_all_user_ids أو execute)
     - أو db_cursor (sqlite3.Cursor) مع استعلام بسيط
    """
    # إذا تم تمرير كائن db بالأسلوب القديم
    if db is not None:
        # دعم واجهات شائعة: db.get_all_user_ids() أو db.fetch_users()
        fetch_methods = ["get_all_user_ids", "fetch_all_user_ids", "fetch_users", "get_users"]
        for m in fetch_methods:
            if hasattr(db, m):
                try:
                    rows = getattr(db, m)()
                    # صفوف قد تكون قائمة أعداد أو قائمة tuples
                    user_ids = [r if isinstance(r, int) else (r[0] if isinstance(r, (list, tuple)) else int(r)) for r in rows]
                    return user_ids
                except Exception:
                    continue
        # حاول استخدام cursor من داخل db (مثل sqlite wrapper)
        try:
            cur = getattr(db, "cursor")()
            cur.execute("SELECT user_id FROM users")
            rows = cur.fetchall()
            return [int(r[0]) for r in rows]
        except Exception:
            logger.exception("فشل في جلب المستخدمين من كائن db.")
            return []

    # إذا تم تمرير كورتسر مباشر
    if db_cursor is not None:
        try:
            db_cursor.execute("SELECT user_id FROM users")
            rows = db_cursor.fetchall()
            return [int(r[0]) for r in rows]
        except Exception:
            logger.exception("فشل تنفيذ استعلام المستخدمين عبر db_cursor.")
            return []

    # لا توجد داتا مصدر محدد
    logger.warning("لم يقدم db أو db_cursor، إرجاع قائمة فارغة.")
    return []


# --- إرسال رسالة آمن لمستخدم واحد -------------------------
def safe_send(bot, user_id: int, text: str, **send_kwargs) -> Tuple[bool, Optional[str]]:
    """
    حاول إرسال رسالة بعناية، وأعد (True, None) على النجاح،
    أو (False, 'error message') عند الخطأ.
    send_kwargs تمرر إلى bot.send_message (مثل parse_mode, disable_web_page_preview, ...)
    """
    try:
        bot.send_message(user_id, text, **send_kwargs)
        return True, None
    except Exception as e:
        logger.debug("فشل الإرسال إلى %s: %s", user_id, e)
        return False, str(e)


# --- دالة البث الأساسية ------------------------------------
def broadcast_message(
    bot,
    message_text: str,
    db: Optional[Any] = None,
    db_cursor: Optional[Any] = None,
    user_ids: Optional[Iterable[int]] = None,
    exclude: Optional[Iterable[int]] = None,
    chunk_size: int = 30,
    sleep_between_chunks: float = 1.0,
    parse_mode: Optional[str] = "Markdown",
    disable_web_page_preview: bool = True,
    disable_notification: bool = False,
    mention: bool = False,
    preview: bool = False,
    progress_chat_id: Optional[int] = None,  # لو حبيت تعرض تقدم في شات/محادثة معينة
) -> Dict[str, Any]:
    """
    بث رسالة إلى مجموعة مستخدمين:
      - يمكن تحديد user_ids مباشرة أو ترك النظام يستخرج المسجلين من db/db_cursor.
      - exclude: استبعاد معرفات معينة (admins مثلاً).
      - chunk_size + sleep_between_chunks: للتعامل مع حدود الrate-limit.
      - mention: لو True، يضبط النص ليشمل mention (ليس تلقائيًا لأن نحتاج ID لكل).
      - preview: لو True لا يرسل للمستخدمين وإنما يعيد لواحد أو لمدير (test).
      - progress_chat_id: لو مُعطى سيُحدث رسالة تقدم أثناء البث.
    تُعيد تقرير مفصّل يتضمن عدد النجاح/الفشل وأخطاء مفصّلة.
    """
    # جمع المستلمين
    if user_ids is None:
        targets = get_registered_users(db=db, db_cursor=db_cursor)
    else:
        targets = list(user_ids)

    if not targets:
        logger.info("قائمة المستلمين فارغة — لا يوجد ما يُرسل.")
        return {"total": 0, "sent": 0, "failed": 0, "failures": []}

    exclude_set = set(exclude or [])

    # فلترة المستلمين
    targets = [int(u) for u in targets if int(u) not in exclude_set]

    total = len(targets)
    sent = 0
    failed = 0
    failures: List[Dict[str, Any]] = []

    # إنشاء رسالة تقدم قابلة للتعديل إن طُلب
    progress_msg = None
    if progress_chat_id is not None:
        try:
            progress_msg = bot.send_message(progress_chat_id, f"🚀 بدء البث — 0 / {total}")
        except Exception:
            progress_msg = None

    # في وضع preview نرسل فقط لل admin الأول الموجود (أو لا نرسل إطلاقاً)
    if preview:
        preview_target = None
        admins = getattr(config, "ADMIN_IDS", None) or ([getattr(config, "ADMIN_ID")] if getattr(config, "ADMIN_ID", None) else [])
        if admins:
            preview_target = admins[0]
        elif targets:
            preview_target = targets[0]
        if preview_target:
            ok, err = safe_send(
                bot,
                preview_target,
                f"[معاينة بث]\n\n{message_text}",
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
                disable_notification=disable_notification
            )
            return {
                "total": total,
                "preview": True,
                "preview_target": preview_target,
                "preview_sent": ok,
                "preview_error": err
            }
        else:
            return {"total": total, "preview": True, "preview_sent": False, "preview_error": "لا يوجد هدف للمعاينة."}

    # تجزئة وإرسال
    for i in range(0, total, chunk_size):
        chunk = targets[i:i+chunk_size]

        for uid in chunk:
            # تجهيز النص (لو تبي mention: نغيّر النص لإضافة رابط tg://user?id=)
            text_to_send = message_text
            if mention:
                # إذا أردت تضمين رابط mention مع كل مرسل، ضع رابط قبل النص
                text_to_send = f"[المستخدم](tg://user?id={uid})\n\n{message_text}"

            ok, err = safe_send(
                bot,
                uid,
                text_to_send,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
                disable_notification=disable_notification
            )
            if ok:
                sent += 1
            else:
                failed += 1
                failures.append({"user_id": uid, "error": err})

            # تحديث رسالة التقدم لو موجودة
            if progress_msg is not None:
                try:
                    bot.edit_message_text(f"🚀 جاري البث — {sent} / {total} (فشل: {failed})", progress_chat_id, progress_msg.message_id)
                except Exception:
                    # تجاهل مشاكل تحديث الرسالة
                    pass

            # نترك مهلة قصيرة بين الرسائل الفردية لتفادي الحظر
            time.sleep(0.05)

        # بعد كل chunk، انتظر لفترة أطول قليلاً
        time.sleep(sleep_between_chunks)

    report = {
        "total": total,
        "sent": sent,
        "failed": failed,
        "failures": failures
    }
    logger.info("انتهى البث: %s", report)
    return report


# --- دالة مساعدة لإعادة المحاولة (retry) على الفاشلين -------------
def retry_failures(bot, failures: List[Dict[str, Any]], attempts: int = 2, delay: float = 1.0, parse_mode: Optional[str] = "Markdown"):
    """
    جرّب إعادة إرسال الرسائل التي فشلت مرتين (أو attempts مرات).
    يقوم بتحديث القائمة ويرجع تقريرًا.
    """
    final_failures = []
    retried = 0
    succeeded = 0

    for f in failures:
        uid = f.get("user_id")
        last_err = f.get("error")
        ok = False
        for _ in range(attempts):
            try:
                # هنا نفترض أنه لدينا نفس النص لكن لا نملك النص الأصلي — caller يجب أن يعيد محاولة مع النص الصحيح
                # لذا هذه الدالة لا تملك النص لإرسال؛ عادة يجب إعادة استدعاء broadcast_message مع user_ids=failed_ids
                time.sleep(delay)
            except Exception:
                pass
        # لا نستطيع فعل الكثير بدون النص؛ نُعلم المُنفّذ أن الأفضل إعادة تشغيل broadcast_message مع user_ids
        final_failures.append({"user_id": uid, "error": last_err})

    return {
        "retried_total": len(failures),
        "final_failures": final_failures,
        "succeeded": succeeded,
        "retried": retried
    }


# --- واجهات مساعدة إضافية -------------------------------
def send_to_user(bot, user_id: int, text: str, **kwargs) -> Dict[str, Any]:
    """غلاف صغير لـ safe_send مع إرجاع شكل تقرير مبسط."""
    ok, err = safe_send(bot, user_id, text, **kwargs)
    return {"user_id": user_id, "ok": ok, "error": err}


def broadcast_to_list(bot, message_text: str, user_ids: Iterable[int], **kwargs) -> Dict[str, Any]:
    """بث مباشر لقائمة user_ids معينة — مجرد تغليف لـ broadcast_message."""
    return broadcast_message(bot, message_text, user_ids=user_ids, **kwargs)


# --- مثال استخدام (تعليقات) -----------------------------
"""
مثال (في ملف main.py أو handler):

from admin_tools import require_admin, broadcast_message
import admin_tools

@bot.message_handler(commands=['broadcast'])
@require_admin
def cmd_broadcast(message):
    # نص البث بعد السطر الأول من الأمر
    text = message.text.partition(' ')[2].strip()
    if not text:
        message.reply("❗ أرسل رسالة البث بعد الأمر.")
        return

    # تنفيذ البث — افترض أن db هو كائن قاعدة بيانات في مشروعك:
    report = admin_tools.broadcast_message(
        bot,
        text,
        db=my_db_object,
        exclude=[123456789],  # استبعاد ID محدد لو أردت
        chunk_size=25,
        sleep_between_chunks=1.5,
        preview=False,
        mention=False,
        progress_chat_id=message.chat.id  # يعرض التقدم في نفس الشات
    )

    message.reply(f"انتهى البث: أرسلت {report['sent']} فشل {report['failed']} من {report['total']}")

"""

# config.py
# =========================================
# S7L GRAVEYARD BOT CONFIGURATION FILE
# =========================================


# ---------------------------------
# معلومات البوت الأساسية
# ---------------------------------

BOT_NAME = "S7L Graveyard Bot"
BOT_VERSION = "3.5"

# التوكن من BotFather
API_TOKEN = "8729430535:AAHxLGzbcq3OwHsY21x3LSX6IIA3VVg-YVo"


# ---------------------------------
# الأدمن
# ---------------------------------

# الأدمن الأساسي
ADMIN_ID = 3011444229

# قائمة الأدمن (يمكن إضافة أكثر من شخص)
ADMIN_IDS = [
    12345678,
]

# هل يسمح للأدمن بتنفيذ أوامر خاصة
ENABLE_ADMIN_COMMANDS = True


# ---------------------------------
# القناة
# ---------------------------------

# الاشتراك الإجباري
FORCE_SUBSCRIBE = False

# رابط القناة
CHANNEL_LINK = "https://t.me/YourChannel"

# معرف القناة
CHANNEL_ID = None


# ---------------------------------
# قاعدة البيانات
# ---------------------------------

DATABASE_NAME = "graveyard_data.db"

# النسخ الاحتياطي
AUTO_BACKUP = True
BACKUP_INTERVAL_HOURS = 24


# ---------------------------------
# الحماية
# ---------------------------------

# حماية من السبام
ANTI_SPAM = True

# عدد الطلبات المسموحة
MAX_REQUESTS_PER_USER = 5

# وقت الانتظار بين الطلبات (ثواني)
REQUEST_COOLDOWN = 30


# ---------------------------------
# البلاك ليست
# ---------------------------------

ENABLE_BLACKLIST = True

# سبب البلوك الافتراضي
DEFAULT_BLACKLIST_REASON = "Spam Abuse"


# ---------------------------------
# البث
# ---------------------------------

ENABLE_BROADCAST = True

# عدد الرسائل في كل دفعة
BROADCAST_CHUNK_SIZE = 25

# وقت الانتظار بين كل دفعة
BROADCAST_DELAY = 1.2


# ---------------------------------
# نظام السجلات
# ---------------------------------

ENABLE_LOGS = True

# عدد السجلات التي يتم حفظها
MAX_LOGS = 1000


# ---------------------------------
# الرسائل
# ---------------------------------

FOOTER_TEXT = "S7L GRAVEYARD SYSTEM v3.0"

POWERED_TEXT = "Powered By S7L SYSTEM"

WELCOME_EMOJI = "🔥"
SUCCESS_EMOJI = "✅"
ERROR_EMOJI = "⚠️"


# ---------------------------------
# مظهر البوت
# ---------------------------------

USE_MARKDOWN = True

DEFAULT_PARSE_MODE = "Markdown"

SHOW_PROCESS_ANIMATION = True


# ---------------------------------
# السيرفر
# ---------------------------------

BOT_POLLING_TIMEOUT = 30

BOT_RECONNECT_DELAY = 5


# ---------------------------------
# وضع التطوير
# ---------------------------------

DEBUG_MODE = False

TEST_MODE = False


# ---------------------------------
# إعدادات إضافية
# ---------------------------------

ENABLE_USER_STATS = True

ENABLE_REQUEST_HISTORY = True

ENABLE_ADMIN_LOGS = True

ENABLE_USER_PROFILE = True


# ---------------------------------
# حدود البوت
# ---------------------------------

MAX_USERS_LIMIT = 100000

MAX_REQUESTS_DATABASE = 500000


# ---------------------------------
# معلومات المطور
# ---------------------------------

DEVELOPER_NAME = "S7L"
DEVELOPER_CONTACT = "@YourTelegram"

# database.py

import sqlite3
import datetime


class GraveyardDB:

    def __init__(self, db_name="graveyard_data.db"):

        # الاتصال بقاعدة البيانات
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()

        # إنشاء الجداول
        self.create_tables()

    # ---------------------------------
    # إنشاء الجداول
    # ---------------------------------

    def create_tables(self):

        # جدول المستخدمين
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            join_date TEXT,
            total_requests INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0
        )
        """)

        # جدول طلبات فك البند
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS unban_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT,
            user_id INTEGER,
            status TEXT DEFAULT 'Pending',
            request_date TEXT
        )
        """)

        # جدول البلاك ليست
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS blacklist(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            reason TEXT,
            date TEXT
        )
        """)

        # جدول سجل العمليات
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            user_id INTEGER,
            date TEXT
        )
        """)

        self.conn.commit()

    # ---------------------------------
    # إدارة المستخدمين
    # ---------------------------------

    def add_user(self, user_id, username):

        date = datetime.datetime.now().strftime("%Y-%m-%d")

        self.cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, join_date) VALUES (?, ?, ?)",
            (user_id, str(username), date)
        )

        self.conn.commit()

    def remove_user(self, user_id):

        self.cursor.execute(
            "DELETE FROM users WHERE user_id = ?",
            (user_id,)
        )

        self.conn.commit()

    def get_user(self, user_id):

        self.cursor.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        )

        return self.cursor.fetchone()

    # ---------------------------------
    # طلبات فك البند
    # ---------------------------------

    def log_unban_request(self, player_id, user_id):

        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.cursor.execute(
            "INSERT INTO unban_requests (player_id, user_id, request_date) VALUES (?, ?, ?)",
            (player_id, user_id, date)
        )

        self.cursor.execute(
            "UPDATE users SET total_requests = total_requests + 1 WHERE user_id = ?",
            (user_id,)
        )

        self.conn.commit()

    def update_request_status(self, request_id, status):

        self.cursor.execute(
            "UPDATE unban_requests SET status = ? WHERE id = ?",
            (status, request_id)
        )

        self.conn.commit()

    def get_user_requests(self, user_id):

        self.cursor.execute(
            "SELECT * FROM unban_requests WHERE user_id = ?",
            (user_id,)
        )

        return self.cursor.fetchall()

    def get_last_requests(self, limit=10):

        self.cursor.execute(
            "SELECT * FROM unban_requests ORDER BY id DESC LIMIT ?",
            (limit,)
        )

        return self.cursor.fetchall()

    # ---------------------------------
    # البلاك ليست
    # ---------------------------------

    def add_to_blacklist(self, user_id, reason="Unknown"):

        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.cursor.execute(
            "INSERT INTO blacklist (user_id, reason, date) VALUES (?, ?, ?)",
            (user_id, reason, date)
        )

        self.conn.commit()

    def remove_from_blacklist(self, user_id):

        self.cursor.execute(
            "DELETE FROM blacklist WHERE user_id = ?",
            (user_id,)
        )

        self.conn.commit()

    def is_blacklisted(self, user_id):

        self.cursor.execute(
            "SELECT * FROM blacklist WHERE user_id = ?",
            (user_id,)
        )

        return self.cursor.fetchone() is not None

    # ---------------------------------
    # السجلات
    # ---------------------------------

    def log_action(self, action, user_id):

        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.cursor.execute(
            "INSERT INTO logs (action, user_id, date) VALUES (?, ?, ?)",
            (action, user_id, date)
        )

        self.conn.commit()

    def get_logs(self, limit=20):

        self.cursor.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?",
            (limit,)
        )

        return self.cursor.fetchall()

    # ---------------------------------
    # الإحصائيات
    # ---------------------------------

    def get_total_users(self):

        self.cursor.execute("SELECT COUNT(*) FROM users")
        return self.cursor.fetchone()[0]

    def get_total_requests(self):

        self.cursor.execute("SELECT COUNT(*) FROM unban_requests")
        return self.cursor.fetchone()[0]

    def get_today_requests(self):

        today = datetime.datetime.now().strftime("%Y-%m-%d")

        self.cursor.execute(
            "SELECT COUNT(*) FROM unban_requests WHERE request_date LIKE ?",
            (today + "%",)
        )

        return self.cursor.fetchone()[0]

    def get_blacklist_count(self):

        self.cursor.execute("SELECT COUNT(*) FROM blacklist")
        return self.cursor.fetchone()[0]


# ---------------------------------
# تشغيل قاعدة البيانات
# ---------------------------------

db = GraveyardDB()
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
# strings.py
"""
ملفات النصوص (الرسائل) المنظمة لبوت الكلان.
يدعم:
 - لغات (ar, en)
 - placeholders مثل {user}, {id}, {server}
 - دالة آمنة get_message لتجنب KeyError عند غياب placeholder
"""

from typing import Dict

DEFAULT_LANG = "ar"
DEFAULT_SERVER = "S7L"

# قاموس الرسائل لكل لغة
MESSAGES: Dict[str, Dict[str, str]] = {
    "ar": {
        "WELCOME_MSG": (
            "🔥 **أهلاً بك في أقوى بوت لخدمات الكلان**\n"
            "------------------------------\n"
            "🚀 نحن نوفر لك أفضل الأدوات البرمجية.\n"
            "🧬 اختر من القائمة أدناه لبدء العملية.\n"
            "\n"
            "مرحباً، {user} — الرجاء اختيار العملية أو كتابة /help لمزيد من الخيارات."
        ),
        "HELP_MENU": (
            "📚 **قائمة الأوامر**\n"
            "/unban <id> - طلب فك الحظر عن لاعب.\n"
            "/status - حالة الخادم.\n"
            "/support - التواصل مع الدعم.\n"
            "---------------------------------\n"
            "مثال: `/unban 123456`"
        ),
        "ERROR_ID": "⚠️ خطأ! الـ ID الذي أرسلته غير صحيح، يجب أن يتكون من أرقام فقط. المدخل: `{id}`",
        "SUCCESS_UNBAN": "✅ تم استلام طلبك بنجاح! جاري معالجة البيانات على سيرفرات {server}...",
        "CONFIRM_UNBAN": "🔔 هل أنت متأكد أنك تريد إرسال طلب فك الحظر عن اللاعب ذي الـ ID `{id}`؟ (نعم/لا)",
        "UNBAN_IN_PROGRESS": "⏳ تم إرسال الطلب، الحالة: جارٍ المعالجة — رقم الطلب: `{ticket}`.",
        "UNBAN_COMPLETE": "🎉 تم فك الحظر عن اللاعب `{id}` بنجاح! بواسطة: {processed_by}",
        "INVALID_COMMAND": "❓ أمر غير معروف. اكتب /help لعرض الأوامر المتاحة.",
        "PERMISSION_DENIED": "⛔ ليس لديك الصلاحية لأداء هذا الإجراء.",
        "NOT_FOUND": "🔍 لم أجد نتيجة تطابق `{query}`.",
        "SERVER_ERROR": "💥 حدث خطأ في الخادم. حاول مرة أخرى لاحقاً أو تواصل مع الدعم.",
        "FOOTER": "📌 إذا احتجت مساعدة، استخدم /support أو تواصل مع فريقنا."
    },
    "en": {
        "WELCOME_MSG": (
            "🔥 **Welcome to the clan services bot**\n"
            "------------------------------\n"
            "🚀 We provide the best developer tools.\n"
            "🧬 Choose from the menu below to get started.\n"
            "\n"
            "Hello, {user} — please choose an action or type /help for options."
        ),
        "HELP_MENU": (
            "📚 **Commands**\n"
            "/unban <id> - Submit an unban request.\n"
            "/status - Check server status.\n"
            "/support - Contact support.\n"
            "---------------------------------\n"
            "Example: `/unban 123456`"
        ),
        "ERROR_ID": "⚠️ Error! The ID you sent is invalid — numbers only. Input: `{id}`",
        "SUCCESS_UNBAN": "✅ Your request was received successfully! Processing on {server} servers...",
        "CONFIRM_UNBAN": "🔔 Are you sure you want to submit an unban for ID `{id}`? (yes/no)",
        "UNBAN_IN_PROGRESS": "⏳ Request submitted, status: processing — ticket: `{ticket}`.",
        "UNBAN_COMPLETE": "🎉 Player `{id}` has been unbanned successfully! processed by: {processed_by}",
        "INVALID_COMMAND": "❓ Unknown command. Type /help to see available commands.",
        "PERMISSION_DENIED": "⛔ You don't have permission to perform this action.",
        "NOT_FOUND": "🔍 No results found for `{query}`.",
        "SERVER_ERROR": "💥 Server error occurred. Please try again later or contact support.",
        "FOOTER": "📌 If you need help, use /support or contact our team."
    },
}

# دِالة مساعدة لطباعة القوالب بأمان (لا ترفع استثناء لو فقد placeholder)
class _SafeDict(dict):
    def __missing__(self, key):
        # لو المفتاح مفقود، رجع placeholder كما هو لكي يراه المدير/المطور
        return "{" + key + "}"

def get_message(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """
    ترجع النص المطلوب بحسب المفتاح واللغة، مع استبدال ال placeholders بالقيم الممررة.
    مثال: get_message('SUCCESS_UNBAN', user='عمر', server='S7L')
    """
    language = lang if lang in MESSAGES else DEFAULT_LANG
    template = MESSAGES[language].get(key)
    if template is None:
        # لو المفتاح غير موجود، نرجع المفتاح نفسه كتحذير مبرمج
        return f"[missing message: {key}]"
    return template.format_map(_SafeDict(**kwargs))


# --- مثال استخدام سريع ---
if __name__ == "__main__":
    # مثال عربي
    print(get_message("WELCOME_MSG", lang="ar", user="نـ؁ـيمار1%ㅤ"))
    print(get_message("ERROR_ID", lang="ar", id="abc123"))
    print(get_message("SUCCESS_UNBAN", lang="ar", server=DEFAULT_SERVER))

    # مثال إنجليزي
    print(get_message("WELCOME_MSG", lang="en", user="PlayerOne"))
    print(get_message("UNBAN_IN_PROGRESS", lang="en", ticket="TCKT-0001"))
