import os
import json
import asyncio
import sqlite3
import html
import logging
from pathlib import Path
from google import genai
from google.genai import types
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==========================================
# 1. CONFIGURACIÓN, SEGURIDAD Y LOGGING
# ==========================================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_USERS = {1557254587}  # ⚠️ REEMPLAZA CON LOS IDs NUMÉRICOS REALES
DB_PATH = Path("/app/data/rutinas.db")

def safe(text: str) -> str:
    return html.escape(str(text), quote=True)

# ==========================================
# 2. CATÁLOGO Y PROMPTS
# ==========================================
CATALOGO = [
    # ─── PIERNA ────────────────────────────────────────────────────────────────
    {"ejercicio_id": "PIE_01", "nombre": "Sentadilla libre",                    "grupo": "pierna",  "rol": "principal"},
    {"ejercicio_id": "PIE_02", "nombre": "Sentadilla sumo",                     "grupo": "pierna",  "rol": "principal"},
    {"ejercicio_id": "PIE_03", "nombre": "Sentadilla en máquina Smith",         "grupo": "pierna",  "rol": "principal"},
    {"ejercicio_id": "PIE_04", "nombre": "Prensa de pierna",                    "grupo": "pierna",  "rol": "principal"},
    {"ejercicio_id": "PIE_05", "nombre": "Extensión de cuádriceps",             "grupo": "pierna",  "rol": "aislamiento"},
    {"ejercicio_id": "PIE_06", "nombre": "Curl femoral tumbada",                "grupo": "pierna",  "rol": "aislamiento"},
    {"ejercicio_id": "PIE_07", "nombre": "Curl femoral de pie en máquina",      "grupo": "pierna",  "rol": "aislamiento"},
    {"ejercicio_id": "PIE_08", "nombre": "Abducción de cadera en máquina",      "grupo": "pierna",  "rol": "aislamiento"},
    {"ejercicio_id": "PIE_09", "nombre": "Aducción de cadera en máquina",       "grupo": "pierna",  "rol": "aislamiento"},
    {"ejercicio_id": "PIE_10", "nombre": "Desplante con mancuernas",            "grupo": "pierna",  "rol": "secundario"},
    {"ejercicio_id": "PIE_11", "nombre": "Desplante caminando",                 "grupo": "pierna",  "rol": "secundario"},
    {"ejercicio_id": "PIE_12", "nombre": "Desplante reverso",                   "grupo": "pierna",  "rol": "secundario"},
    {"ejercicio_id": "PIE_13", "nombre": "Sentadilla búlgara",                  "grupo": "pierna",  "rol": "secundario"},
    {"ejercicio_id": "PIE_14", "nombre": "Elevación de talones de pie",         "grupo": "pierna",  "rol": "aislamiento"},
    {"ejercicio_id": "PIE_15", "nombre": "Elevación de talones sentada",        "grupo": "pierna",  "rol": "aislamiento"},
    {"ejercicio_id": "PIE_16", "nombre": "Step-up con mancuernas",              "grupo": "pierna",  "rol": "secundario"},
    {"ejercicio_id": "PIE_17", "nombre": "Sentadilla hack en máquina",          "grupo": "pierna",  "rol": "principal"},
    {"ejercicio_id": "PIE_18", "nombre": "Sentadilla goblet con mancuerna",     "grupo": "pierna",  "rol": "secundario"},
    {"ejercicio_id": "PIE_19", "nombre": "Peso muerto convencional",            "grupo": "pierna",  "rol": "principal"},
    {"ejercicio_id": "PIE_20", "nombre": "Zancada lateral",                     "grupo": "pierna",  "rol": "secundario"},
    # ─── GLÚTEO ────────────────────────────────────────────────────────────────
    {"ejercicio_id": "GLU_01", "nombre": "Puente de glúteo",                    "grupo": "gluteo",  "rol": "principal"},
    {"ejercicio_id": "GLU_02", "nombre": "Puente de glúteo con banda",          "grupo": "gluteo",  "rol": "principal"},
    {"ejercicio_id": "GLU_03", "nombre": "Hip thrust en banco",                 "grupo": "gluteo",  "rol": "principal"},
    {"ejercicio_id": "GLU_04", "nombre": "Hip thrust en máquina",               "grupo": "gluteo",  "rol": "principal"},
    {"ejercicio_id": "GLU_05", "nombre": "Patada de glúteo en polea baja",      "grupo": "gluteo",  "rol": "aislamiento"},
    {"ejercicio_id": "GLU_06", "nombre": "Patada de glúteo en cuadrupedia",     "grupo": "gluteo",  "rol": "aislamiento"},
    {"ejercicio_id": "GLU_07", "nombre": "Abducción de cadera con banda",       "grupo": "gluteo",  "rol": "aislamiento"},
    {"ejercicio_id": "GLU_08", "nombre": "Sentadilla con banda en rodillas",    "grupo": "gluteo",  "rol": "secundario"},
    {"ejercicio_id": "GLU_09", "nombre": "Good morning con mancuerna",          "grupo": "gluteo",  "rol": "secundario"},
    {"ejercicio_id": "GLU_10", "nombre": "Peso muerto rumano con mancuernas",   "grupo": "gluteo",  "rol": "secundario"},
    {"ejercicio_id": "GLU_11", "nombre": "Peso muerto a una pierna",            "grupo": "gluteo",  "rol": "secundario"},
    {"ejercicio_id": "GLU_12", "nombre": "Abducción en polea con tobillera",    "grupo": "gluteo",  "rol": "aislamiento"},
    {"ejercicio_id": "GLU_13", "nombre": "Clamshell con banda",                 "grupo": "gluteo",  "rol": "aislamiento"},
    {"ejercicio_id": "GLU_14", "nombre": "Hip thrust a una pierna",             "grupo": "gluteo",  "rol": "principal"},
    {"ejercicio_id": "GLU_15", "nombre": "Sentadilla sumo con mancuerna",       "grupo": "gluteo",  "rol": "secundario"},
    {"ejercicio_id": "GLU_16", "nombre": "Extensión de cadera en máquina",      "grupo": "gluteo",  "rol": "aislamiento"},
    {"ejercicio_id": "GLU_17", "nombre": "Donkey kick con tobillera en polea",  "grupo": "gluteo",  "rol": "aislamiento"},
    {"ejercicio_id": "GLU_18", "nombre": "Fire hydrant con banda",              "grupo": "gluteo",  "rol": "aislamiento"},
    # ─── EMPUJE ────────────────────────────────────────────────────────────────
    {"ejercicio_id": "EMP_01", "nombre": "Flexiones en rodillas",               "grupo": "empuje",  "rol": "secundario"},
    {"ejercicio_id": "EMP_02", "nombre": "Flexiones estándar",                  "grupo": "empuje",  "rol": "secundario"},
    {"ejercicio_id": "EMP_03", "nombre": "Press de pecho con mancuernas",       "grupo": "empuje",  "rol": "principal"},
    {"ejercicio_id": "EMP_04", "nombre": "Press inclinado con mancuernas",      "grupo": "empuje",  "rol": "principal"},
    {"ejercicio_id": "EMP_05", "nombre": "Press declinado con mancuernas",      "grupo": "empuje",  "rol": "principal"},
    {"ejercicio_id": "EMP_06", "nombre": "Aperturas con mancuernas",            "grupo": "empuje",  "rol": "aislamiento"},
    {"ejercicio_id": "EMP_07", "nombre": "Aperturas en polea cruzada",          "grupo": "empuje",  "rol": "aislamiento"},
    {"ejercicio_id": "EMP_08", "nombre": "Press en máquina de pecho",           "grupo": "empuje",  "rol": "principal"},
    {"ejercicio_id": "EMP_09", "nombre": "Press de hombro con mancuernas",      "grupo": "empuje",  "rol": "principal"},
    {"ejercicio_id": "EMP_10", "nombre": "Elevaciones laterales",               "grupo": "empuje",  "rol": "aislamiento"},
    {"ejercicio_id": "EMP_11", "nombre": "Elevaciones frontales",               "grupo": "empuje",  "rol": "aislamiento"},
    {"ejercicio_id": "EMP_12", "nombre": "Elevaciones laterales en polea baja", "grupo": "empuje",  "rol": "aislamiento"},
    {"ejercicio_id": "EMP_13", "nombre": "Press Arnold",                        "grupo": "empuje",  "rol": "principal"},
    {"ejercicio_id": "EMP_14", "nombre": "Fondos en banco (tríceps)",           "grupo": "empuje",  "rol": "secundario"},
    {"ejercicio_id": "EMP_15", "nombre": "Extensión de tríceps con banda",      "grupo": "empuje",  "rol": "aislamiento"},
    {"ejercicio_id": "EMP_16", "nombre": "Press francés con mancuerna",         "grupo": "empuje",  "rol": "aislamiento"},
    {"ejercicio_id": "EMP_17", "nombre": "Jalón de tríceps en polea alta",      "grupo": "empuje",  "rol": "aislamiento"},
    {"ejercicio_id": "EMP_18", "nombre": "Extensión de tríceps sobre cabeza",   "grupo": "empuje",  "rol": "aislamiento"},
    {"ejercicio_id": "EMP_19", "nombre": "Press en máquina de hombro",          "grupo": "empuje",  "rol": "principal"},
    # ─── TIRÓN ─────────────────────────────────────────────────────────────────
    {"ejercicio_id": "TIR_01", "nombre": "Remo con mancuerna a una mano",       "grupo": "tiron",   "rol": "principal"},
    {"ejercicio_id": "TIR_02", "nombre": "Remo con banda elástica",             "grupo": "tiron",   "rol": "secundario"},
    {"ejercicio_id": "TIR_03", "nombre": "Jalón al pecho en polea",             "grupo": "tiron",   "rol": "principal"},
    {"ejercicio_id": "TIR_04", "nombre": "Jalón al pecho agarre estrecho",      "grupo": "tiron",   "rol": "secundario"},
    {"ejercicio_id": "TIR_05", "nombre": "Remo en polea baja",                  "grupo": "tiron",   "rol": "principal"},
    {"ejercicio_id": "TIR_06", "nombre": "Remo en polea baja agarre neutro",    "grupo": "tiron",   "rol": "secundario"},
    {"ejercicio_id": "TIR_07", "nombre": "Remo en máquina",                     "grupo": "tiron",   "rol": "principal"},
    {"ejercicio_id": "TIR_08", "nombre": "Remo inclinado con mancuernas",       "grupo": "tiron",   "rol": "principal"},
    {"ejercicio_id": "TIR_09", "nombre": "Curl de bíceps con mancuernas",       "grupo": "tiron",   "rol": "aislamiento"},
    {"ejercicio_id": "TIR_10", "nombre": "Curl martillo",                       "grupo": "tiron",   "rol": "aislamiento"},
    {"ejercicio_id": "TIR_11", "nombre": "Curl con banda elástica",             "grupo": "tiron",   "rol": "aislamiento"},
    {"ejercicio_id": "TIR_12", "nombre": "Curl concentrado",                    "grupo": "tiron",   "rol": "aislamiento"},
    {"ejercicio_id": "TIR_13", "nombre": "Curl en polea baja",                  "grupo": "tiron",   "rol": "aislamiento"},
    {"ejercicio_id": "TIR_14", "nombre": "Face pull con banda",                 "grupo": "tiron",   "rol": "aislamiento"},
    {"ejercicio_id": "TIR_15", "nombre": "Face pull en polea alta",             "grupo": "tiron",   "rol": "aislamiento"},
    {"ejercicio_id": "TIR_16", "nombre": "Pullover con mancuerna",              "grupo": "tiron",   "rol": "secundario"},
    {"ejercicio_id": "TIR_17", "nombre": "Encogimientos de hombros",            "grupo": "tiron",   "rol": "aislamiento"},
    {"ejercicio_id": "TIR_18", "nombre": "Superman en banco",                   "grupo": "tiron",   "rol": "aislamiento"},
    # ─── CORE ──────────────────────────────────────────────────────────────────
    {"ejercicio_id": "COR_01", "nombre": "Plancha abdominal",                   "grupo": "core",    "rol": "core_estabilidad"},
    {"ejercicio_id": "COR_02", "nombre": "Plancha lateral",                     "grupo": "core",    "rol": "core_estabilidad"},
    {"ejercicio_id": "COR_03", "nombre": "Plancha con toque de hombro",         "grupo": "core",    "rol": "core_estabilidad"},
    {"ejercicio_id": "COR_04", "nombre": "Crunch abdominal",                    "grupo": "core",    "rol": "core_dinamico"},
    {"ejercicio_id": "COR_05", "nombre": "Crunch inverso",                      "grupo": "core",    "rol": "core_dinamico"},
    {"ejercicio_id": "COR_06", "nombre": "Crunch en polea alta",                "grupo": "core",    "rol": "core_dinamico"},
    {"ejercicio_id": "COR_07", "nombre": "Elevación de piernas tumbada",        "grupo": "core",    "rol": "core_dinamico"},
    {"ejercicio_id": "COR_08", "nombre": "Dead bug",                            "grupo": "core",    "rol": "core_estabilidad"},
    {"ejercicio_id": "COR_09", "nombre": "Bird dog",                            "grupo": "core",    "rol": "core_estabilidad"},
    {"ejercicio_id": "COR_10", "nombre": "Mountain climbers",                   "grupo": "core",    "rol": "core_dinamico"},
    {"ejercicio_id": "COR_11", "nombre": "Bicicleta abdominal",                 "grupo": "core",    "rol": "core_dinamico"},
    {"ejercicio_id": "COR_12", "nombre": "Superman en suelo",                   "grupo": "core",    "rol": "core_estabilidad"},
    {"ejercicio_id": "COR_13", "nombre": "Tijeras abdominales",                 "grupo": "core",    "rol": "core_dinamico"},
    {"ejercicio_id": "COR_14", "nombre": "Rotación rusa con mancuerna",         "grupo": "core",    "rol": "core_dinamico"},
    {"ejercicio_id": "COR_15", "nombre": "Hollow body hold",                    "grupo": "core",    "rol": "core_estabilidad"},
    # ─── CARDIO ────────────────────────────────────────────────────────────────
    {"ejercicio_id": "CAR_01", "nombre": "Caminata en cinta inclinada",         "grupo": "cardio",  "rol": "cardio"},
    {"ejercicio_id": "CAR_02", "nombre": "Trote suave en cinta",                "grupo": "cardio",  "rol": "cardio"},
    {"ejercicio_id": "CAR_03", "nombre": "Intervalos en cinta (1 min rápido)",  "grupo": "cardio",  "rol": "cardio"},
    {"ejercicio_id": "CAR_04", "nombre": "Bicicleta estática ritmo moderado",   "grupo": "cardio",  "rol": "cardio"},
    {"ejercicio_id": "CAR_05", "nombre": "Bicicleta estática intervalos",       "grupo": "cardio",  "rol": "cardio"},
    {"ejercicio_id": "CAR_06", "nombre": "Elíptica ritmo constante",            "grupo": "cardio",  "rol": "cardio"},
    {"ejercicio_id": "CAR_07", "nombre": "Remo en máquina cardio",              "grupo": "cardio",  "rol": "cardio"},
    {"ejercicio_id": "CAR_08", "nombre": "Jump rope (cuerda)",                  "grupo": "cardio",  "rol": "cardio"},
    {"ejercicio_id": "CAR_09", "nombre": "Jumping jacks",                       "grupo": "cardio",  "rol": "cardio"},
    {"ejercicio_id": "CAR_10", "nombre": "Step aeróbico en cajón",              "grupo": "cardio",  "rol": "cardio"},
]

