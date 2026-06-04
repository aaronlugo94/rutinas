"""
nutricion.py — Motor de nutrición adaptativa.
Adaptado de job_dieta.py V5.2 para la DB unificada.

Ciencia aplicada:
  SISO: regresión lineal 28 días → ajuste de multiplicador calórico
  MIMO: diagnóstico multi-variable (grasa + músculo + peso)
  Macros: proteína 2.2g/kg FFM, grasas 0.7g/kg, carbs por diferencia
  Piso calórico: nunca < BMR × 1.15
"""
from __future__ import annotations
import json
import logging
import os
import time
from datetime import datetime, timedelta

import pytz

import database as db

logger = logging.getLogger(__name__)
TZ     = pytz.timezone(os.environ.get("TZ", "America/Phoenix"))

# ── ESTADOS MIMO ──────────────────────────────────────────────────────────────

ESTADOS_MIMO = {
    "CATABOLISMO":    ("🔴", "Pérdida de músculo sin quema de grasa. Sube carbs peri-entreno."),
    "RECOMPOSICION":  ("🟣", "Recomposición activa. Proteína en límite superior."),
    "CUTTING_LIMPIO": ("🟢", "Déficit funcionando. Mantén el curso."),
    "ESTANCAMIENTO":  ("🟡", "Adaptación metabólica. Forzar oxidación de lípidos."),
    "ZONA_GRIS":      ("⚪", "Señales mixtas. Puede ser ruido hídrico."),
}

FALLBACK_PLAN = {
    "diagnostico": "Plan IA no disponible esta semana. Mantén los macros calculados.",
    "dias": []
}

# ── MIMO ─────────────────────────────────────────────────────────────────────

def evaluar_mimo(delta_peso: float, delta_grasa: float, delta_musculo: float,
                 mult_actual: float) -> tuple[str, float, str]:
    TOL = 0.2
    if delta_peso < -0.8 and delta_musculo < -TOL and delta_grasa > -TOL:
        estado = "CATABOLISMO"
        mult   = mult_actual + 1
        razon  = f"Pérdida peso ({delta_peso:+.2f}kg) y músculo ({delta_musculo:+.2f}%) sin quemar grasa."
    elif abs(delta_peso) <= 0.3 and delta_grasa < -TOL and delta_musculo > TOL:
        estado = "RECOMPOSICION"
        mult   = mult_actual
        razon  = f"Peso estable. Grasa ({delta_grasa:+.2f}%), músculo ({delta_musculo:+.2f}%) — recomp. activa."
    elif delta_peso <= -0.3 and delta_grasa < -TOL and abs(delta_musculo) <= TOL:
        estado = "CUTTING_LIMPIO"
        mult   = mult_actual
        razon  = f"Pérdida controlada ({delta_peso:+.2f}kg) de tejido adiposo. Músculo preservado."
    elif delta_peso > -0.2 and delta_grasa >= -TOL and delta_musculo <= TOL:
        estado = "ESTANCAMIENTO"
        mult   = mult_actual - 1
        razon  = "Sin mejora en composición. Adaptación metabólica detectada."
    else:
        estado = "ZONA_GRIS"
        mult   = mult_actual
        razon  = "Señales mixtas. Puede ser ruido hídrico. Requiere más datos."

    return estado, max(20.0, min(mult, 34.0)), razon


# ── SISO ─────────────────────────────────────────────────────────────────────

def calcular_tendencia_peso(historial: list[dict]) -> float | None:
    """
    Regresión lineal sobre 28 días de pesajes.
    Retorna kg/semana. None si < 3 puntos.
    Misma técnica que MacroFactor y Cronometer.
    """
    if len(historial) < 3:
        return None
    import numpy as np
    fechas = [datetime.strptime(r["Fecha"], "%Y-%m-%d") for r in historial]
    x = [(f - fechas[0]).days for f in fechas]
    y = [float(r["Peso_kg"]) for r in historial]
    pendiente = np.polyfit(x, y, 1)[0]
    return round(pendiente * 7, 3)


