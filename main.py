"""Telegram Bot Gateway for MyFinance."""

import os
import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from dotenv import load_dotenv
from core.processor import get_processor, MessageType, ProcessResult
from database import test_connection, get_or_create_user

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Store pending confirmations in memory
# In production, use Redis or database
pending_confirmations: dict[int, dict] = {}


from core.config_loader import ConfigLoader

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    welcome_message = ConfigLoader.get("BOT_WELCOME_MESSAGE")
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_message = ConfigLoader.get("BOT_HELP_MESSAGE")
    await update.message.reply_text(help_message)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from inline buttons."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    telegram_id = user.id if user else None
    callback_data = query.data

    logger.info(f"Callback from {telegram_id}: {callback_data}")

    if callback_data == "confirm":
        # Handle confirmation
        processor = get_processor()
        result = processor.process(
            "confirmar",
            MessageType.TEXT,
            telegram_id=telegram_id,
            channel="telegram",
        )

        await query.edit_message_text(result.response)

    elif callback_data == "cancel":
        # Handle cancellation
        processor = get_processor()
        result = processor.process(
            "cancelar",
            MessageType.TEXT,
            telegram_id=telegram_id,
            channel="telegram",
        )

        await query.edit_message_text(result.response)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    user = update.message.from_user
    text = update.message.text
    telegram_id = user.id if user else None

    logger.info(f"[GATEWAY] TEXT telegram_id={telegram_id} input='{text}'")

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    # Process the message
    processor = get_processor()
    result = processor.process(
        text,
        MessageType.TEXT,
        telegram_id=telegram_id,
        channel="telegram",
    )

    logger.info(
        f"[GATEWAY] RESULT route='{result.route}' action='{result.action}' "
        f"response='{str(result.response)[:150]}'"
    )

    # Check if we need to show confirmation buttons
    if result.action == "CONFIRMAR":
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="confirm"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            result.response,
            reply_markup=reply_markup,
        )
    else:
        # Send regular response
        await update.message.reply_text(result.response)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo/images."""
    user = update.message.from_user
    telegram_id = user.id if user else None

    logger.info(f"[GATEWAY] PHOTO telegram_id={telegram_id}")

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    # Get the photo
    photo = update.message.photo[-1]  # Get highest resolution
    file = await context.bot.get_file(photo.file_id)

    # Download to temp file
    temp_path = f"/tmp/{photo.file_id}.jpg"
    await file.download_to_drive(temp_path)
    logger.info(f"[GATEWAY] PHOTO saved to '{temp_path}'")

    # Process image
    processor = get_processor()
    result = processor.process(
        temp_path,
        MessageType.IMAGE,
        telegram_id=telegram_id,
        channel="telegram",
    )

    logger.info(
        f"[GATEWAY] PHOTO RESULT route='{result.route}' action='{result.action}' "
        f"response='{str(result.response)[:150]}'"
    )

    # Check if we need to show confirmation buttons
    if result.action == "CONFIRMAR":
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="confirm"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            result.response,
            reply_markup=reply_markup,
        )
    else:
        # Send regular response
        await update.message.reply_text(result.response)

    # Clean up temp file
    try:
        os.remove(temp_path)
    except Exception:
        pass


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.error(f"Error: {context.error}")
    if update and update.message:
        await update.message.reply_text(
            "Lo siento, tuve un problema. Por favor intenta de nuevo."
        )


def main() -> None:
    """Run the bot."""
    # Initialize configuration
    ConfigLoader.load()
    
    # Get token from environment
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token or token == "your_bot_token":
        print("ERROR: TELEGRAM_BOT_TOKEN not configured in .env")
        return

    # Test database connection
    if test_connection():
        logger.info("Database connection: OK")
    else:
        logger.warning("Database connection: FAILED (continuing anyway)")

    # Create application
    application = Application.builder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Add error handler
    application.add_error_handler(error_handler)

    # Start polling
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
