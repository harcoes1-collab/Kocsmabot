import json
import logging
import os
import re
import asyncio
import random
from datetime import datetime, timedelta, timezone

# ===== Python 3.14 workaround =====
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from telegram import Update, ChatPermissions
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# BEÁLLÍTÁSOK
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

DATA_FILE = "bot_data.json"

DELETE_BAD_MESSAGES = True
DELETE_WARNING_AFTER_SECONDS = 18

FIRST_MUTE_MINUTES = 10
REPEAT_MUTE_MINUTES = 60

WELCOME_MESSAGE = (
    "🍻 <b>Üdvözlünk szerény kis kocsmánkban!</b>\n"
    "Érezd magad otthon, nyugodtan fáradj a pulthoz — "
    "a társaság barátságos és befogadó.\n"
    "Egyetlen dologra figyelj: tisztelettel beszéljetek egymással.\n"
    "Ha valakivel trágárul vagy sértően beszélsz, közbe fogok lépni."
)

BANNED_PATTERNS = [
    "fasz",
    "fasznak",
    "faszom",
    "geci",
    "kurva",
    "bazdmeg",
    "baszdmeg",
    "szar",
    "anyad",
    "anyád",
    "hulye",
    "hülye",
    "idiota",
    "idióta",
    "retardalt",
    "retardált",
    "picsa",
    "szopjal",
    "szopjál",
    "rohadék",
    "rohadek",
    "fasszopo",
    "faszopo",
    "faszopo",
    "fasszopó",
    "buzi",
    "gyoker",
    "gyökér",
]

WARNING_MESSAGES = [
    "Nyugi van, nem ez kocsmai bunyó.",
    "Ez már túlment a határon.",
    "Túl sok volt a hab a korsóban? 🍺",
    "Vedd lejjebb a hangerőt, haver!",
    "Hé, ez nem a hátsó udvar!",
    "A pultnál ilyet nem mondunk.",
    "Kicsit túlcsordult a korsó, nem? 🍻",
    "Itt mindenki inni jött, nem veszekedni.",
    "Na ebből most elég lesz, kortyolj inkább egyet.",
    "Túl lett tolva, jön a csend.",
]

WARNING_COOLDOWN_SECONDS = 45

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# az httpx túl sokat logol, visszavesszük
logging.getLogger("httpx").setLevel(logging.WARNING)

# =========================
# ADATTÁROLÁS
# =========================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "offenses": {},
            "last_warning_ts": {},
        }
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "offenses": {},
            "last_warning_ts": {},
        }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


DB = load_data()


def get_nested(d, *keys, default=None):
    cur = d
    for key in keys:
        if key not in cur:
            return default
        cur = cur[key]
    return cur


def set_offense(chat_id: int, user_id: int, value: int):
    chat_key = str(chat_id)
    user_key = str(user_id)
    DB.setdefault("offenses", {})
    DB["offenses"].setdefault(chat_key, {})
    DB["offenses"][chat_key][user_key] = value
    save_data(DB)


def get_offense(chat_id: int, user_id: int) -> int:
    return int(get_nested(DB, "offenses", str(chat_id), str(user_id), default=0) or 0)


def increment_offense(chat_id: int, user_id: int) -> int:
    current = get_offense(chat_id, user_id)
    current += 1
    set_offense(chat_id, user_id, current)
    return current


def get_last_warning_ts(chat_id: int, user_id: int) -> int:
    return int(get_nested(DB, "last_warning_ts", str(chat_id), str(user_id), default=0) or 0)


def set_last_warning_ts(chat_id: int, user_id: int, ts: int):
    chat_key = str(chat_id)
    user_key = str(user_id)
    DB.setdefault("last_warning_ts", {})
    DB["last_warning_ts"].setdefault(chat_key, {})
    DB["last_warning_ts"][chat_key][user_key] = ts
    save_data(DB)

# =========================
# SZÖVEG NORMALIZÁLÁS
# =========================

LEET_MAP = {
    "0": "o",
    "1": "i",
    "!": "i",
    "|": "i",
    "3": "e",
    "4": "a",
    "@": "a",
    "$": "s",
    "5": "s",
    "7": "t",
    "+": "t",
    "8": "b",
    "9": "g",
}

SEPARATOR_CHARS_PATTERN = r"[\s\.\,\-\_\*\~\`\:\;\(\)\[\]\{\}\\/]+"

