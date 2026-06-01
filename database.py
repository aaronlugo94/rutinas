"""
database.py — DB unificada Coach.
Tablas gym:    usuarios, rutinas, pesos, sesion_activa, peso_flow,
               gamificacion, badges, progreso, swaps, estado,
               allowed_users, login_tokens, analisis_historial
Tablas cuerpo: pesajes, historico_dietas, config_nutricion
"""
from __future__ import annotations
import logging
import os
import sqlite3
from contextlib import contextmanager

logger  = logging.getLogger(__name__)
DB_PATH = os.environ.get("DB_PATH", "coach.db")

@contextmanager
def get_db():
    _dir = os.path.dirname(DB_PATH)
    if _dir:
        os.makedirs(_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def execute(sql, params=()):
    with get_db() as conn:
        conn.execute(sql, params)

def fetchone(sql, params=()):
    with get_db() as conn:
        return conn.execute(sql, params).fetchone()

def fetchall(sql, params=()):
    with get_db() as conn:
        return conn.execute(sql, params).fetchall()

def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS allowed_users (
            user_id INTEGER PRIMARY KEY, activo INTEGER DEFAULT 1);

        CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY, nombre TEXT, genero TEXT,
            nivel TEXT, objetivo TEXT, limitaciones TEXT DEFAULT 'ninguna',
            dias INTEGER DEFAULT 4, duracion_min INTEGER DEFAULT 60,
            ambiente_preferido TEXT DEFAULT 'gym', hora_recordatorio TEXT,
            anos_entrenando INTEGER DEFAULT 0, pin TEXT);

        CREATE TABLE IF NOT EXISTS estado (
            user_id INTEGER PRIMARY KEY, semana INTEGER DEFAULT 1,
            dia TEXT DEFAULT 'lunes', objetivo TEXT);

        CREATE TABLE IF NOT EXISTS rutinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            semana INTEGER, dia TEXT, orden INTEGER DEFAULT 0,
            ejercicio_id TEXT, ejercicio TEXT, patron TEXT, grupo TEXT,
            rol TEXT, series INTEGER, reps TEXT, notas TEXT,
            emg_score INTEGER DEFAULT 1, completado INTEGER DEFAULT 0);

        CREATE TABLE IF NOT EXISTS pesos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            ejercicio_id TEXT, semana INTEGER, dia TEXT, peso_lbs REAL,
            series_hechas INTEGER, reps_hechas TEXT,
            fecha TEXT DEFAULT (date('now')));

        CREATE TABLE IF NOT EXISTS progreso (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            semana INTEGER, dia TEXT, ejercicio_id TEXT, rir INTEGER,
            progreso_reportado TEXT, fatiga_reportada INTEGER,
            fecha TEXT DEFAULT (date('now')));

        CREATE TABLE IF NOT EXISTS swaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            original_id TEXT, nuevo_id TEXT, grupo TEXT, rol TEXT,
            fecha TEXT DEFAULT (date('now')));

        CREATE TABLE IF NOT EXISTS gamificacion (
            user_id INTEGER PRIMARY KEY, xp_total INTEGER DEFAULT 0,
            racha_actual INTEGER DEFAULT 0, racha_maxima INTEGER DEFAULT 0,
            ultimo_entreno TEXT, nivel TEXT DEFAULT 'Principiante');

        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            badge TEXT, fecha TEXT DEFAULT (date('now')));

        CREATE TABLE IF NOT EXISTS sesion_activa (
            user_id INTEGER PRIMARY KEY, semana INTEGER, dia TEXT,
            ej_idx INTEGER DEFAULT 0, fase TEXT DEFAULT 'ejercicio',
            updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

        CREATE TABLE IF NOT EXISTS peso_flow (
            user_id INTEGER PRIMARY KEY, semana INTEGER, dia TEXT,
            ejercicios TEXT, idx INTEGER DEFAULT 0,
            updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

        CREATE TABLE IF NOT EXISTS milestones (
            user_id INTEGER PRIMARY KEY, semana_max INTEGER DEFAULT 0);

        CREATE TABLE IF NOT EXISTS prioridad_bloques (
            user_id INTEGER, grupo TEXT, semana INTEGER,
            prioridad INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, grupo, semana));

        CREATE TABLE IF NOT EXISTS sesion_ambiente (
            user_id INTEGER PRIMARY KEY, ambiente TEXT DEFAULT 'gym');

        CREATE TABLE IF NOT EXISTS login_tokens (
            token TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used INTEGER DEFAULT 0);

        CREATE TABLE IF NOT EXISTS analisis_historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            fecha TEXT NOT NULL, texto TEXT NOT NULL,
            tipo TEXT DEFAULT 'nocturno');

        CREATE TABLE IF NOT EXISTS pesajes (
            Fecha TEXT PRIMARY KEY, Timestamp INTEGER UNIQUE,
            Peso_kg REAL, Grasa_Porcentaje REAL, Agua REAL,
            Musculo_Pct REAL, Musculo_kg REAL, BMR INTEGER, VisFat REAL,
            BMI REAL, EdadMetabolica INTEGER, FatFreeWeight REAL,
            Proteina REAL, MasaOsea REAL);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_pesajes_ts ON pesajes(Timestamp);
        CREATE INDEX IF NOT EXISTS idx_pesajes_fecha ON pesajes(Fecha);

        CREATE TABLE IF NOT EXISTS historico_dietas (
            fecha TEXT PRIMARY KEY, score_comp INTEGER, estado_mimo TEXT,
            kcal_mult REAL, calorias INTEGER, proteina INTEGER,
            carbs INTEGER, grasas INTEGER, dieta_html TEXT, delta_peso REAL);

        CREATE TABLE IF NOT EXISTS config_nutricion (
            clave TEXT PRIMARY KEY, valor TEXT);
        """)
        conn.execute("INSERT OR IGNORE INTO config_nutricion (clave, valor) VALUES ('kcal_mult','1.0')")
    logger.info("DB inicializada: %s", DB_PATH)

# ── GYM ───────────────────────────────────────────────────────────────────────

def get_allowed_users():
    return {r["user_id"] for r in fetchall("SELECT user_id FROM allowed_users WHERE activo=1")}

def add_allowed_user(user_id):
    execute("INSERT OR IGNORE INTO allowed_users (user_id, activo) VALUES (?,1)", (user_id,))

def get_perfil(user_id):
    row = fetchone("SELECT * FROM usuarios WHERE user_id=?", (user_id,))
    return dict(row) if row else {}

def upsert_perfil(user_id, **kwargs):
    perfil = get_perfil(user_id) or {}
    perfil.update(kwargs)
    perfil["user_id"] = user_id
    cols   = ", ".join(perfil.keys())
    pholds = ", ".join(["?"] * len(perfil))
    sets   = ", ".join(f"{k}=excluded.{k}" for k in perfil if k != "user_id")
    execute(f"INSERT INTO usuarios ({cols}) VALUES ({pholds}) ON CONFLICT(user_id) DO UPDATE SET {sets}",
            tuple(perfil.values()))

def get_estado(user_id):
    row = fetchone("SELECT semana, dia FROM estado WHERE user_id=?", (user_id,))
    return (row["semana"], row["dia"]) if row else (1, "lunes")

def upsert_estado(user_id, semana, dia):
    execute("INSERT INTO estado (user_id,semana,dia) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET semana=?,dia=?",
            (user_id, semana, dia, semana, dia))

def has_plan(user_id):
    row = fetchone("SELECT COUNT(*) as n FROM rutinas WHERE user_id=?", (user_id,))
    return bool(row and row["n"] > 0)

def clear_plan(user_id, keep_swaps=True):
    for tbl in ["rutinas","progreso","estado","sesion_activa","peso_flow"]:
        execute(f"DELETE FROM {tbl} WHERE user_id=?", (user_id,))

def insert_plan(user_id, semanas, swaps, by_id):
    clear_plan(user_id)
    swap_map = {s["original_id"]: s["nuevo_id"] for s in swaps if s.get("nuevo_id")}
    n = 0
    with get_db() as conn:
        for sem in semanas:
            for dia_obj in sem["dias"]:
                dia = dia_obj["dia"]
                for orden, ej in enumerate(dia_obj["ejercicios"]):
                    eid = swap_map.get(ej.get("id",""), ej.get("id",""))
                    obj = by_id.get(eid)
                    if not obj: continue
                    conn.execute("""INSERT INTO rutinas
                        (user_id,semana,dia,orden,ejercicio_id,ejercicio,patron,grupo,rol,series,reps,notas,emg_score,completado)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                        (user_id, sem["semana"], dia, orden,
                         obj.id, obj.nombre, obj.patron, obj.grupo, obj.rol,
                         ej.get("series",3), ej.get("reps","8-10"), obj.cue, obj.emg_score))
                    n += 1
    return n

