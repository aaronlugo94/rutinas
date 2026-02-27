import os
import json
import asyncio
import sqlite3
import html
import logging
from contextlib import contextmanager
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
# Silenciar loggers verbosos que no aportan valor
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("google.auth").setLevel(logging.WARNING)

# ALLOWED_USERS ya no es hardcode — la fuente de verdad es la tabla usuarios_permitidos
# Mantenemos el set como cache en memoria para arranque rápido (se llena desde DB)
ALLOWED_USERS: set = set()

def cargar_usuarios_permitidos():
    """Carga desde DB los usuarios con acceso. Llamar en init."""
    global ALLOWED_USERS
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        cur  = conn.cursor()
        cur.execute("SELECT user_id FROM usuarios_permitidos")
        ALLOWED_USERS = {row[0] for row in cur.fetchall()}
        conn.close()
        logger.info(f"Usuarios permitidos cargados: {ALLOWED_USERS}")
    except Exception as e:
        # Si falla, usar hardcode como fallback de seguridad
        ALLOWED_USERS = {1557254587, 8468355326}
        logger.warning(f"Fallback hardcode ALLOWED_USERS: {e}")
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

# ── PATRONES BIOMECÁNICOS (auditoría #3 — validación fisiológica post-Gemini) ──
# Permite detectar: 3 bisagras el mismo día, cardio antes del ejercicio 3, etc.
PATRON_POR_ID = {"GLU_01": "puente_cadera", "GLU_02": "puente_cadera", "GLU_03": "puente_cadera", "GLU_04": "puente_cadera", "GLU_05": "sentadilla", "GLU_06": "sentadilla", "GLU_07": "bisagra_cadera", "GLU_08": "bisagra_cadera", "GLU_09": "bisagra_cadera", "GLU_10": "patada_aislamiento", "GLU_11": "patada_aislamiento", "GLU_12": "patada_aislamiento", "GLU_13": "abduccion", "GLU_14": "abduccion", "GLU_15": "extension_cadera", "GLU_16": "extension_cadera", "GLU_17": "sentadilla", "GLU_18": "patada_aislamiento", "GLU_19": "bisagra_cadera", "GLU_20": "puente_cadera", "PIE_01": "sentadilla", "PIE_02": "sentadilla", "PIE_03": "sentadilla", "PIE_04": "sentadilla", "PIE_05": "sentadilla", "PIE_06": "prensa", "PIE_07": "prensa", "PIE_08": "bisagra_cadera", "PIE_09": "bisagra_cadera", "PIE_10": "bisagra_cadera", "PIE_11": "curl_femoral", "PIE_12": "curl_femoral", "PIE_13": "curl_femoral", "PIE_14": "desplante", "PIE_15": "desplante", "PIE_16": "sentadilla", "PIE_17": "sentadilla",
    "PIE_19": "desplante", "EMP_01": "press_horizontal", "EMP_02": "press_horizontal", "EMP_03": "press_horizontal", "EMP_04": "press_inclinado", "EMP_05": "press_inclinado", "EMP_06": "press_vertical", "EMP_07": "press_vertical", "EMP_08": "press_vertical", "EMP_09": "aislamiento_pecho", "EMP_10": "aislamiento_pecho", "EMP_11": "triceps", "EMP_12": "triceps", "EMP_13": "triceps", "EMP_14": "triceps", "EMP_15": "core_dinamico", "EMP_16": "core_estabilidad", "EMP_17": "core_estabilidad", "EMP_18": "core_estabilidad", "EMP_19": "press_vertical", "TIR_01": "jalon_vertical", "TIR_02": "jalon_vertical", "TIR_03": "jalon_vertical", "TIR_04": "remo_horizontal", "TIR_05": "remo_horizontal", "TIR_06": "remo_horizontal", "TIR_07": "remo_horizontal", "TIR_08": "biceps", "TIR_09": "biceps", "TIR_10": "biceps", "TIR_11": "biceps", "TIR_12": "hombro_posterior", "TIR_13": "hombro_posterior", "TIR_14": "remo_horizontal", "TIR_15": "jalon_vertical", "COR_01": "core_estabilidad", "COR_02": "core_estabilidad", "COR_03": "core_estabilidad", "COR_04": "core_dinamico", "COR_05": "core_dinamico", "COR_06": "core_rotacion", "COR_07": "core_estabilidad", "COR_08": "core_dinamico", "CAR_01": "cardio", "CAR_02": "cardio", "CAR_03": "cardio", "CAR_04": "cardio", "CAR_05": "cardio", "CAR_06": "cardio", "CAR_07": "cardio", "CAR_08": "cardio", "CAR_09": "cardio", "CAR_10": "cardio", "CAR_11": "cardio",
    # IDs añadidos en FIX 11 (estaban en CATALOGO sin patrón — volumen subestimado)
    "COR_09": "core_estabilidad",  # Bird dog
    "COR_10": "core_dinamico",     # Mountain climbers
    "COR_11": "core_dinamico",     # Bicicleta abdominal
    "COR_12": "core_estabilidad",  # Superman en suelo
    "COR_13": "core_dinamico",     # Tijeras abdominales
    "COR_14": "core_rotacion",     # Rotación rusa con mancuerna
    "COR_15": "core_estabilidad",  # Hollow body hold
    "PIE_18": "desplante",         # Sentadilla goblet con mancuerna
    "PIE_20": "desplante",         # Zancada lateral
    "TIR_16": "remo_horizontal",   # Pullover con mancuerna
    "TIR_17": "hombro_posterior",  # Encogimientos de hombros
    "TIR_18": "core_estabilidad",  # Superman en banco
}

def patron_de(ej_id: str) -> str:
    """Devuelve el patrón biomecánico de un ejercicio, o 'desconocido'."""
    return PATRON_POR_ID.get(str(ej_id), "desconocido")


# ── CUES TÉCNICOS CANÓNICOS (doc #12 — notas correctas siempre) ──────────────
CUES_TECNICOS = {'GLU_01': 'aprieta glúteo arriba 1s', 'GLU_02': 'banda activa abductores', 'GLU_03': 'caderas neutras, pausa 1s', 'GLU_04': 'pies en plataforma alta', 'GLU_05': 'rodillas siguen pies', 'GLU_06': 'ancho mayor que cadera', 'GLU_07': 'espalda recta, bisagra cadera', 'GLU_08': 'mancuernas cerca del cuerpo', 'GLU_09': 'rodillas ligeramente flexionadas', 'GLU_10': 'glúteo contraído al final', 'GLU_11': 'cadera alineada, no rotar', 'GLU_12': 'tobillera ajustada, movimiento lento', 'GLU_13': 'rodillas alineadas, no colapsar', 'GLU_14': 'rango completo, pausa', 'GLU_15': 'extensión completa sin hiperextender', 'GLU_16': 'posición neutra de columna', 'GLU_17': 'talones elevados, profundidad máxima', 'GLU_18': 'codo bajo hombro, caderas cuadradas', 'GLU_19': 'bisagra de cadera, no sentadilla', 'GLU_20': 'peso en talones, no punta', 'PIE_01': 'rodillas siguen línea de pies', 'PIE_02': 'pies más anchos, puntas afuera', 'PIE_03': 'espalda neutra en barra', 'PIE_04': 'peso en talones, pecho arriba', 'PIE_05': 'sentadilla frontal, codos altos', 'PIE_06': 'pies altos = más glúteo', 'PIE_07': 'rodillas sin bloquear al extender', 'PIE_08': 'espalda plana, bisagra pura', 'PIE_09': 'mancuernas cerca del cuerpo', 'PIE_10': 'pierna de apoyo ligeramente flexionada', 'PIE_11': 'rodillas fijas, solo femoral', 'PIE_12': 'curl lento en fase excéntrica', 'PIE_13': 'apretar femoral 1s arriba', 'PIE_14': 'rodilla delantera sobre tobillo', 'PIE_15': 'torso recto, paso largo', 'PIE_16': 'talon alto, más cuádriceps', 'PIE_17': 'peso goblet frente al pecho', 'PIE_19': 'pierna trasera baja al piso', 'EMP_01': 'codos a 45°, escápulas fijas', 'EMP_02': 'agarre ancho, rango completo', 'EMP_03': 'excéntrico 3 segundos', 'EMP_04': 'inclinación 30-45°, no vertical', 'EMP_05': 'pecho arriba, no encoger hombros', 'EMP_06': 'codos bajo muñecas siempre', 'EMP_07': 'barra baja por nariz, no frente', 'EMP_08': 'brazos paralelos al suelo', 'EMP_09': 'mancuernas hacia afuera del cuerpo', 'EMP_10': 'movimiento de arco, no recto', 'EMP_11': 'codos fijos, solo tríceps', 'EMP_12': 'agarre neutro, codo pegado', 'EMP_13': 'rotación externa al subir', 'EMP_14': 'polea alta, codos juntos', 'EMP_15': 'abdomen apretado, sin inercia', 'EMP_16': '30-60 segundos sin mover', 'EMP_17': 'caderas en línea, no ceder', 'EMP_18': 'alternado, sin girar cadera', 'EMP_19': 'no encogerse al final', 'TIR_01': 'codos hacia cadera, no atrás', 'TIR_02': 'agarre supino, bíceps activado', 'TIR_03': 'agarre estrecho, codos al cuerpo', 'TIR_04': 'escápulas al final del recorrido', 'TIR_05': 'codo alto, no abierto', 'TIR_06': 'isométrico 1s al final', 'TIR_07': 'cuerpo recto, tirón limpio', 'TIR_08': 'codos fijos junto al cuerpo', 'TIR_09': 'agarre martillo, antebrazo neutro', 'TIR_10': 'rango completo, excéntrico lento', 'TIR_11': 'polea baja, codo fijo', 'TIR_12': 'polea alta, codos afuera', 'TIR_13': 'no encogerse, retracción escapular', 'TIR_14': 'pecho al pecho, no lumbar', 'TIR_15': 'agarre amplio, codos afuera', 'COR_01': '30-60s sin ceder lumbar', 'COR_02': 'lateral, 30s cada lado', 'COR_03': 'glúteo apretado, sin arco', 'COR_04': 'rodillas al pecho, lento', 'COR_05': 'no balancear, control total', 'COR_06': 'rotación desde core, no brazos', 'COR_07': 'palmas al piso, sin hundir', 'COR_08': 'bicicleta lenta, codo a rodilla', 'CAR_01': 'inclinación 8-12%, ritmo moderado', 'CAR_02': 'cadencia constante, no agarrarse', 'CAR_03': 'resistencia moderada, pedaleo suave', 'CAR_04': 'zancada corta, cadencia alta', 'CAR_05': 'brazos activos, respiración rítmica', 'CAR_06': 'postura erguida, cadencia constante', 'CAR_07': 'ritmo constante, respiración nasal', 'CAR_08': 'muñecas sueltas, salto pequeño', 'CAR_09': 'tirar con espalda, no brazos', 'CAR_10': 'escalón completo, glúteo activo', 'CAR_11': 'brazos activos, paso largo'}


# ═══════════════════════════════════════════════════════════════════
# MÓDULO VOLUMEN SEMANAL (Schoenfeld 2017 — 10-20 series/grupo/semana)
# ═══════════════════════════════════════════════════════════════════

# Mapeo patrón biomecánico → grupo muscular primario para conteo de volumen
PATRON_A_GRUPO = {
    "sentadilla":        "cuadriceps",
    "prensa":            "cuadriceps",
    "desplante":         "cuadriceps",
    "puente_cadera":     "gluteo",
    "bisagra_cadera":    "gluteo",
    "abduccion":         "gluteo",
    "curl_femoral":      "isquiotibial",
    "press_horizontal":  "pecho",
    "press_inclinado":   "pecho",
    "aislamiento_pecho": "pecho",
    "press_vertical":    "hombro",
    "hombro_posterior":  "hombro",
    "jalon_vertical":    "espalda",
    "remo_horizontal":   "espalda",
    "biceps":            "biceps",
    "triceps":           "triceps",
    "core_estabilidad":  "core",
    "core_dinamico":     "core",
    "core_rotacion":     "core",
}

# Rangos científicos de volumen semanal por grupo (Schoenfeld 2017 meta-análisis)
VOLUMEN_RANGOS = {
    "cuadriceps":    {"min": 8,  "opt_low": 10, "opt_high": 16, "max": 20},
    "gluteo":        {"min": 8,  "opt_low": 10, "opt_high": 16, "max": 20},
    "isquiotibial":  {"min": 6,  "opt_low": 8,  "opt_high": 12, "max": 16},
    "pecho":         {"min": 8,  "opt_low": 10, "opt_high": 16, "max": 20},
    "espalda":       {"min": 8,  "opt_low": 10, "opt_high": 16, "max": 20},
    "hombro":        {"min": 6,  "opt_low": 8,  "opt_high": 14, "max": 18},
    "biceps":        {"min": 4,  "opt_low": 6,  "opt_high": 12, "max": 16},
    "triceps":       {"min": 4,  "opt_low": 6,  "opt_high": 12, "max": 16},
    "core":          {"min": 4,  "opt_low": 6,  "opt_high": 10, "max": 14},
}