def strip_accents_hu(text: str) -> str:
    replacements = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ö": "o", "ő": "o",
        "ú": "u", "ü": "u", "ű": "u",
    }
    text = text.lower()
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def leet_normalize(text: str) -> str:
    out = []
    for ch in text:
        out.append(LEET_MAP.get(ch, ch))
    return "".join(out)


def collapse_repeated_chars(text: str) -> str:
    return re.sub(r"(.)\1{2,}", r"\1", text)


def normalize_text_variants(text: str) -> list[str]:
    base = strip_accents_hu(text)
    base = leet_normalize(base)
    base = collapse_repeated_chars(base)

    compact = re.sub(SEPARATOR_CHARS_PATTERN, "", base)
    alnum_only = re.sub(r"[^a-z0-9]", "", base)

    return list({base, compact, alnum_only})


def contains_banned_content(text: str) -> str | None:
    variants = normalize_text_variants(text)

    for bad in BANNED_PATTERNS:
        bad_norm = strip_accents_hu(bad)
        for variant in variants:
            if bad_norm in variant:
                return bad
    return None

# =========================
# SEGÉDFÜGGVÉNYEK
# =========================

async def is_user_admin(chat, user_id: int) -> bool:
    try:
        member = await chat.get_member(user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def delete_later(message, delay: int):
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except Exception:
        pass


async def safe_warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    if not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    now_ts = int(datetime.now(timezone.utc).timestamp())
    last_ts = get_last_warning_ts(chat_id, user_id)

    if now_ts - last_ts < WARNING_COOLDOWN_SECONDS:
        return

    set_last_warning_ts(chat_id, user_id, now_ts)

    try:
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(delete_later(sent, DELETE_WARNING_AFTER_SECONDS))
    except Exception:
        logger.exception("Nem sikerült figyelmeztető üzenetet küldeni.")

# =========================
# PARANCSOK
# =========================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(
        "🍺 Kocsma moderátor bot aktív.\n"
        "Figyelem a trágár és sértő beszédet, szükség esetén törlök és némítok."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(
        "/start - bot indítása\n"
        "/help - segítség\n"
        "/offenses - megmutatja a saját szabálysértéseid számát"
    )


async def offenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    count = get_offense(update.effective_chat.id, update.effective_user.id)
    await update.message.reply_text(f"Eddigi szabálysértéseid száma: {count}")

# =========================
# ÜDVÖZLÉS
# =========================

async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue

        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{member.mention_html()}\n\n{WELCOME_MESSAGE}",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            logger.exception("Nem sikerült üdvözlő üzenetet küldeni.")

# =========================
# MODERÁLÁS
# =========================

async def moderate_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    message = update.message
    user = update.effective_user
    chat = update.effective_chat

    if user.is_bot:
        return

    text = message.text or message.caption or ""
    if not text.strip():
        return

    found = contains_banned_content(text)
    if not found:
        return

    if await is_user_admin(chat, user.id):
        random_message = random.choice(WARNING_MESSAGES)

        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"🍺 {user.mention_html()} {random_message}",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

        return

    if DELETE_BAD_MESSAGES:
        try:
            await message.delete()
        except Exception:
            logger.exception("Nem sikerült törölni a szabályszegő üzenetet.")

    offense_count = increment_offense(chat.id, user.id)
    random_message = random.choice(WARNING_MESSAGES)

    if offense_count == 1:
        mute_minutes = FIRST_MUTE_MINUTES
        reason_text = (
            f"⚠️ {user.mention_html()} {random_message}\n"
            f"{mute_minutes} perc pihenő."
        )
    else:
        mute_minutes = REPEAT_MUTE_MINUTES
        reason_text = (
            f"⚠️ {user.mention_html()} {random_message}\n"
            f"{mute_minutes} perc csend."
        )

    until_date = datetime.now(timezone.utc) + timedelta(minutes=mute_minutes)

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_manage_topics=False,
            ),
            until_date=until_date,
        )
    except Exception:
        logger.exception("Nem sikerült mute-olni a felhasználót.")
        await safe_warn_user(
            update,
            context,
            (
                f"⚠️ {user.mention_html()} trágár vagy sértő beszédet használt. "
                "A mute nem sikerült — ellenőrizd, hogy a bot admin-e és van-e joga korlátozni a tagokat."
            ),
        )
        return

    await safe_warn_user(update, context, reason_text)

# =========================
# FUTTATÁS
# =========================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("offenses", offenses_command))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, moderate_message))
    app.add_handler(MessageHandler(filters.CAPTION, moderate_message))

    print("Bot elindult...")
    app.run_polling()


if __name__ == "__main__":
    main()
