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
    print(get_message("WELCOME_MSG", lang="ar", user="MODFFX4T"))
    print(get_message("ERROR_ID", lang="ar", id="abc123"))
    print(get_message("SUCCESS_UNBAN", lang="ar", server=DEFAULT_SERVER))

    # مثال إنجليزي
    print(get_message("WELCOME_MSG", lang="en", user="PlayerOne"))
    print(get_message("UNBAN_IN_PROGRESS", lang="en", ticket="TCKT-0001"))