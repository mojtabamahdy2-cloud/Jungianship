import logging
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from src.config import TELEGRAM_BOT_TOKEN
from src.db.repository import Repository
from src.engine.retriever import HybridRetriever
from src.engine.generator import DialecticalEngine
from src.bot.handlers import BotHandlers

logger = logging.getLogger(__name__)

def create_bot_app():
    """Configure and build the Telegram Application."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing from .env configuration.")

    # Initialize components
    repo = Repository()
    retriever = HybridRetriever(repo)
    engine = DialecticalEngine(retriever)
    handlers = BotHandlers(repo, engine)

    # Build Application
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Register Command Handlers
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_cmd))
    app.add_handler(CommandHandler("ask", handlers.ask))
    app.add_handler(CommandHandler("dream", handlers.dream))
    app.add_handler(CommandHandler("concept", handlers.concept))
    app.add_handler(CommandHandler("quote", handlers.quote_cmd))
    app.add_handler(CommandHandler("synchronicity", handlers.quote_cmd))
    app.add_handler(CommandHandler("mode", handlers.mode_cmd))
    app.add_handler(CommandHandler("sources", handlers.sources_cmd))
    app.add_handler(CommandHandler("clear", handlers.clear_cmd))
    app.add_handler(CommandHandler("stats", handlers.stats_cmd))

    # Freeform text messages -> routed to Jungian ask handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.ask))

    # Inline button callback handler
    app.add_handler(CallbackQueryHandler(handlers.callback_handler))

    # Error handling
    async def on_error(update, context):
        logger.error(f"Update {update} caused error: {context.error}")

    app.add_error_handler(on_error)

    return app

def run_bot():
    """Entrypoint to run the Telegram Bot polling loop."""
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logger.info("Initializing Jungianship Telegram Bot...")

    # Explicit event loop for Python 3.14+ compatibility
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = create_bot_app()
    logger.info("Jungianship Bot is active and listening for messages. Press Ctrl+C to terminate.")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    run_bot()