def get_ejercicios_dia(user_id, semana, dia):
    return [dict(r) for r in fetchall(
        "SELECT * FROM rutinas WHERE user_id=? AND semana=? AND dia=? ORDER BY orden",
        (user_id, semana, dia))]

def get_dias_semana(user_id, semana):
    return [r["dia"] for r in fetchall(
        "SELECT DISTINCT dia FROM rutinas WHERE user_id=? AND semana=? ORDER BY id",
        (user_id, semana))]

def rutina_completa(user_id, semana, dia):
    rows = fetchall("SELECT completado FROM rutinas WHERE user_id=? AND semana=? AND dia=?",
                    (user_id, semana, dia))
    return bool(rows) and all(r["completado"] for r in rows)

def avanzar_dia(user_id, semana, dia_actual, max_semana=4):
    dias = get_dias_semana(user_id, semana)
    if dia_actual in dias:
        idx = dias.index(dia_actual)
        if idx + 1 < len(dias):
            return semana, dias[idx+1]
    if semana < max_semana:
        nueva = semana + 1
        dias_nueva = get_dias_semana(user_id, nueva)
        if dias_nueva:
            return nueva, dias_nueva[0]
    return semana, dia_actual

def get_ultimo_peso(user_id, ejercicio_id):
    row = fetchone("SELECT peso_lbs,series_hechas,reps_hechas,fecha FROM pesos WHERE user_id=? AND ejercicio_id=? ORDER BY semana DESC, id DESC LIMIT 1",
                   (user_id, ejercicio_id))
    return dict(row) if row else None