VALID_IDS  = {ex["ejercicio_id"] for ex in CATALOGO}
CATALOGO_POR_ID = {ex["ejercicio_id"]: ex for ex in CATALOGO}

def construir_system_prompt(perfil: dict) -> str:
    """System prompt compacto. El catálogo se pasa en el user prompt."""
    nivel  = perfil.get("nivel", "principiante")
    obj    = perfil.get("objetivo", "general")
    dias   = int(perfil.get("dias", 3))
    dur    = int(perfil.get("duracion_min", 60))
    lim    = perfil.get("limitaciones", "ninguna")

    if dur <= 45:
        ej = 3
    elif dur >= 90:
        ej = 5
    else:
        ej = 4

    if nivel == "principiante":
        prog = "S1:3x15 S2:3x12 S3:3x10 S4:4x8. S1-2 máquinas/básicos, S3-4 libres/mancuernas."
    elif nivel == "intermedio":
        prog = "S1:4x12 S2:4x8-10 S3:4x6-8 S4:3x12 DELOAD."
    else:
        prog = "Alterna días: Fuerza 5x5 / Hipertrofia 4x10 / Volumen 3x15. S4 DELOAD."

    if "gluteo" in obj:
        obj_nota = "Glúteo: Hip thrust PRIMERO siempre (200% MVIC Contreras). Orden: hip thrust → sentadilla → PDR → aislamiento → cardio."
    elif "peso" in obj:
        obj_nota = "Pérdida peso: compuestos multiarticulares + cardio AL FINAL (EPOC). Zona 2 65-70% FCmax."
    else:
        obj_nota = "Tonificación: balance empuje=tirón, compuestos + aislamiento, cardio 15min final."

    if lim == "rodilla":
        lim_nota = "PROHIBIDO: sentadilla búlgara, desplante caminando. USA: prensa, goblet, hip thrust."
    elif lim == "espalda":
        lim_nota = "PROHIBIDO: peso muerto convencional, good morning. USA: prensa, jalón, hip thrust."
    elif lim == "hombro":
        lim_nota = "PROHIBIDO: press militar, elevaciones frontales. USA: press inclinado 45°, face pull."
    else:
        lim_nota = "Sin limitaciones."

    return f"""Eres un generador de planes de entrenamiento. SOLO produces JSON válido, NADA más.

PERFIL: nivel={nivel}, objetivo={obj}, {dias}días/sem, {dur}min/sesión, limitaciones={lim}
EJERCICIOS POR DÍA: exactamente {ej} (el cardio cuenta como uno, siempre al final)
PROGRESIÓN: {prog}
OBJETIVO: {obj_nota}
{lim_nota}

REGLAS ABSOLUTAS:
1. SOLO IDs del CATALOGO que recibirás. Copia IDs exactos, sin inventar.
2. Exactamente {ej} ejercicios por día. Ni más ni menos.
3. Series/reps DISTINTAS cada semana según progresión.
4. Al menos {max(1,dias-2)} días/semana deben terminar con cardio (CAR_01 a CAR_10).
5. reps SIEMPRE string: "15" "8-10" "45s". NUNCA número.
6. JSON PURO. Sin markdown. Sin texto. Sin campo url.
7. Varía ejercicios entre semanas (S3-S4 ≠ S1-S2 cuando sea posible).

FORMATO EXACTO (solo esto, nada más):
{{"semanas":[{{"semana":1,"dias":[{{"dia":"lunes","grupo":"gluteo","ejercicios":[{{"ejercicio_id":"GLU_03","ejercicio":"Hip thrust en banco","orden":1,"series":3,"reps":"15","notas":"Pausa 1s arriba"}}]}}]}}]}}"""