def aplicar_siso(tendencia: float | None, mult_actual: float,
                 bmr: int = 2000, peso: float = 100) -> tuple[float, str, bool]:
    """
    Ajusta el multiplicador calórico según la tendencia de 28 días.
    Piso: BMR × 1.15. Techo: 34 kcal/kg.
    """
    piso_kcal = round(bmr * 1.15)
    piso_mult = max(round(piso_kcal / peso, 1), 21.0)

    if tendencia is None:
        return mult_actual, "⏳ Datos insuficientes. Multiplicador mantenido.", False

    if tendencia < -1.0:
        nuevo  = mult_actual + 1.0
        razon  = f"📉 Pérdida demasiado rápida ({tendencia:+.2f} kg/sem). Aumentando multiplicador."
        cambio = True
    elif tendencia < -0.25:
        nuevo  = mult_actual
        razon  = f"✅ Progreso óptimo ({tendencia:+.2f} kg/sem). Multiplicador mantenido."
        cambio = False
    else:
        nuevo  = mult_actual - 1.0
        razon  = f"🛑 Estancamiento ({tendencia:+.2f} kg/sem). Recortando multiplicador."
        cambio = True

    nuevo_seguro = max(piso_mult, min(nuevo, 34.0))
    if nuevo_seguro != nuevo:
        razon += f" (Piso BMR: {piso_kcal} kcal)"
    return nuevo_seguro, razon, cambio


# ── MACROS ────────────────────────────────────────────────────────────────────

def calcular_macros(peso: float, fat_free_weight: float, mult: float,
                    bmr: int) -> dict:
    """
    Macros basados en evidencia:
    Proteína: 2.2g/kg FFM (Helms, Schoenfeld)
    Grasas: 0.7g/kg peso total (mínimo saludable)
    Carbs: calorías restantes / 4
    """
    calorias = round(peso * mult)
    proteina = round(fat_free_weight * 2.2)
    grasas   = round(peso * 0.7)
    carbs    = max(0, round((calorias - (proteina * 4 + grasas * 9)) / 4))
    return {
        "calorias": calorias,
        "proteina": proteina,
        "carbs":    carbs,
        "grasas":   grasas,
    }


# ── GENERACIÓN DE PLAN IA ─────────────────────────────────────────────────────

# Tabla de equivalencias de proteína — se inyecta en el prompt de Gemini
EQUIVALENCIAS_PROTEINA = """
FUENTES DE PROTEÍNA (g por 100g cocinado):
Pollo pechuga: 31g | Atún en agua: 30g | Res magra: 26g | Salmón: 25g
Huevo entero: 13g (1 huevo = 6g prot) | Camarón: 24g | Sardinas: 25g
Queso cottage: 11g | Yogur griego: 10g | Leche (250ml): 8g
Frijoles/Lentejas cocinados: 9g | Tofu firme: 17g | Edamame: 11g
Whey protein: 1 scoop (30g) = 24g proteína
EQUIVALENCIAS: 1 pechuga mediana (150g) = 47g | 1 lata atún = 51g | 3 huevos = 18g
"""


