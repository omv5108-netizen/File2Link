import os
import logging
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

# ─── Configuration ───────────────────────────────────────────────
BOT_TOKEN = "8723304184:AAH0j1kr7xq9TGA2X4cAvhNJgjnb7ANeeoQ"
BASE_URL  = os.environ.get("BASE_URL", "http://localhost:8000")
PORT      = int(os.environ.get("PORT", 8000))
FILES_DIR = "downloads"

os.makedirs(FILES_DIR, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ─── /start Handler ───────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 नमस्ते! मुझे कोई भी File भेजें।\n"
        "मैं आपको उसका Download Link दूंगा! 🔗"
    )


# ─── File Handler ─────────────────────────────────────────────────
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    logger.info(f"File received from {message.from_user.id}")

    try:
        if message.document:
            tg_file   = await message.document.get_file()
            file_name = message.document.file_name or f"file_{message.document.file_id}"
        elif message.photo:
            photo     = message.photo[-1]
            tg_file   = await photo.get_file()
            file_name = f"photo_{photo.file_id}.jpg"
        elif message.video:
            tg_file   = await message.video.get_file()
            file_name = message.video.file_name or f"video_{message.video.file_id}.mp4"
        elif message.audio:
            tg_file   = await message.audio.get_file()
            file_name = message.audio.file_name or f"audio_{message.audio.file_id}.mp3"
        elif message.voice:
            tg_file   = await message.voice.get_file()
            file_name = f"voice_{message.voice.file_id}.ogg"
        else:
            await message.reply_text("❌ Supported files: Document, Photo, Video, Audio")
            return

        await message.reply_text("⏳ File मिल गई, link बना रहे हैं...")

        save_path = os.path.join(FILES_DIR, file_name)
        await tg_file.download_to_drive(save_path)
        logger.info(f"Saved: {save_path}")

        download_url = f"{BASE_URL}/download/{file_name}"
        await message.reply_text(
            f"✅ हो गया!\n\n"
            f"📁 File: `{file_name}`\n\n"
            f"🔗 Download Link:\n{download_url}",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply_text(f"❌ Error आई: {str(e)}")


# ─── HTTP Server ──────────────────────────────────────────────────
async def download_handler(request: web.Request):
    file_name = request.match_info["file_name"]
    file_path = os.path.join(FILES_DIR, file_name)
    if not os.path.exists(file_path):
        raise web.HTTPNotFound(text="File not found")
    return web.FileResponse(
        path=file_path,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'}
    )

async def index_handler(request: web.Request):
    return web.Response(text="✅ Bot is running!", content_type="text/plain")


# ─── Main ─────────────────────────────────────────────────────────
async def main():
    # Webhook पहले delete करें
    tg_app = Application.builder().token(BOT_TOKEN).build()

    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE,
        handle_file
    ))

    web_app = web.Application()
    web_app.router.add_get("/", index_handler)
    web_app.router.add_get("/download/{file_name}", download_handler)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"✅ Web server started on port {PORT}")

    await tg_app.initialize()
    # Webhook delete karo pehle
    await tg_app.bot.delete_webhook(drop_pending_updates=True)
    await tg_app.start()
    await tg_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("✅ Bot polling started!")

    try:
        await asyncio.Event().wait()
    finally:
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
    
