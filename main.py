import os
import json
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

ALLOWED_USERS = {123456789, 987654321}  # ⚠️ REEMPLAZA CON LOS IDs NUMÉRICOS REALES
DB_PATH = Path("/app/data/rutinas.db")

def safe(text: str) -> str:
    return html.escape(str(text), quote=True)

# ==========================================
# 2. CATÁLOGO Y PROMPTS
# ==========================================
CATALOGO = [
    # ─── PIERNA ───────────────────────────────────────────────────────
    {"ejercicio_id": "PIE_01", "nombre": "Sentadilla libre",                    "grupo": "pierna"},
    {"ejercicio_id": "PIE_02", "nombre": "Sentadilla sumo",                     "grupo": "pierna"},
    {"ejercicio_id": "PIE_03", "nombre": "Sentadilla en máquina Smith",         "grupo": "pierna"},
    {"ejercicio_id": "PIE_04", "nombre": "Prensa de pierna",                    "grupo": "pierna"},
    {"ejercicio_id": "PIE_05", "nombre": "Extensión de cuádriceps",             "grupo": "pierna"},
    {"ejercicio_id": "PIE_06", "nombre": "Curl femoral tumbada",                "grupo": "pierna"},
    {"ejercicio_id": "PIE_07", "nombre": "Curl femoral de pie en máquina",      "grupo": "pierna"},
    {"ejercicio_id": "PIE_08", "nombre": "Abducción de cadera en máquina",      "grupo": "pierna"},
    {"ejercicio_id": "PIE_09", "nombre": "Aducción de cadera en máquina",       "grupo": "pierna"},
    {"ejercicio_id": "PIE_10", "nombre": "Desplante con mancuernas",            "grupo": "pierna"},
    {"ejercicio_id": "PIE_11", "nombre": "Desplante caminando",                 "grupo": "pierna"},
    {"ejercicio_id": "PIE_12", "nombre": "Desplante reverso",                   "grupo": "pierna"},
    {"ejercicio_id": "PIE_13", "nombre": "Sentadilla búlgara",                  "grupo": "pierna"},
    {"ejercicio_id": "PIE_14", "nombre": "Elevación de talones de pie",         "grupo": "pierna"},
    {"ejercicio_id": "PIE_15", "nombre": "Elevación de talones sentada",        "grupo": "pierna"},
    {"ejercicio_id": "PIE_16", "nombre": "Step-up con mancuernas",              "grupo": "pierna"},
    {"ejercicio_id": "PIE_17", "nombre": "Sentadilla hack en máquina",          "grupo": "pierna"},
    {"ejercicio_id": "PIE_18", "nombre": "Sentadilla goblet con mancuerna",     "grupo": "pierna"},
    {"ejercicio_id": "PIE_19", "nombre": "Peso muerto convencional",            "grupo": "pierna"},
    {"ejercicio_id": "PIE_20", "nombre": "Zancada lateral",                     "grupo": "pierna"},
    # ─── GLÚTEO ───────────────────────────────────────────────────────
    {"ejercicio_id": "GLU_01", "nombre": "Puente de glúteo",                    "grupo": "gluteo"},
    {"ejercicio_id": "GLU_02", "nombre": "Puente de glúteo con banda",          "grupo": "gluteo"},
    {"ejercicio_id": "GLU_03", "nombre": "Hip thrust en banco",                 "grupo": "gluteo"},
    {"ejercicio_id": "GLU_04", "nombre": "Hip thrust en máquina",               "grupo": "gluteo"},
    {"ejercicio_id": "GLU_05", "nombre": "Patada de glúteo en polea baja",      "grupo": "gluteo"},
    {"ejercicio_id": "GLU_06", "nombre": "Patada de glúteo en cuadrupedia",     "grupo": "gluteo"},
    {"ejercicio_id": "GLU_07", "nombre": "Abducción de cadera con banda",       "grupo": "gluteo"},
    {"ejercicio_id": "GLU_08", "nombre": "Sentadilla con banda en rodillas",    "grupo": "gluteo"},
    {"ejercicio_id": "GLU_09", "nombre": "Good morning con mancuerna",          "grupo": "gluteo"},
    {"ejercicio_id": "GLU_10", "nombre": "Peso muerto rumano con mancuernas",   "grupo": "gluteo"},
    {"ejercicio_id": "GLU_11", "nombre": "Peso muerto a una pierna",            "grupo": "gluteo"},
    {"ejercicio_id": "GLU_12", "nombre": "Abducción en polea con tobillera",    "grupo": "gluteo"},
    {"ejercicio_id": "GLU_13", "nombre": "Clamshell con banda",                 "grupo": "gluteo"},
    {"ejercicio_id": "GLU_14", "nombre": "Hip thrust a una pierna",             "grupo": "gluteo"},
    {"ejercicio_id": "GLU_15", "nombre": "Sentadilla sumo con mancuerna",       "grupo": "gluteo"},
    {"ejercicio_id": "GLU_16", "nombre": "Extensión de cadera en máquina",      "grupo": "gluteo"},
    {"ejercicio_id": "GLU_17", "nombre": "Donkey kick con tobillera en polea",  "grupo": "gluteo"},
    {"ejercicio_id": "GLU_18", "nombre": "Fire hydrant con banda",              "grupo": "gluteo"},
    # ─── EMPUJE (Pecho / Hombro / Tríceps) ───────────────────────────
    {"ejercicio_id": "EMP_01", "nombre": "Flexiones en rodillas",               "grupo": "empuje"},
    {"ejercicio_id": "EMP_02", "nombre": "Flexiones estándar",                  "grupo": "empuje"},
    {"ejercicio_id": "EMP_03", "nombre": "Press de pecho con mancuernas",       "grupo": "empuje"},
    {"ejercicio_id": "EMP_04", "nombre": "Press inclinado con mancuernas",      "grupo": "empuje"},
    {"ejercicio_id": "EMP_05", "nombre": "Press declinado con mancuernas",      "grupo": "empuje"},
    {"ejercicio_id": "EMP_06", "nombre": "Aperturas con mancuernas",            "grupo": "empuje"},
    {"ejercicio_id": "EMP_07", "nombre": "Aperturas en polea cruzada",          "grupo": "empuje"},
    {"ejercicio_id": "EMP_08", "nombre": "Press en máquina de pecho",           "grupo": "empuje"},
    {"ejercicio_id": "EMP_09", "nombre": "Press de hombro con mancuernas",      "grupo": "empuje"},
    {"ejercicio_id": "EMP_10", "nombre": "Elevaciones laterales",               "grupo": "empuje"},
    {"ejercicio_id": "EMP_11", "nombre": "Elevaciones frontales",               "grupo": "empuje"},
    {"ejercicio_id": "EMP_12", "nombre": "Elevaciones laterales en polea baja", "grupo": "empuje"},
    {"ejercicio_id": "EMP_13", "nombre": "Press Arnold",                        "grupo": "empuje"},
    {"ejercicio_id": "EMP_14", "nombre": "Fondos en banco (tríceps)",           "grupo": "empuje"},
    {"ejercicio_id": "EMP_15", "nombre": "Extensión de tríceps con banda",      "grupo": "empuje"},
    {"ejercicio_id": "EMP_16", "nombre": "Press francés con mancuerna",         "grupo": "empuje"},
    {"ejercicio_id": "EMP_17", "nombre": "Jalón de tríceps en polea alta",      "grupo": "empuje"},
    {"ejercicio_id": "EMP_18", "nombre": "Extensión de tríceps sobre cabeza",   "grupo": "empuje"},
    {"ejercicio_id": "EMP_19", "nombre": "Press en máquina de hombro",          "grupo": "empuje"},
    # ─── TIRÓN (Espalda / Bíceps) ─────────────────────────────────────
    {"ejercicio_id": "TIR_01", "nombre": "Remo con mancuerna a una mano",       "grupo": "tiron"},
    {"ejercicio_id": "TIR_02", "nombre": "Remo con banda elástica",             "grupo": "tiron"},
    {"ejercicio_id": "TIR_03", "nombre": "Jalón al pecho en polea",             "grupo": "tiron"},
    {"ejercicio_id": "TIR_04", "nombre": "Jalón al pecho agarre estrecho",      "grupo": "tiron"},
    {"ejercicio_id": "TIR_05", "nombre": "Remo en polea baja",                  "grupo": "tiron"},
    {"ejercicio_id": "TIR_06", "nombre": "Remo en polea baja agarre neutro",    "grupo": "tiron"},
    {"ejercicio_id": "TIR_07", "nombre": "Remo en máquina",                     "grupo": "tiron"},
    {"ejercicio_id": "TIR_08", "nombre": "Remo inclinado con mancuernas",       "grupo": "tiron"},
    {"ejercicio_id": "TIR_09", "nombre": "Curl de bíceps con mancuernas",       "grupo": "tiron"},
    {"ejercicio_id": "TIR_10", "nombre": "Curl martillo",                       "grupo": "tiron"},
    {"ejercicio_id": "TIR_11", "nombre": "Curl con banda elástica",             "grupo": "tiron"},
    {"ejercicio_id": "TIR_12", "nombre": "Curl concentrado",                    "grupo": "tiron"},
    {"ejercicio_id": "TIR_13", "nombre": "Curl en polea baja",                  "grupo": "tiron"},
    {"ejercicio_id": "TIR_14", "nombre": "Face pull con banda",                 "grupo": "tiron"},
    {"ejercicio_id": "TIR_15", "nombre": "Face pull en polea alta",             "grupo": "tiron"},
    {"ejercicio_id": "TIR_16", "nombre": "Pullover con mancuerna",              "grupo": "tiron"},
    {"ejercicio_id": "TIR_17", "nombre": "Encogimientos de hombros",            "grupo": "tiron"},
    {"ejercicio_id": "TIR_18", "nombre": "Superman en banco",                   "grupo": "tiron"},
    # ─── CORE ─────────────────────────────────────────────────────────
    {"ejercicio_id": "COR_01", "nombre": "Plancha abdominal",                   "grupo": "core"},
    {"ejercicio_id": "COR_02", "nombre": "Plancha lateral",                     "grupo": "core"},
    {"ejercicio_id": "COR_03", "nombre": "Plancha con toque de hombro",         "grupo": "core"},
    {"ejercicio_id": "COR_04", "nombre": "Crunch abdominal",                    "grupo": "core"},
    {"ejercicio_id": "COR_05", "nombre": "Crunch inverso",                      "grupo": "core"},
    {"ejercicio_id": "COR_06", "nombre": "Crunch en polea alta",                "grupo": "core"},
    {"ejercicio_id": "COR_07", "nombre": "Elevación de piernas tumbada",        "grupo": "core"},
    {"ejercicio_id": "COR_08", "nombre": "Dead bug",                            "grupo": "core"},
    {"ejercicio_id": "COR_09", "nombre": "Bird dog",                            "grupo": "core"},
    {"ejercicio_id": "COR_10", "nombre": "Mountain climbers",                   "grupo": "core"},
    {"ejercicio_id": "COR_11", "nombre": "Bicicleta abdominal",                 "grupo": "core"},
    {"ejercicio_id": "COR_12", "nombre": "Superman en suelo",                   "grupo": "core"},
    {"ejercicio_id": "COR_13", "nombre": "Tijeras abdominales",                 "grupo": "core"},
    {"ejercicio_id": "COR_14", "nombre": "Rotación rusa con mancuerna",         "grupo": "core"},
    {"ejercicio_id": "COR_15", "nombre": "Hollow body hold",                    "grupo": "core"},
    # ─── CARDIO ───────────────────────────────────────────────────────
    {"ejercicio_id": "CAR_01", "nombre": "Caminata en cinta inclinada",         "grupo": "cardio"},
    {"ejercicio_id": "CAR_02", "nombre": "Trote suave en cinta",                "grupo": "cardio"},
    {"ejercicio_id": "CAR_03", "nombre": "Intervalos en cinta (1 min rápido)",  "grupo": "cardio"},
    {"ejercicio_id": "CAR_04", "nombre": "Bicicleta estática ritmo moderado",   "grupo": "cardio"},
    {"ejercicio_id": "CAR_05", "nombre": "Bicicleta estática intervalos",       "grupo": "cardio"},
    {"ejercicio_id": "CAR_06", "nombre": "Elíptica ritmo constante",            "grupo": "cardio"},
    {"ejercicio_id": "CAR_07", "nombre": "Remo en máquina cardio",              "grupo": "cardio"},
    {"ejercicio_id": "CAR_08", "nombre": "Jump rope (cuerda)",                  "grupo": "cardio"},
    {"ejercicio_id": "CAR_09", "nombre": "Jumping jacks",                       "grupo": "cardio"},
    {"ejercicio_id": "CAR_10", "nombre": "Step aeróbico en cajón",              "grupo": "cardio"},
]