def generar_plan_ia(peso: float, grasa: float, visceral: float, agua: float,
                    fat_free_weight: float, macros: dict, bmr: int,
                    delta_peso: float, delta_grasa: float, delta_musculo: float,
                    estado_mimo: str, razon_mimo: str,
                    datos_gym: dict | None = None) -> dict:
    """
    Genera plan semanal de 7 días con Gemini 2.5 Pro.
    Retorna dict con 'diagnostico' y 'dias'.
    Garantiza retorno válido — nunca lanza excepción.
    """
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return FALLBACK_PLAN

    gym_ctx = ""
    if datos_gym:
        gym_ctx = (
            f"\nACTIVIDAD GYM ESTA SEMANA:\n"
            f"- Sesiones: {datos_gym.get('sesiones',0)} | Racha: {datos_gym.get('racha',0)} días\n"
            f"- Grupos entrenados: {', '.join(datos_gym.get('grupos',[]))}\n"
        )

    prompt = f"""Eres mi nutriólogo deportivo y coach de recomposición corporal.
Diseña un plan completo de 7 días basado en mis datos exactos.

PERFIL ACTUAL:
- Peso: {peso}kg | Grasa: {grasa}% | Visceral: {visceral} | Agua: {agua}%
- Masa libre de grasa (FFM): {fat_free_weight}kg
- Variación semanal: Peso ({delta_peso:+.2f}kg), Grasa ({delta_grasa:+.2f}%), Músculo ({delta_musculo:+.2f}%)
- Estado metabólico: {estado_mimo} — {razon_mimo}
{gym_ctx}
MACROS DIARIOS:
- Calorías: {macros['calorias']} kcal | Proteína: {macros['proteina']}g | Carbs: {macros['carbs']}g | Grasas: {macros['grasas']}g
- MÍNIMO ABSOLUTO: {bmr} kcal (BMR real)

{EQUIVALENCIAS_PROTEINA}

RESTRICCIONES ALIMENTARIAS: {perfil.get('alergias','ninguna').replace('_',' ')}
TIPO DE DIETA: {perfil.get('tipo_dieta','omnivoro')}

RESTRICCIONES DE ESTILO DE VIDA (OBLIGATORIAS):
1. LUNES, MIÉRCOLES, JUEVES (Oficina + Gym 45 min): cenas saciantes y altas en proteína
2. MARTES Y VIERNES (Home Office): entreno 30 min en casa
3. DESAYUNOS: ultra-rápidos (<5 min), portátiles
4. COLACIÓN: 1 fruta fresca diaria
5. FIN DE SEMANA: recuperación activa, 1 comida social el sábado permitida

FORMATO — responde SOLO con JSON válido, sin markdown:
{{
  "diagnostico": "Análisis de la semana y filosofía del plan. Sin HTML.",
  "dias": [
    {{
      "nombre": "LUNES — Día de Ataque 1",
      "tipo": "GYM",
      "subtitulo": "Oficina + Gym 45 min — Empuje",
      "comidas": [
        {{"label": "Desayuno", "texto": "descripción concreta"}},
        {{"label": "Almuerzo",  "texto": "descripción concreta"}},
        {{"label": "Colacion",  "texto": "descripción concreta"}},
        {{"label": "Cena",      "texto": "descripción concreta"}}
      ]
    }}
  ]
}}
Tipos válidos: GYM, CASA, FIN_DE_SEMANA, RESETEO
El array dias debe tener exactamente 7 elementos (Lunes a Domingo)."""

    client = genai.Client(api_key=api_key)
    for intento in range(3):
        try:
            resp  = client.models.generate_content(model="gemini-2.5-pro", contents=prompt)
            texto = resp.text.strip() if resp and resp.text else ""
            if not texto:
                continue
            if texto.startswith("```"):
                texto = texto.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            plan = json.loads(texto)
            if "diagnostico" not in plan or "dias" not in plan:
                continue
            if len(plan["dias"]) < 7:
                logger.warning("Gemini generó %d/7 días", len(plan["dias"]))
                continue
            logger.info("✅ Plan semanal generado (%d días)", len(plan["dias"]))
            return plan
        except json.JSONDecodeError as e:
            logger.warning("JSON inválido intento %d: %s", intento+1, e)
        except Exception as e:
            logger.warning("Gemini intento %d: %s", intento+1, e)
        time.sleep(2)

    logger.error("Gemini falló 3 intentos — usando plan fallback")
    return FALLBACK_PLAN


# ── EJECUCIÓN DOMINICAL ───────────────────────────────────────────────────────