def get_peso_sugerido(user_id, ejercicio_id):
    u = get_ultimo_peso(user_id, ejercicio_id)
    if not u or not u.get("peso_lbs"): return None
    return round(float(u["peso_lbs"]) + 5.0, 1)

def save_peso(user_id, ejercicio_id, semana, dia, peso_lbs, series=None, reps=None):
    execute("INSERT INTO pesos (user_id,ejercicio_id,semana,dia,peso_lbs,series_hechas,reps_hechas) VALUES (?,?,?,?,?,?,?)",
            (user_id, ejercicio_id, semana, dia, peso_lbs, series, reps))

def get_progresion_ejercicio(user_id, ejercicio_id):
    return [dict(r) for r in fetchall(
        "SELECT semana, MAX(peso_lbs) as mejor_peso, series_hechas, reps_hechas FROM pesos WHERE user_id=? AND ejercicio_id=? AND peso_lbs IS NOT NULL GROUP BY semana ORDER BY semana ASC",
        (user_id, ejercicio_id))]

def get_ejercicios_con_historial(user_id):
    return [dict(r) for r in fetchall("""
        SELECT p.ejercicio_id, r.ejercicio, r.grupo,
               COUNT(DISTINCT p.semana) as semanas_registradas,
               MAX(p.peso_lbs) as peso_maximo, MIN(p.peso_lbs) as peso_minimo
        FROM pesos p JOIN rutinas r ON r.user_id=p.user_id AND r.ejercicio_id=p.ejercicio_id
        WHERE p.user_id=? AND p.peso_lbs IS NOT NULL
        GROUP BY p.ejercicio_id HAVING COUNT(DISTINCT p.semana)>=1
        ORDER BY r.grupo, MAX(p.peso_lbs) DESC""", (user_id,))]

def get_resumen_progresion(user_id):
    rows = fetchall("""SELECT ejercicio_id, MIN(peso_lbs) as primer_peso, MAX(peso_lbs) as ultimo_peso,
        MAX(semana) as ultima_semana, MIN(semana) as primera_semana
        FROM pesos WHERE user_id=? AND peso_lbs IS NOT NULL GROUP BY ejercicio_id
        HAVING MAX(semana)>MIN(semana) ORDER BY (MAX(peso_lbs)-MIN(peso_lbs)) DESC""", (user_id,))
    return {r["ejercicio_id"]: dict(r) for r in rows}