VALID_IDS = {ex["ejercicio_id"] for ex in CATALOGO}
CATALOGO_POR_ID = {ex["ejercicio_id"]: ex for ex in CATALOGO}

SYSTEM_PROMPT = f"""
Eres un planificador de entrenamiento para una persona PRINCIPIANTE con acceso a gimnasio completo.
NO hablas con el usuario. SOLO generas JSON válido.

REGLAS DURAS (OBLIGATORIAS):
1) Usa EXCLUSIVAMENTE el siguiente CATALOGO. No inventes ejercicios ni IDs.
2) Genera un plan exacto de 4 semanas con progresión suave.
3) Semanas 1-2: ejercicios más simples (peso corporal, máquinas guiadas).
   Semanas 3-4: introduce mancuernas y mayor variedad.
4) Varía los ejercicios entre días para evitar repetición y mantener motivación.
5) Cada día incluye 4-5 ejercicios con orden lógico (compuesto → aislamiento).
6) 'reps' debe ser texto (ej. "12" o "30s").
7) Formato de salida: JSON ESTRICTO, sin texto extra, sin markdown.
8) Sin campo 'url' — elimínalo completamente del JSON de salida.

CATALOGO_JSON:
{json.dumps(CATALOGO, ensure_ascii=False)}

FORMATO DE SALIDA EXACTO:
{{
  "semanas": [
    {{
      "semana": 1,
      "dias": [
        {{
          "dia": "lunes",
          "grupo": "pierna",
          "ejercicios": [
            {{"ejercicio_id": "PIE_01", "ejercicio": "Sentadilla libre", "orden": 1, "series": 3, "reps": "12", "notas": "Baja lento, rodillas hacia afuera"}}
          ]
        }}
      ]
    }}
  ]
}}
"""

