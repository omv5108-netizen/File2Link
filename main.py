import os
import logging
import asyncio
from aiohttp import web
import aiofiles
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ─── Configuration ───────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL   = os.environ.get("BASE_URL", "http://localhost:8000")  # e.g. https://your-app.onrender.com
PORT       = int(os.environ.get("PORT", 8000))
FILES_DIR  = "downloads"

os.makedirs(FILES_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─── Telegram Handler ─────────────────────────────────────────────
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    # Detect which kind of file was sent
    if message.document:
        tg_file   = await message.document.get_file()
        file_name = message.document.file_name or f"file_{message.document.file_id}"
    elif message.photo:
        photo     = message.photo[-1]          # highest resolution
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
        await message.reply_text("❌ कोई supported file नहीं मिली। Document, Photo, Video या Audio भेजें।")
        return

    # Save file locally
    save_path = os.path.join(FILES_DIR, file_name)
    await tg_file.download_to_drive(save_path)
    logger.info(f"Saved: {save_path}")

    # Generate download link
    download_url = f"{BASE_URL}/download/{file_name}"
    await message.reply_text(
        f"✅ फाइल मिल गई!\n\n"
        f"📁 File: `{file_name}`\n"
        f"🔗 Download Link:\n{download_url}",
        parse_mode="Markdown"
    )


# ─── HTTP Server (aiohttp) ────────────────────────────────────────
async def download_handler(request: web.Request):
    file_name = request.match_info["file_name"]
    file_path = os.path.join(FILES_DIR, file_name)

    if not os.path.exists(file_path):
        raise web.HTTPNotFound(text="File not found")

    # Force browser to download the file
    return web.FileResponse(
        path=file_path,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'}
    )


async def index_handler(request: web.Request):
    return web.Response(text="✅ Telegram File Bot is running!", content_type="text/plain")


# ─── Main ─────────────────────────────────────────────────────────
async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is not set!")

    # Build Telegram app
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE,
        handle_file
    ))

    # Build aiohttp web app
    web_app = web.Application()
    web_app.router.add_get("/", index_handler)
    web_app.router.add_get("/download/{file_name}", download_handler)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")

    # Start polling
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()
    logger.info("Telegram bot started polling…")

    # Keep running
    try:
        await asyncio.Event().wait()
    finally:
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