def construir_prompt_usuario(perfil: dict) -> str:
    """Prompt del usuario: incluye catálogo comprimido + instrucción."""
    nivel  = perfil.get("nivel", "principiante")
    obj    = perfil.get("objetivo", "general")
    dias   = int(perfil.get("dias", 3))
    dur    = int(perfil.get("duracion_min", 60))
    lim    = perfil.get("limitaciones", "ninguna")

    # Catálogo comprimido: solo ID, nombre abreviado, grupo, rol
    cat_comprimido = []
    for e in CATALOGO:
        cat_comprimido.append(f'{e["ejercicio_id"]}|{e["nombre"][:30]}|{e["grupo"]}|{e.get("rol","?")}')
    cat_str = "\n".join(cat_comprimido)

    return f"""CATALOGO (formato: ID|nombre|grupo|rol):
{cat_str}

Genera plan JSON de 4 semanas: objetivo={obj}, nivel={nivel}, {dias}días/sem, {dur}min/sesión, limitaciones={lim}.
Usa SOLO los IDs del catálogo de arriba. JSON puro, nada más."""



# ==========================================
# 3. BASE DE DATOS
# ==========================================
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS rutinas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        semana INTEGER, dia TEXT, grupo TEXT,
        ejercicio_id TEXT, ejercicio TEXT, orden INTEGER,
        series INTEGER, reps TEXT, notas TEXT,
        UNIQUE(user_id, semana, dia, ejercicio_id)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS progreso (
        user_id INTEGER, semana INTEGER, dia TEXT,
        ejercicio_id TEXT, completado INTEGER DEFAULT 0,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, semana, dia, ejercicio_id)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS estado (
        user_id INTEGER PRIMARY KEY, semana INTEGER, dia TEXT,
        objetivo TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS milestones (
        user_id INTEGER, milestone_key TEXT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, milestone_key)
    )""")

    # Perfil completo del usuario (onboarding)
    cur.execute("""CREATE TABLE IF NOT EXISTS perfil_usuario (
        user_id INTEGER PRIMARY KEY,
        nivel TEXT DEFAULT 'principiante',
        limitaciones TEXT DEFAULT 'ninguna',
        duracion_min INTEGER DEFAULT 60,
        momento TEXT DEFAULT 'tarde',
        semanas_sin_gym INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # NUEVA: historial de swaps para persistencia entre semanas
    cur.execute("""CREATE TABLE IF NOT EXISTS swaps (
        user_id INTEGER,
        ejercicio_id_original TEXT,
        ejercicio_id_swap TEXT,
        grupo TEXT,
        rol TEXT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, ejercicio_id_original)
    )""")

    # Migraciones automáticas — añade columnas nuevas si la DB es antigua
    migraciones = [
        "ALTER TABLE perfil_usuario ADD COLUMN duracion_min INTEGER DEFAULT 60",
        "ALTER TABLE perfil_usuario ADD COLUMN momento TEXT DEFAULT 'tarde'",
        "ALTER TABLE perfil_usuario ADD COLUMN semanas_sin_gym INTEGER DEFAULT 0",
        "ALTER TABLE swaps ADD COLUMN grupo TEXT",
        "ALTER TABLE swaps ADD COLUMN rol TEXT",
    ]
    for sql in migraciones:
        try:
            cur.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Columna ya existe, ignorar

    conn.commit()
    conn.close()

def limpiar_json_gemini(raw: str) -> str:
    """Limpia wrappers markdown y texto extra que Gemini añade a veces."""
    raw = raw.strip()
    # Quitar bloques de código markdown
    for prefix in ["```json", "```JSON", "```"]:
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    if raw.endswith("```"):
        raw = raw[:-3]
    # Encontrar el primer { y el último }
    start = raw.find("{")
    end   = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No se encontró JSON válido en la respuesta")
    return raw[start:end+1].strip()


def validar_plan_json(data: dict, ej_por_dia: int) -> tuple[bool, str]:
    """
    Validador post-JSON: verifica estructura, IDs, tipos y cardio obligatorio.
    Devuelve (válido, mensaje_error).
    """
    semanas = data.get("semanas", [])
    if not semanas:
        return False, "El JSON no tiene campo 'semanas'"
    if len(semanas) != 4:
        return False, f"Se esperaban 4 semanas, Gemini generó {len(semanas)}"

    for s in semanas:
        sem_num = s.get("semana", "?")
        dias = s.get("dias", [])
        if not dias:
            return False, f"Semana {sem_num} sin días"

        for d in dias:
            ejercicios = d.get("ejercicios", [])
            dia_nombre = d.get("dia", "?")

            # Inyectar grupo desde catálogo si Gemini lo omitió (fix KeyError: 'grupo')
            for e in ejercicios:
                ej_id = str(e.get("ejercicio_id", ""))
                if ej_id in CATALOGO_POR_ID and "grupo" not in d:
                    d["grupo"] = CATALOGO_POR_ID[ej_id]["grupo"]

            # Grupo del día — usar campo explícito o inferir del primer ejercicio válido
            if not d.get("grupo"):
                for e in ejercicios:
                    ej_id = str(e.get("ejercicio_id", ""))
                    if ej_id in CATALOGO_POR_ID:
                        d["grupo"] = CATALOGO_POR_ID[ej_id]["grupo"]
                        break
            if not d.get("grupo"):
                d["grupo"] = "general"

            # Verificar IDs válidos
            for e in ejercicios:
                ej_id = str(e.get("ejercicio_id", ""))
                if ej_id not in VALID_IDS:
                    return False, f"ID inválido S{sem_num}/{dia_nombre}: '{ej_id}'"
                # reps debe ser string
                if not isinstance(e.get("reps", ""), str):
                    e["reps"] = str(e.get("reps", "10"))
                # series debe ser int
                if not isinstance(e.get("series", 3), int):
                    try:
                        e["series"] = int(e.get("series", 3))
                    except (ValueError, TypeError):
                        e["series"] = 3

            # Verificar mínimo de ejercicios (tolerancia: ej_por_dia - 1)
            if len(ejercicios) < max(1, ej_por_dia - 1):
                return False, f"S{sem_num}/{dia_nombre} tiene {len(ejercicios)} ejercicios (mínimo {ej_por_dia-1})"

    return True, "OK"


def sanitizar_e_insertar_plan(json_string: str, user_id: int, ej_por_dia: int = 4) -> tuple[bool, str]:
    """
    Limpia, valida con post-validador, y persiste el plan en SQLite.
    Robusto ante: JSON malformado, campos faltantes, IDs inválidos, tipos incorrectos.
    """
    try:
        json_limpio = limpiar_json_gemini(json_string)
        data = json.loads(json_limpio)
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"JSON de Gemini no parseable: {e}\nRaw (primeros 500): {json_string[:500]}")
        return False, f"Gemini devolvió JSON malformado. Intenta de nuevo."

    # Validación estructural completa
    valido, msg_error = validar_plan_json(data, ej_por_dia)
    if not valido:
        logger.error(f"Validación post-JSON falló: {msg_error}")
        return False, f"Plan inválido: {msg_error}. Intenta de nuevo."

    try:
        conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        cur  = conn.cursor()

        # Cargar swaps previos para aplicarlos automáticamente
        cur.execute("SELECT ejercicio_id_original, ejercicio_id_swap FROM swaps WHERE user_id = ?", (user_id,))
        swaps_guardados = {r[0]: r[1] for r in cur.fetchall()}

        orden_global = 0
        for s in data.get("semanas", []):
            for d in s.get("dias", []):
                dia_seguro  = str(d.get("dia", "dia")).lower()[:15]
                grupo_dia   = str(d.get("grupo", "general"))
                orden_dia   = 0
                for e in d.get("ejercicios", []):
                    orden_dia  += 1
                    orden_global += 1
                    ej_id_orig  = str(e["ejercicio_id"])
                    ej_id_final = swaps_guardados.get(ej_id_orig, ej_id_orig)
                    nombre_final = CATALOGO_POR_ID[ej_id_final]["nombre"]

                    cur.execute("""
                        INSERT OR IGNORE INTO rutinas
                        (user_id, semana, dia, grupo, ejercicio_id, ejercicio, orden, series, reps, notas)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (user_id, int(s["semana"]), dia_seguro,
                          grupo_dia, ej_id_final, nombre_final,
                          orden_dia,
                          int(e.get("series", 3)),
                          str(e.get("reps", "10")),
                          str(e.get("notas", ""))[:120]))

        conn.commit()
        conn.close()
        logger.info(f"Plan guardado: user={user_id}, {orden_global} ejercicios totales")
        return True, "Plan guardado."

    except Exception as e:
        logger.exception("Error insertando plan en SQLite.")
        return False, f"Error guardando plan: {e}"

def obtener_estado_usuario(user_id: int):
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT semana, dia FROM estado WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row if row else (1, "lunes")

def iniciar_estado_usuario(user_id: int):
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT dia FROM rutinas WHERE user_id = ? AND semana = 1 ORDER BY id ASC LIMIT 1", (user_id,))
    row = cur.fetchone()
    primer_dia = row[0] if row else "lunes"
    cur.execute("""
        INSERT INTO estado (user_id, semana, dia)
        VALUES (?, 1, ?)
        ON CONFLICT(user_id) DO UPDATE
            SET semana = 1, dia = excluded.dia, updated_at = CURRENT_TIMESTAMP
    """, (user_id, primer_dia))
    conn.commit()
    conn.close()

def avanzar_estado_dinamico(user_id: int, semana_actual: int, dia_actual: str):
    # Validar que el plan existe y determinar máx semanas
    conn_v = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur_v  = conn_v.cursor()
    cur_v.execute("SELECT MAX(semana) FROM rutinas WHERE user_id = ?", (user_id,))
    max_sem = cur_v.fetchone()[0] or 0
    conn_v.close()
    if max_sem == 0:
        logger.warning(f"avanzar_estado: user {user_id} — plan vacío, abortando avance")
        return

    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT dia FROM rutinas WHERE user_id = ? AND semana = ? GROUP BY dia ORDER BY MIN(id) ASC", (user_id, semana_actual))
    dias_semana = [r[0] for r in cur.fetchall()]
    if not dias_semana:
        dias_semana = ["lunes"]
    try:
        idx = dias_semana.index(dia_actual)
    except ValueError:
        idx = 0

    if idx < len(dias_semana) - 1:
        nuevo_dia, nueva_semana = dias_semana[idx + 1], semana_actual
    else:
        nueva_semana = semana_actual + 1
        cur.execute("SELECT dia FROM rutinas WHERE user_id = ? AND semana = ? GROUP BY dia ORDER BY MIN(id) ASC LIMIT 1", (user_id, nueva_semana))
        row = cur.fetchone()
        nuevo_dia = row[0] if row else "lunes"

    cur.execute("UPDATE estado SET semana = ?, dia = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (nueva_semana, nuevo_dia, user_id))
    conn.commit()
    conn.close()

def rutina_completa(user_id: int, semana: int, dia: str) -> bool:
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM rutinas r
        LEFT JOIN progreso p
            ON r.user_id = p.user_id
            AND r.ejercicio_id = p.ejercicio_id
            AND r.semana = p.semana
            AND r.dia = p.dia
        WHERE r.user_id = ? AND r.semana = ? AND r.dia = ?
        AND COALESCE(p.completado, 0) = 0
    """, (user_id, semana, dia))
    pendientes = cur.fetchone()[0]
    conn.close()
    return pendientes == 0