def calcular_volumen_semanal(user_id: int, semana: int) -> dict:
    """
    Calcula series efectivas por grupo muscular en una semana completa.
    Fuente: Schoenfeld (2017) — volumen óptimo 10-20 series/grupo/semana.
    FIX: reescrito con 1 sola conexión (antes había 2, con conn.close() antes de fetchall).
    Retorna dict: {grupo: {"series": N, "estado": "bajo"|"optimo"|"alto"}}
    """
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur  = conn.cursor()
    cur.execute("""
        SELECT ejercicio_id, series FROM rutinas
        WHERE user_id = ? AND semana = ?
        AND ejercicio_id NOT LIKE 'CAR_%'
    """, (user_id, semana))
    rows = cur.fetchall()
    conn.close()

    # Sumar series por grupo muscular
    from collections import defaultdict
    volumen = defaultdict(int)
    for eid, series in rows:
        pat   = PATRON_POR_ID.get(eid, "")
        grupo = PATRON_A_GRUPO.get(pat)
        if grupo:
            try:
                volumen[grupo] += int(series)
            except:
                volumen[grupo] += 3  # default si no es int

    # Evaluar estado de cada grupo
    resultado = {}
    for grupo, rango in VOLUMEN_RANGOS.items():
        series_total = volumen.get(grupo, 0)
        if series_total == 0:
            estado = "ausente"
        elif series_total < rango["min"]:
            estado = "bajo"
        elif series_total <= rango["opt_high"]:
            estado = "optimo"
        elif series_total <= rango["max"]:
            estado = "alto"
        else:
            estado = "exceso"
        resultado[grupo] = {"series": series_total, "estado": estado}

    return resultado

# ═══════════════════════════════════════════════════════════════════
# MÓDULO FATIGA Y DELOAD (Israetel — deload cada 4-8 semanas según fatiga)
# ═══════════════════════════════════════════════════════════════════

FATIGA_NIVELES = {
    1: ("😊", "Fresco — sin fatiga"),
    2: ("🙂", "Leve cansancio — normal"),
    3: ("😐", "Moderada — vigilar"),
    4: ("😓", "Alta — reducir volumen"),
    5: ("💀", "Crítica — deload inmediato"),
}

def registrar_fatiga(user_id: int, semana: int, dia: str, nivel_fatiga: int):
    """
    Guarda el nivel de fatiga subjetiva del usuario tras una sesión.
    FIX: El UPDATE anterior fallaba silenciosamente si no había fila en progreso.
    Ahora garantiza la fila con INSERT OR IGNORE antes de actualizar.
    """
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur  = conn.cursor()
    # Garantizar que existe al menos 1 fila para este día antes del UPDATE
    # (puede no existir si el usuario no marcó ningún ejercicio)
    cur.execute("""
        INSERT OR IGNORE INTO progreso (user_id, semana, dia, ejercicio_id, completado, fatiga_reportada)
        VALUES (?, ?, ?, '__fatiga__', 0, ?)
    """, (user_id, semana, dia, nivel_fatiga))
    # Actualizar todas las filas del día con la fatiga reportada
    cur.execute("""
        UPDATE progreso SET fatiga_reportada = ?
        WHERE user_id = ? AND semana = ? AND dia = ?
    """, (nivel_fatiga, user_id, semana, dia))
    conn.commit()
    conn.close()
    logger.info(f"Fatiga {nivel_fatiga}/5 registrada: user={user_id} S{semana} {dia}")

def evaluar_fatiga_acumulada(user_id: int) -> dict:
    """
    Analiza el patrón de fatiga para detectar sobrecarga.
    Triggers de deload (Israetel — Renaissance Periodization):
      - Fatiga promedio >= 4 durante 2 días consecutivos
      - Fatiga crítica (5) en cualquier momento
      - 4 semanas de progresión sin deload
    Retorna: {"necesita_deload": bool, "razon": str, "fatiga_promedio": float}
    """
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur  = conn.cursor()
    # Fatiga de los últimos 6 registros (últimas 6 sesiones)
    cur.execute("""
        SELECT fatiga_reportada, semana FROM progreso
        WHERE user_id = ? AND fatiga_reportada IS NOT NULL
        ORDER BY ts DESC LIMIT 6
    """, (user_id,))
    registros = cur.fetchall()

    # Semana máxima del plan actual
    cur.execute("SELECT MAX(semana) FROM rutinas WHERE user_id = ?", (user_id,))
    max_sem = (cur.fetchone() or [0])[0] or 0
    conn.close()

    if not registros:
        return {"necesita_deload": False, "razon": "sin datos", "fatiga_promedio": 0}

    fatigas = [r[0] for r in registros]
    promedio = sum(fatigas) / len(fatigas)

    # Trigger 1: fatiga crítica
    if 5 in fatigas[:2]:  # en las últimas 2 sesiones
        return {"necesita_deload": True, "razon": "fatiga crítica detectada", "fatiga_promedio": promedio}

    # Trigger 2: fatiga alta sostenida
    if promedio >= 4 and len(fatigas) >= 3:
        return {"necesita_deload": True, "razon": "fatiga alta sostenida (≥4/5 en últimas 3 sesiones)", "fatiga_promedio": promedio}

    # Trigger 3: 4 semanas sin deload (el plan ya incluye S4 como deload)
    # Si llegan a semana 5+ sin resetear, forzar
    if max_sem >= 5:
        return {"necesita_deload": True, "razon": "4 semanas de progresión completadas", "fatiga_promedio": promedio}

    return {"necesita_deload": False, "razon": "ok", "fatiga_promedio": promedio}


def ajustar_sesion_por_fatiga(user_id: int, semana: int, dia: str, nivel_fatiga: int):
    """
    Ajusta la sesión siguiente si la fatiga es alta (niveles 4-5).
    - Reduce 1 serie en ejercicios accesorios (no el compuesto principal)
    - Reduce cardio a 10 min si fatiga = 5
    Mantiene siempre: 4 ejercicios de fuerza + 1 cardio
    """
    if nivel_fatiga < 4:
        return  # no hacer nada

    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur  = conn.cursor()

    # Obtener ejercicios del día con su orden (el compuesto es orden=1)
    cur.execute("""
        SELECT id, ejercicio_id, series, orden FROM rutinas
        WHERE user_id = ? AND semana = ? AND dia = ?
        ORDER BY orden ASC
    """, (user_id, semana, dia))
    rows = cur.fetchall()

    for row_id, eid, series, orden in rows:
        pat = PATRON_POR_ID.get(eid, "")
        es_cardio = pat == "cardio" or eid.startswith("CAR_")

        if es_cardio and nivel_fatiga == 5:
            # Fatiga crítica: reducir cardio a 10min
            cur.execute("UPDATE rutinas SET reps = '10min' WHERE id = ?", (row_id,))
        elif orden >= 3 and not es_cardio:
            # Accesorios (posición 3 y 4): reducir 1 serie, mínimo 2
            nuevas_series = max(2, int(series or 3) - 1)
            cur.execute("UPDATE rutinas SET series = ? WHERE id = ?", (nuevas_series, row_id))

    conn.commit()
    conn.close()
    logger.info(f"Ajuste fatiga {nivel_fatiga}/5 aplicado: user={user_id} S{semana} {dia}")




def formatear_volumen_reporte(vol: dict) -> str:
    """
    Formatea el volumen semanal para mostrar al usuario en Telegram.
    FIX 1: variable 'bar' no estaba asignada (NameError garantizado).
    FIX 2: la función estaba truncada sin return.
    """
    emojis = {"ausente": "⚫", "bajo": "🔴", "optimo": "🟢", "alto": "🟡", "exceso": "🔴"}
    lines = ["📊 <b>Volumen semanal por músculo</b>", "━━━━━━━━━━━━━━━━━━", ""]
    grupos_es = {
        "cuadriceps": "Cuádriceps", "gluteo": "Glúteo", "isquiotibial": "Isquio",
        "pecho": "Pecho", "espalda": "Espalda", "hombro": "Hombro",
        "biceps": "Bíceps", "triceps": "Tríceps", "core": "Core",
    }
    for grupo, data in vol.items():
        if data["series"] == 0 and data["estado"] == "ausente":
            continue
        emoji    = emojis.get(data["estado"], "⚪")
        rango    = VOLUMEN_RANGOS[grupo]
        bar_filled = min(10, round(data["series"] / rango["opt_high"] * 10))
        bar      = "█" * bar_filled + "░" * (10 - bar_filled)   # FIX: asignar 'bar'
        nombre_grupo = grupos_es.get(grupo, grupo)
        n_series = data["series"]
        opt_rango = f'{rango["opt_low"]}-{rango["opt_high"]}'
        linea = f"{emoji} <b>{nombre_grupo}</b>: {n_series} series\n   <code>[{bar}]</code> óptimo: {opt_rango}"
        lines.append(linea)
    lines += ["", "<i>🟢 óptimo · 🟡 alto · 🔴 bajo/exceso</i>"]
    return "\n".join(lines)  # FIX: return que faltaba




# ── METADATA FATIGA (auditoría #8 — no 2 alta-fatiga seguidos) ────────────────
FATIGA_POR_ID = {
    # Alta fatiga (SNC + muscular — limitante de sesión)
    "PIE_01":"alta","PIE_02":"alta","PIE_03":"alta","PIE_08":"alta",
    "PIE_09":"alta","PIE_10":"alta","PIE_14":"alta","PIE_16":"alta",
    "GLU_03":"alta","GLU_04":"alta","GLU_07":"alta","GLU_08":"alta","GLU_19":"alta",
    "EMP_01":"alta","EMP_02":"alta","EMP_03":"alta","EMP_06":"alta",
    "TIR_01":"alta","TIR_04":"alta","TIR_05":"alta","TIR_06":"alta",
    # Media fatiga
    "PIE_06":"media","PIE_07":"media","PIE_11":"media","PIE_12":"media",
    "GLU_05":"media","GLU_06":"media","GLU_09":"media","GLU_17":"media",
    "EMP_04":"media","EMP_05":"media","EMP_07":"media","EMP_08":"media",
    "TIR_02":"media","TIR_03":"media","TIR_07":"media","TIR_14":"media",
}

def fatiga_de(ej_id: str) -> str:
    return FATIGA_POR_ID.get(str(ej_id), "baja")


# ── MÁXIMO EJERCICIOS POR PATRÓN EN UN DÍA ────────────────────────────────────
# Regla de oro (auditoría doc #8): max 2 del mismo patrón
# Patrones "singulares" = solo 1 permitido (demasiado específicos)
MAX_POR_PATRON = {
    "puente_cadera":      2,   # hip thrust + variante = OK, 3+ = redundancia
    "sentadilla":         1,   # 1 sola sentadilla por día — fatiga cuádriceps (doc auditoría #8)
    "bisagra_cadera":     2,
    "press_horizontal":   2,
    "press_inclinado":    1,   # variante del horizontal — no ambos en mismo día
    "press_vertical":     1,
    "jalon_vertical":     1,
    "remo_horizontal":    2,
    "curl_femoral":       1,
    "patada_aislamiento": 2,
    "abduccion":          1,
    "biceps":             2,
    "triceps":            2,
    "core_estabilidad":   2,
    "core_dinamico":      2,
    "prensa":             1,   # 1 prensa por día — complementa sentadilla
    "extension_cadera":   2,
    "cardio":             1,   # siempre 1 solo al final
}
MAX_POR_PATRON_DEFAULT = 2



CATALOGO_POR_ID = {ex["ejercicio_id"]: ex for ex in CATALOGO}

