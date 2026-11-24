
import os
import re
import asyncio
import logging
import tempfile
import shutil
import uuid
from pathlib import Path
from urllib.parse import quote

import yt_dlp

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError


# =====================================
# تنظیمات اصلی
# =====================================

TOKEN = "9128780938:AAFT7WYD9DC3kY66gish3hdn3zqmWO7XWJw"

CHANNEL_ID = "@linkdoni_hormoz"
CHANNEL_URL = "https://t.me/linkdoni_hormoz"

SUPPORT_ID = "https://t.me/d_yas3in"

BOT_NAME = "مستر دانلودر"

MAX_FILE_SIZE = 49 * 1024 * 1024
MAX_FILES = 10

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# =====================================
# منوی اصلی
# =====================================

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [
            KeyboardButton("📥 دانلود ویدیو"),
            KeyboardButton("🖼 دانلود عکس"),
        ],
        [
            KeyboardButton("📱 دانلود استوری"),
            KeyboardButton("📖 راهنما"),
        ],
        [
            KeyboardButton("🎧 پشتیبانی"),
        ],
    ],
    resize_keyboard=True,
    is_persistent=True
)


# =====================================
# عضویت اجباری
# =====================================

def join_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 عضویت در کانال",
                url=CHANNEL_URL
            )
        ],
        [
            InlineKeyboardButton(
                "✅ بررسی عضویت",
                callback_data="check_join"
            )
        ]
    ])


async def is_member(bot, user_id):
    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=user_id
        )

        return member.status in (
            "member",
            "administrator",
            "creator"
        )

    except TelegramError as error:
        logger.error("Membership check error: %s", error)
        return False


async def require_membership(update, context):
    user = update.effective_user

    if await is_member(context.bot, user.id):
        return True

    message = update.effective_message

    if message:
        await message.reply_text(
            "🔒 برای استفاده از مستر دانلودر ابتدا عضو کانال شو.\n\n"
            "بعد از عضویت، دکمه بررسی عضویت را بزن.",
            reply_markup=join_keyboard()
        )

    return False


# =====================================
# پیام خوش آمدگویی
# =====================================

WELCOME_TEXT = """
✨ به ربات مستر دانلودر خوش آمدید

📥 دانلود عکس و ویدیو از اینستاگرام
📱 دریافت استوری‌های عمومی

🔹 روش استفاده:
لینک پست، ریلز یا استوری عمومی را ارسال کنید.

⚡ سریع، ساده و آسان

از منوی پایین یکی از گزینه‌ها را انتخاب کنید.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_membership(update, context):
        return

    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=MAIN_MENU
    )


# =====================================
# بررسی عضویت
# =====================================

async def check_join(update, context):

    query = update.callback_query
    await query.answer()

    if await is_member(context.bot, query.from_user.id):

        await query.message.reply_text(
            "✅ عضویت شما تأیید شد!\n\n"
            "به مستر دانلودر خوش آمدید.",
            reply_markup=MAIN_MENU
        )

    else:
        await query.message.reply_text(
            "❌ هنوز عضویت شما تأیید نشده است.\n"
            "ابتدا عضو کانال شوید.",
            reply_markup=join_keyboard()
        )


# =====================================
# راهنما
# =====================================

async def show_help(update, context):

    if not await require_membership(update, context):
        return

    help_text = """
📖 راهنمای مستر دانلودر

1️⃣ وارد اینستاگرام شوید.

2️⃣ لینک پست، ریلز یا استوری عمومی را کپی کنید.

3️⃣ لینک را در همین ربات ارسال کنید.

4️⃣ ربات محتوای قابل دریافت را برای شما می‌فرستد.