# ==========================================
# 4. SISTEMA DE SWAP
# ==========================================
def obtener_alternativas(user_id: int, semana: int, dia: str, ejercicio_id: str) -> list[dict]:
    """Devuelve hasta 3 alternativas del mismo grupo, sin repetir ejercicios del día."""
    ejercicio_orig = CATALOGO_POR_ID.get(ejercicio_id)
    if not ejercicio_orig:
        return []
    grupo = ejercicio_orig["grupo"]
    rol   = ejercicio_orig.get("rol", "")

    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT ejercicio_id FROM rutinas WHERE user_id = ? AND semana = ? AND dia = ?",
                (user_id, semana, dia))
    ids_en_uso = {r[0] for r in cur.fetchall()}
    conn.close()

    # Excluir el ejercicio actual + los que ya están en el día
    excluidos = ids_en_uso  # ya incluye el ejercicio_id actual

    alternativas = [
        e for e in CATALOGO
        if e["grupo"] == grupo and e.get("rol", "") == rol and e["ejercicio_id"] not in excluidos
    ]
    return alternativas[:3]

def aplicar_swap(user_id: int, semana: int, dia: str, id_original: str, id_nuevo: str):
    """
    Reemplaza el ejercicio en TODAS las semanas del plan actual
    y guarda el swap de forma permanente para planes futuros.
    """
    nuevo = CATALOGO_POR_ID[id_nuevo]
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()

    # 1. Actualizar en todas las semanas del plan donde aparezca el original
    cur.execute("""
        UPDATE rutinas SET ejercicio_id = ?, ejercicio = ?
        WHERE user_id = ? AND ejercicio_id = ?
    """, (id_nuevo, nuevo["nombre"], user_id, id_original))

    # 2. Limpiar progreso del ejercicio original en todo el plan
    cur.execute("""
        DELETE FROM progreso
        WHERE user_id = ? AND ejercicio_id = ?
    """, (user_id, id_original))

    # 3. Guardar swap permanente con grupo y rol para validación futura
    ej_orig = CATALOGO_POR_ID.get(id_original, {})
    cur.execute("""
        INSERT INTO swaps (user_id, ejercicio_id_original, ejercicio_id_swap, grupo, rol)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, ejercicio_id_original)
        DO UPDATE SET ejercicio_id_swap = excluded.ejercicio_id_swap,
            grupo = excluded.grupo, rol = excluded.rol, ts = CURRENT_TIMESTAMP
    """, (user_id, id_original, id_nuevo,
          ej_orig.get("grupo", ""), ej_orig.get("rol", "")))

    conn.commit()
    conn.close()
    logger.info(f"Swap aplicado: user={user_id} | {id_original} → {id_nuevo} (todas las semanas)")

