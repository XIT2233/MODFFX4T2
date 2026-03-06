# config.py
# =========================================
# MODFFX4T GRAVEYARD BOT CONFIGURATION FILE
# =========================================


# ---------------------------------
# معلومات البوت الأساسية
# ---------------------------------

BOT_NAME = "ONLY HAMED BOT"
BOT_VERSION = "3.5"

# التوكن من BotFather
API_TOKEN = "8625814942:AAF5zQYsDNlH50kw3eg05OYbCRZoctAomlE"


# ---------------------------------
# الأدمن
# ---------------------------------

# الأدمن الأساسي
ADMIN_ID = 8369383281

# قائمة الأدمن (يمكن إضافة أكثر من شخص)
ADMIN_IDS = [
    8369383281,
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

DEVELOPER_NAME = "X4T"
DEVELOPER_CONTACT = "@MODFFX4T"


# ---------------------------------
# نهاية الملف
# ---------------------------------