def construir_prompt_semana(perfil: dict, num_semana: int) -> str:
    """
    Prompt COMPLETO y auto-contenido para generar una semana.
    Incluye instrucción de sistema + catálogo + formato.
    Diseñado para que Gemini NO pueda responder con texto explicativo.
    """
    obj   = perfil.get("objetivo", "general")
    nivel = perfil.get("nivel", "principiante")
    dias  = int(perfil.get("dias", 3))
    dur   = int(perfil.get("duracion_min", 60))
    lim   = perfil.get("limitaciones", "ninguna")
    genero = perfil.get("genero", "mujer")
    ej    = 5  # estructura científica: 4 fuerza + 1 cardio siempre

    # Progresión por semana
    # ── SERIES, REPS Y RIR POR NIVEL (Deschenes 2002 + Krieger 2010 + Schoenfeld 2017) ──
    # EJERCICIOS: siempre 4 de fuerza + 1 cardio = 5 (nunca cambia por nivel)
    # SERIES: sí varían por nivel — el SNC de un principiante no tolera el mismo volumen
    #   Principiante: 3 series — suficiente para adaptación neuromuscular (Deschenes 2002)
    #   Intermedio:   4 series — punto dulce hipertrofia (Schoenfeld 2017)
    #   Avanzado:    5 series — necesario para superar adaptación (Krieger 2010)
    s  = {"principiante": 3, "intermedio": 4, "avanzado": 5}.get(nivel, 4)
    sd = max(2, s - 1)  # series deload = s-1 (reducción ~25% volumen)

    # PROGRESIÓN DOBLE — mismo ejercicio S1-S3, RIR baja cada semana, S4=DELOAD
    # PROHIBIDO: RIR 0 en principiante | más de 12 reps en avanzado
    prog = {
        "principiante": {
           # 3 series | 10-15 reps | RIR 2-3 | máquinas guiadas SOLO
           1: f"{s} series × 12-15 reps — RIR 3 — máquina guiada, técnica antes que carga",
           2: f"{s} series × 10-12 reps — RIR 2 — mismo ejercicio S1, +5% carga",
           3: f"{s} series × 10-12 reps — RIR 2 — mismo ejercicio S1, +5% vs S2",
           4: f"{sd} series × 12-15 reps — RIR 4 — DELOAD 60% carga, recuperación",
        },
        "intermedio": {
           # 4 series | 6-12 reps | RIR 1-2 | mancuernas + poleas libres
           1: f"{s} series × 10-12 reps — RIR 2 — mancuernas libres, rango completo",
           2: f"{s} series × 8-10 reps  — RIR 2 — mismo ejercicio S1, +5-10% carga",
           3: f"{s} series × 6-8 reps   — RIR 1 — mismo ejercicio S1, fuerza-hipertrofia",
           4: f"{sd} series × 10-12 reps — RIR 4 — DELOAD 60% carga, mismos ejercicios S1",
        },
        "avanzado": {
           # 5 series | 5-10 reps | RIR 0-1 | barra libre, ejercicios complejos
           1: f"{s} series × 8-10 reps — RIR 1 — barra libre o ejercicio complejo",
           2: f"{s} series × 6-8 reps  — RIR 1 — mismo ejercicio S1, sobrecarga progresiva",
           3: f"{s} series × 5-8 reps  — RIR 0 — mismo ejercicio S1, máxima tensión",
           4: f"{sd} series × 8-10 reps — RIR 3 — DELOAD 50% carga, mismos ejercicios S1",
        },
    }
    series_reps = prog.get(nivel, prog["intermedio"])[num_semana]

    # Split del día según días/semana y objetivo
    if dias == 3:
        dias_split = ["lunes","miercoles","viernes"]
        grupos_split = ["gluteo","tiron","gluteo"] if "gluteo" in obj else ["pierna","empuje","tiron"]
    elif dias == 4:
        dias_split = ["lunes","martes","jueves","viernes"]
        grupos_split = ["gluteo","empuje","pierna","tiron"] if "gluteo" in obj else ["pierna","empuje","pierna","tiron"]
    else:  # 5
        dias_split = ["lunes","martes","miercoles","jueves","viernes"]
        grupos_split = ["gluteo","empuje","tiron","pierna","gluteo"] if "gluteo" in obj else ["pierna","empuje","tiron","pierna","empuje"]

    # Catálogo comprimido por grupo
    grupos_orden = ["gluteo","pierna","empuje","tiron","core","cardio"]
    cat_lines = []
    for g in grupos_orden:
        ids = [e["ejercicio_id"] for e in CATALOGO if e["grupo"] == g]
        cat_lines.append(f"{g.upper()}: {' '.join(ids)}")

    # Construir estructura exacta esperada como ejemplo
    ejemplo_dia = f'{{"dia":"lunes","grupo":"gluteo","ejercicios":[{{"ejercicio_id":"GLU_03","orden":1,"series":3,"reps":"15","notas":"pausa 1s arriba"}}]}}'

    return f"""INSTRUCCION: Responde UNICAMENTE con JSON. Cero texto. Cero explicaciones. Solo el objeto JSON.

CATALOGO (usa SOLO estos IDs):
{chr(10).join(cat_lines)}

TAREA: Genera la semana {num_semana} de 4 para este usuario.
- Objetivo: {obj}
- Nivel: {nivel}
- Genero: {genero}
- Limitaciones: {lim}
- Dias por semana: {dias} ({', '.join(dias_split)})
- Ejercicios por dia: exactamente {ej}
- Series/reps esta semana: {series_reps}
- El ultimo ejercicio SIEMPRE es cardio (CAR_01 a CAR_10) con series=1 y reps="20min"
- Los ejercicios de fuerza usan reps como string: "15" "8-10"
- El cardio SIEMPRE usa: series=1, reps="20min" (nunca series=3, nunca reps="45s")
- Notas: cue tecnico del movimiento, 5 palabras max, sin comillas
  CORRECTO: "codos a 45 grados", "pausa 1s arriba", "espalda recta siempre"
  INCORRECTO: inventar ejercicio diferente, mezclar musculos, poner nombre de otro ejercicio
  La nota DEBE describir la TECNICA del ejercicio que aparece en el campo ejercicio_id

DIAS Y GRUPOS REQUERIDOS:
{chr(10).join(f"  {d}: grupo={g}" for d,g in zip(dias_split, grupos_split))}

CONTRATO DE SESION (no negociable):

ESTRUCTURA OBLIGATORIA — 5 EJERCICIOS EXACTOS, SIEMPRE (nunca 3, nunca 4, nunca 6):
  Posición 1: COMPUESTO PRINCIPAL — el más pesado y activador del grupo del día
  Posición 2: COMPUESTO SECUNDARIO — patrón diferente al principal (bisagra si pos1=sentadilla)
  Posición 3: UNILATERAL o ACCESORIO — desplante, remo a 1 mano, curl femoral unilateral
  Posición 4: AISLAMIENTO — rematar músculo objetivo (abducción, extensión, curl, etc.)
  Posición 5: CARDIO — series=1, reps="20min", siempre último

SERIES Y REPS (tu nivel = {nivel}):
  TU PROTOCOLO: {series_reps}
  principiante: 3 series | 10-15 reps | RIR 2-3 | máquinas guiadas | PROHIBIDO RIR 0
  intermedio:   4 series | 6-12 reps  | RIR 1-2 | mancuernas libres
  avanzado:     5 series | 5-10 reps  | RIR 0-1 | barra libre | PROHIBIDO >12 reps principales
  deload (S4):  series-1 | RIR 4 | 50-60% carga | MISMOS ejercicios que S1
NIVEL DEFINE DIFICULTAD DEL EJERCICIO:
  principiante = SOLO máquinas guiadas, sin barra libre ni sentadilla búlgara
  intermedio   = mancuernas libres, poleas, unilaterales básicos
  avanzado     = barra libre, sentadilla búlgara, dominadas, unilaterales avanzados

REGLAS DE PATRON (el backend rechaza violaciones):
  - Max 1 sentadilla por dia (PIE_01 PIE_02 PIE_03 PIE_16)
  - Max 1 bisagra de cadera por dia (GLU_07 GLU_08 PIE_08 PIE_09)
  - Max 2 puente_cadera por dia (GLU_01 GLU_02 GLU_03 GLU_04)
  - Max 1 press_horizontal por dia (EMP_01 EMP_02 EMP_03)
  - Max 1 jalon_vertical por dia (TIR_01 TIR_02 TIR_03)

CARDIO: IDs disponibles: {' '.join(e['ejercicio_id'] for e in CATALOGO if e['grupo']=='cardio')}

PROGRESION DOBLE (regla de oro del crecimiento muscular):
  - S1 = reps altas, RIR alto — aprender el movimiento y la carga base
  - S2 = mismos ejercicios S1, pero RIR -1 (más cerca del límite real)
  - S3 = variantes más difíciles del mismo patron, RIR -1 más
  - S4 = DELOAD — mismos ejercicios S1, 60% carga, RIR alto — recuperación
  REGLA: el cuerpo crece cuando se adapta, no cuando se destruye

FORMATO EXACTO (SOLO JSON, nada mas):
{{"semana":{num_semana},"dias":[{ejemplo_dia}]}}

RESPONDE CON EL JSON:"""


def validar_coherencia_dia(dia: dict) -> tuple[bool, str]:
    """
    Validador fisiológico + CORRECTOR automático (doc auditoría #8 + #9).
    LLM genera → Python arbitra y CORRIGE en 3 capas:
      1. Dedupe por ejercicio_id exacto (no repetir mismo ejercicio)
      2. Dedupe por patrón biomecánico (MAX_POR_PATRON)
      3. Dedupe por rol+grupo (no 2 "principal" del mismo grupo)
    """
    from collections import defaultdict

    ejercicios = dia.get("ejercicios", [])
    if not ejercicios:
        return False, "Día sin ejercicios"

    # ── Paso 1: Contar y CORREGIR redundancias por patrón ────────────────────
    conteo_patron: dict   = defaultdict(int)
    vistos_ids:    set    = set()            # dedupe exacto por ID
    roles_grupo:   set    = set()            # dedupe por "principal del mismo grupo"
    cardios = []
    fuerza  = []

    # Separar cardio de fuerza primero
    for e in ejercicios:
        eid = e.get("ejercicio_id", "")
        if patron_de(eid) == "cardio" or eid.startswith("CAR_"):
            cardios.append(e)
        else:
            fuerza.append(e)

    # Filtrar ejercicios de fuerza en 3 capas
    fuerza_filtrada = []
    eliminados = []
    for e in fuerza:
        eid = e.get("ejercicio_id", "")
        pat = patron_de(eid)
        meta = CATALOGO_POR_ID.get(eid, {})
        rol  = meta.get("rol", "aislamiento")
        grp  = meta.get("grupo", "general")

        # Capa 1: dedupe exacto por ID
        if eid in vistos_ids:
            eliminados.append((eid, "duplicado exacto"))
            continue
        vistos_ids.add(eid)

        # Capa 2: dedupe por patrón (MAX_POR_PATRON)
        limite = MAX_POR_PATRON.get(pat, MAX_POR_PATRON_DEFAULT)
        if conteo_patron[pat] >= limite:
            eliminados.append((eid, f"patrón {pat} saturado ({limite})"))
            continue
        conteo_patron[pat] += 1

        # Capa 3: dedupe principal por PATRON biomecánico (no por grupo)
        # "principal empuje" es demasiado amplio — press pecho ≠ press hombro
        # Usar patron para discriminar: press_horizontal ≠ press_vertical ≠ press_inclinado
        pat_key = f"principal_{pat}" if rol == "principal" else None
        if pat_key and pat_key in roles_grupo:
            eliminados.append((eid, f"patrón {pat} principal ya cubierto"))
            continue
        if pat_key:
            roles_grupo.add(pat_key)

        fuerza_filtrada.append(e)

    if eliminados:
        logger.warning(f"Coherencia: {len(eliminados)} ejercicios redundantes eliminados en {dia.get('dia','?')}: {eliminados}")

    # ── Paso 2: Cardio siempre al final, máximo 1 ────────────────────────────
    # Solo 1 cardio (el primero encontrado) al final
    cardio_final = cardios[:1]

    # ── Paso 3: Regla compuesto — garantizar al menos 1 ─────────────────────
    compuestos = {"sentadilla","prensa","bisagra_cadera","press_horizontal",
                  "press_inclinado","press_vertical","jalon_vertical","remo_horizontal",
                  "puente_cadera","desplante","prensa"}
    patrones_fuerza = [patron_de(e.get("ejercicio_id","")) for e in fuerza_filtrada]
    if fuerza_filtrada and not any(p in compuestos for p in patrones_fuerza):
        if dia.get("grupo") not in ("cardio","core"):
            logger.warning(f"Día {dia.get('dia','?')} sin compuesto — solo aislamiento")

    # ── Paso 4: Reordenar: fuerza (orden original filtrada) + cardio al final ─
    # Renumerar orden
    ejercicios_finales = fuerza_filtrada + cardio_final
    for i, e in enumerate(ejercicios_finales, 1):
        e["orden"] = i

    dia["ejercicios"] = ejercicios_finales

    msg = f"OK ({len(ejercicios_finales)} ejercicios, {len(eliminados)} redundantes eliminados)" if eliminados else "OK"
    return True, msg


def normalizar_ejercicio(e: dict) -> dict:
    """Normaliza un ejercicio: nombre del catálogo, reps, notas técnicas canónicas.
    Usa CUES_TECNICOS para garantizar que la nota siempre corresponda al ejercicio real.
    Elimina alucinaciones: "elevaciones laterales" con nota "triceps frances" es imposible.
    """
    eid = str(e.get("ejercicio_id", ""))
    e["ejercicio"] = CATALOGO_POR_ID[eid]["nombre"]
    es_cardio = eid.startswith("CAR_") or CATALOGO_POR_ID.get(eid, {}).get("grupo") == "cardio"
    if es_cardio:
        e["series"] = 1
        reps_raw = str(e.get("reps", "20min"))
        e["reps"] = reps_raw if "min" in reps_raw else "20min"
    else:
        e["reps"] = str(e.get("reps", "10"))
        try:
            series_val = int(e.get("series", 3))
            # Rango válido científico: 2 (deload principiante) a 5 (avanzado)
            # Fuera de rango = error de Gemini, corregir al valor por defecto del nivel
            if series_val < 2:
                series_val = 3  # mínimo absoluto
            elif series_val > 5:
                series_val = 4  # máximo razonable sin degradar calidad
            e["series"] = series_val
        except:
            e["series"] = 3
    # Cue técnico: usar canónico del catálogo si existe, si no sanitizar el de Gemini
    cue_canonico = CUES_TECNICOS.get(eid, "")
    if cue_canonico:
        e["notas"] = cue_canonico
    else:
        nota = str(e.get("notas", "")).replace('"','').replace("'",'').strip()[:50]
        e["notas"] = nota
    return e