async def ejecutar_dominical(bot=None, chat_id: int | None = None,
                              datos_gym: dict | None = None) -> bool:
    """
    Corre cada domingo. Calcula macros, ajusta SISO/MIMO, genera plan IA.
    Envía reporte por Telegram y guarda en DB.
    """
    hoy = datetime.now(TZ)
    if hoy.weekday() != 6:
        logger.info("Hoy es %s — job dominical solo corre domingos", hoy.strftime("%A"))
        return False

    if db.job_ya_ejecutado_hoy():
        logger.warning("Job dominical ya ejecutado hoy — abortando")
        return False

    try:
        import numpy as np
        import pandas as pd

        historial = db.get_historial_pesajes(dias=28)
        if len(historial) < 2:
            if bot and chat_id:
                await bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ Necesito al menos 2 pesajes para calcular tu plan. Pésate mañana.",
                )
            return False

        df = pd.DataFrame(historial)
        df["Fecha"] = pd.to_datetime(df["Fecha"])
        dato_actual = df.iloc[-1]

        # Dato de referencia: pesaje más cercano a hace 7 días (mínimo 5 días atrás)
        fecha_limite = df.iloc[-1]["Fecha"] - timedelta(days=5)
        df_ant = df[df["Fecha"] <= fecha_limite].copy()
        if df_ant.empty:
            if bot and chat_id:
                await bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ No hay pesajes con al menos 5 días de antigüedad aún.",
                )
            return False

        fecha_ref     = dato_actual["Fecha"] - timedelta(days=7)
        df_ant["diff"] = (df_ant["Fecha"] - fecha_ref).abs()
        dato_anterior  = df_ant.loc[df_ant["diff"].idxmin()]

        # Variables
        peso      = float(dato_actual["Peso_kg"])
        grasa     = float(dato_actual["Grasa_Porcentaje"])
        musculo   = float(dato_actual["Musculo_Pct"] or 0)
        agua      = float(dato_actual["Agua"] or 0)
        ffm       = float(dato_actual["FatFreeWeight"] or peso * (1 - grasa/100))
        visceral  = float(dato_actual["VisFat"] or 0)
        bmr       = int(dato_actual["BMR"] or round(peso * 22))

        delta_peso    = peso    - float(dato_anterior["Peso_kg"])
        delta_grasa   = grasa   - float(dato_anterior["Grasa_Porcentaje"])
        delta_musculo = musculo - float(dato_anterior["Musculo_Pct"] or 0)

        # Control metabólico
        mult_actual = db.get_multiplicador()
        tendencia   = calcular_tendencia_peso(historial)
        logger.info("[TENDENCIA] %+.3f kg/semana (%d pesajes)", tendencia or 0, len(historial))

        estado_mimo, _, razon_mimo = evaluar_mimo(delta_peso, delta_grasa, delta_musculo, mult_actual)
        nuevo_mult, razon_siso, hubo_cambio = aplicar_siso(tendencia, mult_actual, bmr, peso)

        if hubo_cambio:
            db.set_multiplicador(nuevo_mult)
            logger.info("[SISO] %s → %s", mult_actual, nuevo_mult)

        macros = calcular_macros(peso, ffm, nuevo_mult, bmr)

        # Generar plan IA
        plan = generar_plan_ia(
            peso, grasa, visceral, agua, ffm, macros, bmr,
            delta_peso, delta_grasa, delta_musculo,
            estado_mimo, razon_mimo, datos_gym,
        )

        # Guardar en DB
        fecha_str = hoy.strftime("%Y-%m-%d")
        db.guardar_dieta(
            fecha      = fecha_str,
            score      = 0,
            estado_mimo= estado_mimo,
            kcal_mult  = nuevo_mult,
            calorias   = macros["calorias"],
            proteina   = macros["proteina"],
            carbs      = macros["carbs"],
            grasas     = macros["grasas"],
            dieta_json = json.dumps(plan, ensure_ascii=False),
            delta_peso = delta_peso,
        )

        # Enviar reporte por Telegram
        if bot and chat_id:
            emoji_mimo, consejo_mimo = ESTADOS_MIMO.get(estado_mimo, ("⚪", ""))
            msg = (
                f"<b>📊 Reporte Metabólico Semanal</b>\n\n"
                f"<b>Estado:</b> {emoji_mimo} {estado_mimo}\n"
                f"{consejo_mimo}\n\n"
                f"<b>Tendencia peso:</b> {f'{tendencia:+.2f} kg/semana' if tendencia else 'calculando...'}\n"
                f"<b>Multiplicador:</b> {mult_actual:.1f} → {nuevo_mult:.1f} kcal/kg\n\n"
                f"<b>Macros esta semana:</b>\n"
                f"  🔥 {macros['calorias']} kcal\n"
                f"  🥩 {macros['proteina']}g proteína\n"
                f"  🍞 {macros['carbs']}g carbs\n"
                f"  🥑 {macros['grasas']}g grasas\n\n"
                f"<b>Diagnóstico IA:</b>\n<i>{plan.get('diagnostico','')[:300]}</i>\n\n"
                f"<i>Plan completo disponible en la web 🌐</i>"
            )
            await bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")

        logger.info("✅ Job dominical completado")
        return True

    except Exception as e:
        logger.error("ejecutar_dominical error: %s", e, exc_info=True)
        return False


