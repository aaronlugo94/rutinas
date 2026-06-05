"""
cuerpo.py — Módulo de composición corporal.
Adaptado de daily_renpho.py para usar la DB unificada.
Se integra al scheduler de api.py — no corre independiente.
"""
from __future__ import annotations
import logging
import os
import time
from datetime import datetime

import pytz

import database as db

logger = logging.getLogger(__name__)
TZ     = pytz.timezone(os.environ.get("TZ", "America/Phoenix"))

# ── RANGOS CLÍNICOS ───────────────────────────────────────────────────────────

RANGOS = {
    "grasa_hombre": {"optimo": (10.0, 20.0), "alerta": (20.1, 25.0), "critico": (25.1, 100)},
    "visceral":     {"optimo": (1,    9),    "alerta": (10,   13),   "critico": (14,   30)},
    "agua":         {"optimo": (53.0, 65.0), "alerta": (49.0, 52.9), "critico": (0,    48.9)},
    "proteina":     {"optimo": (16.5, 20.0), "alerta": (15.0, 16.4), "critico": (0,    14.9)},
    "bmi":          {"optimo": (18.5, 24.9), "alerta": (25.0, 29.9), "critico": (30.0, 99)},
}

def clasificar(valor: float | None, metrica: str) -> str:
    if valor is None or metrica not in RANGOS:
        return ""
    r = RANGOS[metrica]
    if r["optimo"][0] <= valor <= r["optimo"][1]:   return " 🟢"
    if r["alerta"][0] <= valor <= r["alerta"][1]:   return " 🟡"
    if r["critico"][0] <= valor <= r["critico"][1]: return " 🔴"
    return ""


# ── SCORE COMPOSICIÓN CORPORAL ────────────────────────────────────────────────

def calcular_score(m: dict) -> tuple[int, str]:
    """
    Score 0-100 calibrado al perfil del usuario.
    Grasa 35pts · Músculo 25pts · Visceral 25pts · Agua 15pts
    Punto de partida ~24pts, meta 6 meses ~72pts.
    """
    score = 0
    grasa = m.get("Grasa_Porcentaje") or 99
    musculo = m.get("Musculo_Pct") or 0
    visceral = m.get("VisFat") or 30
    agua = m.get("Agua") or 0

    # Grasa corporal (35 pts)
    if   grasa <= 15:  score += 35
    elif grasa <= 18:  score += 28
    elif grasa <= 22:  score += 20
    elif grasa <= 27:  score += 12
    elif grasa <= 30:  score += 7
    else:              score += 3

    # Músculo esquelético (25 pts)
    if   musculo >= 50: score += 25
    elif musculo >= 47: score += 22
    elif musculo >= 45: score += 18
    elif musculo >= 42: score += 13
    elif musculo >= 40: score += 8
    else:               score += 4

    # Grasa visceral (25 pts)
    if   visceral <= 5:  score += 25
    elif visceral <= 8:  score += 20
    elif visceral <= 10: score += 13
    elif visceral <= 13: score += 6
    else:                score += 1

    # Agua corporal (15 pts)
    if   agua >= 60: score += 15
    elif agua >= 56: score += 12
    elif agua >= 53: score += 9
    elif agua >= 50: score += 5
    else:            score += 2

    if score >= 80:   desc = "Élite 🏆"
    elif score >= 65: desc = "Avanzado 💪"
    elif score >= 50: desc = "En progreso 📈"
    elif score >= 35: desc = "Iniciando 🌱"
    else:             desc = "Punto de partida 🎯"

    return score, desc


# ── EVALUACIÓN MIMO ───────────────────────────────────────────────────────────

def evaluar_mimo(delta_peso: float, delta_grasa: float, delta_musculo: float) -> tuple[str, str]:
    """
    Diagnóstico multi-variable de composición corporal.
    Retorna (estado, descripción).
    """
    if abs(delta_peso) < 0.2 and abs(delta_grasa) < 0.3 and abs(delta_musculo) < 0.3:
        return "ESTANCAMIENTO", "Sin cambios significativos — revisar déficit calórico"

    if delta_grasa < -0.3 and delta_musculo >= -0.2 and delta_peso < 0:
        return "CUTTING_LIMPIO", "Grasa baja, músculo preservado ✅"

    if delta_grasa < -0.2 and delta_musculo > 0.2:
        return "RECOMPOSICION", "Grasa baja y músculo sube — recomposición activa 🔥"

    if delta_musculo < -0.5 and delta_grasa <= 0:
        return "CATABOLISMO", "⚠️ Músculo bajando — aumentar proteína y revisar déficit"

    if delta_peso > 0.5 and delta_grasa > 0.2:
        return "SUPERAVIT", "Peso subiendo con grasa — revisar excedente calórico"

    return "ZONA_GRIS", "Señales mixtas — posible fluctuación hídrica"