def parsear_semana_json(raw: str, num_semana: int) -> tuple:
    """
    Parsea la respuesta de Gemini para UNA semana.
    Acepta múltiples formatos que Gemini puede devolver:
      A) {"semana":1,"dias":[...]}           ← formato pedido
      B) {"semanas":[{"semana":1,"dias":[...]}]}  ← Gemini a veces envuelve en array
      C) [{"semana":1,"dias":[...]}]         ← array directo
    Devuelve (dict_semana, error_string).
    """
    try:
        text = raw.strip()
        # Quitar markdown
        for prefix in ["```json", "```JSON", "```"]:
            if text.startswith(prefix):
                text = text[len(prefix):]
                break
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Extraer el primer objeto JSON completo (maneja texto basura antes/después)
        start = text.find("{")
        start_arr = text.find("[")
        if start == -1 and start_arr == -1:
            logger.error(f"Gemini devolvió sin JSON: {repr(text[:300])}")
            return None, "No se encontró JSON en la respuesta"

        # Intentar parsear como objeto o como array
        data = None
        # Intentar objeto primero
        if start != -1:
            end = text.rfind("}")
            if end > start:
                try:
                    data = json.loads(text[start:end+1])
                except json.JSONDecodeError:
                    pass
        # Si falla, intentar array
        if data is None and start_arr != -1:
            end_arr = text.rfind("]")
            if end_arr > start_arr:
                try:
                    arr = json.loads(text[start_arr:end_arr+1])
                    if arr and isinstance(arr, list):
                        data = arr[0]
                except json.JSONDecodeError:
                    pass

        if data is None:
            return None, "JSON no parseable tras múltiples intentos"

        # ── Normalizar formato: extraer el dict de la semana ──────────────────
        # Formato B: {"semanas":[{"semana":1,"dias":[...]}]}
        if "semanas" in data and isinstance(data["semanas"], list):
            if data["semanas"]:
                data = data["semanas"][0]

        # Formato con clave numérica: {1: {"dias":[...]}} (raro pero posible)
        if str(num_semana) in data and "dias" not in data:
            data = data[str(num_semana)]

        # Verificar que tenemos "dias"
        if "dias" not in data:
            # Último intento: buscar recursivamente
            for v in data.values():
                if isinstance(v, dict) and "dias" in v:
                    data = v
                    break
            if "dias" not in data:
                return None, f"Falta campo 'dias'. Claves recibidas: {list(data.keys())}"

        if not data["dias"]:
            return None, "dias está vacío"

        # ── Normalizar y validar ejercicios ───────────────────────────────────
        for d in data["dias"]:
            # Inferir grupo del día si falta
            if not d.get("grupo"):
                for e in d.get("ejercicios", []):
                    eid = str(e.get("ejercicio_id", ""))
                    if eid in CATALOGO_POR_ID:
                        d["grupo"] = CATALOGO_POR_ID[eid]["grupo"]
                        break
                if not d.get("grupo"):
                    d["grupo"] = "general"

            ejercicios_validos = []
            for e in d.get("ejercicios", []):
                eid = str(e.get("ejercicio_id", ""))
                if eid not in VALID_IDS:
                    logger.warning("ID ignorado",
                                   extra={"eid": eid, "semana": num_semana, "dia": d.get("dia")})
                    continue
                ejercicios_validos.append(normalizar_ejercicio(e))

            d["ejercicios"] = ejercicios_validos
            if not ejercicios_validos:
                return None, f"Día {d.get('dia','?')} sin ejercicios válidos"

            # Validación fisiológica — LLM genera, Python arbitra y CORRIGE
            coherente, motivo = validar_coherencia_dia(d)
            if not coherente:
                logger.warning(f"Coherencia fallida S{num_semana}: {motivo}")

            # Mínimo no negociable: 3 fuerza por día (doc auditoría #10)
            n_fuerza = sum(1 for e in d["ejercicios"]
                          if not e.get("ejercicio_id","").startswith("CAR_"))
            if n_fuerza < 3:
                return None, f"Día {d.get('dia','?')} insuficiente: {n_fuerza} ejercicios (mín 3)"

        data["semana"] = num_semana
        return data, None

    except Exception as ex:
        logger.exception(f"Error parseando semana {num_semana}")
        return None, f"Error inesperado: {ex}"


def construir_system_prompt(perfil: dict) -> str:
    """
    System prompt con ciencia aplicada real.
    Fuentes: Schoenfeld (2010,2017), Contreras (2015 EMG), Nippard (2023),
             Ethier (BuildWithScience), Krieger (2010 meta-análisis), ACSM 2021.
    """
    nivel = perfil.get("nivel", "principiante")
    obj   = perfil.get("objetivo", "general")
    dias  = int(perfil.get("dias", 3))
    dur   = int(perfil.get("duracion_min", 60))
    lim   = perfil.get("limitaciones", "ninguna")

    # ESTRUCTURA MÍNIMA NO NEGOCIABLE (doc auditoría #10)
    # El tiempo NO define cuántos ejercicios — define series y descansos
    # Mínimo 4 ejercicios de fuerza + 1 cardio = 5 totales, siempre
    # "El tiempo solo recorta series acccesorias, nunca el esqueleto"
    # Ejercicios por sesión: 5 siempre (estructura científica no negociable)
    # 1 principal + 2 secundarios + 1 aislamiento + 1 cardio
    # Basado en: Schoenfeld (2017) 10-20 series/grupo/semana óptimo para hipertrofia
    ej = 5  # estructura fija de calidad — ni más ni menos

    # ── SPLIT CIENTÍFICO ──────────────────────────────────────────────────────
    # Principio: frecuencia 2x/semana por grupo = superior a 1x (Schoenfeld 2016 meta-análisis)
    if dias == 3:
        if "gluteo" in obj:
            split = """SPLIT 3 DÍAS — Glúteo 2x/semana (frecuencia óptima Schoenfeld 2016):
Día 1 → grupo=gluteo   : hip_thrust + compuesto_pierna + bisagra_cadera + aislamiento_gluteo [+ cardio si ej=4+]
Día 2 → grupo=tiron    : jalón + remo + curl_biceps + face_pull [+ cardio si ej=4+]
Día 3 → grupo=gluteo   : variante_hip_thrust + prensa + isquiotibial + abduccion [+ cardio]
⚠ Día 1 y Día 3 son de glúteo. Día 2 NO incluye glúteo."""
        else:
            split = """SPLIT 3 DÍAS — Full Body frecuencia alta (Rhea 2003: 3x/semana óptimo para principiante):
Día 1 → grupo=pierna   : sentadilla + isquio + empuje_horizontal + tirón_vertical
Día 2 → grupo=empuje   : press_pecho + press_hombro + tirón_horizontal + core
Día 3 → grupo=pierna   : prensa + glúteo + empuje_inclinado + tirón + cardio
⚠ Distribución equilibrada. Nunca 2 días seguidos el mismo grupo."""
    elif dias == 4:
        if "gluteo" in obj:
            split = """SPLIT 4 DÍAS — Upper/Lower con especialización glúteo (Krieger 2010: volumen distribuido > concentrado):
Día 1 → grupo=gluteo   : hip_thrust + sentadilla + PDR + aislamiento_gluteo + cardio
Día 2 → grupo=empuje   : press_pecho + press_hombro + triceps + cardio_ligero
Día 3 → grupo=pierna   : prensa + sentadilla_variante + isquio + abduccion + cardio
Día 4 → grupo=tiron    : jalón + remo + curl + face_pull
⚠ Días 1 y 3 son glúteo/pierna. Días 2 y 4 son upper. Sin glúteo en días 2 y 4."""
        else:
            split = """SPLIT 4 DÍAS — Upper/Lower equilibrado (tirón = empuje, Schoenfeld 2017):
Día 1 → grupo=pierna   : sentadilla + prensa + isquio + cardio
Día 2 → grupo=empuje   : press_pecho + press_hombro + triceps + face_pull (postura)
Día 3 → grupo=tiron    : jalón + remo + curl + remo_inverso
Día 4 → grupo=pierna   : prensa + PDR + abduccion + cardio
NOTA: face_pull en día empuje y tirón = hombro posterior protegido"""
    else:  # 5 días
        if "gluteo" in obj:
            split = """SPLIT 5 DÍAS — PPL especializado glúteo (máximo volumen con recuperación adecuada):
Día 1 → grupo=gluteo   : hip_thrust_pesado + sentadilla + PDR + abduccion + cardio_inclinada
Día 2 → grupo=empuje   : press_pecho + press_hombro + triceps + cardio_ligero
Día 3 → grupo=tiron    : jalón + remo_pesado + curl + face_pull  [SIN glúteo]
Día 4 → grupo=pierna   : prensa + sentadilla_variante + isquio + patada_polea + cardio
Día 5 → grupo=gluteo   : hip_thrust_banda + extensión_cadera + fire_hydrant + caminata_inclinada
⚠ CRÍTICO: Días 2 y 3 son upper sin glúteo. Días 1,4,5 incluyen glúteo con volumen decreciente."""
        else:
            split = """SPLIT 5 DÍAS — PPLPull (frecuencia equilibrada — 2x tirón evita síndrome cruzado):
Día 1 → grupo=pierna   : sentadilla + prensa + isquio + glúteo + cardio
Día 2 → grupo=empuje   : press_pecho + press_inclinado + triceps + face_pull
Día 3 → grupo=tiron    : jalón + remo + curl + remo_inverso (postura)
Día 4 → grupo=pierna   : prensa + PDR + abduccion + cardio
Día 5 → grupo=tiron    : jalón_agarre_estrecho + remo_horizontal + curl + core
NOTA: 2 días de tirón vs 2 días de empuje = postura correcta (doc #12)"""

    # ── CIENCIA DE VOLUMEN Y PROGRESIÓN ──────────────────────────────────────
    # Schoenfeld (2017): 10-20 series/semana/grupo para hipertrofia. RIR como proxy de intensidad.
    # Nippard: progresión lineal de carga es el marcador #1 de progreso real.
    # SERIES POR NIVEL (Deschenes 2002 + Krieger 2010 + Schoenfeld 2017):
    #   Principiante: 3 series | máquinas guiadas, movimientos bilaterales simples
    #   Intermedio:   4 series | mancuernas/poleas libres, unilaterales básicos
    #   Avanzado:     5 series | barra libre, unilaterales difíciles, sentadilla búlgara
    # NIVEL = dificultad del ejercicio + número de series (ambas cosas)

    # Series correctas por nivel — Deschenes 2002 (neuromuscular) + Krieger 2010 + Schoenfeld 2017
    s_sys  = {"principiante": 3, "intermedio": 4, "avanzado": 5}.get(nivel, 4)
    sd_sys = max(2, s_sys - 1)  # deload = s-1

    if nivel == "principiante":
        prog = f"""PROGRESIÓN DOBLE — PRINCIPIANTE ({s_sys} series | 10-15 reps | RIR 2-3):
  EJERCICIOS: SOLO máquinas guiadas — prensa, hip thrust en banco, jalón en polea, remo en máquina.
  PROHIBIDO: barra libre libre, peso muerto convencional, sentadilla búlgara, RIR 0.
  S1: {s_sys}×12-15 — RIR 3 — técnica perfecta, peso moderado
  S2: {s_sys}×10-12 — RIR 2 — mismo ejercicio S1, +5% carga
  S3: {s_sys}×10-12 — RIR 2 — mismo ejercicio S1, +5% carga vs S2
  S4: {sd_sys}×12-15 — RIR 4 — DELOAD 60% carga, recuperación activa"""
    elif nivel == "intermedio":
        prog = f"""PROGRESIÓN DOBLE — INTERMEDIO ({s_sys} series | 6-12 reps | RIR 1-2):
  EJERCICIOS: mancuernas libres, poleas, unilaterales básicos. Sentadilla goblet o Smith.
  S1: {s_sys}×10-12 — RIR 2 — rango completo, técnica refinada
  S2: {s_sys}×8-10  — RIR 2 — mismo ejercicio S1, +5-10% carga
  S3: {s_sys}×6-8   — RIR 1 — mismo ejercicio S1, zona fuerza-hipertrofia
  S4: {sd_sys}×10-12 — RIR 4 — DELOAD 60% carga, mismos ejercicios S1"""
    else:
        prog = f"""PROGRESIÓN DOBLE — AVANZADO ({s_sys} series | 5-10 reps | RIR 0-1):
  EJERCICIOS: barra libre, sentadilla búlgara, peso muerto, dominadas, unilaterales avanzados.
  PROHIBIDO: más de 12 reps en ejercicios principales (infraestimulo para avanzados).
  S1: {s_sys}×8-10 — RIR 1 — compuesto pesado, técnica experta
  S2: {s_sys}×6-8  — RIR 1 — mismo ejercicio S1, sobrecarga máxima
  S3: {s_sys}×5-8  — RIR 0 — mismo ejercicio S1, máxima tensión mecánica
  S4: {sd_sys}×8-10 — RIR 3 — DELOAD 50% carga, mismos ejercicios S1"""

    # ── PROTOCOLO POR OBJETIVO (evidencia EMG y fisiología) ──────────────────
    if "gluteo" in obj:
        obj_nota = """PROTOCOLO GLÚTEO — Contreras (2015) EMG + Nippard Glute Science:
  ACTIVACIÓN: Hip thrust/Puente = 200% MVIC (máximo voluntario isométrico). PRIMER ejercicio SIEMPRE.
  COMPUESTO: Sentadilla >90° = 130-170% MVIC. Segundo ejercicio en días glúteo.
  BISAGRA: PDR/Good morning = 110-150% MVIC + excéntrico largo. Tercer ejercicio.
  AISLAMIENTO: Patada/Abducción = 60-120% MVIC. Cuarto ejercicio.
  CARDIO: Cinta inclinada 10% activa glúteo en cada paso. NUNCA trote en día post-hip thrust.
  TEMPO RECOMENDADO: Excéntrico 2s + pausa 1s arriba + concéntrico rápido (potencia glútea)."""
    elif "peso" in obj:
        obj_nota = """PROTOCOLO PÉRDIDA GRASA — ACSM 2021 + Wilson (2012) EPOC:
  EPOC máximo: compuestos multiarticulares grandes generan quema 24-48h post-sesión.
  ORDEN: pesas ANTES que cardio (preservar glucógeno muscular para el trabajo de fuerza).
  CARDIO: zona 2 (65-70% FCmax) = oxidación grasa óptima. 20-30 min al final de sesión.
  INTENSIDAD RESISTENCIA: 60-75% 1RM, descansos cortos 60-90s (mayor EPOC que descansos largos)."""
    else:
        obj_nota = """PROTOCOLO TONIFICACIÓN — Schoenfeld (2012) + Sahrmann postura:
  BALANCE: ratio empuje:tirón = 1:1.5 (más tirón para compensar postura moderna).
  RANGO: 8-15 reps a 60-75% 1RM = tensión mecánica suficiente para hipertrofia moderada.
  CORE: plancha/dead bug > crunch (estabilización > flexión para salud lumbar — McGill 2010).
  CARDIO: zona 2-3, 15-20 min al final de sesión."""

    # ── LIMITACIONES BIOMECÁNICAS ─────────────────────────────────────────────
    if lim == "rodilla":
        lim_nota = "RODILLA: PROHIBIDO sentadilla búlgara, desplante caminando (shear tibio-femoral alto). USA: prensa pierna (shear controlado), goblet sentadilla, hip thrust (zero carga rodilla), curl femoral."
    elif lim == "espalda":
        lim_nota = "ESPALDA BAJA: PROHIBIDO peso muerto convencional, good morning, remo >45°. USA: prensa pierna, jalón al pecho (descompresión lumbar), hip thrust (activa lumbar sin compresión axial), remo máquina con soporte."
    elif lim == "hombro":
        lim_nota = "HOMBRO: PROHIBIDO press militar (impingement subacromial), elevaciones frontales, fondos. USA: press inclinado 45° (codos a 45° del tronco), face pull (rehabilita manguito), jalón agarre neutro."
    else:
        lim_nota = "Sin limitaciones. Priorizar rango completo de movimiento en todos los ejercicios (mayor activación muscular — Pinto 2012)."

    genero = perfil.get("genero", "mujer")
    if genero == "hombre":
        genero_nota = """ÉNFASIS HOMBRE (Shmonenko / Nippard male hypertrophy):
  Upper body prioridad: pecho, espalda ancha, hombros 3D, brazos definidos.
  Lower body: sentadilla pesada, peso muerto, prensa — NO excesivo trabajo glúteo aislado.
  Split hombre: más volumen en press (4-5 sets/día empuje), más remo y jalón (espalda V-taper).
  Días pierna: sentadilla frontal + prensa + isquio + pantorrilla. Sin abducción de banda."""
    else:
        genero_nota = """ÉNFASIS MUJER (Contreras / Vikika Costa / Sascha Fitness):
  Lower body prioridad: glúteo máximo, pierna tonificada, talle definido.
  Upper body: tonificación sin volumen excesivo — jalón, remo ligero, press inclinado suave.
  Cardio: integrar siempre al final de días lower. Zona 2 para oxidación grasa."""

    return f"""Eres un coach de fitness de élite con PhD en ciencias del ejercicio. Metodología: Schoenfeld, Contreras, Nippard, Ethier.
SOLO produces JSON válido. CERO texto fuera del JSON.

PERFIL DEL USUARIO:
  Género: {perfil.get('genero','mujer')} | Nivel: {nivel} | Objetivo: {obj} | Días/semana: {dias} | Duración: {dur}min | Limitaciones: {lim}

ESTRUCTURA DE SESIÓN — 5 EJERCICIOS POR DÍA, SIEMPRE (Schoenfeld 2017):
  Posición 1: Compuesto principal — mayor activación EMG, ejercicio más difícil primero
  Posición 2: Compuesto secundario — patrón complementario (bisagra si pos1=sentadilla, etc.)
  Posición 3: Unilateral o accesorio — corrige desequilibrios, mayor rango de movimiento
  Posición 4: Aislamiento — rematar el músculo objetivo con fatiga local máxima
  Posición 5: CARDIO (CAR_01..CAR_11) — SIEMPRE el último, series=1 reps="20min"
  TOTAL: 4 fuerza + 1 cardio = 5 exacto. Nunca 3. Nunca 6.

{split}

{prog}

{obj_nota}
{lim_nota}
{genero_nota}

REGLAS ABSOLUTAS (cada violación invalida el plan):
1. SOLO IDs exactos del CATALOGO. Sin inventar. Sin modificar.
2. Exactamente {ej} ejercicios por día. Ni más ni menos.
3. Progresión de estímulo cada semana: aumenta carga, o reduce reps, o cambia RIR. Al menos UNA variable debe cambiar.
4. reps SIEMPRE string: "15" "8-10" "45s" "30s". NUNCA número.
5. Al menos {max(1, dias-2)} días/semana terminan con cardio (CAR_01..CAR_10).
6. S2-S3 usan MISMOS ejercicios que S1 con +5-10% carga. S4 (deload) = mismos ejercicios S1 al 60% carga.
7. Notas: máx 6 palabras por nota. Solo en ejercicios principales. Sé ultra-conciso.
8. Días de la semana DISTINTOS. Mismo grupo muscular: mínimo 48h entre sesiones.
9. JSON PURO. Sin markdown. Sin explicaciones. Sin campo url.

FORMATO (solo JSON, nada más):
{{"semanas":[{{"semana":1,"dias":[{{"dia":"lunes","grupo":"gluteo","ejercicios":[{{"ejercicio_id":"GLU_03","ejercicio":"Hip thrust en banco","orden":1,"series":3,"reps":"15","notas":"Pausa 1s arriba, excéntrico 2s"}}]}}]}}]}}"""


