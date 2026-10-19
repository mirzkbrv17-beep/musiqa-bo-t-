import os
import sqlite3
import tempfile
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
AUDD_TOKEN = os.getenv("AUDD_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
DB_PATH = os.getenv("DB_PATH", "music_bot.db")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("music-bot")
HEADERS = {"User-Agent": "MusiqaTelegramBot/1.0 (personal project)"}

def db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL
    )""")
    con.commit()
    return con

def touch_user(user_id: int):
    now = datetime.now(timezone.utc).isoformat()
    with db() as con:
        con.execute(
            """INSERT INTO users(user_id, first_seen, last_seen) VALUES(?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET last_seen=excluded.last_seen""",
            (user_id, now, now),
        )

def monthly_users() -> int:
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    with db() as con:
        row = con.execute("SELECT COUNT(*) FROM users WHERE last_seen >= ?", (since,)).fetchone()
    return int(row[0] or 0)

def header() -> str:
    return f"🎵 Musiqa Bot • {monthly_users():,} oylik foydalanuvchi"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_user.id)
    await update.message.reply_text(
        f"{header()}\n\n"
        "Musiqa nomini yozing — 10 tagacha bepul/litsenziyali audio variant qidiraman.\n"
        "🎙 Ovozli xabarda qo‘shiq nomini ayting.\n"
        "🎬 Video/audio yuboring — musiqa nomini aniqlashga urinaman.\n\n"
        "Eslatma: bu katalogda barcha mashhur tijoriy qo‘shiqlar bo‘lmasligi mumkin."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_user.id)
    await update.message.reply_text(
        "Foydalanish:\n"
        "• Qo‘shiq nomini yozing\n"
        "• Ovozli xabarda nomini ayting (OPENAI_API_KEY kerak)\n"
        "• Musiqa eshitiladigan video/audio yuboring (AUDD_TOKEN kerak)\n"
        "• Natijadagi tugmani tanlang\n\n"
        "Qidiruv Internet Archive’dagi ochiq audio materiallardan foydalanadi."
    )

def archive_search(query: str):
    """Search Internet Archive's open audio collection. No API key required."""
    params = {
        "q": f'collection:opensource_audio AND mediatype:audio AND "{query}"',
        "fl[]": ["identifier", "title", "creator", "licenseurl"],
        "rows": 10,
        "page": 1,
        "output": "json",
    }
    try:
        r = requests.get(
            "https://archive.org/advancedsearch.php",
            params=params, headers=HEADERS, timeout=25
        )
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
    except Exception:
        log.exception("Internet Archive search failed")
        return []
    results = []
    for doc in docs:
        identifier = doc.get("identifier")
        if not identifier:
            continue
        try:
            meta_resp = requests.get(
                f"https://archive.org/metadata/{quote(identifier, safe='')}",
                headers=HEADERS, timeout=25
            )
            meta_resp.raise_for_status()
            metadata = meta_resp.json()
        except Exception:
            log.exception("Could not fetch archive metadata for %s", identifier)
            continue

        meta = metadata.get("metadata", {})
        license_url = str(meta.get("licenseurl") or doc.get("licenseurl") or "").lower()
        # Only use items that explicitly state a public-domain or Creative Commons license.
        allowed = ("creativecommons.org/publicdomain", "creativecommons.org/licenses/by/",
                   "creativecommons.org/licenses/by-sa/", "creativecommons.org/licenses/by-nd/",
                   "creativecommons.org/licenses/by-nc/", "creativecommons.org/licenses/by-nc-sa/",
                   "creativecommons.org/licenses/by-nc-nd/")
        if not any(x in license_url for x in allowed):
            continue
        files = metadata.get("files", [])
        audio_file = next((f for f in files if str(f.get("name","")).lower().endswith(".mp3")
                           and f.get("source") != "metadata"
                           and not f.get("private")), None)
        if not audio_file:
            audio_file = next((f for f in files if str(f.get("name","")).lower().endswith((".ogg", ".wav", ".m4a"))
                               and f.get("source") != "metadata" and not f.get("private")), None)
        if not audio_file:
            continue
        results.append({
            "name": str(meta.get("title") or doc.get("title") or identifier),
            "artist_name": str(meta.get("creator") or doc.get("creator") or "Noma’lum ijrochi"),
            "identifier": identifier,
            "filename": audio_file["name"],
            "size": int(audio_file.get("size") or 0),
            "license": license_url,
            "url": f"https://archive.org/download/{quote(identifier, safe='')}/{quote(audio_file['name'], safe='/')}",
            "page": f"https://archive.org/details/{quote(identifier, safe='')}",
        })
        if len(results) >= 10:
            break
    return results

def audd_identify(path: str):
    if not AUDD_TOKEN:
        return None
    try:
        with open(path, "rb") as audio:
            r = requests.post(
                "https://api.audd.io/",
                data={"api_token": AUDD_TOKEN, "return": "spotify,apple_music"},
                files={"file": audio},
                timeout=60,
            )
        r.raise_for_status()
        payload = r.json()
        if payload.get("status") == "success" and payload.get("result"):
            result = payload["result"]
            return {
                "title": result.get("title", ""),
                "artist": result.get("artist", ""),
                "spotify": (result.get("spotify") or {}).get("external_urls", {}).get("spotify"),
                "apple": (result.get("apple_music") or {}).get("url"),
            }
    except Exception:
        log.exception("Audio recognition failed")
    return None

def results_keyboard(tracks):
    rows = []
    for i, track in enumerate(tracks):
        label = f"{i+1}. {track.get('name','Noma’lum trek')} — {track.get('artist_name','Noma’lum ijrochi')}"
        if len(label) > 60:
            label = label[:57] + "..."
        rows.append([InlineKeyboardButton(label, callback_data=f"track:{i}")])
    return InlineKeyboardMarkup(rows)

async def show_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    tracks = archive_search(query)
    if not tracks:
        await update.effective_message.reply_text(
            f"{header()}\n\n"
            "Ochiq litsenziyali audio topilmadi. Boshqa nom bilan qidiring. "
            "Bu katalogda barcha mashhur qo‘shiqlar mavjud emas."
        )
        return
    context.user_data["tracks"] = tracks
    lines = [header(), f"\n🔎 “{query}” uchun topilgan variantlar:"]
    for i, t in enumerate(tracks, 1):
        lines.append(f"{i}. {t['name']} — {t['artist_name']}")
    lines.append("\nYuklab olish uchun variantni tanlang:")
    await update.effective_message.reply_text("\n".join(lines), reply_markup=results_keyboard(tracks))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_user.id)
    query = (update.message.text or "").strip()
    if query:
        await show_search(update, context, query)