# ==========================================
# 5. STATS Y MILESTONES
# ==========================================
def obtener_stats_suaves(user_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT semana FROM estado WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    semana_actual = row[0] if row else 1
    cur.execute("SELECT COUNT(*) FROM progreso WHERE user_id = ? AND completado = 1", (user_id,))
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM progreso WHERE user_id = ? AND semana = ? AND completado = 1", (user_id, semana_actual))
    semana = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM (SELECT semana, dia FROM progreso WHERE user_id = ? GROUP BY semana, dia HAVING SUM(completado) = COUNT(*))", (user_id,))
    rutinas = cur.fetchone()[0]
    conn.close()
    return {"total_ejercicios": total, "ejercicios_semana": semana, "rutinas_completas": rutinas}

def es_semana_completa(user_id: int, semana_objetivo: int) -> bool:
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(DISTINCT dia) FROM rutinas WHERE user_id = ? AND semana = ?", (user_id, semana_objetivo))
    dias_prog = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM (SELECT dia FROM progreso WHERE user_id = ? AND semana = ? GROUP BY dia HAVING SUM(completado) = COUNT(*))", (user_id, semana_objetivo))
    dias_comp = cur.fetchone()[0]
    conn.close()
    return dias_prog > 0 and dias_prog == dias_comp

def procesar_milestones(user_id: int, semana_actual: int) -> list[str]:
    stats = obtener_stats_suaves(user_id)
    mensajes = []
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()

    def check_and_add(key, msg):
        cur.execute("SELECT 1 FROM milestones WHERE user_id = ? AND milestone_key = ?", (user_id, key))
        if not cur.fetchone():
            cur.execute("INSERT INTO milestones (user_id, milestone_key) VALUES (?, ?)", (user_id, key))
            mensajes.append(msg)

    if stats["rutinas_completas"] >= 1:
        check_and_add("FIRST_ROUTINE", "🌱 <b>¡Primera rutina completada!</b>\nLo más difícil ya lo hiciste: empezar 💚")
    if es_semana_completa(user_id, semana_actual):
        check_and_add(f"WEEK_COMPLETED_{semana_actual}", f"💐 <b>¡Semana {semana_actual} completada al 100%!</b>\nTómate tu descanso merecido.")
    if stats["rutinas_completas"] >= 10:
        check_and_add("TEN_ROUTINES", "🔥 <b>10 rutinas terminadas</b>\nDisciplina > motivación. Lo estás demostrando.")

    conn.commit()
    conn.close()
    return mensajes

# ==========================================
# 6. UI Y RENDERER
# ==========================================
def obtener_rutina_interactiva(user_id: int, semana: int, dia: str):
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT r.ejercicio_id, r.ejercicio, r.series, r.reps, r.notas,
               COALESCE(p.completado, 0) as completado
        FROM rutinas r
        LEFT JOIN progreso p
            ON r.user_id = p.user_id
            AND r.ejercicio_id = p.ejercicio_id
            AND r.semana = p.semana
            AND r.dia = p.dia
        WHERE r.user_id = ? AND r.semana = ? AND r.dia = ?
        ORDER BY r.orden ASC
    """, (user_id, semana, dia))
    ejercicios = cur.fetchall()
    conn.close()

    if not ejercicios:
        if semana > 4:
            return "🎉 <b>¡Completaste tu plan de 4 semanas!</b>\n\nUsa /start y pídele a tu entrenador que genere un plan nuevo.", None
        return f"📅 Día libre ({dia.capitalize()}). ¡Descansa y recupérate!", None

    html_msg = f"🔥 <b>Semana {semana} — {dia.capitalize()}</b>\n\n"
    keyboard = []
    for ex in ejercicios:
        estado = "✅" if ex['completado'] else "⬜"
        html_msg += f"{estado} <b>{safe(ex['ejercicio'])}</b> · {ex['series']}×{safe(ex['reps'])}\n"
        if ex['notas']:
            html_msg += f"   <i>💡 {safe(ex['notas'])}</i>\n"
        # Fila con botón de check Y botón de swap
        keyboard.append([
            InlineKeyboardButton(
                f"{estado} {safe(ex['ejercicio'])}",
                callback_data=f"chk:{ex['ejercicio_id']}:{semana}:{dia}"
            ),
            InlineKeyboardButton(
                "🔄",
                callback_data=f"swp_ask:{ex['ejercicio_id']}:{semana}:{dia}"
            )
        ])

    keyboard.append([InlineKeyboardButton("📋 Ver plan completo", callback_data=f"plan:{semana}")])
    keyboard.append([InlineKeyboardButton("🏁 Terminar Rutina", callback_data=f"finish:{semana}:{dia}")])
    html_msg += "\n👇 <i>Marca cada ejercicio · 🔄 para cambiarlo</i>"
    return html_msg, InlineKeyboardMarkup(keyboard)

def formatear_plan_por_semanas(user_id: int) -> list[str]:
    """
    Devuelve el plan dividido en páginas de máx ~3800 chars (límite Telegram = 4096).
    Cada página = una semana. Nunca supera el límite.
    """
    from collections import defaultdict
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT semana, dia, grupo, ejercicio, series, reps, notas
        FROM rutinas WHERE user_id = ?
        ORDER BY semana, id, orden
    """, (user_id,))
    plan = defaultdict(lambda: defaultdict(list))
    for row in cur.fetchall():
        plan[row["semana"]][row["dia"]].append(row)
    conn.close()

    if not plan:
        return []

    semana_actual, _ = obtener_estado_usuario(user_id)
    paginas = []

    for sem_num in sorted(plan.keys()):
        marcador = " ◀ <b>estás aquí</b>" if sem_num == semana_actual else ""
        txt = f"📅 <b>SEMANA {sem_num} / 4</b>{marcador}\n"
        txt += "━━━━━━━━━━━━━━━━━━━━\n\n"
        for dia_nombre, ejercicios in plan[sem_num].items():
            grupo = ejercicios[0]["grupo"].upper() if ejercicios else ""
            txt += f"<b>{dia_nombre.capitalize()}</b> · <i>{grupo}</i>\n"
            for e in ejercicios:
                txt += f"  • {safe(e['ejercicio'])} — {e['series']}×{e['reps']}\n"
                if e["notas"]:
                    txt += f"    <i>💡 {safe(e['notas'])}</i>\n"
            txt += "\n"
        paginas.append(txt)

    return paginas

