import os
import sqlite3
import tempfile
import logging
from datetime import datetime, timedelta, timezone

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "").strip()
AUDD_TOKEN = os.getenv("AUDD_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "music_bot.db")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("music-bot")

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
    # This is an actual rolling 30-day active-user count, not a fabricated number.
    return f"🎵 Musiqa Bot  •  {monthly_users():,} oylik foydalanuvchi"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_user.id)
    msg = (
        f"{header()}\n\n"
        "Musiqa nomini yozing — 10 ta mos variant topaman.\n"
        "🎙 Ovozli xabarda qo‘shiq nomini ayting.\n"
        "🎬 Video/audio yuboring — qo‘shiqni aniqlashga urinaman.\n\n"
        "Tanlangan trek Jamendo’da bepul va litsenziya asosida yuklab olishga ruxsat berilgan bo‘lsa, bot fayl qilib yuboradi. "
        "Boshqa qo‘shiqlar uchun rasmiy havolalarni ko‘rsatadi."
    )
    await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_user.id)
    await update.message.reply_text(
        "Foydalanish:\n"
        "• Qo‘shiq nomini yozing\n"
        "• Ovozli xabarda nomini ayting\n"
        "• Musiqa eshitiladigan video/audio yuboring\n"
        "• Natijadagi tugmani tanlang\n\n"
        "Eslatma: video/audio tanish uchun AUDD_TOKEN, musiqa qidirish/yuklash uchun "
        "JAMENDO_CLIENT_ID kerak bo‘ladi."
    )

def jamendo_search(query: str):
    if not JAMENDO_CLIENT_ID:
        return []
    url = "https://api.jamendo.com/v3.0/tracks/"
    params = {
        "client_id": JAMENDO_CLIENT_ID,
        "format": "json",
        "limit": 10,
        "search": query,
        "include": "musicinfo",
        "audioformat": "mp32",
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception:
        log.exception("Jamendo search failed")
        return []

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
        title = track.get("name", "Noma’lum trek")
        artist = track.get("artist_name", "Noma’lum ijrochi")
        label = f"{i+1}. {title} — {artist}"
        if len(label) > 60:
            label = label[:57] + "..."
        rows.append([InlineKeyboardButton(label, callback_data=f"track:{i}")])
    return InlineKeyboardMarkup(rows)

async def show_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    tracks = jamendo_search(query)
    if not tracks:
        await update.effective_message.reply_text(
            f"{header()}\n\n"
            "Hozircha mos trek topilmadi yoki qidiruv API sozlanmagan. "
            "Bot egasi JAMENDO_CLIENT_ID ni sozlaganini tekshirsin."
        )
        return
    context.user_data["tracks"] = tracks
    lines = [header(), f"\n🔎 “{query}” uchun topilgan 10 ta variant:"]
    for i, t in enumerate(tracks, 1):
        lines.append(f"{i}. {t.get('name','Noma’lum')} — {t.get('artist_name','Noma’lum ijrochi')}")
    lines.append("\nYuklab olish yoki havolani ko‘rish uchun variantni tanlang:")
    await update.effective_message.reply_text("\n".join(lines), reply_markup=results_keyboard(tracks))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_user.id)
    query = (update.message.text or "").strip()
    if query:
        await show_search(update, context, query)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_user.id)
    await update.message.reply_text(
        f"{header()}\n\nOvozli xabarni tekshiryapman…"
    )
    # Telegram voice files are usually OGG/Opus. AUDD can identify audio, but
    # speech-to-text of a spoken song title is a separate service; this starter
    # uses optional OpenAI transcription when OPENAI_API_KEY is set.
    file_obj = await context.bot.get_file(update.message.voice.file_id)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "voice.ogg")
        await file_obj.download_to_drive(path)
        query = await transcribe_audio(path)
    if query:
        await show_search(update, context, query)
    else:
        await update.message.reply_text(
            "Ovozli xabardan nomni aniqlay olmadim. OPENAI_API_KEY sozlang yoki qo‘shiq nomini matn qilib yuboring."
        )