# ── OBTENER DATOS RENPHO ──────────────────────────────────────────────────────

def obtener_datos_renpho() -> dict:
    """Extrae el pesaje más reciente de la API de Renpho."""
    from renpho import RenphoClient

    email    = os.environ["RENPHO_EMAIL"]
    password = os.environ["RENPHO_PASSWORD"]

    cliente = RenphoClient(email, password)
    mediciones = None

    try:
        mediciones = cliente.get_all_measurements()
    except Exception as e:
        logger.warning("Fallback a MAC: %s", e)

    if not mediciones:
        devices = cliente.get_device_info()
        mac = devices[0].get("mac") if devices else None
        if not mac:
            raise ValueError("No hay dispositivos Renpho vinculados")
        mediciones = cliente.get_measurements(
            table_name=mac, user_id=cliente.user_id, total_count=10
        )

    if not mediciones:
        raise ValueError("Renpho devolvió lista vacía")

    def ts(m):
        for k in ["timeStamp","time_stamp","timestamp","created_at","createTime","measureTime"]:
            if m.get(k):
                return m[k]
        return 0

    mas_reciente = max(mediciones, key=ts)
    m = mas_reciente

    timestamp = ts(m)
    fecha_dt  = datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e10 else timestamp, tz=TZ)
    fecha_str = fecha_dt.strftime("%Y-%m-%d")

    return {
        "fecha_str":        fecha_str,
        "time_stamp":       int(timestamp),
        "peso":             float(m.get("weight") or m.get("peso") or 0),
        "grasa":            float(m.get("bodyfat") or m.get("grasa") or 0),
        "agua":             float(m.get("water") or m.get("agua") or 0),
        "musculo_pct":      float(m.get("muscle_mass") or m.get("musculo_pct") or 0),
        "masa_muscular_kg": float(m.get("muscle_mass_kg") or 0),
        "bmr":              int(m.get("bmr") or m.get("BMR") or 0),
        "grasa_visceral":   float(m.get("visceral_fat") or m.get("grasa_visceral") or 0),
        "bmi":              float(m.get("bmi") or m.get("BMI") or 0),
        "edad_metabolica":  int(m.get("body_age") or m.get("edad_metabolica") or 0),
        "fat_free_weight":  float(m.get("fat_free_weight") or 0),
        "proteina":         float(m.get("protein") or m.get("proteina") or 0),
        "masa_osea":        float(m.get("bone_mass") or m.get("masa_osea") or 0),
    }


# ── ANÁLISIS IA ───────────────────────────────────────────────────────────────

