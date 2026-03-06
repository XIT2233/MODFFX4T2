# admin_tools.py
"""
أدوات إدارية موسّعة لبوت تيليجرام (telebot).
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

# انتهاء الملف