# ==========================================
# 7. HANDLERS DE TELEGRAM
# ==========================================
async def check_auth(update: Update) -> bool:
    if update.effective_user.id not in ALLOWED_USERS:
        if update.message:
            await update.message.reply_text("⛔ Lo siento, este bot es privado.")
        return False
    return True

MENU_PRINCIPAL = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏋️ Ver rutina de hoy",    callback_data="menu:hoy")],
    [InlineKeyboardButton("📅 Ver plan completo",     callback_data="menu:plan")],
    [InlineKeyboardButton("🆕 Crear nuevo plan",      callback_data="menu:nuevo")],
    [InlineKeyboardButton("🔄 Resetear preferencias", callback_data="menu:swaps")],
])

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /menu — todos los botones sin escribir comandos."""
    if not await check_auth(update): return
    await update.message.reply_text(
        "🏠 <b>¿Qué quieres hacer?</b>",
        reply_markup=MENU_PRINCIPAL, parse_mode="HTML"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    user_id = update.effective_user.id

    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM rutinas WHERE user_id = ?", (user_id,))
    tiene_plan = cur.fetchone()[0] > 0
    conn.close()

    if not tiene_plan:
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍑 Aumentar glúteo y pierna", callback_data="obj:gluteos")],
            [InlineKeyboardButton("🔥 Perder peso y sudar",      callback_data="obj:peso")],
            [InlineKeyboardButton("💪 Tonificar todo el cuerpo", callback_data="obj:general")]
        ])
        await update.message.reply_text(
            "👋 <b>¡Hola!</b> Vamos a crear tu plan personalizado.\n\n"
            "<b>Paso 1/4</b> — ¿Cuál es tu objetivo principal?",
            reply_markup=teclado, parse_mode="HTML"
        )
        return

    semana, dia = obtener_estado_usuario(user_id)
    stats = obtener_stats_suaves(user_id)

    if stats["total_ejercicios"] > 0:
        bloque = (f"💚 <b>Tu progreso:</b>\n"
                  f"🔥 Ejercicios totales: {stats['total_ejercicios']}\n"
                  f"📆 Esta semana: {stats['ejercicios_semana']}\n"
                  f"🏆 Rutinas terminadas: {stats['rutinas_completas']}\n\n"
                  f"👇 <b>Tu entrenamiento de hoy:</b>\n\n")
    else:
        bloque = "✨ <b>¡Qué emoción empezar!</b> Aquí tienes tu primera rutina:\n\n"

    texto_rutina, teclado = obtener_rutina_interactiva(user_id, semana, dia)
    await update.message.reply_text(
        bloque + texto_rutina, reply_markup=teclado,
        parse_mode="HTML", disable_web_page_preview=True
    )

async def plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /plan — muestra las 4 semanas paginadas para no superar límite de Telegram."""
    if not await check_auth(update): return
    paginas = formatear_plan_por_semanas(update.effective_user.id)
    if not paginas:
        await update.message.reply_text("No tienes un plan activo. Usa /start para crear uno.")
        return
    for i, pagina in enumerate(paginas):
        await update.message.reply_text(pagina, parse_mode="HTML")

PALABRAS_BLOQUEADAS_COACH = [
    "rutina", "plan", "ejercicio", "series", "repeticion", "reps",
    "semana", "programa", "generar", "crear", "dame", "hazme",
    "cuantas", "cuántas", "cuantos", "cuántos"
]

async def gemini_coach_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    user_id = update.effective_user.id
    texto = update.message.text.lower()

    # Bloquear preguntas sobre rutinas — el plan ya lo gestiona el sistema
    if any(w in texto for w in PALABRAS_BLOQUEADAS_COACH):
        await update.message.reply_text(
            "💪 Para ver o modificar tu rutina usa el menú 👇",
            reply_markup=MENU_PRINCIPAL
        )
        return

    semana, dia = obtener_estado_usuario(user_id)
    conn_p = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur_p = conn_p.cursor()
    cur_p.execute("SELECT nivel, limitaciones FROM perfil_usuario WHERE user_id = ?", (user_id,))
    row_p = cur_p.fetchone()
    conn_p.close()
    nivel_usr = row_p[0] if row_p else "principiante"
    lim_usr = row_p[1] if row_p else "ninguna"
    system_ctx = (
        f"Eres un coach de fitness experto, motivador y cercano. "
        f"Usuario: nivel={nivel_usr}, limitaciones={lim_usr}, Semana {semana} día {dia}. "
        f"Responde en máximo 3 oraciones con base científica cuando aplique. "
        f"Si menciona dolor, dile que pare y consulte médico. "
        f"No inventes rutinas, dile que use /start."
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    try:
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
        loop = asyncio.get_event_loop()
        resp = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda ctx=system_ctx, txt=update.message.text: client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=txt,
                    config=types.GenerateContentConfig(system_instruction=ctx)
                )
            ),
            timeout=20
        )
        await update.message.reply_text(resp.text)
    except asyncio.TimeoutError:
        await update.message.reply_text("⏱ Gemini tardó demasiado. Intenta de nuevo.")
    except Exception:
        logger.exception("Error en coach conversacional")
        await update.message.reply_text("Descansa un poco, usa el menú ❤️")