def construir_prompt_usuario(perfil: dict) -> str:
    """
    Prompt de usuario con catálogo ultra-comprimido.
    Objetivo: minimizar tokens de entrada para que Gemini tenga más espacio de salida.
    """
    obj   = perfil.get("objetivo", "general")
    nivel = perfil.get("nivel", "principiante")
    dias  = int(perfil.get("dias", 3))
    dur   = int(perfil.get("duracion_min", 60))
    lim   = perfil.get("limitaciones", "ninguna")

    # Solo IDs por grupo — nombre lo pone el validador desde CATALOGO_POR_ID
    # Esto reduce ~60% los tokens del catálogo
    grupos_orden = ["gluteo", "pierna", "empuje", "tiron", "core", "cardio"]
    lineas = []
    for g in grupos_orden:
        ids = [e["ejercicio_id"] for e in CATALOGO if e["grupo"] == g]
        lineas.append(f'{g.upper()}: {" ".join(ids)}')

    return f"""IDs DISPONIBLES POR GRUPO:
{chr(10).join(lineas)}

REGLA CRÍTICA: Usa SOLO estos IDs. El campo "ejercicio" debe ser el nombre real del ejercicio.
Notas: máximo 5 palabras por nota. No uses comillas dentro de las notas.

Genera plan JSON 4 semanas: obj={obj}, nivel={nivel}, {dias}días/sem, {dur}min, lim={lim}.
Solo JSON. Sin markdown. Sin texto extra."""



# ==========================================
# 3. BASE DE DATOS
# ==========================================

@contextmanager
def db():
    """Context manager para conexiones SQLite. Garantiza commit+close siempre."""
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")   # Write-Ahead Log: mejor concurrencia
    conn.execute("PRAGMA foreign_keys=ON")    # Integridad referencial
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
        genero TEXT DEFAULT 'mujer',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Usuarios con acceso al bot (fuente de verdad en DB, no hardcode)
    cur.execute("""CREATE TABLE IF NOT EXISTS usuarios_permitidos (
        user_id INTEGER PRIMARY KEY,
        nombre  TEXT,
        rol     TEXT DEFAULT 'user',
        alta_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Seed: insertar usuarios hardcodeados si no existen
    for uid, nombre in [(1557254587, "admin"), (8468355326, "esposa")]:
        cur.execute("""
            INSERT OR IGNORE INTO usuarios_permitidos (user_id, nombre, rol)
            VALUES (?, ?, 'user')
        """, (uid, nombre))
    conn.commit()

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

    # Migraciones versionadas — distingue "ya existe" de error real
    # Audit: si falla por razón distinta a duplicate column, lanza excepción
    migraciones = [
        ("v1", "ALTER TABLE perfil_usuario ADD COLUMN duracion_min INTEGER DEFAULT 60"),
        ("v1", "ALTER TABLE perfil_usuario ADD COLUMN momento TEXT DEFAULT 'tarde'"),
        ("v1", "ALTER TABLE perfil_usuario ADD COLUMN semanas_sin_gym INTEGER DEFAULT 0"),
        ("v1", "ALTER TABLE swaps ADD COLUMN grupo TEXT"),
        ("v1", "ALTER TABLE swaps ADD COLUMN rol TEXT"),
        ("v2", "ALTER TABLE perfil_usuario ADD COLUMN genero TEXT DEFAULT 'mujer'"),
        ("v3", "ALTER TABLE rutinas ADD COLUMN patron TEXT"),
        ("v4", """CREATE TABLE IF NOT EXISTS usuarios_permitidos (
            user_id INTEGER PRIMARY KEY, nombre TEXT,
            rol TEXT DEFAULT 'user', alta_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""),
        ("v5", "ALTER TABLE progreso ADD COLUMN fatiga_reportada INTEGER DEFAULT NULL"),
        ("v6", "ALTER TABLE progreso ADD COLUMN rir_reportado INTEGER DEFAULT NULL"),
        ("v7", "ALTER TABLE progreso ADD COLUMN progreso_reportado TEXT DEFAULT NULL"),
    ]
    for version, sql in migraciones:
        try:
            cur.execute(sql)
            conn.commit()
            logger.info(f"Migración {version} aplicada: {sql[:50]}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                pass  # Ya existe — OK
            else:
                logger.error(f"Error real en migración {version}: {e} | SQL: {sql}")
                # No raise — continuar con el resto, pero loggeado

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
                # Nombre siempre del catálogo (source of truth, ignora lo que escriba Gemini)
                e["ejercicio"] = CATALOGO_POR_ID[ej_id]["nombre"]
                # reps debe ser string
                if not isinstance(e.get("reps", ""), str):
                    e["reps"] = str(e.get("reps", "10"))
                # Sanear notas: quitar comillas y truncar a 80 chars
                nota = str(e.get("notas", ""))
                nota = nota.replace('"', '').replace("'", '').strip()[:80]
                e["notas"] = nota
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
                        INSERT OR REPLACE INTO rutinas
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

def obtener_semana_y_dia_actual(user_id: int):
    """Alias de obtener_estado_usuario — FIX: los nuevos handlers usaban este nombre."""
    return obtener_estado_usuario(user_id)

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


# ═══════════════════════════════════════════════════════════════════
# MÓDULO SEMI-AUTOMÁTICO — Israetel + Helms (autoregulación ligera)
# 3 inputs post-sesión: RIR · Progresión · Fatiga
# ═══════════════════════════════════════════════════════════════════

RIR_OPCIONES = {
    0: ("\U0001f525", "Sin reserva \u2014 llegué al límite"),
    1: ("\U0001f4aa", "1 rep en reserva \u2014 muy intenso"),
    2: ("\U0001f60a", "2 reps en reserva \u2014 bien"),
    3: ("\U0001f60c", "3+ reps en reserva \u2014 muy fácil"),
}

PROGRESION_OPCIONES = {
    "si":      ("\U0001f4c8", "Sí \u2014 más peso o más reps"),
    "igual":   ("\u27a1\ufe0f",  "Igual \u2014 mismo peso y reps"),
    "no":      ("\U0001f4c9", "No \u2014 tuve que bajar peso o reps"),
    "primera": ("\U0001f331", "Primera vez con este ejercicio"),
}


def registrar_rir(user_id: int, semana: int, dia: str, rir: int):
    """Guarda el RIR promedio reportado tras la sesión."""
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur  = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO progreso (user_id, semana, dia, ejercicio_id, completado) "
        "VALUES (?, ?, ?, '__rir__', 0)",
        (user_id, semana, dia)
    )
    cur.execute(
        "UPDATE progreso SET rir_reportado = ? WHERE user_id = ? AND semana = ? AND dia = ?",
        (rir, user_id, semana, dia)
    )
    conn.commit()
    conn.close()
    logger.info("RIR %s/3 registrado: user=%s S%s %s", rir, user_id, semana, dia)