def get_progresiones_con_peso(user_id, semana):
    return [dict(r) for r in fetchall("""
        SELECT p.ejercicio_id, r.ejercicio, r.grupo,
               MAX(p.peso_lbs) as peso_actual,
               (SELECT MAX(p2.peso_lbs) FROM pesos p2 WHERE p2.user_id=p.user_id AND p2.ejercicio_id=p.ejercicio_id AND p2.semana<p.semana) as peso_anterior
        FROM pesos p JOIN rutinas r ON r.user_id=p.user_id AND r.ejercicio_id=p.ejercicio_id
        WHERE p.user_id=? AND p.semana=? AND p.peso_lbs IS NOT NULL
        GROUP BY p.ejercicio_id HAVING peso_actual>COALESCE(peso_anterior,0)
        ORDER BY (peso_actual-COALESCE(peso_anterior,0)) DESC""", (user_id, semana))]

def save_progreso_sesion(user_id, semana, dia, rir=2, progresion="si", fatiga=2):
    execute("INSERT INTO progreso (user_id,semana,dia,rir,progreso_reportado,fatiga_reportada) VALUES (?,?,?,?,?,?)",
            (user_id, semana, dia, rir, progresion, fatiga))

def get_stats(user_id):
    row = fetchone("SELECT COUNT(DISTINCT dia||semana) as rutinas_completas FROM progreso WHERE user_id=?", (user_id,))
    return {"rutinas_completas": row["rutinas_completas"] if row else 0}

def get_swaps(user_id):
    return [dict(r) for r in fetchall("SELECT original_id, nuevo_id FROM swaps WHERE user_id=?", (user_id,))]

def save_swap(user_id, original_id, nuevo_id, grupo, rol):
    execute("INSERT INTO swaps (user_id,original_id,nuevo_id,grupo,rol) VALUES (?,?,?,?,?)",
            (user_id, original_id, nuevo_id, grupo, rol))

def save_sesion_activa(user_id, semana, dia, ej_idx, fase="ejercicio"):
    execute("INSERT INTO sesion_activa (user_id,semana,dia,ej_idx,fase) VALUES (?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET semana=?,dia=?,ej_idx=?,fase=?,updated=CURRENT_TIMESTAMP",
            (user_id,semana,dia,ej_idx,fase,semana,dia,ej_idx,fase))

def get_sesion_activa(user_id):
    row = fetchone("SELECT * FROM sesion_activa WHERE user_id=?", (user_id,))
    return dict(row) if row else None

def clear_sesion_activa(user_id):
    execute("DELETE FROM sesion_activa WHERE user_id=?", (user_id,))

def save_peso_flow(user_id, semana, dia, ejercicios, idx):
    import json
    ejs = json.dumps(ejercicios)
    execute("INSERT INTO peso_flow (user_id,semana,dia,ejercicios,idx) VALUES (?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET semana=?,dia=?,ejercicios=?,idx=?,updated=CURRENT_TIMESTAMP",
            (user_id,semana,dia,ejs,idx,semana,dia,ejs,idx))

def get_peso_flow(user_id):
    import json
    row = fetchone("SELECT * FROM peso_flow WHERE user_id=?", (user_id,))
    if not row: return None
    d = dict(row)
    try: d["ejercicios"] = json.loads(d["ejercicios"])
    except: d["ejercicios"] = []
    return d

def clear_peso_flow(user_id):
    execute("DELETE FROM peso_flow WHERE user_id=?", (user_id,))

def create_login_token(user_id):
    import secrets
    token = secrets.token_urlsafe(32)
    execute("INSERT INTO login_tokens (token,user_id) VALUES (?,?)", (token, user_id))
    execute("DELETE FROM login_tokens WHERE created_at < datetime('now','-5 minutes')")
    return token

def consume_login_token(token):
    row = fetchone("SELECT user_id FROM login_tokens WHERE token=? AND used=0 AND created_at > datetime('now','-5 minutes')", (token,))
    if not row: return None
    execute("UPDATE login_tokens SET used=1 WHERE token=?", (token,))
    return int(row["user_id"])