# ── ACCESO WEB ────────────────────────────────────────────────────────────────

def get_plan_actual() -> dict | None:
    """Retorna el último plan de nutrición para la web."""
    dieta = db.get_ultima_dieta()
    if not dieta:
        return None
    try:
        plan = json.loads(dieta["dieta_html"]) if dieta.get("dieta_html") else {}
    except Exception:
        plan = {}

    return {
        "fecha":        dieta["fecha"],
        "estado_mimo":  dieta["estado_mimo"],
        "calorias":     dieta["calorias"],
        "proteina":     dieta["proteina"],
        "carbs":        dieta["carbs"],
        "grasas":       dieta["grasas"],
        "kcal_mult":    dieta["kcal_mult"],
        "diagnostico":  plan.get("diagnostico", ""),
        "dias":         plan.get("dias", []),
    }


def get_macros_hoy(user_id: int | None = None) -> dict | None:
    """
    Macros del día. Fuente de datos en orden de precisión:
    1. Báscula Renpho (más preciso — FFM real)
    2. Perfil del usuario (BMR estimado con Mifflin-St Jeor)
    3. Fallback genérico (sin datos)
    """
    pesaje = db.get_ultimo_pesaje()
    if pesaje and pesaje.get("Peso_kg"):
        peso  = float(pesaje["Peso_kg"])
        grasa = float(pesaje.get("Grasa_Porcentaje") or 30)
        ffm   = float(pesaje.get("FatFreeWeight") or (peso * (1 - grasa/100)))
        bmr   = int(pesaje.get("BMR") or round(peso * 22))
        mult  = db.get_multiplicador()
        macros = calcular_macros(peso, ffm, mult, bmr)
        macros["fuente"] = "bascula"
        return macros

    # Sin báscula — usar perfil
    if user_id:
        perfil = db.get_perfil(user_id)
        peso   = float(perfil.get("peso_kg_estimado") or 90)
        sexo   = perfil.get("sexo", "hombre")
        edad   = int(perfil.get("edad") or 30)
        altura = 175 if sexo == "hombre" else 163
        act    = perfil.get("actividad_nivel", "sedentario")

        # Mifflin-St Jeor
        if sexo == "hombre":
            bmr = round(10 * peso + 6.25 * altura - 5 * edad + 5)
        else:
            bmr = round(10 * peso + 6.25 * altura - 5 * edad - 161)

        factor = {"sedentario": 1.2, "moderado": 1.375, "activo": 1.55}.get(act, 1.2)
        tdee   = round(bmr * factor)

        # Objetivo determina déficit/superávit
        obj = perfil.get("objetivo", "general")
        cals_objetivo = {
            "peso":    round(tdee * 0.82),   # -18% déficit moderado
            "mamado":  round(tdee * 1.10),   # +10% superávit lean bulk
            "general": round(tdee * 0.90),   # -10% recomposición
            "gluteo":  round(tdee * 0.95),   # -5% leve déficit
        }.get(obj, round(tdee * 0.90))

        # FFM estimada (asume 30% grasa para hombre promedio, 28% mujer)
        grasa_est = 0.28 if sexo == "mujer" else 0.30
        ffm_est   = peso * (1 - grasa_est)

        # Multiplicador = calorías / peso
        mult_est = cals_objetivo / peso
        macros   = calcular_macros(peso, ffm_est, mult_est, bmr)
        macros["fuente"]   = "estimado"
        macros["nota"]     = "⚠️ Basado en estimaciones — pésate para mayor precisión"
        macros["tdee"]     = tdee
        return macros

    return None