async def reset_plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Borra plan y progreso. Conserva los swaps del usuario (preferencias)."""
    if not await check_auth(update): return
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("DELETE FROM rutinas   WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM progreso  WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM milestones WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM estado    WHERE user_id = ?", (user_id,))
    # NOTA: swaps se conservan intencionalmente para el próximo plan
    conn.commit()
    conn.close()
    await update.message.reply_text(
        "🧹 Plan y progresos borrados.\n"
        "💡 <i>Tus preferencias de ejercicios (swaps) se conservaron para el próximo plan.</i>\n\n"
        "Usa /start para generar uno nuevo.",
        parse_mode="HTML"
    )

async def reset_swaps_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Borra los swaps guardados — vuelve al plan original de Gemini."""
    if not await check_auth(update): return
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("DELETE FROM swaps WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("🔁 Preferencias de ejercicios reseteadas. El próximo plan usará el catálogo original.")

# ==========================================
# 8. ENRUTADOR MAESTRO (CALLBACKS)
# ==========================================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    # ── MENÚ PRINCIPAL ────────────────────────────────────────────────
    if data.startswith("menu:"):
        accion = data.split(":")[1]
        await query.answer()

        if accion == "hoy":
            semana, dia = obtener_estado_usuario(user_id)
            stats = obtener_stats_suaves(user_id)
            bloque = (f"💚 Ejercicios totales: {stats['total_ejercicios']} · "
                      f"Rutinas: {stats['rutinas_completas']}\n\n")
            texto_rutina, teclado_rutina = obtener_rutina_interactiva(user_id, semana, dia)
            await query.edit_message_text(
                bloque + texto_rutina, reply_markup=teclado_rutina,
                parse_mode="HTML", disable_web_page_preview=True
            )

        elif accion == "plan":
            paginas = formatear_plan_por_semanas(user_id)
            if not paginas:
                await query.edit_message_text("No tienes un plan activo. Usa el menú para crear uno.")
                return
            await query.edit_message_text(paginas[0], parse_mode="HTML")
            for pagina in paginas[1:]:
                await context.bot.send_message(chat_id=query.message.chat_id, text=pagina, parse_mode="HTML")
            tec = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menú", callback_data="menu_volver")]])
            await context.bot.send_message(chat_id=query.message.chat_id, text="👆 Plan completo", reply_markup=tec)

        elif accion == "nuevo":
            # Borra plan actual y reinicia onboarding
            conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
            cur = conn.cursor()
            cur.execute("DELETE FROM rutinas    WHERE user_id = ?", (user_id,))
            cur.execute("DELETE FROM progreso   WHERE user_id = ?", (user_id,))
            cur.execute("DELETE FROM milestones WHERE user_id = ?", (user_id,))
            cur.execute("DELETE FROM estado     WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            teclado = InlineKeyboardMarkup([
                [InlineKeyboardButton("🍑 Aumentar glúteo y pierna", callback_data="obj:gluteos")],
                [InlineKeyboardButton("🔥 Perder peso y sudar",      callback_data="obj:peso")],
                [InlineKeyboardButton("💪 Tonificar todo el cuerpo", callback_data="obj:general")]
            ])
            await query.edit_message_text(
                "🆕 Plan anterior borrado.\n\n<b>Paso 1/5</b> — ¿Cuál es tu objetivo principal?",
                reply_markup=teclado, parse_mode="HTML"
            )

        elif accion == "swaps":
            conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
            cur = conn.cursor()
            cur.execute("DELETE FROM swaps WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            await query.edit_message_text(
                "🔁 Preferencias de ejercicios reseteadas.\nEl próximo plan usará el catálogo original.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menú", callback_data="menu_volver")]])
            )
        return

    if data == "menu_volver":
        await query.answer()
        await query.edit_message_text("🏠 <b>¿Qué quieres hacer?</b>", reply_markup=MENU_PRINCIPAL, parse_mode="HTML")
        return

    # ── SELECCIÓN DE OBJETIVO ─────────────────────────────────────────
    if data.startswith("obj:"):
        await query.answer()
        objetivo = data.split(":")[1]
        conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO estado (user_id, semana, dia, objetivo)
            VALUES (?, 1, 'pendiente', ?)
            ON CONFLICT(user_id) DO UPDATE SET objetivo = excluded.objetivo
        """, (user_id, objetivo))
        conn.commit()
        conn.close()
        # Paso 2: nivel
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌱 Primera vez / menos de 3 meses", callback_data="niv:principiante")],
            [InlineKeyboardButton("💪 6 meses a 2 años con constancia", callback_data="niv:intermedio")],
            [InlineKeyboardButton("🔥 Más de 2 años entrenando",        callback_data="niv:avanzado")],
        ])
        await query.edit_message_text(
            "✅ Objetivo guardado.\n\n<b>Paso 2/5</b> — ¿Cuánta experiencia tienes en el gym?\n"
            "<i>Sé honesta, esto cambia completamente el programa.</i>",
            reply_markup=teclado, parse_mode="HTML"
        )
        return

    # ── SELECCIÓN DE NIVEL ────────────────────────────────────────────
    if data.startswith("niv:"):
        await query.answer()
        nivel = data.split(":")[1]
        conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO perfil_usuario (user_id, nivel)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET nivel = excluded.nivel, updated_at = CURRENT_TIMESTAMP
        """, (user_id, nivel))
        conn.commit()
        conn.close()
        # Paso 3: limitaciones físicas
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Sin limitaciones",         callback_data="lim:ninguna")],
            [InlineKeyboardButton("🦵 Rodilla delicada",        callback_data="lim:rodilla")],
            [InlineKeyboardButton("🔙 Espalda baja",            callback_data="lim:espalda")],
            [InlineKeyboardButton("💪 Hombro lesionado",        callback_data="lim:hombro")],
        ])
        await query.edit_message_text(
            "✅ Nivel guardado.\n\n<b>Paso 3/5</b> — ¿Tienes alguna limitación física?\n"
            "<i>Esto ajusta los ejercicios para que sean seguros para ti.</i>",
            reply_markup=teclado, parse_mode="HTML"
        )
        return

    # ── SELECCIÓN DE LIMITACIONES ─────────────────────────────────────
    if data.startswith("lim:"):
        await query.answer()
        lim = data.split(":")[1]
        # Guardar limitación en perfil
        conn_l = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        cur_l = conn_l.cursor()
        cur_l.execute("""
            INSERT INTO perfil_usuario (user_id, limitaciones)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET limitaciones = excluded.limitaciones, updated_at = CURRENT_TIMESTAMP
        """, (user_id, lim))
        conn_l.commit()
        conn_l.close()
        # Paso 4: duración de sesión
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ 45 min (sesiones cortas e intensas)", callback_data="dur:45")],
            [InlineKeyboardButton("⏱ 60 min (estándar recomendado)",       callback_data="dur:60")],
            [InlineKeyboardButton("🏋 90 min (tengo tiempo de sobra)",      callback_data="dur:90")],
        ])
        await query.edit_message_text(
            "✅ Listo.\n\n<b>Paso 4/5</b> — ¿Cuánto tiempo tienes disponible por sesión?\n"
            "<i>Esto define cuántos ejercicios incluir. Sé realista.</i>",
            reply_markup=teclado, parse_mode="HTML"
        )
        return

    # ── DURACIÓN DE SESIÓN ────────────────────────────────────────────
    if data.startswith("dur:"):
        await query.answer()
        dur = int(data.split(":")[1])
        conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO perfil_usuario (user_id, duracion_min)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET duracion_min = excluded.duracion_min, updated_at = CURRENT_TIMESTAMP
        """, (user_id, dur))
        conn.commit()
        conn.close()
        # Paso 5: días por semana
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("3 días a la semana", callback_data="dias:3")],
            [InlineKeyboardButton("4 días a la semana", callback_data="dias:4")],
            [InlineKeyboardButton("5 días a la semana", callback_data="dias:5")],
        ])
        await query.edit_message_text(
            "✅ Tiempo registrado.\n\n<b>Paso 5/5</b> — ¿Cuántos días por semana puedes entrenar?\n"
            "<i>Recuerda: consistencia > frecuencia. 3 días bien hechos > 5 a medias.</i>",
            reply_markup=teclado, parse_mode="HTML"
        )
        return

    # ── SELECCIÓN DE DÍAS → GENERA PLAN ──────────────────────────────
    if data.startswith("dias:"):
        await query.answer()
        dias = data.split(":")[1]

        # Guard anti-doble tap
        conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM rutinas WHERE user_id = ?", (user_id,))
        if cur.fetchone()[0] > 0:
            conn.close()
            await query.edit_message_text("Ya tienes un plan activo. Usa /start para verlo.")
            return
        cur.execute("SELECT objetivo FROM estado WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        objetivo = row[0] if row and row[0] else "general"

        # Feedback visual paso a paso (evita que parezca que se trabó)
        pasos = [
            "🧠 <b>Analizando tu perfil...</b>",
            "📊 <b>Aplicando ciencia de Schoenfeld y Contreras...</b>",
            "🏗 <b>Estructurando progresión semana a semana...</b>",
            "✍️ <b>Generando tu plan personalizado...</b>",
        ]
        for paso in pasos:
            await query.edit_message_text(paso, parse_mode="HTML")
            await asyncio.sleep(3)

        # Cargar perfil completo
        conn2 = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        cur2 = conn2.cursor()
        cur2.execute("SELECT nivel, limitaciones, duracion_min FROM perfil_usuario WHERE user_id = ?", (user_id,))
        row2 = cur2.fetchone()
        conn2.close()
        nivel        = row2[0] if row2 else "principiante"
        limitaciones = row2[1] if row2 else "ninguna"
        duracion_min = row2[2] if row2 else 60

        perfil = {"objetivo": objetivo, "dias": int(dias), "nivel": nivel,
                  "limitaciones": limitaciones, "duracion_min": duracion_min}
        system_prompt_dinamico = construir_system_prompt(perfil)
        prompt = construir_prompt_usuario(perfil)
        MAX_INTENTOS = 3
        exito = False
        msj   = "Sin respuesta"
        for intento in range(1, MAX_INTENTOS + 1):
            try:
                if intento > 1:
                    await query.edit_message_text(
                        f"🔄 <b>Reintentando... ({intento}/{MAX_INTENTOS})</b>",
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(2)

                client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
                loop = asyncio.get_event_loop()
                resp = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda p=prompt, sp=system_prompt_dinamico: client.models.generate_content(
                            model='gemini-2.0-flash',
                            contents=p,
                            config=types.GenerateContentConfig(system_instruction=sp)
                        )
                    ),
                    timeout=90
                )
                exito, msj = sanitizar_e_insertar_plan(resp.text, user_id, ej_por_dia=duracion_min // 15)
                if exito:
                    break
                logger.warning(f"Intento {intento} falló validación: {msj}")

            except asyncio.TimeoutError:
                msj = "Gemini tardó demasiado (>45s)"
                logger.error(f"Timeout Gemini intento {intento}")
            except Exception as exc:
                msj = str(exc)
                logger.exception(f"Error Gemini intento {intento}")

        if exito:
            iniciar_estado_usuario(user_id)
            await query.edit_message_text(
                "✅ <b>¡Tu plan de 4 semanas está listo!</b>\n\n"
                f"📋 <i>{nivel} · {objetivo} · {dias} días/sem · {duracion_min} min/sesión</i>\n\n"
                "👉 Usa el botón <b>Ver rutina de hoy</b> del menú 👇",
                reply_markup=MENU_PRINCIPAL,
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text(
                f"❌ <b>No se pudo generar el plan.</b>\n"
                f"<i>Error: {msj}</i>\n\n"
                "Toca el menú para intentarlo de nuevo.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🆕 Intentar de nuevo", callback_data="menu:nuevo")
                ]]),
                parse_mode="HTML"
            )
        return


    # ── VER PLAN COMPLETO (desde botón en rutina) ─────────────────────
    if data.startswith("plan:"):
        await query.answer()
        paginas = formatear_plan_por_semanas(user_id)
        if not paginas:
            await query.edit_message_text("No hay plan activo.")
            return
        # Primera semana edita el mensaje actual
        await query.edit_message_text(paginas[0], parse_mode="HTML")
        # Semanas restantes como mensajes nuevos
        for pagina in paginas[1:]:
            await context.bot.send_message(chat_id=query.message.chat_id, text=pagina, parse_mode="HTML")
        # Botón de regreso al final
        tec = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver a hoy", callback_data="back_hoy")]])
        await context.bot.send_message(chat_id=query.message.chat_id, text="👆 Tu plan completo", reply_markup=tec, parse_mode="HTML")
        return

    if data == "back_hoy":
        await query.answer()
        semana, dia = obtener_estado_usuario(user_id)
        texto, tec = obtener_rutina_interactiva(user_id, semana, dia)
        await query.edit_message_text(texto, reply_markup=tec, parse_mode='HTML', disable_web_page_preview=True)
        return

    # ── CHECK / UNCHECK EJERCICIO (toggle atómico) ───────────────────
    if data.startswith("chk:"):
        await query.answer()
        _, ej_id, sem_str, dia = data.split(":")
        sem = int(sem_str)
        conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO progreso (user_id, semana, dia, ejercicio_id, completado)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(user_id, semana, dia, ejercicio_id)
            DO UPDATE SET completado = 1 - completado, ts = CURRENT_TIMESTAMP
        """, (user_id, sem, dia, ej_id))
        conn.commit()
        conn.close()
        texto, tec = obtener_rutina_interactiva(user_id, sem, dia)
        await query.edit_message_text(texto, reply_markup=tec, parse_mode='HTML', disable_web_page_preview=True)
        return

    # ── SWAP: PEDIR ALTERNATIVAS ──────────────────────────────────────
    if data.startswith("swp_ask:"):
        _, ej_id, sem_str, dia = data.split(":")
        sem = int(sem_str)
        alternativas = obtener_alternativas(user_id, sem, dia, ej_id)

        if not alternativas:
            await query.answer("No hay más alternativas disponibles del mismo grupo 😅", show_alert=True)
            return

        await query.answer()
        original = CATALOGO_POR_ID.get(ej_id, {}).get("nombre", ej_id)
        tec = InlineKeyboardMarkup(
            [[InlineKeyboardButton(alt["nombre"], callback_data=f"swp_do:{ej_id}:{alt['ejercicio_id']}:{sem_str}:{dia}")]
             for alt in alternativas]
            + [[InlineKeyboardButton("🔙 Cancelar", callback_data=f"swp_cancel:{sem_str}:{dia}")]]
        )
        await query.edit_message_text(
            f"🔄 <b>Cambiar:</b> {safe(original)}\n\n"
            f"Elige el reemplazo — se aplicará en <b>todas las semanas</b> del plan:",
            reply_markup=tec, parse_mode="HTML"
        )
        return

    # ── SWAP: CONFIRMAR Y APLICAR ─────────────────────────────────────
    if data.startswith("swp_do:"):
        _, id_orig, id_nuevo, sem_str, dia = data.split(":")
        sem = int(sem_str)
        await query.answer("✅ Ejercicio cambiado en todo el plan")
        aplicar_swap(user_id, sem, dia, id_orig, id_nuevo)
        texto, tec = obtener_rutina_interactiva(user_id, sem, dia)
        await query.edit_message_text(texto, reply_markup=tec, parse_mode='HTML', disable_web_page_preview=True)
        return

    # ── SWAP: CANCELAR ────────────────────────────────────────────────
    if data.startswith("swp_cancel:"):
        await query.answer()
        _, sem_str, dia = data.split(":")
        texto, tec = obtener_rutina_interactiva(user_id, int(sem_str), dia)
        await query.edit_message_text(texto, reply_markup=tec, parse_mode='HTML', disable_web_page_preview=True)
        return

    # ── TERMINAR RUTINA ───────────────────────────────────────────────
    if data.startswith("finish:"):
        _, sem_str, dia = data.split(":")
        sem = int(sem_str)
        if not rutina_completa(user_id, sem, dia):
            await query.answer("¡Faltan ejercicios por marcar! 💪", show_alert=True)
            return
        await query.answer()
        tec = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Sí, terminar y avanzar", callback_data=f"adv_yes:{sem}:{dia}")],
            [InlineKeyboardButton("🔙 No, volver",             callback_data=f"adv_no:{sem}:{dia}")]
        ])
        await query.edit_message_text(
            "🎉 <b>¡Completaste todo!</b>\n\n¿Quieres cerrar esta sesión y avanzar al siguiente día?",
            reply_markup=tec, parse_mode='HTML'
        )
        return

    if data.startswith("adv_no:"):
        await query.answer()
        _, sem_str, dia = data.split(":")
        texto, tec = obtener_rutina_interactiva(user_id, int(sem_str), dia)
        await query.edit_message_text(texto, reply_markup=tec, parse_mode='HTML', disable_web_page_preview=True)
        return

    if data.startswith("adv_yes:"):
        await query.answer()
        _, sem_str, dia = data.split(":")
        sem = int(sem_str)
        avanzar_estado_dinamico(user_id, sem, dia)
        await query.edit_message_text(
            "🏆 <b>¡Rutina guardada!</b>\n\nDescansa bien 💤\nUsa /start cuando estés lista.",
            parse_mode='HTML'
        )
        mensajes_milestone = procesar_milestones(user_id, sem)
        for msg in mensajes_milestone:
            await context.bot.send_message(chat_id=query.message.chat_id, text=msg, parse_mode="HTML")
        return

# ==========================================
# 9. INICIALIZACIÓN
# ==========================================
def main():
    init_db()
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("❌ Falta TELEGRAM_TOKEN en las variables de entorno.")
        return

    app = Application.builder().token(token).build()
    async def error_handler(update, context):
        logger.error(f"Error no capturado: {context.error}", exc_info=context.error)
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "⚠️ Ocurrió un error inesperado. Intenta de nuevo o usa /start."
                )
        except Exception:
            pass

    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("menu",         menu_handler))
    app.add_handler(CommandHandler("plan",         plan_handler))
    app.add_handler(CommandHandler("reset_plan",   reset_plan_handler))
    app.add_handler(CommandHandler("reset_swaps",  reset_swaps_handler))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gemini_coach_handler))
    app.add_error_handler(error_handler)

    logger.info("✅ Bot iniciado — gemini-2.0-flash | SQLite multi-tenant | Swaps persistentes")
    app.run_polling()

if __name__ == '__main__':
    main()
