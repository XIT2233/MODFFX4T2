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