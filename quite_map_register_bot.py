#!/usr/bin/env python

import logging
import secrets
from datetime import datetime, timezone

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import settings
from database import SessionLocal
from models import User, PendingRegistration

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


async def start_or_activate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start or /activate - automatically complete registration"""
    user = update.effective_user
    telegram_username = user.username or f"user_{user.id}"
    command = update.message.text.split()[0] if update.message.text else "/start"
    
    db = SessionLocal()
    try:
        # Check if user is already registered
        existing_user = db.query(User).filter(
            User.telegram_handle == telegram_username
        ).first()
        
        if existing_user:
            if existing_user.is_active:
                await update.message.reply_text(
                    f"Вы уже зарегистрированы и активированы!\n"
                    f"Ваш логин: {existing_user.username}\n\n"
                    f"Вы можете войти на сайте используя ваш логин и пароль."
                )
            else:
                # Generate activation link if not activated
                if existing_user.activation_token:
                    base_url = settings.BASE_URL.rstrip('/')
                    activation_link = f"{base_url}/activate/{existing_user.activation_token}"
                    await update.message.reply_text(
                        f"Вы уже зарегистрированы, но аккаунт не активирован.\n"
                        f"Ваш логин: {existing_user.username}\n\n"
                        f"Для активации перейдите по ссылке:\n{activation_link}",
                        disable_web_page_preview=False
                    )
                else:
                    await update.message.reply_text(
                        f"Вы уже зарегистрированы, но аккаунт не активирован.\n"
                        f"Ваш логин: {existing_user.username}\n\n"
                        f"Обратитесь к администратору для активации аккаунта."
                    )
            return
        
        # Look up pending registration by telegram handle
        pending_reg = db.query(PendingRegistration).filter(
            PendingRegistration.telegram_handle == telegram_username
        ).first()
        
        if not pending_reg:
            await update.message.reply_text(
                "Добро пожаловать в бот регистрации QuiteMap!\n\n"
                "Для регистрации перейдите на сайт и заполните форму регистрации "
                "с вашим Telegram handle. После этого вернитесь сюда и отправьте /start или /activate."
            )
            return
        
        # Check if expired - ensure timezone-aware comparison
        expires_at = pending_reg.expires_at
        if expires_at.tzinfo is None:
            # Make timezone-aware if naive (SQLite issue)
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < datetime.now(timezone.utc):
            db.delete(pending_reg)
            db.commit()
            await update.message.reply_text(
                "Ваша регистрация истекла. Пожалуйста, начните регистрацию заново на сайте."
            )
            return
        
        # Check if username is still available
        existing_user_by_username = db.query(User).filter(
            User.username == pending_reg.username
        ).first()
        
        if existing_user_by_username:
            db.delete(pending_reg)
            db.commit()
            await update.message.reply_text(
                f"Ошибка: Логин '{pending_reg.username}' уже занят. "
                "Пожалуйста, начните регистрацию заново на сайте с другим логином."
            )
            return
        
        # Generate activation token
        activation_token = secrets.token_urlsafe(32)
        
        # Create user account
        new_user = User(
            username=pending_reg.username,
            hashed_password=pending_reg.hashed_password,
            telegram_handle=pending_reg.telegram_handle,
            activation_token=activation_token,
            is_active=False
        )
        
        db.add(new_user)
        
        # Delete pending registration
        db.delete(pending_reg)
        
        db.commit()
        db.refresh(new_user)
        
        # Generate activation link
        base_url = settings.BASE_URL.rstrip('/')
        activation_link = f"{base_url}/activate/{activation_token}"
        
        # Send success message
        await update.message.reply_text(
            f"✅ Регистрация успешно завершена!\n\n"
            f"Ваш логин: {new_user.username}\n"
            f"Telegram handle: @{new_user.telegram_handle}\n\n"
            f"Для активации аккаунта перейдите по ссылке:\n"
            f"{activation_link}\n\n"
            f"После активации вы сможете войти на сайте используя ваш логин и пароль.",
            disable_web_page_preview=False
        )
        
        logger.info(f"User {new_user.username} registered via Telegram bot ({command})")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Registration error: {e}", exc_info=True)
        await update.message.reply_text(
            f"Произошла ошибка при регистрации: {str(e)}\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору."
        )
    finally:
        db.close()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message"""
    await update.message.reply_text(
        "Добро пожаловать в бот регистрации QuiteMap!\n\n"
        "Для регистрации:\n"
        "1. Перейдите на сайт и заполните форму регистрации\n"
        "2. Укажите ваш Telegram handle в форме\n"
        "3. Вернитесь в этот бот и отправьте /start или /activate\n\n"
        "После регистрации вы получите ссылку для активации аккаунта."
    )


def main() -> None:
    """Start the bot"""
    # Validate API key
    if not settings.TG_BOT_API_KEY:
        logger.error("TG_BOT_API_KEY is not set in environment variables!")
        raise ValueError("TG_BOT_API_KEY must be set in .env or .env.local file")
    
    # Create the Application
    application = Application.builder().token(settings.TG_BOT_API_KEY).build()
    
    # Register handlers
    application.add_handler(CommandHandler('start', start_or_activate))
    application.add_handler(CommandHandler('activate', start_or_activate))
    application.add_handler(CommandHandler('help', help_command))
    
    # Start the Bot
    logger.info("Telegram registration bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
