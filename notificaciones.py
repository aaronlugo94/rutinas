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
    """
    Coach IA real — no reportero.
    Analiza patrones, conecta gym con composición corporal,
    da UNA recomendación concreta y accionable para mañana.
    """
    if not GEMINI_API_KEY:
        return _fallback_sin_gemini(datos)

    try:
        from google import genai

        # Datos de la sesión
        pesos_str    = "\n".join(datos["pesos"]) or "Sin registros de peso"
        progs_str    = ", ".join(datos["progresiones"]) or "ninguna"
        sin_prog_str = ", ".join(datos["sin_progresion"]) or "ninguno"
        fatiga_map   = {1:"muy fresco", 2:"normal", 3:"cansado", 4:"muy cansado", 5:"agotado"}
        fatiga_str   = fatiga_map.get(datos.get("fatiga", 2), "normal")

        # Datos de sueño
        sueño_perfil = perfil.get("sueño_horas", 0)
        sueño_str = ""
        if sueño_perfil and sueño_perfil > 0:
            if sueño_perfil < 6:
                sueño_str = f"\nSUEÑO ANOCHE: {sueño_perfil}h — CRÍTICO para recuperación"
            elif sueño_perfil < 7:
                sueño_str = f"\nSUEÑO ANOCHE: {sueño_perfil}h — subóptimo"
            else:
                sueño_str = f"\nSUEÑO ANOCHE: {sueño_perfil}h — adecuado"

        # Datos corporales si existen
        pesaje = db.get_ultimo_pesaje()
        cuerpo_str = ""
        if pesaje:
            cuerpo_str = (
                f"\nCOMPOSICIÓN CORPORAL (último pesaje {pesaje.get('Fecha','')}):\n"
                f"Peso: {pesaje.get('Peso_kg','?')} kg | "
                f"Grasa: {pesaje.get('Grasa_Porcentaje','?')}% | "
                f"Agua: {pesaje.get('Agua','?')}% | "
                f"BMR: {pesaje.get('BMR','?')} kcal"
            )

        # Historial de progresión (últimas 4 semanas)
        uid = datos.get("user_id")
        patron_str = ""
        if uid:
            historial = db.fetchall("""
                SELECT ejercicio_id, semana, MAX(peso_lbs) as peso
                FROM pesos WHERE user_id=? 
                GROUP BY ejercicio_id, semana
                ORDER BY semana DESC LIMIT 20
            """, (uid,))
            if historial:
                desde = {}
                for row in historial:
                    eid = row["ejercicio_id"]
                    if eid not in desde:
                        desde[eid] = {"semanas": [], "pesos": []}
                    desde[eid]["semanas"].append(row["semana"])
                    desde[eid]["pesos"].append(row["peso"])
                estancados = [eid for eid, v in desde.items()
                              if len(v["pesos"]) >= 2 and v["pesos"][0] == v["pesos"][1]]
                if estancados:
                    patron_str = f"\nESTANCAMIENTO DETECTADO en: {', '.join(estancados[:3])}"

        # Perfil físico
        obj_vida    = perfil.get("objetivo_vida", "general")
        nivel       = perfil.get("nivel", "intermedio")
        tdee_est    = perfil.get("tdee_estimado", 0)
        actividad   = perfil.get("actividad_nivel", "sedentario")
        semana_plan = datos.get("semana", 1)
        es_deload   = semana_plan == 4

        prompt = f"""Eres el coach personal de este usuario. Tienes acceso a sus datos reales. 
Tu trabajo NO es motivar con frases genéricas — es analizar datos y decirle exactamente qué hacer.

PERFIL:
- Objetivo: {obj_vida} | Nivel: {nivel} | Actividad diaria: {actividad}
- Semana {semana_plan}/4 del ciclo {'— SEMANA DE DELOAD' if es_deload else ''}
- Racha de entrenamiento: {datos.get('racha', 0)} días consecutivos
{f"- TDEE estimado: {tdee_est} kcal/día" if tdee_est else ""}

HOY — {datos.get('grupo', '').upper()}:
Fatiga reportada: {fatiga_str}

PESOS USADOS:
{pesos_str}

PROGRESIONES (subió vs semana anterior):
{progs_str}

SIN PROGRESIÓN:
{sin_prog_str}
{patron_str}
{cuerpo_str}

INSTRUCCIONES PARA TU RESPUESTA:
1. Empieza con lo más importante que dicen los datos HOY (máx 1 línea)
2. Si hay estancamiento en algún ejercicio, explica POR QUÉ puede estar pasando (fatiga acumulada, falta proteína, técnica, etc.)
3. Da UNA sola acción concreta para MAÑANA — específica, con números si aplica
4. Máximo 3-4 líneas en total. Sin listas. Sin bullet points. Texto corrido.
5. Usa números reales de los datos. No inventes nada.
6. Si es semana de deload: refuerza que NO suban pesos y explica la supercompensación.
7. Si la fatiga es 4-5: recomienda priorizar sueño y proteína esa noche específicamente.

Responde SOLO en español. Tono directo de coach, no de motivador."""

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
    datos["user_id"] = user_id
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
    - Recordatorio mañana a la hora configurada
    - Resumen nocturno a las 9pm
    - Detección de inactividad: si llevas 2+ días sin entrenar
    """
    HORA_NOCHE = "21:00"

    rows = db.fetchall(
        "SELECT u.user_id, u.hora_recordatorio, u.nombre "
        "FROM usuarios u JOIN allowed_users a ON a.user_id = u.user_id "
        "WHERE a.activo = 1", (),
    )

    for row in rows:
        row  = dict(row)
        uid  = row["user_id"]
        hora = row.get("hora_recordatorio") or ""

        # ── Recordatorio mañana ───────────────────────────────────────────────
        # Skip si está en modo pausa
        if hora and hora.startswith("PAUSA:"):
            from datetime import datetime, date
            try:
                fecha_ret = datetime.strptime(hora.split("PAUSA:")[1], "%d/%m/%Y").date()
                if date.today() >= fecha_ret:
                    # Pausa terminada — limpiar
                    db.execute("UPDATE usuarios SET hora_recordatorio=NULL WHERE user_id=?", (uid,))
                    logger.info("Pausa terminada para %s", uid)
            except Exception:
                pass
            continue

        if hora and hora == hora_actual:
            try:
                # Verificar inactividad antes de mandar recordatorio normal
                dias_inactivo = _dias_sin_entrenar(uid)
                if dias_inactivo >= 2:
                    msg = await _msg_inactividad(uid, dias_inactivo)
                else:
                    msg = msg_recordatorio(uid)
                if msg:
                    await bot.send_message(chat_id=uid, text=msg, parse_mode="HTML")
                    logger.info("Recordatorio enviado a %s (inactivo: %d días)", uid, dias_inactivo)
            except Exception as e:
                logger.warning("Recordatorio %s: %s", uid, e)

        # ── Resumen nocturno ──────────────────────────────────────────────────
        if hora_actual == HORA_NOCHE:
            try:
                msg = await msg_resumen_nocturno(uid)
                if msg:
                    await bot.send_message(chat_id=uid, text=msg, parse_mode="HTML")
                    logger.info("Resumen nocturno enviado a %s", uid)
            except Exception as e:
                logger.warning("Resumen nocturno %s: %s", uid, e)


def _dias_sin_entrenar(user_id: int) -> int:
    """Cuántos días lleva el usuario sin completar una sesión."""
    from datetime import datetime, date
    row = db.fetchone("""
        SELECT MAX(fecha) as ultima FROM progreso WHERE user_id=?
    """, (user_id,))
    if not row or not row["ultima"]:
        return 999  # nunca ha entrenado
    ultima = datetime.strptime(row["ultima"], "%Y-%m-%d").date()
    return (date.today() - ultima).days


async def _msg_inactividad(user_id: int, dias: int) -> str:
    """
    Mensaje personalizado de reenganche cuando llevas 2+ días sin entrenar.
    Gemini analiza tus datos y da un mensaje específico, no genérico.
    """
    import os
    from google import genai

    perfil     = db.get_perfil(user_id)
    semana, dia = db.get_estado(user_id)
    ejs        = db.get_ejercicios_dia(user_id, semana, dia)
    grupo_hoy  = ejs[0].get("grupo", "") if ejs else ""
    racha_max  = db.fetchone(
        "SELECT racha_maxima FROM gamificacion WHERE user_id=?", (user_id,)
    )
    racha_max_n = int(racha_max["racha_maxima"]) if racha_max else 0

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        # Fallback sin IA
        if dias == 2:
            return f"Han pasado 2 días. Hoy toca {grupo_hoy.upper() if grupo_hoy else 'entrenar'}. 💪"
        return f"Llevas {dias} días sin entrenar. Tu cuerpo está listo. 🔥"

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""Eres un coach personal. El usuario lleva {dias} días sin entrenar.
Escribe UN mensaje corto de reenganche (máx 2 líneas) que sea:
- Específico a sus datos (no genérico)
- Directo, sin drama
- Que mencione qué toca hoy

DATOS:
- Días sin entrenar: {dias}
- Racha máxima histórica: {racha_max_n} días
- Grupo muscular de hoy: {grupo_hoy or 'no definido'}
- Objetivo: {perfil.get('objetivo', 'general')}

Sin emojis excesivos. Sin "¡" ni drama. Solo motivación real en 1-2 líneas."""

        resp = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )
        return resp.text.strip() if resp and resp.text else f"Llevas {dias} días. Hoy toca volver. 💪"
    except Exception as e:
        logger.warning("Gemini inactividad: %s", e)
        return f"Llevas {dias} días sin entrenar. Hoy toca {grupo_hoy.upper() if grupo_hoy else 'volver'}. 💪"