def analizar_con_ia(m: dict, anterior: dict | None, tend_7d: dict | None,
                    datos_gym: dict | None = None) -> str:
    """
    Análisis Gemini cruzado: composición corporal + datos del gym.
    datos_gym: dict con progresiones, sesiones, racha (opcional).
    """
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return "<i>Análisis no disponible — falta GEMINI_API_KEY.</i>"

    ctx_delta = ""
    if anterior:
        dias = (datetime.strptime(m["fecha_str"], "%Y-%m-%d") -
                datetime.strptime(anterior["Fecha"], "%Y-%m-%d")).days
        ctx_delta = (
            f"vs hace {dias}d: "
            f"peso {m['peso'] - float(anterior['Peso_kg']):+.1f}kg, "
            f"grasa {m['grasa'] - float(anterior['Grasa_Porcentaje']):+.1f}%, "
            f"músculo {m['musculo_pct'] - float(anterior.get('Musculo_Pct') or 0):+.1f}%"
        )

    tend_str = ""
    if tend_7d and tend_7d.get("peso_prom"):
        diff = m["peso"] - float(tend_7d["peso_prom"])
        tend_str = f"Tendencia 7d: {diff:+.2f} kg vs promedio semanal"

    gym_ctx = ""
    if datos_gym:
        gym_ctx = (
            f"\nDATOS GYM:\n"
            f"Racha: {datos_gym.get('racha',0)} días | "
            f"Sesiones semana: {datos_gym.get('sesiones_semana',0)} | "
            f"Progresiones: {datos_gym.get('progresiones',[][:3])}"
        )

    score, desc = calcular_score({"Grasa_Porcentaje": m["grasa"],
                                  "Musculo_Pct": m["musculo_pct"],
                                  "VisFat": m["grasa_visceral"],
                                  "Agua": m["agua"]})

    # Perfil del usuario para contexto adicional
    perfil_uid = None
    if chat_id:
        try:
            perfil_uid = db.get_perfil(chat_id)
        except Exception:
            pass

    tdee_str = ""
    sueño_str = ""
    if perfil_uid:
        tdee = perfil_uid.get("tdee_estimado", 0)
        if tdee:
            tdee_str = f"\nTDEE estimado: {tdee} kcal/día"
        sueño = perfil_uid.get("sueño_horas", 0)
        if sueño and sueño < 7:
            sueño_str = f"\nSueño reciente: {sueño}h — subóptimo para recuperación"

    prompt = f"""Eres el coach de composición corporal de este usuario. Tienes sus datos reales.

DATOS HOY ({m['fecha_str']}):
Peso: {m['peso']}kg | Grasa: {m['grasa']}% | Músculo: {m['musculo_pct']}% 
Visceral: {m['grasa_visceral']} | Agua: {m['agua']}% | BMR: {m['bmr']} kcal
Score corporal: {score}/100 ({desc})
{ctx_delta}
{tend_str}
{tdee_str}
{sueño_str}
{gym_ctx}

REGLAS:
- Diferencia fluctuación hídrica (cambios <0.5kg en 24h) de cambio real de grasa
- Si músculo = 0% es dato anómalo de la báscula — no lo analices, menciónalo brevemente
- Máximo 3 líneas, texto corrido sin listas
- Línea 1: qué dicen los datos HOY con números
- Línea 2: una acción concreta para las próximas 24h
- Línea 3: conexión gym-composición si hay datos gym

USA SOLO <b> e <i>. MÁXIMO 100 palabras. En español."""

    client = genai.Client(api_key=api_key)
    for intento in range(3):
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash", contents=prompt
            )
            texto = resp.text.strip() if resp and resp.text else ""
            if texto:
                return texto
        except Exception as e:
            logger.warning("Gemini intento %d: %s", intento + 1, e)
            time.sleep(2)

    return "<i>Análisis no disponible en este momento.</i>"


# ── MENSAJE TELEGRAM ──────────────────────────────────────────────────────────

def generar_mensaje_diario(m: dict, anterior: dict | None,
                           tend_7d: dict | None, analisis: str) -> str:
    """
    Mensaje diario corto — solo lo que importa y cambió.
    Sin repetir datos estáticos que no cambian día a día.
    """
    score, desc = calcular_score({"Grasa_Porcentaje": m["grasa"],
                                  "Musculo_Pct": m["musculo_pct"],
                                  "VisFat": m["grasa_visceral"],
                                  "Agua": m["agua"]})
    ant = anterior

    # Solo mostrar delta de peso — lo más relevante cada día
    peso_str = f"{m['peso']}kg"
    if ant:
        dp = m["peso"] - float(ant["Peso_kg"])
        if abs(dp) >= 0.1:
            emoji = "🟢" if dp < 0 else "🔴"
            peso_str += f" ({dp:+.1f}kg) {emoji}"

    # Tendencia 7 días
    tend_str = ""
    if tend_7d and tend_7d.get("peso_prom"):
        diff = m["peso"] - float(tend_7d["peso_prom"])
        if diff < -0.3:   tend_str = " · 📉 bajando"
        elif diff > 0.3:  tend_str = " · 📈 subiendo"
        else:             tend_str = " · ➡️ estable"

    # MIMO solo si hay cambio real
    mimo_str = ""
    if ant:
        dp = m["peso"] - float(ant["Peso_kg"])
        dg = m["grasa"] - float(ant["Grasa_Porcentaje"])
        dm = m["musculo_pct"] - float(ant.get("Musculo_Pct") or 0)
        estado, mimo_desc = evaluar_mimo(dp, dg, dm)
        if estado not in ("ZONA_GRIS",):
            emoji_map = {"RECOMPOSICION":"🟣","CUTTING_LIMPIO":"🟢",
                         "CATABOLISMO":"🔴","ESTANCAMIENTO":"🟡"}
            mimo_str = f"\n{emoji_map.get(estado,'⚪')} {mimo_desc}"

    msg = (
        f"⚖️ <b>{m['fecha_str']}</b>  Score: {score}/100\n"
        f"Peso: {peso_str}{tend_str}"
        f"{mimo_str}\n\n"
        f"🧠 {analisis}"
    )
    return msg


# ── FLUJO PRINCIPAL ───────────────────────────────────────────────────────────

