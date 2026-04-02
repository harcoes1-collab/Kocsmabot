import json
import logging
import os
import re
import asyncio
import random
import html
from datetime import datetime, timedelta, timezone

from flask import Flask, request, abort
from telegram import Bot, ChatPermissions
from telegram.request import HTTPXRequest

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecret")
PORT = int(os.getenv("PORT", "8000"))

if not BOT_TOKEN:
    raise RuntimeError("Hiányzik a BOT_TOKEN környezeti változó.")

flask_app = Flask(__name__)

DATA_FILE = "bot_data.json"

DELETE_BAD_MESSAGES = True

FIRST_MUTE_MINUTES = 5
SECOND_MUTE_MINUTES = 10
THIRD_MUTE_MINUTES = 30
FOURTH_PLUS_MUTE_MINUTES = 60

WELCOME_MESSAGE = (
    "🍻 <b>Üdvözlünk szerény kis kocsmánkban!</b>\n"
    "Érezd magad otthon, nyugodtan fáradj a pulthoz — "
    "a társaság barátságos és befogadó.\n"
    "Egyetlen dologra figyelj: tisztelettel beszéljetek egymással.\n"
    "Ha valakivel trágárul vagy sértően beszélsz, közbe fogok lépni."
)

BANNED_PATTERNS = [
    "fasz", "fasznak", "faszom", "faszfej", "faszkalap",
    "geci", "gecifej", "geciseg", "geciláda",
    "kurva", "kurvanyád", "kurva anyád",
    "bazdmeg", "baszdmeg",
    "szar", "szarkupac", "szarfészek", "szarházi", "szarhazi",
    "fos", "fost", "fosadék", "fosadek",
    "anyad", "anyád", "anyád picsája", "anyad picsaja",
    "hulye", "hülye", "hulyegyerek", "hülyegyerek",
    "idiota", "idióta",
    "retardalt", "retardált",
    "picsa", "picsád", "picsad",
    "pina", "pinád", "pinad",
    "szopjal", "szopjál", "szopó", "szopo", "szopás",
    "szopdki", "szopd ki",
    "rohadék", "rohadek", "rohadt", "rohadt élet",
    "dög", "dögölj meg", "dogolj meg",
    "buzi",
    "kocsog", "köcsög", "kocsogok", "köcsögök",
    "balfasz", "balfaszok",
    "csicska", "csicskagyász",
    "nyomorek", "nyomorék",
    "barom", "baromarc", "baromfej",
    "segg", "seggfej", "seggnyaló",
    "segghuly", "segghülye",
    "tetves", "tetves kurva",
    "hányadék", "hanyadek",
    "undorító", "undorito",
    "féreg", "fereg",
    "patkány", "patkany",
    "majom", "majomarc",
    "hulladék", "hulladek",
    "csicskageci",
    "anyaszomorító",
    "istenbarma",
    "gyászkeret",
    "szellemi fogyatékos",
    "kretén", "kreten",
    "degenerált", "degeneralt",
    "hülyegyökér", "hulyegyoker"
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
    "Ez most nem volt egy szép kör, próbáld újra kulturáltan.",
    "Lassíts, mielőtt kiborul a korsó.",
    "Ez már nem fér bele a ház szabályaiba.",
    "Kicsit elgurult a söröskupak, nem?",
    "Állj meg egy pillanatra, ez már sok.",
    "Ez nem az a hely, ahol így beszélünk.",
    "Ez most erős volt, inkább pihenj egyet.",
    "Nem kell itt a feszkó, chill egy kicsit.",
    "Ez a hangnem nem játszik itt.",
    "Kulturáltabban is megy, próbáld úgy.",
    "Ez most mínusz egy kör.",
    "Kicsit elszabadult a nyelved.",
    "Nem kell a dráma, maradjunk normálisak.",
    "Oltsd el magad sürgős jelleggel!.",
    "Higgadj le, aztán folytathatjuk.",
    "Ez már piros lap.",
    "Ez most túl lett tolva, vegyél vissza.",
    "Nem ide való ez a stílus.",
    "Kérlek maradj tiszteletteljes.",
    "Ez most nem fér bele, próbáld újra.",
    "Figyelj a hangnemre.",
    "Ez a viselkedés nem oké itt.",
    "Álljunk meg egy szóra, ez így nem jó.",
    "Maradjunk inkább normális keretek között.",
    "Próbálj meg kulturáltabban fogalmazni.",
    "Na ezt most visszaküldjük a csap alá.",
    "Ez most nem egy dicsőséges kör volt.",
    "A csapos már néz rád furán..",
    "Ezért nem jár újratöltés.",
    "Most inkább tedd le a korsót egy percre.",
    "Ez most olyan volt, mint a langyos sör.",
    "A sörbe rakd az arcodat, ne más arcába.",
    "Ez most nem ütött, inkább csak fröccsent.",
    "A hangulat jó volt, amíg ezt be nem dobtad.",
    "Na ezt most kiöntjük a pult mögött.",
    "Kicsit savanyú lett ez a kör.",
    "Ez most nem a legjobb házi főzet.",
    "A törzsvendégek ezért már morognak.",
    "Ez most nem tapsot kapott, csak csendet.",
    "Inkább még egy sör, kevesebb szó.",
    "Ez most nem ülte meg a hangulatot.",
    "Kicsit túlerjedt ez a mondat.",
    "Ez most lecsúszott, de nem jól.",
    "A csapból sem folyik ennyi feszültség.",
    "Na ebből nem kér még egy kört senki.",
    "Ez most inkább volt melléöntés.",
    "Ez most nem volt egy nyerő rendelés.",
    "A pult ezt most nem jegyzi fel jóként.",
    "Ez most inkább volt zajos, mint okos.",
    "Kicsit túl lett húzva a csap.",
    "Ez most nem a baráti kör kategória.",
    "Ezt most inkább hagyjuk ülepedni.",
    "Na ezt most elvitte a huzat a kocsmából."
]

