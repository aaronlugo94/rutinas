"""
main.py — Punto de entrada del bot.
"""
import logging
import os

from telegram.ext import Application

import database as db
import handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Silenciar el polling HTTP de telegram — solo muestra errores reales
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main() -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("Falta TELEGRAM_TOKEN en variables de entorno")

    db.init_db()
    handlers.load_allowed_users()

    app = Application.builder().token(token).build()
    handlers.register_handlers(app)

    logger.info("🏋️ GymCoach iniciando...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
