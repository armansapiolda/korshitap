"""Entrypoint for running KORSHI TAP Telegram bot locally."""

import asyncio
from app.bot.bot import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 Бот KORSHI TAP остановлен.")
