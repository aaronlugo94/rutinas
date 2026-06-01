"""
notificaciones.py — Mensajes automáticos diarios.

Mañana (hora configurada por usuario):
  Recordatorio corto de qué toca hoy — gym o rest day.

Noche (hora_recordatorio + 12 horas, o 9pm fijo):
  Si entrenó: Gemini analiza los pesos del día y da feedback real.
  Si no entrenó: mensaje corto sin drama.
  Si fue rest day: mensaje de recovery.

Gemini recibe datos reales — no responde preguntas genéricas.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, time

import pytz

import database as db
import catalog as cat

logger = logging.getLogger(__name__)

TZ      = pytz.timezone("America/Phoenix")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

GRUPO_ICON = {
    "gluteo": "🍑", "pierna": "🦵", "empuje": "💪",
    "tiron": "🏋️", "core": "🎯", "cardio": "🏃",
}

# ── RECORDATORIO DE MAÑANA ────────────────────────────────────────────────────

def msg_recordatorio(user_id: int) -> str:
    """Mensaje corto para la mañana — qué toca hoy."""
    try:
        semana, dia = db.get_estado(user_id)
        ejs = db.get_ejercicios_dia(user_id, semana, dia)
    except Exception:
        return ""

    if not ejs:
        return (
            "🌿 Hoy es recovery activo.\n"
            "Movilidad, caminata o core ligero — 20-30 min."
        )

    grupo = ejs[0].get("grupo", "general")
    icon  = GRUPO_ICON.get(grupo, "💪")
    fuerza = [e for e in ejs if not e["ejercicio_id"].startswith("CAR")]
    nombres = [e["ejercicio"][:22] for e in fuerza[:3]]

    # Peso sugerido del ejercicio principal
    primer = fuerza[0] if fuerza else None
    sug = db.get_peso_sugerido(user_id, primer["ejercicio_id"]) if primer else None
    sug_str = f"\n→ {primer['ejercicio'][:20]}: {sug} lbs hoy" if sug else ""

    return (
        f"{icon} Hoy toca {grupo.upper()}\n"
        f"{' · '.join(nombres)}{sug_str}\n\n"
        "Abre el bot cuando estés listo 👇"
    )


# ── RESUMEN NOCTURNO CON GEMINI ───────────────────────────────────────────────

def _datos_sesion(user_id: int, semana: int, dia: str) -> dict:
    """Recopila datos reales de la sesión para darle a Gemini."""
    ejs       = db.get_ejercicios_dia(user_id, semana, dia)
    fuerza    = [e for e in ejs if not e["ejercicio_id"].startswith("CAR")]
    completado = db.rutina_completa(user_id, semana, dia)

    pesos_hoy   = []
    progresiones = []
    sin_progres  = []

    for e in fuerza:
        eid    = e["ejercicio_id"]
        hist   = db.get_progresion_ejercicio(user_id, eid)
        ultimo = db.get_ultimo_peso(user_id, eid)

        if not ultimo or not ultimo.get("peso_lbs"):
            continue

        peso_hoy = float(ultimo["peso_lbs"])
        pesos_hoy.append(f"{e['ejercicio'][:24]}: {peso_hoy:g} lbs × {e['series']}×{e['reps']}")

        if len(hist) >= 2:
            peso_anterior = float(hist[-2]["mejor_peso"])
            diff = peso_hoy - peso_anterior
            if diff > 0:
                progresiones.append(f"{e['ejercicio'][:20]}: +{diff:g} lbs")
            elif diff == 0:
                sin_progres.append(e["ejercicio"][:20])

    # Racha
    racha = db.fetchone(
        "SELECT racha_actual FROM gamificacion WHERE user_id=?", (user_id,)
    )
    racha_n = int(racha["racha_actual"]) if racha else 0

    # Fatiga reportada
    fat_row = db.fetchone(
        "SELECT fatiga_reportada FROM progreso WHERE user_id=? AND semana=? AND dia=?",
        (user_id, semana, dia)
    )
    fatiga = int(fat_row["fatiga_reportada"]) if fat_row and fat_row["fatiga_reportada"] else None

    return {
        "completado":    completado,
        "grupo":         ejs[0].get("grupo", "") if ejs else "",
        "pesos":         pesos_hoy,
        "progresiones":  progresiones,
        "sin_progresion": sin_progres,
        "racha":         racha_n,
        "fatiga":        fatiga,
        "semana":        semana,
    }


async def _gemini_analisis(datos: dict, perfil: dict) -> str:
    """Llama a Gemini con datos reales. Retorna análisis en 3-4 líneas."""
    if not GEMINI_API_KEY:
        return _fallback_sin_gemini(datos)

    try:
        from google import genai

        pesos_str    = "\n".join(datos["pesos"]) or "Sin registros"
        progs_str    = ", ".join(datos["progresiones"]) or "ninguna"
        sin_prog_str = ", ".join(datos["sin_progresion"]) or "ninguno"
        fatiga_map   = {1: "muy fresco", 2: "normal", 3: "cansado", 4: "muy cansado", 5: "agotado"}
        fatiga_str   = fatiga_map.get(datos["fatiga"], "no reportada")

        prompt = f"""Eres un coach de gym. Analiza esta sesión y da feedback en 3-4 líneas MÁXIMO.