📌 نکات:
• پیج خصوصی پشتیبانی نمی‌شود.
• استوری باید عمومی و قابل دسترسی باشد.
• بعضی لینک‌ها به دلیل محدودیت اینستاگرام دریافت نمی‌شوند.
• دکمه دریافت موزیک فقط در صورت وجود اطلاعات آهنگ کار می‌کند.
"""

    await update.message.reply_text(
        help_text,
        reply_markup=MAIN_MENU
    )


# =====================================
# پشتیبانی
# =====================================

async def support(update, context):

    if not await require_membership(update, context):
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🎧 ارتباط با پشتیبانی",
                url=SUPPORT_ID
            )
        ]
    ])

    await update.message.reply_text(
        "📞 برای ارتباط با پشتیبانی روی دکمه زیر بزنید.",
        reply_markup=keyboard
    )


# =====================================
# استخراج اطلاعات آهنگ
# =====================================

def get_music_query(info):

    if not isinstance(info, dict):
        return None

    entries = info.get("entries")

    if entries:
        for entry in entries:
            result = get_music_query(entry)
            if result:
                return result

    track = info.get("track")
    artist = info.get("artist") or info.get("creator")

    if track and artist:
        return f"{artist} {track}"

    if track:
        return str(track)

    return None


# =====================================
# دانلود اینستاگرام
# =====================================

def download_instagram(url):

    folder = tempfile.mkdtemp(prefix="master_downloader_")

    options = {
        "outtmpl": os.path.join(
            folder,
            "%(id)s_%(autonumber)s.%(ext)s"
        ),
        "format": "best[filesize<49000000]/best",
        "merge_output_format": "mp4",
        "noplaylist": False,
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 2,
        "socket_timeout": 30,
        "max_downloads": MAX_FILES,
        "max_filesize": MAX_FILE_SIZE,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)

        music_query = get_music_query(info)

        allowed = {
            ".mp4",
            ".m4v",
            ".mov",
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        }

        files = []

        for path in Path(folder).iterdir():

            if path.is_file() and path.suffix.lower() in allowed:
                if path.stat().st_size > 0:
                    files.append(str(path))

        files.sort()

        return folder, files, music_query, None

    except Exception as error:
        logger.error("Download error: %s", error)
        return folder, [], None, str(error)


# =====================================
# بررسی لینک اینستاگرام
# =====================================

def get_instagram_url(text):

    pattern = (
        r"https?://"
        r"(?:www\.)?"
        r"(?:instagram\.com|instagr\.am)"
        r"/[^\s]+"
    )

    match = re.search(pattern, text)

    if not match:
        return None

    return match.group(0).rstrip(".,!?)]}")


# =====================================
# دکمه دریافت موزیک
# =====================================

def music_keyboard(music_query):

    if music_query:
        music_url = (
            "https://music.youtube.com/search?q="
            + quote(music_query)
        )

        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🎵 دریافت موزیک",
                    url=music_url
                )
            ]
        ])

    music_id = uuid.uuid4().hex[:12]

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🎵 دریافت موزیک",
                callback_data=f"music:{music_id}"
            )
        ]
    ])


async def music_not_found(update, context):

    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "❌ آهنگ پیدا نشد.\n\n"
        "اطلاعات نام آهنگ در داده‌های این پست موجود نبود."
    )


# =====================================
# دریافت و ارسال فایل‌ها
# =====================================

async def process_download(update, context, url):

    message = update.message

    status = await message.reply_text(
        "⏳ در حال دریافت لینک و آماده‌سازی فایل‌ها...\n"
        "لطفاً کمی صبر کنید."
    )

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    folder, files, music_query, error = await asyncio.to_thread(
        download_instagram,
        url
    )

    try:

        if error:
            await status.edit_text(
                "❌ دریافت این لینک با مشکل مواجه شد.\n\n"
                "ممکن است اینستاگرام دسترسی دانلود را محدود کرده باشد.\n"
                "لطفاً لینک دیگری امتحان کنید."
            )
            return

        if not files:
            await status.edit_text(
                "❌ فایلی از این لینک دریافت نشد.\n\n"
                "لینک یک محتوای عمومی و قابل دسترسی را امتحان کنید."
            )
            return

        await status.edit_text(
            f"✅ تعداد {len(files)} فایل دریافت شد.\n"
            "در حال ارسال..."
        )

        sent = 0
        failed = 0

        for path in files[:MAX_FILES]:

            size = os.path.getsize(path)
            ext = Path(path).suffix.lower()

            if size > MAX_FILE_SIZE:
                failed += 1
                continue

            try:
                with open(path, "rb") as file:

                    if ext in (".jpg", ".jpeg", ".png") and size < 10 * 1024 * 1024:

                        await message.reply_photo(
                            photo=file,
                            caption="📷 دریافت‌شده از مستر دانلودر"
                        )

                    elif ext in (".mp4", ".m4v", ".mov"):

                        await message.reply_video(
                            video=file,
                            supports_streaming=True,
                            caption="🎬 دریافت‌شده از مستر دانلودر",
                            reply_markup=music_keyboard(music_query)
                        )

                    else:

                        await message.reply_document(
                            document=file,
                            caption="📁 دریافت‌شده از مستر دانلودر"
                        )

                sent += 1

            except TelegramError as send_error:
                logger.error("File send error: %s", send_error)
                failed += 1

        await status.edit_text(
            "🎉 عملیات به پایان رسید!\n\n"
            f"✅ فایل‌های ارسال‌شده: {sent}\n"
            f"⚠️ فایل‌های ارسال‌نشده: {failed}\n\n"
            "ممنون از استفاده شما از مستر دانلودر ❤️"
        )

    finally:
        shutil.rmtree(folder, ignore_errors=True)


# =====================================
# مدیریت پیام‌های کاربران
# =====================================

async def handle_message(update, context):

    if not await require_membership(update, context):
        return

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    if text == "📖 راهنما":
        await show_help(update, context)
        return

    if text == "🎧 پشتیبانی":
        await support(update, context)
        return

    if text == "📥 دانلود ویدیو":
        await update.message.reply_text(
            "🎬 لینک پست یا ریلز عمومی اینستاگرام را ارسال کنید."
        )
        return

    if text == "🖼 دانلود عکس":
        await update.message.reply_text(
            "🖼 لینک پست عکس اینستاگرام را ارسال کنید."
        )
        return

    if text == "📱 دانلود استوری":
        await update.message.reply_text(
            "📱 لینک استوری عمومی اینستاگرام را ارسال کنید.\n\n"
            "⚠️ استوری خصوصی یا غیرقابل دسترسی دریافت نمی‌شود."
        )
        return

    url = get_instagram_url(text)

    if not url:
        await update.message.reply_text(
            "❌ لینک معتبر اینستاگرام پیدا نشد.\n\n"
            "لطفاً لینک پست، ریلز یا استوری را ارسال کنید.",
            reply_markup=MAIN_MENU
        )
        return

    await process_download(update, context, url)


# =====================================
# مدیریت خطاها
# =====================================

async def error_handler(update, context):

    logger.error(
        "Bot error:",
        exc_info=context.error
    )


# =====================================
# اجرای ربات
# =====================================

def main():

    if (
        not TOKEN.strip()
        or TOKEN == "توکن_واقعی_ربات_را_اینجا_قرار_بده"
    ):
        print("لطفاً توکن واقعی ربات را در قسمت TOKEN وارد کنید.")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        CallbackQueryHandler(
            check_join,
            pattern="^check_join$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            music_not_found,
            pattern="^music:"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    app.add_error_handler(error_handler)

    print("مستر دانلودر با موفقیت آماده اجرا شد.")
    print("برای توقف ربات Ctrl + C را بزنید.")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