async def ejecutar_diario(bot=None, chat_id: int | None = None,
                          datos_gym: dict | None = None) -> bool:
    """
    Ejecuta el check diario de Renpho.
    bot: instancia del bot de Telegram para enviar el mensaje.
    chat_id: ID del usuario que recibe el reporte.
    datos_gym: datos cruzados del gym para análisis IA.
    Retorna True si hubo pesaje nuevo.
    """
    try:
        m        = obtener_datos_renpho()
        es_nuevo = db.guardar_pesaje(m)

        if not es_nuevo:
            logger.debug("💤 Pesaje duplicado")
            return False

        # Anti-duplicado de envío: verificar que no hayamos mandado ya hoy
        from datetime import datetime
        hoy = datetime.now().strftime("%Y-%m-%d")
        ya_enviado = db.fetchone(
            "SELECT id FROM analisis_historial WHERE user_id=? AND fecha=? AND tipo='cuerpo'",
            (chat_id, hoy)
        ) if chat_id else None
        if ya_enviado:
            logger.info("💤 Reporte corporal ya enviado hoy a %s", chat_id)
            return False

        logger.info("🚀 Nuevo pesaje %s — generando análisis...", m["fecha_str"])

        anterior = db.get_pesaje_anterior(m["fecha_str"])
        tend_7d  = db.get_tendencia_7d(m["fecha_str"])
        analisis = analizar_con_ia(m, anterior, tend_7d, datos_gym)

        # Guardar análisis en historial
        if chat_id:
            db.save_analisis(chat_id, analisis, "cuerpo")

        # Enviar por Telegram si hay bot
        if bot and chat_id:
            msg = generar_mensaje_diario(m, anterior, tend_7d, analisis)
            try:
                await bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
                logger.info("✅ Reporte enviado a %s", chat_id)
            except Exception as e:
                logger.warning("Error enviando Telegram: %s", e)

        return True

    except Exception as e:
        logger.error("ejecutar_diario error: %s", e, exc_info=True)
        return False


# ── ACCESO RÁPIDO PARA LA WEB ─────────────────────────────────────────────────

def get_resumen_cuerpo() -> dict | None:
    """Datos del último pesaje formateados para la API web."""
    pesaje = db.get_ultimo_pesaje()
    if not pesaje:
        return None
    score, desc = calcular_score(pesaje)
    anterior = db.get_pesaje_anterior(pesaje["Fecha"])
    tend_7d  = db.get_tendencia_7d(pesaje["Fecha"])

    # Proyección a meta
    grasa_actual = pesaje.get("Grasa_Porcentaje") or 0
    ffm          = pesaje.get("FatFreeWeight") or (pesaje.get("Peso_kg", 0) * (1 - grasa_actual/100))
    peso_meta    = ffm / (1 - 0.22) if ffm else None
    kg_a_perder  = round(pesaje.get("Peso_kg", 0) - peso_meta, 1) if peso_meta else None
    semanas_eta  = round(kg_a_perder / 0.5, 0) if kg_a_perder and kg_a_perder > 0 else 0

    mimo = None
    if anterior:
        dp = pesaje["Peso_kg"] - anterior["Peso_kg"]
        dg = pesaje["Grasa_Porcentaje"] - anterior["Grasa_Porcentaje"]
        dm = (pesaje.get("Musculo_Pct") or 0) - (anterior.get("Musculo_Pct") or 0)
        mimo, _ = evaluar_mimo(dp, dg, dm)

    return {
        "fecha":        pesaje["Fecha"],
        "peso_kg":      pesaje["Peso_kg"],
        "grasa_pct":    pesaje["Grasa_Porcentaje"],
        "musculo_pct":  pesaje["Musculo_Pct"],
        "agua_pct":     pesaje["Agua"],
        "visceral":     pesaje["VisFat"],
        "bmr":          pesaje["BMR"],
        "bmi":          pesaje["BMI"],
        "ffm_kg":       pesaje["FatFreeWeight"],
        "score":        score,
        "score_desc":   desc,
        "estado_mimo":  mimo,
        "peso_meta_kg": round(peso_meta, 1) if peso_meta else None,
        "kg_a_perder":  kg_a_perder,
        "semanas_eta":  int(semanas_eta),
        "anterior": {
            "fecha":       anterior["Fecha"],
            "peso_kg":     anterior["Peso_kg"],
            "grasa_pct":   anterior["Grasa_Porcentaje"],
            "musculo_pct": anterior.get("Musculo_Pct"),
        } if anterior else None,
    }
