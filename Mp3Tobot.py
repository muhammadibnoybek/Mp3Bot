import os
import uuid
import asyncio
import subprocess
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
)
from shazamio import Shazam

# Render avtomatik ravishda bu o'zgaruvchilarni beradi
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", 10000))

TEMP_DIR = "/tmp/temp"
os.makedirs(TEMP_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)

shazam = Shazam()

# ------------------------------------------------------------------
# 1. START BUYRUG'I: Menyu chiqarish
# ------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Rejimni tozalaymiz (agar oldin tanlangan bo'lsa)
    context.user_data['mode'] = None
    
    text = (
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🤖 Men <b>@Video_mpRobot</b> man. Iltimos, nima qilishni xohlayotganingizni tanlang:\n\n"
        "🎬 <b>Video → MP3:</b> Videoni musiqaga aylantirish.\n"
        "🎵 <b>Musiqa aniqlash:</b> Ovoz yoki audiodagi qo'shiqni topish.\n\n"
        "⚠️ <b>Diqqat:</b> Render bepul tarifi tufayli faqat <b>20 MB</b> gacha bo'lgan fayllar ishlaydi."
    )
    
    keyboard = [
        [InlineKeyboardButton("🎬 Video → MP3 qilish", callback_data="mode_mp3")],
        [InlineKeyboardButton("🎵 Musiqa aniqlash", callback_data="mode_shazam")],
        [InlineKeyboardButton("📤 Do'stlarga ulashish", url="https://t.me/share/url?url=https://t.me/Video_mpRobot&text=Mana zo'r bot!")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

# ------------------------------------------------------------------
# 2. TUGMA BOSILGANDA REJIMNI TANLASH
# ------------------------------------------------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "mode_mp3":
        context.user_data['mode'] = 'mp3'
        await query.edit_message_text(
            text="🎬 <b>Video → MP3 rejimi tanlandi!</b>\n\nEndi menga istalgan videoni yuboring, men uni MP3 qilib beraman.",
            parse_mode="HTML"
        )
    elif query.data == "mode_shazam":
        context.user_data['mode'] = 'shazam'
        await query.edit_message_text(
            text="🎵 <b>Musiqa aniqlash rejimi tanlandi!</b>\n\nEndi menga ovozli xabar yoki audio fayl yuboring, men undagi musiqani topaman.",
            parse_mode="HTML"
        )

# ------------------------------------------------------------------
# 3. MUSIQA ANIQLASH YORDAMCHI FUNKSIYASI
# ------------------------------------------------------------------
async def recognize_music(file_path: str):
    try:
        result = await shazam.recognize(file_path)
        if result and "track" in result:
            track = result["track"]
            title = track.get("title", "Noma'lum")
            artist = track.get("subtitle", "Noma'lum ijrochi")
            url = track.get("share", {}).get("href", "")
            return f"🎵 <b>{title}</b>\n👤 <b>{artist}</b>" + (f"\n🔗 <a href='{url}'>Shazam'da ochish</a>" if url else "")
        else:
            return None
    except Exception as e:
        logging.error(f"Shazam xatosi: {e}")
        return None

# ------------------------------------------------------------------
# 4. MEDIA (VIDEO, OVOZ, AUDIO) QABUL QILISH
# ------------------------------------------------------------------
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    mode = context.user_data.get('mode')
    
    # Agar foydalanuvchi rejim tanlamagan bo'lsa
    if not mode:
        await msg.reply_text("Iltimos, avval /start buyrug'ini bosib, kerakli bo'limni tanlang.")
        return

    tg_file = None
    file_size = 0
    file_type = "fayl"
    is_audio = False

    if msg.video:
        file_size = msg.video.file_size
        file_type = "video"
    elif msg.video_note:
        file_size = msg.video_note.file_size
        file_type = "dumaloq video"
    elif msg.animation:
        file_size = msg.animation.file_size
        file_type = "animatsiya (GIF)"
    elif msg.document and (msg.document.mime_type or "").startswith("video/"):
        file_size = msg.document.file_size
        file_type = "video hujjat"
    elif msg.voice:
        file_size = msg.voice.file_size
        file_type = "ovozli xabar"
        is_audio = True
    elif msg.audio:
        file_size = msg.audio.file_size
        file_type = "audio fayl"
        is_audio = True

    if file_size == 0:
        await msg.reply_text("Iltimos, tegishli fayl yuboring.")
        return

    # 20 MB limitini tekshirish
    if file_size > 20 * 1024 * 1024:
        await msg.reply_text(
            f"❌ <b>Kechirasiz!</b>\n\n"
            f"Siz yuborgan {file_type} hajmi <b>20 MB</b> dan katta.\n"
            f"Iltimos, kichikroq hajmdagi faylni sinab ko'ring.",
            parse_mode="HTML"
        )
        return

    # Rejimga qarab tekshirish
    if mode == 'mp3' and is_audio:
        await msg.reply_text("❌ Siz <b>Video → MP3</b> rejimini tanladingiz. Iltimos, video yuboring.\nYoki /start bosib boshqa rejimni tanlang.", parse_mode="HTML")
        return
    elif mode == 'shazam' and not is_audio:
        await msg.reply_text("❌ Siz <b>Musiqa aniqlash</b> rejimini tanladingiz. Iltimos, ovozli xabar yoki audio yuboring.\nYoki /start bosib boshqa rejimni tanlang.", parse_mode="HTML")
        return

    # Faylni yuklab olish
    if msg.video: tg_file = await msg.video.get_file()
    elif msg.video_note: tg_file = await msg.video_note.get_file()
    elif msg.animation: tg_file = await msg.animation.get_file()
    elif msg.document: tg_file = await msg.document.get_file()
    elif msg.voice: tg_file = await msg.voice.get_file()
    elif msg.audio: tg_file = await msg.audio.get_file()

    uid = uuid.uuid4().hex
    in_path = os.path.join(TEMP_DIR, uid + ".in")
    out_path = os.path.join(TEMP_DIR, uid + ".mp3")
    status = await msg.reply_text("⏳ Yuklanmoqda...")

    try:
        await tg_file.download_to_drive(in_path)
        
        # Agar rejim 'shazam' bo'lsa
        if mode == 'shazam':
            await status.edit_text("🎵 Musiqa aniqlanmoqda...")
            music_info = await recognize_music(in_path)
            if music_info:
                await status.edit_text(music_info, parse_mode="HTML")
            else:
                await status.edit_text("😔 Kechirasiz, musiqa aniqlanmadi. Boshqa fayl sinab ko'ring.")
            return

        # Agar rejim 'mp3' bo'lsa
        await status.edit_text("🎛 MP3 ga aylantirilmoqda...")
        subprocess.run(
            ["ffmpeg", "-y", "-i", in_path, "-vn", "-acodec", "libmp3lame", "-q:a", "6", out_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        await status.edit_text("📤 Yuborilmoqda...")
        keyboard = [
            [InlineKeyboardButton("📤 Do'stlarga ulashish", url="https://t.me/share/url?url=https://t.me/Video_mpRobot&text=Mana zo'r bot! Videolarni MP3 ga o'girib beradi.")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        with open(out_path, "rb") as f:
            await msg.reply_audio(
                audio=f, 
                title="Audio", 
                performer="@Video_mpRobot", 
                reply_markup=reply_markup
            )
        await status.delete()

    except subprocess.CalledProcessError:
        await status.edit_text("❌ Konvertatsiya xatosi. Fayl buzilgan bo'lishi mumkin.")
    except Exception as e:
        logging.exception(e)
        await status.edit_text(f"❌ Xatolik: {e}")
    finally:
        for p in (in_path, out_path):
            try: os.remove(p)
            except OSError: pass

# ------------------------------------------------------------------
# 5. ASOSIY FUNKSIYA
# ------------------------------------------------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler)) # Tugmalarni ushlash
    app.add_handler(MessageHandler(
        filters.VIDEO | filters.VIDEO_NOTE | filters.ANIMATION |
        filters.Document.VIDEO | filters.VOICE | filters.AUDIO,
        handle_media
    ))

    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/webhook"
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="/webhook",
            webhook_url=webhook_url,
        )
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
