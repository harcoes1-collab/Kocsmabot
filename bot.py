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

LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "-5015553528"))

if not BOT_TOKEN:
    raise RuntimeError("Hiányzik a BOT_TOKEN környezeti változó.")

flask_app = Flask(__name__)

DATA_FILE = "bot_data.json"
DELETE_BAD_MESSAGES = True

SEVERITY_MUTE_MINUTES = {
    1: 5,
    2: 10,
    3: 30,
    4: 60,
}

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
    "Gyújts inkább rá haver.",
    "Tekerj inkább egy vicces cigit..",
    "Kulturáltabban is megy, próbáld úgy.",
    "Ez most mínusz egy kör.",
    "Kicsit elszabadult a nyelved.",
    "Nem kell a dráma, maradjunk normálisak.",
    "Oltsd el magad sürgős jelleggel!.",
    "Higgadj le, aztán folytathatjuk.",
    "Belefőzzünk a sörbe?",
    "Ez most túl lett tolva, vegyél vissza.",
    "Nem ide való ez a stílus.",
    "Kérlek maradj tiszteletteljes.",
    "Ez most nem fér bele, próbáld újra.",
    "Figyelj a hangnemre.",
    "Ez a viselkedés nem oké itt.",
    "Na mivan? Pálinka akarsz lenni? Csak mert megoldható ha sokat káromkodsz..",
    "Maradjunk inkább normális keretek között.",
    "Próbálj meg kulturáltabban fogalmazni.",
    "Na ezt most visszaküldjük a csap alá.",
    "Ez most nem egy dicsőséges kör volt.",
    "A csapos már furán néz rád..",
    "Ezért nem jár újratöltés.",
    "Most inkább tedd le a korsót egy percre.",
    "Ez most olyan volt, mint a langyos sör.",
    "A sörbe rakd az arcodat, ne más arcába.",
    "Néz már! A kidobó PONT téged keres..",
    "A hangulat jó volt, amíg ezt be nem dobtad.",
    "Na ezt most kiöntjük a pult mögött.",
    "Kicsit savanyú lett ez a kör.",
    "Ez most nem a legjobb házi főzet.",
    "A törzsvendégek ezért már morognak.",
    "Lőre, lőre előre! Még egy és lecsücsülsz a földre!",
    "Inkább még egy sör, kevesebb szó.",
    "Ez most nem ülte meg a hangulatot.",
    "Lépjél csak ki egy cigire!",
    "Ez most lecsúszott, de nem jól.",
    "A csapból sem folyik ennyi feszültség.",
    "Na ebből nem kér még egy kört senki.",
    "Ez most inkább volt melléöntés.",
    "Ez most nem volt egy nyerő rendelés.",
    "A pult ezt most nem jegyzi fel jónak.",
    "Mondtuk nincs hitelre ivászat! Pusztulj dolgozni!",
    "Lőre, lőre előre! Te meg koccansz a padló kövére!",
    "Ez most nem a baráti kör kategória.",
    "Ezt most inkább hagyjuk ülepedni.",
    "Na ezt most elvitte a huzat a kocsmából."
    "Ezt most leöblítjük egy nagy csönddel."
    "Még egy ilyen, és a padló lesz a partnered."
    "Kocc, és már csúszol is kifelé."
    "Ez most olyan volt, mint a kiömlött sör – kár érte."
    "A kidobó már bemelegít rád."
    "Ez most egy lépés a kijárat felé."
    "Ez most már ajtóközeli viselkedés."
    "A következő köröd lehet kint lesz."
    "Ne ugass, hanem igyál csendben."
    "Ne rázd már a korsót, kifröccsen a hangulat."
    "Ezt most egy húzásra lenyeljük és elfelejtjük."
    "Kicsit túltoltad a szeszt a mondatba."
    "Ez után inkább víz kéne, nem több szó."
    "A pult ezt most nem szolgálja ki."
    "Ha még egy ilyet töltesz ki, borul az asztal."
    "Kicsit sok lett benned a bátorság folyékony formában."
    "Most inkább vizet kérj, ne szót."
    "Ez már nem részegség, ez probléma."
    "Ne rázd már a korsót, nem habverseny van."
    "Kicsit túltoltad a komlót a dumába."
    "Ez most olyan, mint a felmelegedett dobozos."
    "Kicsit túlerjedt a stílusod."
    "Nem kell mindenből nagyfröccsöt csinálni."
    "Kicsit sok lett benned a házi főzet."
    "Ne keverd túl, nem koktélverseny van."
    "Kicsit túl sok lett a százalék benned."
    "Ez most tiszta koccintós szint."
    "Ez most tipik olcsó kör volt."
    "Ezt még a koccintós is kikérné magának."
    "Ne keverd a sört a pálinkával, meg a dumát a balhéval."
    "Kicsit túl lett keverve a pia és az ego."
    "Ne csinálj ebből tömény problémát."
]