# ==========================================
# 3. BASE DE DATOS
# ==========================================
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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

    # NUEVA: historial de swaps para persistencia entre semanas
    cur.execute("""CREATE TABLE IF NOT EXISTS swaps (
        user_id INTEGER,
        ejercicio_id_original TEXT,
        ejercicio_id_swap TEXT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, ejercicio_id_original)
    )""")

    conn.commit()
    conn.close()

def sanitizar_e_insertar_plan(json_string: str, user_id: int) -> tuple[bool, str]:
    try:
        raw_json = json_string.strip()
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:-3].strip()
        elif raw_json.startswith("```"):
            raw_json = raw_json[3:-3].strip()
        data = json.loads(raw_json)

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # Cargar swaps previos del usuario para aplicarlos al nuevo plan
        cur.execute("SELECT ejercicio_id_original, ejercicio_id_swap FROM swaps WHERE user_id = ?", (user_id,))
        swaps_guardados = {r[0]: r[1] for r in cur.fetchall()}

        for s in data.get("semanas", []):
            for d in s.get("dias", []):
                dia_seguro = str(d["dia"]).lower()[:15]
                for e in d.get("ejercicios", []):
                    ej_id_original = str(e["ejercicio_id"])
                    if ej_id_original not in VALID_IDS:
                        conn.rollback()
                        conn.close()
                        return False, f"Alucinación: ID {ej_id_original} no está en el catálogo."

                    # Aplicar swap persistente si existe
                    ej_id_final = swaps_guardados.get(ej_id_original, ej_id_original)
                    nombre_final = CATALOGO_POR_ID[ej_id_final]["nombre"]

                    cur.execute("""
                        INSERT OR IGNORE INTO rutinas
                        (user_id, semana, dia, grupo, ejercicio_id, ejercicio, orden, series, reps, notas)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (user_id, int(s["semana"]), dia_seguro,
                          str(d["grupo"]), ej_id_final, nombre_final,
                          int(e.get("orden", 1)), int(e.get("series", 3)),
                          str(e.get("reps", "10")), e.get("notas", "")))
        conn.commit()
        conn.close()
        return True, "Plan guardado."
    except Exception as e:
        logger.exception("Error validando/insertando JSON de Gemini.")
        return False, f"Error validando JSON: {e}"

def obtener_estado_usuario(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT semana, dia FROM estado WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row if row else (1, "lunes")

def iniciar_estado_usuario(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT dia FROM rutinas WHERE user_id = ? AND semana = 1 ORDER BY MIN(id) ASC LIMIT 1", (user_id,))
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT ejercicio_id FROM rutinas WHERE user_id = ? AND semana = ? AND dia = ?",
                (user_id, semana, dia))
    ids_en_uso = {r[0] for r in cur.fetchall()}
    conn.close()

    # Excluir el ejercicio actual + los que ya están en el día
    excluidos = ids_en_uso  # ya incluye el ejercicio_id actual

    alternativas = [
        e for e in CATALOGO
        if e["grupo"] == grupo and e["ejercicio_id"] not in excluidos
    ]
    return alternativas[:3]

def aplicar_swap(user_id: int, semana: int, dia: str, id_original: str, id_nuevo: str):
    """
    Reemplaza el ejercicio en TODAS las semanas del plan actual
    y guarda el swap de forma permanente para planes futuros.
    """
    nuevo = CATALOGO_POR_ID[id_nuevo]
    conn = sqlite3.connect(DB_PATH)
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

    # 3. Guardar swap permanente (se aplicará a planes futuros también)
    cur.execute("""
        INSERT INTO swaps (user_id, ejercicio_id_original, ejercicio_id_swap)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, ejercicio_id_original)
        DO UPDATE SET ejercicio_id_swap = excluded.ejercicio_id_swap, ts = CURRENT_TIMESTAMP
    """, (user_id, id_original, id_nuevo))

    conn.commit()
    conn.close()
    logger.info(f"Swap aplicado: user={user_id} | {id_original} → {id_nuevo} (todas las semanas)")

# ==========================================
# 5. STATS Y MILESTONES
# ==========================================
def obtener_stats_suaves(user_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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

def formatear_plan_completo(user_id: int) -> str:
    """Genera un resumen de las 4 semanas para /plan."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT semana, dia, grupo, ejercicio, series, reps
        FROM rutinas WHERE user_id = ?
        ORDER BY semana, MIN(id), orden
    """, (user_id,))
    # Agrupar por semana y dia
    from collections import defaultdict
    plan = defaultdict(lambda: defaultdict(list))
    for row in cur.fetchall():
        plan[row["semana"]][row["dia"]].append(row)
    conn.close()

    if not plan:
        return "No tienes un plan activo. Usa /start para crear uno."

    semana_actual, _ = obtener_estado_usuario(user_id)
    texto = "📅 <b>Tu plan completo de 4 semanas</b>\n"
    texto += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for sem_num in sorted(plan.keys()):
        marcador = " ◀ aquí" if sem_num == semana_actual else ""
        texto += f"<b>🗓 SEMANA {sem_num}{marcador}</b>\n"
        for dia_nombre, ejercicios in plan[sem_num].items():
            grupo = ejercicios[0]["grupo"].upper() if ejercicios else ""
            texto += f"  <i>{dia_nombre.capitalize()} · {grupo}</i>\n"
            for e in ejercicios:
                texto += f"    • {safe(e['ejercicio'])} {e['series']}×{e['reps']}\n"
        texto += "\n"

    return texto

# ==========================================
# 7. HANDLERS DE TELEGRAM
# ==========================================
async def check_auth(update: Update) -> bool:
    if update.effective_user.id not in ALLOWED_USERS:
        if update.message:
            await update.message.reply_text("⛔ Lo siento, este bot es privado.")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    user_id = update.effective_user.id

    conn = sqlite3.connect(DB_PATH)
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
            "👋 <b>¡Hola!</b> No tenemos un plan activo.\n\nVamos a crear uno. ¿Cuál es tu objetivo principal?",
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
    """Comando /plan — muestra el plan completo de 4 semanas."""
    if not await check_auth(update): return
    texto = formatear_plan_completo(update.effective_user.id)
    await update.message.reply_text(texto, parse_mode="HTML")

async def gemini_coach_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    user_id = update.effective_user.id
    semana, dia = obtener_estado_usuario(user_id)
    system_ctx = (
        f"Eres un entrenador personal motivador y cercano. "
        f"El usuario está en Semana {semana}, día {dia}. "
        f"Responde en máximo 3 oraciones. "
        f"Si menciona dolor, dile que pare y consulte a un médico. "
        f"No inventes rutinas ni ejercicios, dile que use /start."
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    try:
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
        resp = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=update.message.text,
            config=types.GenerateContentConfig(system_instruction=system_ctx)
        )
        await update.message.reply_text(resp.text)
    except Exception:
        logger.exception("Error en coach conversacional")
        await update.message.reply_text("Descansa un poco, usa el menú /start ❤️")

async def reset_plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Borra plan y progreso. Conserva los swaps del usuario (preferencias)."""
    if not await check_auth(update): return
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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

    # ── SELECCIÓN DE OBJETIVO ─────────────────────────────────────────
    if data.startswith("obj:"):
        await query.answer()
        objetivo = data.split(":")[1]
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO estado (user_id, semana, dia, objetivo)
            VALUES (?, 1, 'pendiente', ?)
            ON CONFLICT(user_id) DO UPDATE SET objetivo = excluded.objetivo
        """, (user_id, objetivo))
        conn.commit()
        conn.close()
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{i} días a la semana", callback_data=f"dias:{i}")]
            for i in [3, 4, 5]
        ])
        await query.edit_message_text("¡Excelente! 🎯\n\n¿Cuántos días a la semana quieres entrenar?", reply_markup=teclado)
        return

    # ── SELECCIÓN DE DÍAS → GENERA PLAN ──────────────────────────────
    if data.startswith("dias:"):
        await query.answer()
        dias = data.split(":")[1]

        # Guard anti-doble tap
        conn = sqlite3.connect(DB_PATH)
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

        await query.edit_message_text("⏳ <i>Diseñando tu plan perfecto... Dame unos segundos.</i>", parse_mode="HTML")
        prompt = (f"Genera el plan completo de 4 semanas en JSON estricto. "
                  f"Usa SOLO el catálogo. OBJETIVO: {objetivo}. "
                  f"DÍAS POR SEMANA: Exactamente {dias} días.")
        try:
            client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
            resp = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
            )
            exito, msj = sanitizar_e_insertar_plan(resp.text, user_id)
            if exito:
                iniciar_estado_usuario(user_id)
                await query.edit_message_text(
                    "✅ <b>¡Tu plan está listo!</b>\n\nToca /start para ver tu primera rutina.\nUsa /plan para ver las 4 semanas completas.",
                    parse_mode="HTML"
                )
            else:
                await query.edit_message_text(f"❌ Problema armando el plan: {msj}\nIntenta de nuevo con /start.")
        except Exception:
            logger.exception("Error contactando a Gemini durante la generación del plan.")
            await query.edit_message_text("Error de conexión con IA. Intenta de nuevo.")
        return

    # ── VER PLAN COMPLETO (desde botón en rutina) ─────────────────────
    if data.startswith("plan:"):
        await query.answer()
        texto = formatear_plan_completo(user_id)
        tec = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver a hoy", callback_data="back_hoy")]])
        await query.edit_message_text(texto, reply_markup=tec, parse_mode="HTML")
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
        conn = sqlite3.connect(DB_PATH)
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
    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("plan",         plan_handler))
    app.add_handler(CommandHandler("reset_plan",   reset_plan_handler))
    app.add_handler(CommandHandler("reset_swaps",  reset_swaps_handler))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gemini_coach_handler))

    logger.info("✅ Bot iniciado — gemini-2.0-flash | SQLite multi-tenant | Swaps persistentes")
    app.run_polling()

if __name__ == '__main__':
    main()