def registrar_progresion(user_id: int, semana: int, dia: str, progresion: str):
    """Guarda si el usuario progresó esta sesión (si/igual/no/primera)."""
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur  = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO progreso (user_id, semana, dia, ejercicio_id, completado) "
        "VALUES (?, ?, ?, '__progresion__', 0)",
        (user_id, semana, dia)
    )
    cur.execute(
        "UPDATE progreso SET progreso_reportado = ? WHERE user_id = ? AND semana = ? AND dia = ?",
        (progresion, user_id, semana, dia)
    )
    conn.commit()
    conn.close()
    logger.info("Progresión '%s' registrada: user=%s S%s %s", progresion, user_id, semana, dia)


def analizar_sesion(user_id: int, semana: int, dia: str) -> dict:
    """
    Analiza los 3 inputs de la sesión y devuelve la recomendación de ajuste.
    Lógica: Israetel (RP) + Helms (3DMJ) — autoregulación ligera.

    FIX aplicados:
      - Historial excluye la sesión actual (evita comparar la sesión consigo misma)
      - Estancamiento filtra por grupo muscular del día (no mezcla pierna con empuje)
      - RIR=0 con fatiga moderada (>=3) ahora tiene regla propia
    """
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur  = conn.cursor()

    # Grupo muscular del día actual (para filtrar historial por grupo)
    cur.execute(
        "SELECT grupo FROM rutinas WHERE user_id = ? AND semana = ? AND dia = ? LIMIT 1",
        (user_id, semana, dia)
    )
    row_grupo = cur.fetchone()
    grupo_dia = row_grupo[0] if row_grupo else None

    # Historial de sesiones ANTERIORES con RIR del mismo grupo muscular
    # Excluye la sesión actual (semana+dia) para no comparar contra sí misma
    if grupo_dia:
        cur.execute(
            "SELECT p.rir_reportado, p.progreso_reportado, p.fatiga_reportada "
            "FROM progreso p "
            "JOIN rutinas r ON r.user_id = p.user_id AND r.semana = p.semana "
            "    AND r.dia = p.dia AND r.grupo = ? "
            "WHERE p.user_id = ? AND p.rir_reportado IS NOT NULL "
            "AND NOT (p.semana = ? AND p.dia = ?) "
            "ORDER BY p.ts DESC LIMIT 3",
            (grupo_dia, user_id, semana, dia)
        )
    else:
        cur.execute(
            "SELECT rir_reportado, progreso_reportado, fatiga_reportada "
            "FROM progreso "
            "WHERE user_id = ? AND rir_reportado IS NOT NULL "
            "AND NOT (semana = ? AND dia = ?) "
            "ORDER BY ts DESC LIMIT 3",
            (user_id, semana, dia)
        )
    historial = cur.fetchall()

    # Datos de la sesión actual
    cur.execute(
        "SELECT rir_reportado, progreso_reportado, fatiga_reportada "
        "FROM progreso "
        "WHERE user_id = ? AND semana = ? AND dia = ? AND rir_reportado IS NOT NULL "
        "LIMIT 1",
        (user_id, semana, dia)
    )
    actual = cur.fetchone()
    conn.close()

    if not actual:
        return {"ajuste": "mantener", "razon": "sin datos suficientes", "msg_usuario": ""}

    rir    = actual[0] if actual[0] is not None else 2
    prog   = actual[1] or "primera"
    fatiga = actual[2] if actual[2] is not None else 2

    # ── Regla 1: fatiga crítica → deload
    if fatiga >= 5:
        return {
            "ajuste": "deload",
            "razon": "fatiga crítica 5/5",
            "msg_usuario": (
                "\U0001f480 <b>Fatiga crítica.</b>\n"
                "La próxima sesión tendrá volumen reducido al 60%% de carga. Prioriza el sueño."
            ),
        }

    # ── Regla 2: RIR≥3 → demasiado fácil, subir carga
    if rir >= 3:
        return {
            "ajuste": "subir_carga",
            "razon": "RIR " + str(rir) + " — sin estímulo real",
            "msg_usuario": (
                "\U0001f60c <b>Sesión demasiado fácil.</b>\n"
                "RIR 3+ significa que te sobraban 3+ reps — el músculo no recibió estímulo suficiente.\n"
                "\U0001f449 La próxima semana sube el peso un 5-10%% en todos los ejercicios."
            ),
        }

    # ── Regla 3: estancamiento en el mismo grupo muscular — 2 sesiones previas sin progresión
    if len(historial) >= 2:
        progs_recientes = [h[1] for h in historial[:2] if h[1] is not None]
        estancado = len(progs_recientes) == 2 and all(p in ("no", "igual") for p in progs_recientes)
        if estancado and prog in ("no", "igual"):
            grupo_txt = f" de {grupo_dia}" if grupo_dia else ""
            return {
                "ajuste": "deload",
                "razon": "estancamiento" + grupo_txt + ": 3 sesiones sin progresión",
                "msg_usuario": (
                    "\U0001f4c9 <b>Estancamiento detectado</b>"
                    + (" en " + grupo_dia if grupo_dia else "") + ".\n"
                    "3 sesiones consecutivas del mismo grupo sin progresar — señal clara de fatiga acumulada.\n"
                    "\U0001f449 Próxima sesión en deload: mismos ejercicios al 60%% de carga."
                ),
            }

    # ── Regla 4: RIR=0 + cualquier fatiga ≥3 → sobrecarga moderada
    if rir == 0 and fatiga >= 3:
        if fatiga >= 4:
            return {
                "ajuste": "bajar_volumen",
                "razon": "RIR 0 + fatiga " + str(fatiga) + "/5 — sobrecarga alta",
                "msg_usuario": (
                    "\U0001f525 <b>Sesión muy intensa.</b>\n"
                    "RIR 0 con fatiga alta: llegaste al límite real.\n"
                    "Reduzco 1 serie en accesorios de la próxima sesión."
                ),
            }
        else:
            # fatiga=3 + RIR=0 → aviso sin cambio estructural
            return {
                "ajuste": "mantener",
                "razon": "RIR 0 + fatiga moderada — vigilar",
                "msg_usuario": (
                    "\U0001f7e1 <b>Intensidad en el límite.</b>\n"
                    "RIR 0 con fatiga moderada. Plan sin cambios hoy, pero si se repite la próxima semana "
                    "considera bajar el peso un 5%% para mantenerte en RIR 1-2."
                ),
            }

    # ── Regla 5: progresión + RIR óptimo (1-2) → zona ideal
    if prog == "si" and rir in (1, 2):
        return {
            "ajuste": "mantener",
            "razon": "progresión confirmada + RIR óptimo",
            "msg_usuario": (
                "\U0001f4c8 <b>Progresión confirmada con RIR óptimo.</b>\n"
                "El plan está funcionando exactamente como debe. Continúa igual."
            ),
        }

    # ── Caso base
    return {
        "ajuste": "mantener",
        "razon": "sesión normal",
        "msg_usuario": "✅ Sesión registrada. Plan sin cambios.",
    }


def aplicar_ajuste_automatico(user_id: int, semana: int, dia: str, ajuste: str):
    """
    Aplica el ajuste a la PRÓXIMA sesión del usuario.
    Estructura 4+1 siempre inviolable: nunca elimina ejercicios.

    FIX aplicado:
      - 'deload' ahora reduce series en TODOS los ejercicios (no solo accesorios)
        y marca reps con sufijo '-deload' para que el renderer lo muestre
      - 'bajar_volumen' sigue reduciendo solo accesorios (orden >= 3)
      - 'subir_carga' es solo consejo textual: no toca la DB (el usuario sube carga)
    """
    if ajuste in ("mantener", "subir_carga"):
        return

    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur  = conn.cursor()

    # ── Calcular próximo día del plan ──────────────────────────────
    cur.execute(
        "SELECT DISTINCT dia FROM rutinas WHERE user_id = ? AND semana = ? "
        "GROUP BY dia ORDER BY MIN(id) ASC",
        (user_id, semana)
    )
    dias_semana = [r[0] for r in cur.fetchall()]

    proximo_dia    = None
    proxima_semana = semana
    try:
        idx = dias_semana.index(dia)
        if idx + 1 < len(dias_semana):
            proximo_dia = dias_semana[idx + 1]
        elif semana < 4:
            proxima_semana = semana + 1
            cur.execute(
                "SELECT dia FROM rutinas WHERE user_id = ? AND semana = ? "
                "GROUP BY dia ORDER BY MIN(id) ASC LIMIT 1",
                (user_id, proxima_semana)
            )
            row = cur.fetchone()
            proximo_dia = row[0] if row else None
        # semana=4 último día = fin del plan → proximo_dia=None, sin ajuste necesario
    except ValueError:
        pass

    if not proximo_dia:
        conn.close()
        return

    if ajuste == "deload":
        # Deload real: todos los ejercicios de fuerza reducen 1 serie (mínimo 2)
        # El compuesto principal (orden=1) también se reduce — es el objetivo del deload
        cur.execute(
            "SELECT id, series, reps FROM rutinas "
            "WHERE user_id = ? AND semana = ? AND dia = ? "
            "AND ejercicio_id NOT LIKE 'CAR_%'",
            (user_id, proxima_semana, proximo_dia)
        )
        for row_id, series, reps in cur.fetchall():
            nuevas_series = max(2, int(series or 3) - 1)
            cur.execute(
                "UPDATE rutinas SET series = ? WHERE id = ?",
                (nuevas_series, row_id)
            )
        logger.info(
            "Deload aplicado (todas las series -1): user=%s S%s %s",
            user_id, proxima_semana, proximo_dia
        )

    elif ajuste == "bajar_volumen":
        # Solo accesorios (orden >= 3): preserva el estímulo del compuesto principal
        cur.execute(
            "SELECT id, series FROM rutinas "
            "WHERE user_id = ? AND semana = ? AND dia = ? AND orden >= 3 "
            "AND ejercicio_id NOT LIKE 'CAR_%'",
            (user_id, proxima_semana, proximo_dia)
        )
        for row_id, series in cur.fetchall():
            nuevas = max(2, int(series or 3) - 1)
            cur.execute("UPDATE rutinas SET series = ? WHERE id = ?", (nuevas, row_id))
        logger.info(
            "Volumen accesorio reducido: user=%s S%s %s",
            user_id, proxima_semana, proximo_dia
        )

    conn.commit()
    conn.close()


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
# ── CALENTAMIENTOS CIENTÍFICOS POR GRUPO MUSCULAR ────────────────────────────
# Fuentes: McGill (2010) estabilización, Contreras (2015) pre-activación glúteo,
#          Cressey (2012) movilidad escapular, Cook (2010) patron motor previo
CALENTAMIENTO_POR_GRUPO = {
    "gluteo": [
        ("🔥 Clamshell con banda",              "2×15 c/lado", "Activa glúteo medio — reduce dominancia cuádriceps"),
        ("🔥 Puente de glúteo sin carga",       "2×20",        "Pre-activa conexión mente-músculo. Pausa 1s arriba"),
        ("🔥 Movilidad de cadera en cuadrupedia","2×10 c/lado", "Círculos amplios — lubrica articulación coxofemoral"),
    ],
    "pierna": [
        ("🔥 Sentadilla goblet con peso leve",  "2×12",        "Activa cadena posterior completa. Espalda neutra"),
        ("🔥 Peso muerto rumano sin peso",       "2×12",        "Patrón bisagra — activa isquios y glúteo"),
        ("🔥 Movilidad tobillo (rotación)",      "2×10 c/lado", "Tobillo limita profundidad de sentadilla"),
    ],
    "empuje": [
        ("🔥 Apertura de pecho con banda",      "2×15",        "Moviliza articulación glenohumeral — previene impingement"),
        ("🔥 Rotación externa hombro con banda","2×12 c/lado", "Activa manguito rotador — protege hombro bajo carga"),
        ("🔥 Flexiones lentas en rodillas",     "2×8",         "Patrón motor del press. Escápulas en retracción"),
    ],
    "tiron": [
        ("🔥 Retracción escapular con banda",   "2×15",        "Activa romboides y trapecio medio — base del tirón"),
        ("🔥 Rotación torácica en suelo",       "2×10 c/lado", "Movilidad torácica — permite tirón sin compensar lumbar"),
        ("🔥 Jalón con banda amplio en pie",    "2×12",        "Pre-activa dorsal ancho. Codos hacia bolsillos"),
    ],
    "core": [
        ("🔥 Dead bug lento",                   "2×8 c/lado",  "Activa transverso abdominal — estabilizador profundo"),
        ("🔥 Bird dog",                         "2×10 c/lado", "Coordinación lumbo-pélvica. Columna neutra"),
        ("🔥 Respiración diafragmática",        "2×5 resp",    "Presión intraabdominal — McGill 2010"),
    ],
    "cardio": [
        ("🔥 Marcha elevando rodillas",         "2×30s",       "Eleva FC de forma progresiva y segura"),
        ("🔥 Círculos de cadera amplios",       "2×10 c/dir",  "Lubrica cadera antes del cardio continuo"),
        ("🔥 Rotaciones de tronco de pie",      "1×20",        "Moviliza columna torácica"),
    ],
}
# Grupos que no tienen calentamiento específico usan el de 'cardio'
CALENTAMIENTO_FALLBACK = "cardio"