WARNING_COOLDOWN_SECONDS = 5

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


def create_bot() -> Bot:
    request_client = HTTPXRequest(
        connection_pool_size=10,
        pool_timeout=20.0,
        read_timeout=20.0,
        write_timeout=20.0,
        connect_timeout=20.0,
    )
    return Bot(BOT_TOKEN, request=request_client)


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"offenses": {}, "last_warning_ts": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"offenses": {}, "last_warning_ts": {}}


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


LEET_MAP = {
    "0": "o", "1": "i", "!": "i", "|": "i", "3": "e", "4": "a",
    "@": "a", "$": "s", "5": "s", "7": "t", "+": "t", "8": "b", "9": "g",
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
    return "".join(LEET_MAP.get(ch, ch) for ch in text)


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


def mention_html(user_id: int, first_name: str) -> str:
    safe_name = html.escape(first_name or "Felhasználó")
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'


def get_mute_minutes(offense_count: int) -> int:
    if offense_count == 1:
        return FIRST_MUTE_MINUTES
    if offense_count == 2:
        return SECOND_MUTE_MINUTES
    if offense_count == 3:
        return THIRD_MUTE_MINUTES
    return FOURTH_PLUS_MUTE_MINUTES


async def is_user_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        logger.exception("Nem sikerült admin státuszt ellenőrizni.")
        return False


async def safe_warn_user(bot: Bot, chat_id: int, user_id: int, text: str):
    now_ts = int(datetime.now(timezone.utc).timestamp())
    last_ts = get_last_warning_ts(chat_id, user_id)

    if now_ts - last_ts < WARNING_COOLDOWN_SECONDS:
        logger.info("safe_warn_user: cooldown aktív")
        return

    set_last_warning_ts(chat_id, user_id, now_ts)

    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        logger.info("safe_warn_user: figyelmeztetés elküldve")
    except Exception:
        logger.exception("Nem sikerült figyelmeztető üzenetet küldeni.")


async def handle_start(bot: Bot, chat_id: int):
    logger.info("start_command lefutott")
    await bot.send_message(
        chat_id=chat_id,
        text="🍺 Kocsma moderátor bot aktív.\nFigyelem a trágár és sértő beszédet, szükség esetén törlök és némítok."
    )
    logger.info("start_command: válasz elküldve")


async def handle_help(bot: Bot, chat_id: int):
    await bot.send_message(
        chat_id=chat_id,
        text="/start - bot indítása\n/help - segítség\n/offenses - megmutatja a saját szabálysértéseid számát"
    )


async def handle_offenses(bot: Bot, chat_id: int, user_id: int):
    count = get_offense(chat_id, user_id)
    await bot.send_message(chat_id=chat_id, text=f"Eddigi szabálysértéseid száma: {count}")


async def handle_new_members(bot: Bot, message: dict):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    for member in message.get("new_chat_members", []):
        if member.get("is_bot"):
            continue
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"{mention_html(member['id'], member.get('first_name', 'Tag'))}\n\n{WELCOME_MESSAGE}",
                parse_mode="HTML",
            )
            logger.info("welcome_new_members: üdvözlés elküldve")
        except Exception:
            logger.exception("Nem sikerült üdvözlő üzenetet küldeni.")