def save_analisis(user_id, texto, tipo="nocturno"):
    from datetime import datetime
    execute("INSERT INTO analisis_historial (user_id,fecha,texto,tipo) VALUES (?,?,?,?)",
            (user_id, datetime.now().strftime("%Y-%m-%d"), texto, tipo))

def get_usuarios_con_recordatorio(hora):
    return [r["user_id"] for r in fetchall(
        "SELECT u.user_id FROM usuarios u JOIN allowed_users a ON a.user_id=u.user_id WHERE u.hora_recordatorio=? AND a.activo=1",
        (hora,))]

# ── CUERPO ────────────────────────────────────────────────────────────────────

def guardar_pesaje(m):
    with get_db() as conn:
        cur = conn.execute("""INSERT OR IGNORE INTO pesajes
            (Fecha,Timestamp,Peso_kg,Grasa_Porcentaje,Agua,Musculo_Pct,Musculo_kg,BMR,VisFat,BMI,EdadMetabolica,FatFreeWeight,Proteina,MasaOsea)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (m["fecha_str"],m["time_stamp"],m["peso"],m["grasa"],m["agua"],
             m["musculo_pct"],m.get("masa_muscular_kg"),m.get("bmr"),
             m.get("grasa_visceral"),m.get("bmi"),m.get("edad_metabolica"),
             m.get("fat_free_weight"),m.get("proteina"),m.get("masa_osea")))
        return cur.rowcount == 1

def get_ultimo_pesaje():
    row = fetchone("SELECT * FROM pesajes ORDER BY Fecha DESC LIMIT 1")
    return dict(row) if row else None

def get_pesaje_anterior(fecha_actual):
    row = fetchone("SELECT * FROM pesajes WHERE Fecha < ? ORDER BY Fecha DESC LIMIT 1", (fecha_actual,))
    return dict(row) if row else None

def get_historial_pesajes(dias=90):
    return [dict(r) for r in fetchall(
        "SELECT * FROM pesajes WHERE Fecha >= date('now', ?) ORDER BY Fecha ASC",
        (f"-{dias} days",))]

def get_tendencia_7d(fecha_actual):
    row = fetchone("""SELECT AVG(Peso_kg) as peso_prom, AVG(Grasa_Porcentaje) as grasa_prom, AVG(Musculo_Pct) as musculo_prom
        FROM pesajes WHERE Fecha < ? AND Fecha >= date(?, '-7 days')""", (fecha_actual, fecha_actual))
    return dict(row) if row else None

def get_multiplicador():
    row = fetchone("SELECT valor FROM config_nutricion WHERE clave='kcal_mult'")
    return float(row["valor"]) if row else 1.0

def set_multiplicador(valor):
    execute("INSERT INTO config_nutricion (clave,valor) VALUES ('kcal_mult',?) ON CONFLICT(clave) DO UPDATE SET valor=?",
            (str(valor), str(valor)))

def get_ultima_dieta():
    row = fetchone("SELECT * FROM historico_dietas ORDER BY fecha DESC LIMIT 1")
    return dict(row) if row else None

def guardar_dieta(fecha, score, estado_mimo, kcal_mult, calorias, proteina, carbs, grasas, dieta_json, delta_peso=None):
    execute("""INSERT INTO historico_dietas (fecha,score_comp,estado_mimo,kcal_mult,calorias,proteina,carbs,grasas,dieta_html,delta_peso)
        VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(fecha) DO UPDATE SET
        score_comp=?,estado_mimo=?,kcal_mult=?,calorias=?,proteina=?,carbs=?,grasas=?,dieta_html=?,delta_peso=?""",
        (fecha,score,estado_mimo,kcal_mult,calorias,proteina,carbs,grasas,dieta_json,delta_peso,
         score,estado_mimo,kcal_mult,calorias,proteina,carbs,grasas,dieta_json,delta_peso))

def job_ya_ejecutado_hoy():
    from datetime import datetime
    hoy = datetime.now().strftime("%Y-%m-%d")
    return fetchone("SELECT fecha FROM historico_dietas WHERE fecha=?", (hoy,)) is not None