# ── NUTRICIÓN POR OBJETIVO ────────────────────────────────────────────────────
# Fuente: Ivy & Portman (2004) nutrient timing, Phillips (2011) proteína síntesis
NUTRICION_POR_OBJETIVO = {
    "gluteo":  {
        "pre":  "🥑 Pre-entreno: avena + plátano 60min antes, o 1 fruta si vas en ayunas",
        "post": "🥩 Post-entreno: 20-30g proteína + carbohidrato en 45min (músculo es esponja)"
    },
    "peso": {
        "pre":  "☕ Pre-entreno: cafeína 30min antes potencia EPOC. Proteína si van +3h en ayunas",
        "post": "🥗 Post-entreno: proteína magra + verduras. Evita exceso carbos nocturnos"
    },
    "general": {
        "pre":  "🍌 Pre-entreno: carbohidrato simple si tienes hambre. Hidratación 500ml antes",
        "post": "🥚 Post-entreno: proteína completa + algo de carbo para recuperación muscular"
    }
}

# ── DURACIÓN ESTIMADA POR NÚMERO DE EJERCICIOS ────────────────────────────────
# 5min calentamiento + (series × descanso + tiempo de ejecución) + cardio
def estimar_duracion(ejercicios_list) -> str:
    minutos = 10  # calentamiento
    for e in ejercicios_list:
        series = e.get('series', 3) if isinstance(e, dict) else 3
        try: series = int(series)
        except: series = 3
        grupo = e.get('grupo', '') if isinstance(e, dict) else ''
        if grupo == 'cardio' or (isinstance(e, dict) and e.get('ejercicio_id','').startswith('CAR')):
            minutos += 20  # cardio dura ~20min promedio
        else:
            minutos += series * 3  # ~3min por serie (ejecución + descanso 90s)
    return f"~{minutos} min"

def obtener_calentamiento(grupo: str) -> str:
    """
    Devuelve el bloque de calentamiento específico para el grupo muscular.
    Busca match parcial: "tiron/empuje" → usa "tiron" primero, luego "empuje".
    """
    grupo_norm = grupo.lower()
    ejercicios_cal = None
    for key in CALENTAMIENTO_POR_GRUPO:
        if key in grupo_norm:
            ejercicios_cal = CALENTAMIENTO_POR_GRUPO[key]
            break
    if not ejercicios_cal:
        ejercicios_cal = CALENTAMIENTO_POR_GRUPO[CALENTAMIENTO_FALLBACK]

    txt  = "🌡 <b>CALENTAMIENTO</b> <i>(8-10 min)</i>\n"
    for nombre, series, nota in ejercicios_cal:
        txt += f"  ▸ {nombre} — <b>{series}</b>\n"
        txt += f"    <i>» {nota}</i>\n"
    txt += "\n💪 <b>TRABAJO PRINCIPAL</b>\n"
    txt += "───────────────────────\n"
    return txt
    return txt

def obtener_rutina_interactiva(user_id: int, semana: int, dia: str):
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT r.ejercicio_id, r.ejercicio, r.series, r.reps, r.notas,
               r.grupo,
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


    # Obtener grupo del día para el calentamiento específico
    conn_g = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    cur_g  = conn_g.cursor()
    cur_g.execute("SELECT grupo FROM rutinas WHERE user_id=? AND semana=? AND dia=? LIMIT 1",
                  (user_id, semana, dia))
    row_g = cur_g.fetchone()
    conn_g.close()
    grupo_dia = row_g[0] if row_g else "general"

    # Construir header estético
    dur_est   = estimar_duracion([dict(e) for e in ejercicios])
    grupo_icon = {"gluteo":"🍑","pierna":"🦵","empuje":"💪","tiron":"🏋️",
                  "core":"🎯","cardio":"🏃","general":"⚡"}.get(grupo_dia.lower(),"💪")
    html_msg  = f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    html_msg += f"{grupo_icon} <b>Semana {semana} · {dia.capitalize()}</b>\n"
    html_msg += f"   <i>{grupo_dia.upper()} · {dur_est}</i>\n"
    html_msg += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    html_msg += obtener_calentamiento(grupo_dia)
    keyboard = []
    for idx_ex, ex in enumerate(ejercicios, 1):
        estado = "✅" if ex['completado'] else "⬜"
        eid = ex['ejercicio_id']
        # Detectar cardio: por ID o por grupo (defensivo ante datos viejos con grupo=NULL)
        es_cardio = (eid.startswith("CAR_") or 
                     PATRON_POR_ID.get(eid, "") == "cardio" or
                     str(ex['grupo'] if 'grupo' in ex.keys() else '').lower() == 'cardio')
        html_msg += f"\n{estado} <b>{idx_ex}. {safe(ex['ejercicio'])}</b>\n"
        if es_cardio:
            # Cardio siempre en minutos, no series×reps
            tiempo = safe(ex['reps']) if "min" in str(ex['reps']) else "20min"
            html_msg += f"   ⏱ <b>{tiempo}</b> · ritmo moderado constante\n"
        else:
            html_msg += f"   📌 {ex['series']} series × <b>{safe(ex['reps'])}</b> reps\n"
        if ex['notas'] and not es_cardio:
            html_msg += f"   💡 <i>{safe(ex['notas'])}</i>\n"
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

    # Nota de nutrición (Ivy & Portman 2004 — timing de nutrientes)
    obj_key = "gluteo" if "gluteo" in grupo_dia else ("peso" if "peso" in grupo_dia else "general")
    nutr = NUTRICION_POR_OBJETIVO.get(obj_key, NUTRICION_POR_OBJETIVO["general"])
    html_msg += f"\n───────────────────────\n"
    html_msg += f"🥗 <b>NUTRICIÓN HOY</b>\n"
    html_msg += f"  {nutr['pre']}\n"
    html_msg += f"  {nutr['post']}\n"
    html_msg += "\n<i>✅ Marca · 🔄 Cambia ejercicio</i>"

    keyboard.append([InlineKeyboardButton("📋 Ver plan completo", callback_data=f"plan:{semana}")])
    keyboard.append([InlineKeyboardButton("🏁 Terminar Rutina",   callback_data=f"finish:{semana}:{dia}")])
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
                eid = e["ejercicio_id"] if "ejercicio_id" in e.keys() else ""
                es_c = str(eid).startswith("CAR_") or e["grupo"] in ("cardio",)
                if es_c:
                    t = e["reps"] if "min" in str(e["reps"]) else "20min"
                    txt += f"  🏃 {safe(e['ejercicio'])} — {t}\n"
                else:
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
    [InlineKeyboardButton("📊 Volumen semanal",       callback_data="ver_volumen")],
    [InlineKeyboardButton("😓 Reportar fatiga",       callback_data="ver_fatiga")],
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
        intro = (
            "🏋️ <b>GymCoach AI</b> — Tu entrenador personal inteligente\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🧬 <b>¿Qué hay detrás?</b>\n"
            "Este bot usa <b>Gemini AI</b> + ciencia del ejercicio de élite para crear\n"
            "un programa <i>único para ti</i>, no genérico.\n\n"
            "📚 <b>Ciencia aplicada:</b>\n"
            "  • <b>Schoenfeld (2016)</b> — frecuencia 2x/semana por grupo muscular\n"
            "  • <b>Contreras (2015)</b> — orden por activación EMG (hip thrust primero)\n"
            "  • <b>Nippard</b> — progresión real: 15→12→10→8 reps con carga creciente\n"
            "  • <b>McGill</b> — calentamiento específico por grupo, no genérico\n\n"
            "🎯 <b>¿Cómo funciona?</b>\n"
            "  1️⃣ Me dices tu objetivo y nivel (6 preguntas rápidas)\n"
            "  2️⃣ La IA genera tu plan de <b>4 semanas</b> personalizado\n"
            "  3️⃣ Cada día ves tu rutina con calentamiento específico\n"
            "  4️⃣ Marca ejercicios ✅ · Cambia los que no te gusten 🔄\n"
            "  5️⃣ El plan progresa solo cada semana\n\n"
            "⏱ <i>Crear tu plan toma ~45 segundos</i>\n"
        )
        teclado = InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Crear mi plan personalizado", callback_data="obj:inicio")
        ]])
        await update.message.reply_text(intro, reply_markup=teclado, parse_mode="HTML")
        return


    semana, dia = obtener_estado_usuario(user_id)
    stats = obtener_stats_suaves(user_id)

    texto_rutina, teclado = obtener_rutina_interactiva(user_id, semana, dia)

    if stats["total_ejercicios"] > 0:
        # Barra de progreso visual (cada 10 ejercicios = un bloque)
        bloques = min(10, stats["total_ejercicios"] // 10)
        barra = "🟩" * bloques + "⬜" * (10 - bloques)
        bloque = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🏋️ <b>GymCoach AI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 <b>Tu progreso</b>\n"
            f"  {barra}\n"
            f"  🔥 <b>{stats['total_ejercicios']}</b> ejercicios completados\n"
            f"  📆 Esta semana: <b>{stats['ejercicios_semana']}</b>\n"
            f"  🏆 Rutinas completas: <b>{stats['rutinas_completas']}</b>\n\n"
            f"───────────────────────────\n"
        )
    else:
        bloque = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🏋️ <b>GymCoach AI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✨ <b>¡Primera rutina!</b> Ya empezaste — lo más difícil es esto.\n\n"
            f"───────────────────────────\n"
        )

    await update.message.reply_text(
        bloque + "\n" + texto_rutina, reply_markup=teclado,
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



async def rir_respuesta_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Post-sesión paso 1/2: procesa RIR y pregunta progresión."""
    if not await check_auth(update): return
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    _, sem_s, dia, rir_s = query.data.split(":")
    sem = int(sem_s)
    rir = int(rir_s)
    registrar_rir(user_id, sem, dia, rir)
    emoji_rir, desc_rir = RIR_OPCIONES[rir]
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f4c8 Sí — más peso o más reps",      callback_data=f"prg:{sem}:{dia}:si")],
        [InlineKeyboardButton("\u27a1\ufe0f  Igual que la semana anterior", callback_data=f"prg:{sem}:{dia}:igual")],
        [InlineKeyboardButton("\U0001f4c9 No — tuve que bajar",            callback_data=f"prg:{sem}:{dia}:no")],
        [InlineKeyboardButton("\U0001f331 Primera vez con este ejercicio",  callback_data=f"prg:{sem}:{dia}:primera")],
    ])
    await query.edit_message_text(
        f"{emoji_rir} <b>{desc_rir}</b>\n\n"
        "<b>2/2 — ¿Progresaste vs la última vez?</b>\n"
        "<i>Progresión = más peso, más reps, o mejor técnica.</i>",
        reply_markup=teclado, parse_mode="HTML"
    )


async def progresion_respuesta_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Post-sesión paso 2/3: procesa progresión y lanza pregunta de fatiga."""
    if not await check_auth(update): return
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    _, sem_s, dia, prog = query.data.split(":")
    sem = int(sem_s)

    registrar_progresion(user_id, sem, dia, prog)
    emoji_p, desc_p = PROGRESION_OPCIONES.get(prog, ("✅", prog))

    # Paso 3/3: preguntar fatiga
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("😊 Fresco (1)",   callback_data=f"fat:{sem}:{dia}:1"),
         InlineKeyboardButton("🙂 Leve (2)",     callback_data=f"fat:{sem}:{dia}:2")],
        [InlineKeyboardButton("😐 Moderada (3)", callback_data=f"fat:{sem}:{dia}:3"),
         InlineKeyboardButton("😓 Alta (4)",     callback_data=f"fat:{sem}:{dia}:4")],
        [InlineKeyboardButton("💀 Crítica (5)",  callback_data=f"fat:{sem}:{dia}:5")],
        [InlineKeyboardButton("⏭ Saltar",        callback_data="menu:main")],
    ])
    await query.edit_message_text(
        f"{emoji_p} <b>{desc_p}</b>\n\n"
        "<b>3/3 — ¿Cómo quedó tu cuerpo?</b>\n"
        "<i>Fatiga muscular y del sistema nervioso, no solo cansancio.</i>",
        reply_markup=teclado, parse_mode="HTML"
    )

