import os, uuid, asyncio, subprocess, logging
from telegram import Update
from telegram.ext import (ApplicationBuilder, CommandHandler,
                          MessageHandler, filters, ContextTypes)

# Render avtomatik ravishda bu o'zgaruvchilarni beradi
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", 10000))

TEMP_DIR = "/tmp/temp"  # Render'da faqat /tmp yozish uchun ochiq
os.makedirs(TEMP_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Salom!\nMenga video yuboring — MP3 qilib qaytaraman.")

def convert_to_mp3(inp: str, out: str):
    subprocess.run(
        ["ffmpeg", "-y", "-i", inp, "-vn", "-acodec", "libmp3lame", "-q:a", "6", out],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    tg_file = None
    if msg.video:
        tg_file = await msg.video.get_file()
    elif msg.video_note:
        tg_file = await msg.video_note.get_file()
    elif msg.animation:
        tg_file = await msg.animation.get_file()
    elif msg.document and (msg.document.mime_type or "").startswith("video/"):
        tg_file = await msg.document.get_file()
    if tg_file is None:
        await msg.reply_text("Iltimos, video fayl yuboring.")
        return
    uid = uuid.uuid4().hex
    in_path = os.path.join(TEMP_DIR, uid + ".in")
    out_path = os.path.join(TEMP_DIR, uid + ".mp3")
    status = await msg.reply_text("⏳ Yuklanmoqda...")
    try:
        await tg_file.download_to_drive(in_path)
        await status.edit_text("🎛 MP3 ga aylantirilmoqda...")
        await asyncio.get_event_loop().run_in_executor(None, convert_to_mp3, in_path, out_path)
        await status.edit_text("📤 Yuborilmoqda...")
        with open(out_path, "rb") as f:
            await msg.reply_audio(audio=f, title="Audio")
        await status.delete()
    except Exception as e:
        logging.exception(e)
        await status.edit_text(f"❌ Xatolik: {e}")
    finally:
        for p in (in_path, out_path):
            try: os.remove(p)
            except OSError: pass

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE | filters.ANIMATION | filters.Document.VIDEO, handle_media))

    # Render'da har doim webhook ishlatiladi
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/webhook"
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="/webhook",
            webhook_url=webhook_url,
        )
    else:
        # Lokal test uchun
        app.run_polling()

if __name__ == "__main__":
    main()