async def transcribe_audio(path: str):
    if not OPENAI_API_KEY:
        return None
    try:
        with open(path, "rb") as f:
            r = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                data={"model": "gpt-4o-mini-transcribe"},
                files={"file": ("voice.ogg", f, "audio/ogg")},
                timeout=90,
            )
        r.raise_for_status()
        return (r.json().get("text") or "").strip() or None
    except Exception:
        log.exception("Transcription failed")
        return None

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_user.id)
    await update.message.reply_text(f"{header()}\n\nOvozli xabarni tekshiryapman…")
    file_obj = await context.bot.get_file(update.message.voice.file_id)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "voice.ogg")
        await file_obj.download_to_drive(path)
        query = await transcribe_audio(path)
    if query:
        await show_search(update, context, query)
    else:
        await update.message.reply_text(
            "Ovozli xabardan nomni matnga aylantira olmadim. OPENAI_API_KEY sozlang yoki nomini matn qilib yuboring."
        )

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_user.id)
    msg = update.message
    media = msg.video or msg.audio or msg.document
    if not media:
        return
    mime = getattr(media, "mime_type", None) or ""
    filename = getattr(media, "file_name", "") or ""
    if msg.document and not (mime.startswith(("video/", "audio/")) or filename.lower().endswith(
        (".mp4", ".mov", ".m4a", ".mp3", ".wav", ".ogg", ".webm")
    )):
        await msg.reply_text("Iltimos, video yoki audio fayl yuboring.")
        return
    size = getattr(media, "file_size", 0) or 0
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        await msg.reply_text(f"Fayl juda katta. {MAX_UPLOAD_MB} MB gacha yuboring.")
        return
    if not AUDD_TOKEN:
        await msg.reply_text("Videodagi musiqani aniqlash uchun AUDD_TOKEN kerak. Hozircha qo‘shiq nomini matn qilib yuborishingiz mumkin.")
        return
    await msg.reply_text(f"{header()}\n\nVideodagi musiqani aniqlayapman…")
    file_obj = await context.bot.get_file(media.file_id)
    with tempfile.TemporaryDirectory() as td:
        ext = os.path.splitext(filename)[1] or (".mp4" if msg.video else ".audio")
        path = os.path.join(td, "media" + ext)
        await file_obj.download_to_drive(path)
        found = audd_identify(path)
    if not found or not found.get("title"):
        await msg.reply_text("Musiqani aniqlay olmadim. Tiniqroq audio bilan qayta urinib ko‘ring.")
        return
    query = " ".join(x for x in [found.get("title"), found.get("artist")] if x).strip()
    links = [x for x in [found.get("spotify"), found.get("apple")] if x]
    await msg.reply_text(
        f"🎧 Aniqlangan musiqa: {query}\n" +
        (("\n".join(links) + "\n\n") if links else "\n") +
        "Ochiq litsenziyali audio variantlarini qidiryapman…"
    )
    await show_search(update, context, query)

async def choose_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    touch_user(query.from_user.id)
    try:
        index = int(query.data.split(":")[1])
        track = context.user_data.get("tracks", [])[index]
    except (ValueError, IndexError, TypeError):
        await query.edit_message_text("Bu natija eskirgan. Qo‘shiq nomini qayta yuboring.")
        return

    url = track.get("url")
    if not url:
        await query.message.reply_text("Audio havolasi topilmadi.")
        return
    size = track.get("size", 0)
    if size and size > 48 * 1024 * 1024:
        await query.message.reply_text(f"Fayl Telegram orqali yuborish uchun katta. Tinglash/yuklab olish: {track['page']}")
        return
    await query.message.reply_text(f"⬇️ {track['name']} — {track['artist_name']}\nFaylni tayyorlayapman…")
    temp_path = None
    try:
        with requests.get(url, headers=HEADERS, timeout=60, stream=True) as r:
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=os.path.splitext(track["filename"])[1], delete=False) as f:
                temp_path = f.name
                for chunk in r.iter_content(chunk_size=128 * 1024):
                    if chunk:
                        f.write(chunk)
        with open(temp_path, "rb") as audio:
            await query.message.reply_audio(
                audio=audio,
                title=track["name"][:64],
                performer=track["artist_name"][:64],
                caption=f"📄 Litsenziya: {track.get('license') or 'Manba sahifasida tekshiring'}\n{track['page']}",
            )
    except Exception:
        log.exception("Audio download/send failed")
        await query.message.reply_text(f"Faylni yuborib bo‘lmadi. Manbadan oching: {track['page']}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

async def post_init(app: Application):
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required")

def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN ni hosting Environment Variables bo‘limiga kiriting.")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(choose_track, pattern=r"^track:\d+$"))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.VIDEO | filters.AUDIO | filters.Document.ALL, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