async def handle_moderation(bot: Bot, message: dict):
    logger.info("moderate_message handler lefutott")

    chat = message.get("chat", {})
    user = message.get("from", {})

    chat_id = chat.get("id")
    chat_type = chat.get("type")
    user_id = user.get("id")
    first_name = user.get("first_name", "Felhasználó")
    message_id = message.get("message_id")

    if not chat_id or not user_id or not message_id:
        logger.info("moderate_message: hiányzó mezők")
        return

    if user.get("is_bot"):
        logger.info("moderate_message: user bot, kilépés")
        return

    text = message.get("text") or message.get("caption") or ""
    logger.info("moderate_message: kapott szöveg: %r", text)

    if not text.strip():
        return

    found = contains_banned_content(text)
    logger.info("moderate_message: talált tiltott minta = %r", found)

    if not found:
        return

    user_mention = mention_html(user_id, first_name)

    if await is_user_admin(bot, chat_id, user_id):
        random_message = random.choice(WARNING_MESSAGES)
        await safe_warn_user(
            bot,
            chat_id,
            user_id,
            f"🍺 {user_mention} {random_message}"
        )
        logger.info("moderate_message: admin warning elküldve")
        return

    if DELETE_BAD_MESSAGES:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info("moderate_message: szabályszegő üzenet törölve")
        except Exception:
            logger.exception("Nem sikerült törölni a szabályszegő üzenetet.")

    offense_count = increment_offense(chat_id, user_id)
    random_message = random.choice(WARNING_MESSAGES)
    mute_minutes = get_mute_minutes(offense_count)

    if chat_type != "supergroup":
        await safe_warn_user(
            bot,
            chat_id,
            user_id,
            f"⚠️ {user_mention} {random_message}"
        )
        logger.info("moderate_message: nem supergroup, mute kihagyva")
        return

    if offense_count == 1:
        reason_text = f"⚠️ {user_mention} {random_message}\n{mute_minutes} perc pihenő."
    elif offense_count == 2:
        reason_text = f"⚠️ {user_mention} {random_message}\n{mute_minutes} perc csend."
    elif offense_count == 3:
        reason_text = f"⚠️ {user_mention} {random_message}\n{mute_minutes} perc mute."
    else:
        reason_text = f"⚠️ {user_mention} {random_message}\n{mute_minutes} perc mute."

    until_date = datetime.now(timezone.utc) + timedelta(minutes=mute_minutes)

    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
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
        logger.info("moderate_message: mute sikeres")
    except Exception:
        logger.exception("Nem sikerült mute-olni a felhasználót.")
        await safe_warn_user(
            bot,
            chat_id,
            user_id,
            f"⚠️ {user_mention} {random_message}"
        )
        return

    await safe_warn_user(bot, chat_id, user_id, reason_text)


async def process_update_data(update_data: dict):
    bot = create_bot()

    message = update_data.get("message")
    if not message:
        logger.info("Nem message típusú update, kihagyva.")
        return

    chat = message.get("chat", {})
    user = message.get("from", {})
    chat_id = chat.get("id")
    user_id = user.get("id")
    text = message.get("text") or ""

    if message.get("new_chat_members"):
        await handle_new_members(bot, message)

    if text == "/start":
        await handle_start(bot, chat_id)
        return

    if text == "/help":
        await handle_help(bot, chat_id)
        return

    if text == "/offenses":
        await handle_offenses(bot, chat_id, user_id)
        return

    await handle_moderation(bot, message)


@flask_app.get("/")
def healthcheck():
    return "OK", 200


@flask_app.get("/health")
def health():
    return {"status": "ok"}, 200


@flask_app.post(f"/webhook/{WEBHOOK_SECRET}")
def webhook():
    update_data = request.get_json(silent=True)
    if not update_data:
        logger.error("Nem jött JSON a webhookra.")
        abort(400)

    logger.info("Webhook update megérkezett: %s", update_data)

    try:
        asyncio.run(process_update_data(update_data))
    except Exception:
        logger.exception("Webhook feldolgozási hiba")
        return "error", 500

    return "ok", 200


if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)