WARNING_COOLDOWN_SECONDS = 5

EXTREME_PATTERNS = {
    "kurvanyád", "kurva anyád", "anyád picsája", "anyad picsaja",
    "dögölj meg", "dogolj meg", "csicskageci", "tetves kurva",
    "büdös cigány", "budos cigany", "rohadt cigány", "rohadt roman",
    "tetves cigány", "tetves zsido",
    "koszos migráns", "koszos arab", "csicska", "csicskagyász"
}

HIGH_PATTERNS = {
    "geci", "gecifej", "geciláda", "faszfej", "faszkalap", "balfasz",
    "köcsög", "kocsog", "nyomorék", "nyomorek", "rohadék", "rohadek",
    "hülyegyökér", "hulyegyoker", "szellemi fogyatékos", "degenerált",
    "degeneralt", "retardált", "retardalt"
}

MEDIUM_PATTERNS = {
    "fasz", "fasznak", "faszom", "kurva", "bazdmeg", "baszdmeg",
    "hülye", "hulye", "idióta", "idiota", "buzi", "barom", "seggfej",
    "seggnyaló", "majom", "patkány", "patkany", "féreg", "fereg",
    "undorító", "undorito", "hányadék", "hanyadek"
}

TARGETED_HINTS = (
    "te ", "neked", "téged", "veled", "rólad", "rolad", "teged",
    "anyád", "anyad", "nektek", "ti ","te vagy", "te egy", "te egy kibaszott",
    "te ilyen", "te olyan",
    "neked mondom", "rád értettem",
    "miattad", "te miattad",
    "fogd be", "hallgass", "@"
)

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
        return {
            "offenses": {},
            "last_warning_ts": {},
            "stats": {},
        }
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("offenses", {})
            data.setdefault("last_warning_ts", {})
            data.setdefault("stats", {})
            return data
    except Exception:
        return {
            "offenses": {},
            "last_warning_ts": {},
            "stats": {},
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
    current = get_offense(chat_id, user_id) + 1
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


def get_user_stats(chat_id: int, user_id: int) -> dict:
    chat_key = str(chat_id)
    user_key = str(user_id)
    DB.setdefault("stats", {})
    DB["stats"].setdefault(chat_key, {})
    DB["stats"][chat_key].setdefault(user_key, {
        "offense_count": 0,
        "severity_counts": {"1": 0, "2": 0, "3": 0, "4": 0},
        "last_offense_ts": 0,
        "last_message": "",
        "display_name": "",
    })
    stats = DB["stats"][chat_key][user_key]
    stats.setdefault("offense_count", 0)
    stats.setdefault("severity_counts", {"1": 0, "2": 0, "3": 0, "4": 0})
    for key in ("1", "2", "3", "4"):
        stats["severity_counts"].setdefault(key, 0)
    stats.setdefault("last_offense_ts", 0)
    stats.setdefault("last_message", "")
    stats.setdefault("display_name", "")
    return stats


def update_user_stats(chat_id: int, user_id: int, display_name: str, severity: int, text: str):
    stats = get_user_stats(chat_id, user_id)
    stats["offense_count"] += 1
    stats["severity_counts"][str(severity)] += 1
    stats["last_offense_ts"] = int(datetime.now(timezone.utc).timestamp())
    stats["last_message"] = text[:300]
    stats["display_name"] = display_name
    save_data(DB)


def format_ts(ts: int) -> str:
    if not ts:
        return "nincs adat"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


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
    alnum_only = re.sub(r"[^a-z0-9\s]", "", base)
    collapsed_spaces = re.sub(r"\s+", " ", alnum_only).strip()

    return list({base, compact, alnum_only, collapsed_spaces})


def find_banned_matches(text: str) -> list[str]:
    variants = normalize_text_variants(text)
    found = set()

    for bad in BANNED_PATTERNS:
        bad_norm = strip_accents_hu(bad)
        bad_compact = re.sub(SEPARATOR_CHARS_PATTERN, "", bad_norm)
        for variant in variants:
            if bad_norm in variant or bad_compact in variant:
                found.add(bad)
                break

    return sorted(found)


def classify_severity(text: str, matches: list[str], message: dict) -> int:
    if not matches:
        return 0

    normalized_text = strip_accents_hu(leet_normalize(collapse_repeated_chars(text)))
    unique_count = len(set(matches))
    score = 1

    if any(m in EXTREME_PATTERNS for m in matches):
        score = max(score, 4)
    elif any(m in HIGH_PATTERNS for m in matches):
        score = max(score, 3)
    elif any(m in MEDIUM_PATTERNS for m in matches):
        score = max(score, 2)

    if unique_count >= 3:
        score = max(score, 4)
    elif unique_count == 2:
        score = max(score, 3)

    if message.get("reply_to_message"):
        score = max(score, 3)

    if any(hint in normalized_text for hint in TARGETED_HINTS):
        score = max(score, 3)

    if len(text) <= 12 and unique_count == 1 and score < 2:
        score = 1

    return min(score, 4)


def mention_html(user_id: int, first_name: str) -> str:
    safe_name = html.escape(first_name or "Felhasználó")
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'


def get_mute_minutes(severity: int) -> int:
    return SEVERITY_MUTE_MINUTES.get(severity, 5)


def severity_label(severity: int) -> str:
    return {
        1: "enyhe",
        2: "közepes",
        3: "durva",
        4: "extrém",
    }.get(severity, "ismeretlen")


def normalize_command(text: str) -> str:
    cmd = (text or "").strip().split()[0].lower()
    if "@" in cmd:
        cmd = cmd.split("@", 1)[0]
    return cmd


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


async def send_log(bot: Bot, text: str):
    try:
        await bot.send_message(chat_id=LOG_CHAT_ID, text=text, parse_mode="HTML")
    except Exception:
        logger.exception("Nem sikerült logot küldeni a log channelbe.")


async def handle_start(bot: Bot, chat_id: int):
    logger.info("start_command lefutott")
    await bot.send_message(
        chat_id=chat_id,
        text="🍺 Kocsma moderátor bot aktív."
    )
    logger.info("start_command: válasz elküldve")


async def handle_offenses(bot: Bot, chat_id: int, user_id: int):
    count = get_offense(chat_id, user_id)
    await bot.send_message(chat_id=chat_id, text=f"Eddigi szabálysértéseid száma: {count}")


async def handle_mystats(bot: Bot, chat_id: int, user_id: int):
    stats = get_user_stats(chat_id, user_id)
    text = (
        f"📊 Saját statisztikád:\n"
        f"Összes offense: {stats['offense_count']}\n"
        f"1-es szint: {stats['severity_counts']['1']}\n"
        f"2-es szint: {stats['severity_counts']['2']}\n"
        f"3-as szint: {stats['severity_counts']['3']}\n"
        f"4-es szint: {stats['severity_counts']['4']}\n"
        f"Utolsó offense: {format_ts(stats['last_offense_ts'])}"
    )
    await bot.send_message(chat_id=chat_id, text=text)


async def handle_topoffenders(bot: Bot, chat_id: int):
    chat_stats = get_nested(DB, "stats", str(chat_id), default={}) or {}
    if not chat_stats:
        await bot.send_message(chat_id=chat_id, text="Még nincs statisztika ebben a chatben.")
        return

    rows = []
    for user_id, stats in chat_stats.items():
        rows.append((
            stats.get("display_name") or f"user {user_id}",
            stats.get("offense_count", 0),
            user_id
        ))

    rows.sort(key=lambda x: x[1], reverse=True)
    top_rows = rows[:10]

    lines = ["🏆 Top szabálysértők:"]
    for idx, (name, count, user_id) in enumerate(top_rows, start=1):
        lines.append(f"{idx}. {name} — {count} offense (ID: {user_id})")

    await bot.send_message(chat_id=chat_id, text="\n".join(lines))


async def handle_chatstats(bot: Bot, chat_id: int):
    chat_stats = get_nested(DB, "stats", str(chat_id), default={}) or {}
    if not chat_stats:
        await bot.send_message(chat_id=chat_id, text="Még nincs statisztika ebben a chatben.")
        return

    total_offenses = 0
    sev = {"1": 0, "2": 0, "3": 0, "4": 0}
    unique_users = 0

    for stats in chat_stats.values():
        if stats.get("offense_count", 0) > 0:
            unique_users += 1
        total_offenses += stats.get("offense_count", 0)
        for key in ("1", "2", "3", "4"):
            sev[key] += stats.get("severity_counts", {}).get(key, 0)

    text = (
        f"📈 Chat statisztika:\n"
        f"Érintett userek: {unique_users}\n"
        f"Összes offense: {total_offenses}\n"
        f"1-es szint: {sev['1']}\n"
        f"2-es szint: {sev['2']}\n"
        f"3-as szint: {sev['3']}\n"
        f"4-es szint: {sev['4']}"
    )
    await bot.send_message(chat_id=chat_id, text=text)


async def handle_userstats(bot: Bot, chat_id: int, target_user_id: int):
    stats = get_user_stats(chat_id, target_user_id)
    text = (
        f"📋 User stat ({target_user_id}):\n"
        f"Név: {stats.get('display_name') or 'ismeretlen'}\n"
        f"Összes offense: {stats['offense_count']}\n"
        f"1-es szint: {stats['severity_counts']['1']}\n"
        f"2-es szint: {stats['severity_counts']['2']}\n"
        f"3-as szint: {stats['severity_counts']['3']}\n"
        f"4-es szint: {stats['severity_counts']['4']}\n"
        f"Utolsó offense: {format_ts(stats['last_offense_ts'])}\n"
        f"Utolsó talált üzenet: {stats.get('last_message') or 'nincs adat'}"
    )
    await bot.send_message(chat_id=chat_id, text=text)


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
    chat_title = chat.get("title", "Ismeretlen chat")
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

    matches = find_banned_matches(text)
    logger.info("moderate_message: talált tiltott minták = %r", matches)

    if not matches:
        return

    severity = classify_severity(text, matches, message)
    mute_minutes = get_mute_minutes(severity)
    user_mention = mention_html(user_id, first_name)
    random_message = random.choice(WARNING_MESSAGES)

    update_user_stats(chat_id, user_id, first_name, severity, text)
    offense_count = increment_offense(chat_id, user_id)

    log_text = (
        f"🧾 <b>Káromkodás log</b>\n"
        f"Chat: {html.escape(chat_title)}\n"
        f"User: {mention_html(user_id, first_name)}\n"
        f"User ID: <code>{user_id}</code>\n"
        f"Offense #: {offense_count}\n"
        f"Szint: <b>{severity}</b> ({severity_label(severity)})\n"
        f"Mute: <b>{mute_minutes} perc</b>\n"
        f"Találatok: {html.escape(', '.join(matches))}\n"
        f"Üzenet: <code>{html.escape(text[:800])}</code>"
    )

    if await is_user_admin(bot, chat_id, user_id):
        await safe_warn_user(
            bot,
            chat_id,
            user_id,
            f"🍺 {user_mention} {random_message}"
        )
        await send_log(bot, log_text + "\nMűvelet: <b>admin warning</b>")
        logger.info("moderate_message: admin warning elküldve")
        return

    if DELETE_BAD_MESSAGES:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info("moderate_message: szabályszegő üzenet törölve")
        except Exception:
            logger.exception("Nem sikerült törölni a szabályszegő üzenetet.")

    if chat_type != "supergroup":
        await safe_warn_user(
            bot,
            chat_id,
            user_id,
            f"⚠️ {user_mention} {random_message}\n{mute_minutes} perc lenne a mute, de ez a chat nem supergroup."
        )
        await send_log(bot, log_text + "\nMűvelet: <b>warning only (nem supergroup)</b>")
        logger.info("moderate_message: nem supergroup, mute kihagyva")
        return

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
        await send_log(bot, log_text + "\nMűvelet: <b>warning, mute sikertelen</b>")
        return

    await safe_warn_user(bot, chat_id, user_id, reason_text)
    await send_log(bot, log_text + "\nMűvelet: <b>delete + mute + warning</b>")


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
    command = normalize_command(text)

    if message.get("new_chat_members"):
        await handle_new_members(bot, message)

    if command == "/start":
        await handle_start(bot, chat_id)
        return

    if command == "/offenses":
        await handle_offenses(bot, chat_id, user_id)
        return

    if command == "/mystats":
        await handle_mystats(bot, chat_id, user_id)
        return

    if command in {"/topoffenders", "/chatstats", "/userstats"}:
        if not await is_user_admin(bot, chat_id, user_id):
            return

        if command == "/topoffenders":
            await handle_topoffenders(bot, chat_id)
            return

        if command == "/chatstats":
            await handle_chatstats(bot, chat_id)
            return

        if command == "/userstats":
            parts = text.strip().split(maxsplit=1)
            if len(parts) < 2:
                await bot.send_message(chat_id=chat_id, text="Használat: /userstats <id>")
                return
            try:
                target_user_id = int(parts[1].strip())
            except ValueError:
                await bot.send_message(chat_id=chat_id, text="Érvénytelen user ID.")
                return
            await handle_userstats(bot, chat_id, target_user_id)
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
