"""
main.py — Punto de entrada del bot.
"""
import logging
import asyncio
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


async def enviar_recordatorios(app) -> None:
    """Corre cada minuto. Manda recordatorio a usuarios cuya hora coincide."""
    from datetime import datetime, timezone
    import pytz
    # Hora local Mountain Time (Arizona no cambia horario)
    tz   = pytz.timezone("America/Phoenix")
    hora = datetime.now(tz).strftime("%H:%M")
    uids = db.get_usuarios_con_recordatorio(hora)
    for uid in uids:
        try:
            semana, dia = db.get_estado(uid)
            ejs = db.get_ejercicios_dia(uid, semana, dia)
            if not ejs:
                continue  # día libre, no molestar
            grupo = ejs[0].get("grupo", "")
            msgs  = {
                "gluteo": "Hoy toca glúteo. Hip thrust primero.",
                "pierna": "Día de pierna. El más difícil. El que más vale.",
                "empuje": "Hoy empuje. Calienta el hombro antes del press.",
                "tiron":  "Tirón hoy. Piensa en jalar con los codos.",
            }
            texto = msgs.get(grupo, "Tu rutina de hoy está lista.")
            await app.bot.send_message(
                chat_id = uid,
                text    = texto,
                parse_mode = "HTML",
            )
            logger.info("Recordatorio enviado a %s (%s)", uid, hora)
        except Exception as e:
            logger.warning("Error recordatorio uid=%s: %s", uid, e)


def run_api() -> None:
    """Corre FastAPI en un thread separado."""
    import uvicorn
    from api import app as fastapi_app
    port = int(os.environ.get("API_PORT", "8000"))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port, log_level="warning")


def main() -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("Falta TELEGRAM_TOKEN en variables de entorno")

    db.init_db()
    handlers.load_allowed_users()

    # Arrancar FastAPI en background thread
    import threading
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    logger.info("API corriendo en puerto %s", os.environ.get("API_PORT", "8000"))

    app = Application.builder().token(token).build()
    handlers.register_handlers(app)

    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(
            lambda ctx: asyncio.ensure_future(enviar_recordatorios(app)),
            interval = 60,
            first    = 10,
        )
        logger.info("Scheduler de recordatorios activo")

    logger.info("GymCoach iniciando...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