async def transcribe_audio(path: str):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        with open(path, "rb") as f:
            r = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": "gpt-4o-mini-transcribe"},
                files={"file": ("voice.ogg", f, "audio/ogg")},
                timeout=90,
            )
        r.raise_for_status()
        return (r.json().get("text") or "").strip() or None
    except Exception:
        log.exception("Transcription failed")
        return None

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_user.id)
    msg = update.message
    media = msg.video or msg.audio or msg.document
    if not media:
        return
    mime = getattr(media, "mime_type", None) or ""
    filename = getattr(media, "file_name", "") or ""
    if msg.document and not (mime.startswith("video/") or mime.startswith("audio/") or filename.lower().endswith((".mp4", ".mov", ".m4a", ".mp3", ".wav", ".ogg", ".webm"))):
        await msg.reply_text("Iltimos, video yoki audio fayl yuboring.")
        return
    size = getattr(media, "file_size", 0) or 0
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        await msg.reply_text(f"Fayl juda katta. {MAX_UPLOAD_MB} MB gacha yuboring.")
        return
    if not AUDD_TOKEN:
        await msg.reply_text("Musiqani videodan aniqlash uchun bot egasi AUDD_TOKEN sozlashi kerak.")
        return
    await msg.reply_text(f"{header()}\n\nVideodagi musiqani aniqlayapman…")
    file_obj = await context.bot.get_file(media.file_id)
    with tempfile.TemporaryDirectory() as td:
        ext = os.path.splitext(filename)[1] or (".mp4" if msg.video else ".audio")
        path = os.path.join(td, "media" + ext)
        await file_obj.download_to_drive(path)
        found = audd_identify(path)
    if not found or not found.get("title"):
        await msg.reply_text("Musiqani aniqlay olmadim. Tiniqroq, musiqasi balandroq bo‘lgan qismini yuborib ko‘ring.")
        return
    query = " ".join(x for x in [found.get("title"), found.get("artist")] if x).strip()
    links = []
    if found.get("spotify"):
        links.append(f"Spotify: {found['spotify']}")
    if found.get("apple"):
        links.append(f"Apple Music: {found['apple']}")
    await msg.reply_text(
        f"🎧 Aniqlangan musiqa: {query}\n" +
        ("\n".join(links) + "\n\n" if links else "\n\n") +
        "Shu qo‘shiqqa o‘xshash 10 ta trekni qidiryapman…"
    )
    await show_search(update, context, query)

async def choose_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    touch_user(query.from_user.id)
    try:
        index = int(query.data.split(":")[1])
        tracks = context.user_data.get("tracks", [])
        track = tracks[index]
    except (ValueError, IndexError, TypeError):
        await query.edit_message_text("Bu natija eskirgan. Qo‘shiq nomini qayta yuboring.")
        return

    name = track.get("name", "Noma’lum trek")
    artist = track.get("artist_name", "Noma’lum ijrochi")
    audio_url = track.get("audio")
    download_allowed = str(track.get("audiodownload_allowed", "false")).lower() == "true"
    # Jamendo returns audio links for tracks offered under its own licensing terms.
    # Respect the provider's download permission field.
    if audio_url and download_allowed:
        try:
            await query.message.reply_text(f"⬇️ {name} — {artist}\nFayl tayyorlanmoqda…")
            r = requests.get(audio_url, timeout=45, stream=True)
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_path = f.name
                for chunk in r.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        f.write(chunk)
            try:
                with open(temp_path, "rb") as audio:
                    await query.message.reply_audio(audio=audio, title=name, performer=artist)
            finally:
                os.unlink(temp_path)
            return
        except Exception:
            log.exception("Track download failed")
    links = []
    for label, key in [("Jamendo", "shareurl"), ("Rasmiy audio", "audio")]:
        if track.get(key):
            links.append(f"{label}: {track[key]}")
    await query.message.reply_text(
        f"🎵 {name} — {artist}\n"
        "Bu trek uchun bot orqali yuklab olish ruxsati mavjud emas. "
        "Quyidagi havola orqali tinglashingiz mumkin:\n" + ("\n".join(links) if links else "Jamendo’da qidirib ko‘ring.")
    )

async def post_init(app: Application):
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required")

def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN ni environment variable sifatida kiriting.")
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