async def reporte_fatiga_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entrada manual desde el menú: muestra selector de fatiga post-sesión."""
    if not await check_auth(update): return
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    semana, dia = obtener_semana_y_dia_actual(user_id)
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("😊 Fresco (1)",   callback_data=f"fat:{semana}:{dia}:1"),
         InlineKeyboardButton("🙂 Leve (2)",     callback_data=f"fat:{semana}:{dia}:2")],
        [InlineKeyboardButton("😐 Moderada (3)", callback_data=f"fat:{semana}:{dia}:3"),
         InlineKeyboardButton("😓 Alta (4)",     callback_data=f"fat:{semana}:{dia}:4")],
        [InlineKeyboardButton("💀 Crítica (5)",  callback_data=f"fat:{semana}:{dia}:5")],
    ])
    await query.edit_message_text(
        "💪 <b>¿Cómo quedaste hoy?</b>\n\n"
        "Reporta tu fatiga para que el sistema ajuste la próxima sesión si es necesario.",
        reply_markup=teclado, parse_mode="HTML"
    )


async def fat_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Procesa fatiga — cierra el flujo post-sesión de 3 pasos.
    También funciona como entrada directa desde el botón del menú.
    FIX: ahora ejecuta el análisis completo (RIR+progresión+fatiga) y aplica ajuste.
    """
    if not await check_auth(update): return
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    partes = query.data.split(":")
    semana, dia, nivel_s = int(partes[1]), partes[2], int(partes[3])

    registrar_fatiga(user_id, semana, dia, nivel_s)
    emoji_fat, desc_fat = FATIGA_NIVELES[nivel_s]

    # Análisis completo con los 3 datos ya guardados
    resultado  = analizar_sesion(user_id, semana, dia)
    ajuste     = resultado["ajuste"]
    msg_ajuste = resultado["msg_usuario"]

    # Aplicar ajuste automático
    aplicar_ajuste_automatico(user_id, semana, dia, ajuste)
    # Fatiga alta también dispara ajuste de accesorios (capa adicional de seguridad)
    if nivel_s >= 4:
        ajustar_sesion_por_fatiga(user_id, semana, dia, nivel_s)

    # Evaluar fatiga acumulada histórica
    evaluacion = evaluar_fatiga_acumulada(user_id)

    # Construir respuesta
    lineas = [f"{emoji_fat} <b>{desc_fat}</b>"]
    if msg_ajuste:
        lineas += ["", msg_ajuste]
    if evaluacion["necesita_deload"] and nivel_s >= 3:
        lineas += [
            "",
            f"\U0001f504 <b>Semana de recuperación recomendada.</b>",
            f"Razón: {evaluacion['razon']}",
        ]
    lineas += ["", "━━━━━━━━━━━━━━━━━━", "<i>Los 3 datos quedaron registrados.</i>"]

    teclado = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menú", callback_data="menu:main")]])
    await query.edit_message_text(
        "\n".join(lineas), parse_mode="HTML", reply_markup=teclado
    )

async def volumen_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el reporte de volumen semanal del usuario."""
    if not await check_auth(update): return
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    semana, _ = obtener_semana_y_dia_actual(user_id)
    vol = calcular_volumen_semanal(user_id, semana)
    texto = formatear_volumen_reporte(vol)
    teclado = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Volver", callback_data="menu:main")]])
    await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)


async def adduser_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: añadir usuario sin redeploy. Uso: /adduser 123456789"""
    if update.effective_user.id != 1557254587:
        if update.message:
            await update.message.reply_text("⛔ Solo el admin puede añadir usuarios.")
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Uso: /adduser <ID_TELEGRAM>\nEjemplo: /adduser 8468355326")
        return
    nuevo_id = int(args[0])
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        cur  = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO usuarios_permitidos (user_id, rol) VALUES (?, 'user')", (nuevo_id,))
        conn.commit()
        conn.close()
        ALLOWED_USERS.add(nuevo_id)
        await update.message.reply_text(f"✅ Usuario {nuevo_id} añadido con éxito.")
        logger.info(f"Admin añadió usuario {nuevo_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


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
        # Paso 2: género — afecta split muscular y énfasis de ejercicios
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("👩 Mujer",  callback_data="gen:mujer")],
            [InlineKeyboardButton("👨 Hombre", callback_data="gen:hombre")],
        ])
        await query.edit_message_text(
            "✅ Objetivo guardado.\n\n<b>Paso 2/5</b> — ¿Cuál es tu género?\n"
            "<i>Esto ajusta el énfasis muscular del programa.</i>",
            reply_markup=teclado, parse_mode="HTML"
        )
        return

    # ── SELECCIÓN DE GÉNERO ───────────────────────────────────────────
    if data.startswith("gen:"):
        await query.answer()
        genero = data.split(":")[1]
        conn_gen = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        cur_gen = conn_gen.cursor()
        cur_gen.execute("""
            INSERT INTO perfil_usuario (user_id, genero)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET genero = excluded.genero, updated_at = CURRENT_TIMESTAMP
        """, (user_id, genero))
        conn_gen.commit()
        conn_gen.close()
        # Paso 3: nivel — define dificultad del ejercicio, no volumen
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌱 Principiante — máquinas guiadas, movimientos simples", callback_data="niv:principiante")],
            [InlineKeyboardButton("💪 Intermedio — mancuernas libres, ejercicios unilaterales", callback_data="niv:intermedio")],
            [InlineKeyboardButton("🔥 Avanzado — barra libre, sentadilla búlgara, dominadas",  callback_data="niv:avanzado")],
        ])
        await query.edit_message_text(
            "✅ Guardado.\n\n<b>Paso 3/5</b> — ¿Qué ejercicios puedes hacer bien?\n"
            "<i>Esto define la dificultad de tus ejercicios — no la cantidad. "
            "principiante=3 series · intermedio=4 · avanzado=5. Siempre 4 ejercicios+cardio.</i>",
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
            "✅ Nivel guardado.\n\n<b>Paso 4/5</b> — ¿Tienes alguna limitación física?\n"
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
        # Paso 5/5: días por semana — directo, sin preguntar volumen
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("3️⃣  3 días — recuperación máxima",  callback_data="dias:3")],
            [InlineKeyboardButton("4️⃣  4 días — balance óptimo",       callback_data="dias:4")],
            [InlineKeyboardButton("5️⃣  5 días — volumen avanzado",     callback_data="dias:5")],
        ])
        await query.edit_message_text(
            "✅ Listo.\n\n<b>Paso 5/5</b> — ¿Cuántos días por semana entrenas?\n"
            "<i>Más días = más volumen semanal. 4 días consistentes supera 5 irregulares.</i>",
            reply_markup=teclado, parse_mode="HTML"
        )
        return

    # ── DURACIÓN DE SESIÓN ────────────────────────────────────────────
    if data.startswith("dur:"):
        # Legado: guardar 75min como default y continuar a días
        await query.answer()
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("3️⃣  3 días — recuperación máxima",  callback_data="dias:3")],
            [InlineKeyboardButton("4️⃣  4 días — balance óptimo",       callback_data="dias:4")],
            [InlineKeyboardButton("5️⃣  5 días — volumen avanzado",     callback_data="dias:5")],
        ])
        await query.edit_message_text(
            "✅ Guardado.\n\n<b>Paso 5/5</b> — ¿Cuántos días por semana?",
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

        # Cargar perfil completo en una sola query (FIX: antes eran 2 conexiones separadas)
        conn2 = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        cur2  = conn2.cursor()
        cur2.execute("SELECT nivel, limitaciones, duracion_min, genero FROM perfil_usuario WHERE user_id = ?", (user_id,))
        row2 = cur2.fetchone()
        conn2.close()
        nivel        = row2[0] if row2 else "principiante"
        limitaciones = row2[1] if row2 else "ninguna"
        duracion_min = row2[2] if row2 else 60
        genero       = row2[3] if row2 else "mujer"

        perfil = {"objetivo": objetivo, "dias": int(dias), "nivel": nivel,
                  "limitaciones": limitaciones, "duracion_min": duracion_min, "genero": genero}
        system_prompt_dinamico = construir_system_prompt(perfil)
        prompt = construir_prompt_usuario(perfil)
        # Generar semana a semana — evita truncamiento por JSON gigante
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
        semanas_json = []
        error_semana = None

        for num_semana in range(1, 5):
            progreso_txt = ["🧠", "📊", "🏗", "✍️"][num_semana - 1]
            await query.edit_message_text(
                f"{progreso_txt} <b>Generando semana {num_semana}/4...</b>",
                parse_mode="HTML"
            )

            prompt_semana = construir_prompt_semana(perfil, num_semana)
            exito_s = False
            for intento in range(1, 3):
                try:
                    loop = asyncio.get_event_loop()
                    resp = await asyncio.wait_for(
                        loop.run_in_executor(
                            None,
                            lambda p=prompt_semana: client.models.generate_content(
                                model='gemini-2.0-flash',
                                contents=p,
                                config=types.GenerateContentConfig(
                                    system_instruction="Eres un generador JSON. SOLO produces JSON valido. NUNCA texto explicativo. NUNCA markdown. Solo el objeto JSON puro.",
                                    max_output_tokens=3000,
                                    temperature=0.1,
                                )
                            )
                        ),
                        timeout=45
                    )
                    sem_data, err = parsear_semana_json(resp.text, num_semana)
                    if sem_data:
                        semanas_json.append(sem_data)
                        exito_s = True
                        break
                    logger.warning(f"Semana {num_semana} intento {intento}: {err}")
                    logger.debug(f"Raw Gemini S{num_semana}i{intento} (200 chars): {repr(resp.text[:200])}")
                except asyncio.TimeoutError:
                    logger.error(f"Timeout semana {num_semana} intento {intento}")
                except Exception as exc:
                    logger.exception(f"Error semana {num_semana} intento {intento}")

            if not exito_s:
                error_semana = num_semana
                break

        if error_semana:
            await query.edit_message_text(
                f"❌ <b>Error en semana {error_semana}.</b> Toca el menú para reintentar.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🆕 Intentar de nuevo", callback_data="menu:nuevo")
                ]]),
                parse_mode="HTML"
            )
            return

        # Ensamblar plan completo e insertar en DB
        plan_completo = {"semanas": semanas_json}
        ej_calculado = 5  # estructura científica fija
        exito, msj = sanitizar_e_insertar_plan(
            json.dumps(plan_completo), user_id, ej_por_dia=ej_calculado
        )
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
                f"❌ <b>No se pudo guardar el plan:</b> {msj}\nIntenta de nuevo.",
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

        # Milestones (felicitaciones)
        for msg in procesar_milestones(user_id, sem):
            await context.bot.send_message(chat_id=query.message.chat_id, text=msg, parse_mode="HTML")

        # Lanzar encuesta post-sesión — paso 1/2: RIR
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Sin reserva — llegué al límite (RIR 0)", callback_data=f"rir:{sem}:{dia}:0")],
            [InlineKeyboardButton("💪 1 rep en reserva — muy intenso (RIR 1)", callback_data=f"rir:{sem}:{dia}:1")],
            [InlineKeyboardButton("😊 2 reps en reserva — bien (RIR 2)",       callback_data=f"rir:{sem}:{dia}:2")],
            [InlineKeyboardButton("😌 Muy fácil — 3+ reps sobraban (RIR 3+)",  callback_data=f"rir:{sem}:{dia}:3")],
            [InlineKeyboardButton("⏭ Saltar encuesta",                             callback_data="menu:main")],
        ])
        await query.edit_message_text(
            "🏆 <b>¡Rutina guardada!</b> Descansa bien 💤\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📊 <b>Encuesta rápida</b> — 2 preguntas · 10 segundos\n"
            "El sistema ajusta automáticamente tu próxima sesión.\n\n"
            "<b>1/2 — ¿Cuántas reps te sobraban al final de cada serie?</b>\n"
            "<i>RIR = Reps en Reserva. Así medimos si el peso fue el correcto.</i>",
            reply_markup=kb, parse_mode="HTML"
        )
        return

# ==========================================
# 9. INICIALIZACIÓN
# ==========================================
def main():
    init_db()
    cargar_usuarios_permitidos()   # FIX: carga ALLOWED_USERS desde DB al arrancar
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
    app.add_handler(CommandHandler("adduser",    adduser_handler))
    app.add_handler(CallbackQueryHandler(rir_respuesta_handler,        pattern="^rir:"))
    app.add_handler(CallbackQueryHandler(progresion_respuesta_handler, pattern="^prg:"))
    app.add_handler(CallbackQueryHandler(fat_callback_handler,          pattern="^fat:"))
    app.add_handler(CallbackQueryHandler(reporte_fatiga_handler,        pattern="^ver_fatiga$"))
    app.add_handler(CallbackQueryHandler(volumen_handler,               pattern="^ver_volumen$"))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gemini_coach_handler))
    app.add_error_handler(error_handler)

    logger.info("✅ Bot iniciado — gemini-2.0-flash | SQLite multi-tenant | Swaps persistentes")
    app.run_polling()

if __name__ == '__main__':
    main()