Sé directo, específico, sin frases motivacionales genéricas.

DATOS DEL ENTRENAMIENTO:
Grupo muscular: {datos['grupo']}
Semana: {datos['semana']} de 4
Racha: {datos['racha']} días

PESOS USADOS HOY:
{pesos_str}

PROGRESIONES (subió peso vs semana anterior):
{progs_str}

SIN PROGRESIÓN (igual que semana anterior):
{sin_prog_str}

FATIGA REPORTADA: {fatiga_str}

Usuario: nivel {perfil.get('nivel','intermedio')}, objetivo {perfil.get('objetivo','general')}

Responde en español. Máximo 4 líneas. Sin emojis excesivos. 
Si hay progresiones, mencionarlas con números específicos.
Si algo lleva semanas sin progresar, decirlo y sugerir algo concreto.
Si la fatiga es alta, recomendar descanso específico."""

        client = genai.Client(api_key=GEMINI_API_KEY)
        resp   = client.models.generate_content(
            model    = "gemini-2.0-flash",
            contents = prompt,
        )
        return resp.text.strip()

    except Exception as e:
        logger.warning("Gemini analysis error: %s", e)
        return _fallback_sin_gemini(datos)


def _fallback_sin_gemini(datos: dict) -> str:
    """Resumen sin Gemini — solo datos."""
    lines = []
    if datos["progresiones"]:
        lines.append("Progresaste en: " + ", ".join(datos["progresiones"]))
    if datos["sin_progresion"]:
        lines.append("Sin progresión: " + ", ".join(datos["sin_progresion"]))
    if datos["racha"] > 0:
        lines.append(f"Racha: {datos['racha']} días.")
    return "\n".join(lines) if lines else "Sesión registrada."


async def msg_resumen_nocturno(user_id: int) -> str:
    """
    Mensaje nocturno completo.
    Si entrenó: análisis con Gemini.
    Si no entrenó: mensaje corto.
    Si fue rest day: motivación de recovery.
    """
    try:
        semana, dia = db.get_estado(user_id)
        ejs = db.get_ejercicios_dia(user_id, semana, dia)
    except Exception:
        return ""

    # Rest day
    if not ejs:
        return (
            "🌿 Día de recovery completado.\n"
            "El músculo crece hoy — sueño y proteína."
        )

    datos   = _datos_sesion(user_id, semana, dia)
    perfil  = db.get_perfil(user_id)
    grupo   = datos["grupo"]
    icon    = GRUPO_ICON.get(grupo, "💪")

    # No entrenó
    if not datos["completado"]:
        return (
            f"{icon} Hoy era día de {grupo}.\n\n"
            "No pasa nada — mañana es otro día.\n"
            "Tu plan sigue ahí cuando quieras retomarlo."
        )

    # Sí entrenó — análisis Gemini
    analisis = await _gemini_analisis(datos, perfil)
    if analisis and analisis != _fallback_sin_gemini(datos):
        try:
            db.save_analisis(user_id, analisis, "nocturno")
        except Exception:
            pass

    pesos_str = ""
    if datos["pesos"]:
        pesos_str = "\n" + "\n".join(f"  {p}" for p in datos["pesos"][:4])

    racha_str = f"\n🔥 {datos['racha']} días de racha." if datos["racha"] >= 3 else ""

    return (
        f"{icon} Resumen de hoy — {dia.capitalize()}{racha_str}\n"
        f"{pesos_str}\n\n"
        f"{analisis}"
    )


# ── SCHEDULER — se llama desde api.py ────────────────────────────────────────

async def check_y_enviar(bot, hora_actual: str) -> None:
    """
    Corre cada minuto desde el scheduler.
    Envía recordatorio de mañana a la hora configurada.
    Envía resumen nocturno a las 9pm hora local.
    """
    # Hora fija para resumen nocturno
    HORA_NOCHE = "21:00"

    rows = db.fetchall(
        "SELECT u.user_id, u.hora_recordatorio, u.nombre "
        "FROM usuarios u JOIN allowed_users a ON a.user_id = u.user_id "
        "WHERE a.activo = 1",
        (),
    )

    for row in rows:
        row  = dict(row)
        uid  = row["user_id"]
        hora = row.get("hora_recordatorio") or ""

        # Recordatorio de mañana
        if hora and hora == hora_actual:
            try:
                msg = msg_recordatorio(uid)
                if msg:
                    await bot.send_message(
                        chat_id    = uid,
                        text       = msg,
                        parse_mode = "HTML",
                    )
                    logger.info("Recordatorio mañana enviado a %s", uid)
            except Exception as e:
                logger.warning("Recordatorio %s: %s", uid, e)

        # Resumen nocturno — 9pm fijo para todos
        if hora_actual == HORA_NOCHE:
            try:
                msg = await msg_resumen_nocturno(uid)
                if msg:
                    await bot.send_message(
                        chat_id    = uid,
                        text       = msg,
                        parse_mode = "HTML",
                    )
                    logger.info("Resumen nocturno enviado a %s", uid)
            except Exception as e:
                logger.warning("Resumen nocturno %s: %s", uid, e)
