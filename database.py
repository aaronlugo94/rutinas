"""
database.py — Capa de acceso a datos con SQLite WAL.
Una sola función get_db() como context manager.
"""
from __future__ import annotations

import sqlite3
import logging
import os
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "gymbot.db")


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetchone(sql: str, params=()) -> sqlite3.Row | None:
    with get_db() as conn:
        return conn.execute(sql, params).fetchone()


def fetchall(sql: str, params=()) -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(sql, params).fetchall()


def execute(sql: str, params=()) -> None:
    with get_db() as conn:
        conn.execute(sql, params)


# ─── INIT DB ──────────────────────────────────────────────────────────────────

def init_db() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS usuarios (
        user_id INTEGER PRIMARY KEY,
        nombre TEXT,
        genero TEXT DEFAULT 'mujer',
        nivel TEXT DEFAULT 'principiante',
        objetivo TEXT DEFAULT 'general',
        limitaciones TEXT DEFAULT 'ninguna',
        dias INTEGER DEFAULT 3,
        duracion_min INTEGER DEFAULT 60,
        ambiente_preferido TEXT DEFAULT 'gym',
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS estado (
        user_id INTEGER PRIMARY KEY,
        semana INTEGER DEFAULT 1,
        dia TEXT DEFAULT 'pendiente',
        objetivo TEXT DEFAULT 'general'
    );

    CREATE TABLE IF NOT EXISTS rutinas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        semana INTEGER NOT NULL,
        dia TEXT NOT NULL,
        grupo TEXT,
        ejercicio_id TEXT NOT NULL,
        ejercicio TEXT NOT NULL,
        patron TEXT,
        orden INTEGER DEFAULT 1,
        series INTEGER DEFAULT 3,
        reps TEXT DEFAULT '10-12',
        notas TEXT DEFAULT '',
        emg_score INTEGER DEFAULT 1,
        completado INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS progreso (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        semana INTEGER NOT NULL,
        dia TEXT NOT NULL,
        ejercicio_id TEXT,
        rir_reportado INTEGER,
        progreso_reportado TEXT,
        fatiga_reportada INTEGER,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS swaps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        original_id TEXT NOT NULL,
        reemplazo_id TEXT NOT NULL,
        grupo TEXT,
        rol TEXT,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS milestones (
        user_id INTEGER NOT NULL,
        key TEXT NOT NULL,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, key)
    );

    CREATE TABLE IF NOT EXISTS prioridad_bloques (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        bloque INTEGER NOT NULL,
        semana_inicio INTEGER,
        grupo_prioritario TEXT,
        grupo_secundario TEXT,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS allowed_users (
        user_id INTEGER PRIMARY KEY,
        activo INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS sesion_ambiente (
        user_id INTEGER NOT NULL,
        semana INTEGER NOT NULL,
        dia TEXT NOT NULL,
        ambiente TEXT DEFAULT 'gym',
        PRIMARY KEY (user_id, semana, dia)
    );


    CREATE TABLE IF NOT EXISTS gamificacion (
        user_id INTEGER PRIMARY KEY,
        racha_actual INTEGER DEFAULT 0,
        racha_maxima INTEGER DEFAULT 0,
        ultima_sesion TEXT,
        xp_total INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        badge_key TEXT NOT NULL,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, badge_key)
    );

    CREATE INDEX IF NOT EXISTS idx_badges_user ON badges(user_id);

    CREATE INDEX IF NOT EXISTS idx_rutinas_user_sem_dia
        ON rutinas(user_id, semana, dia);
    CREATE INDEX IF NOT EXISTS idx_progreso_user
        ON progreso(user_id, semana, dia);
    """
    with get_db() as conn:
        for stmt in ddl.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
    logger.info("DB inicializada: %s", DB_PATH)


# ─── USUARIOS Y PERFIL ────────────────────────────────────────────────────────

def get_allowed_users() -> set[int]:
    rows = fetchall("SELECT user_id FROM allowed_users WHERE activo=1")
    return {r["user_id"] for r in rows}


def add_allowed_user(user_id: int) -> None:
    execute("INSERT OR REPLACE INTO allowed_users (user_id, activo) VALUES (?,1)", (user_id,))


def upsert_perfil(user_id: int, **kwargs) -> None:
    cols  = [k for k in kwargs if k in (
        "nombre","genero","nivel","objetivo","limitaciones",
        "dias","duracion_min","ambiente_preferido",
    )]
    if not cols:
        return
    sets  = ", ".join(f"{c}=?" for c in cols)
    vals  = [kwargs[c] for c in cols]
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO usuarios (user_id) VALUES (?)", (user_id,))
        conn.execute(f"UPDATE usuarios SET {sets} WHERE user_id=?", (*vals, user_id))


def get_perfil(user_id: int) -> dict:
    row = fetchone("SELECT * FROM usuarios WHERE user_id=?", (user_id,))
    if not row:
        return {"nivel": "principiante", "objetivo": "general", "limitaciones": "ninguna",
                "dias": 3, "duracion_min": 60, "genero": "mujer", "ambiente_preferido": "gym"}
    return dict(row)


def get_estado(user_id: int) -> tuple[int, str]:
    row = fetchone("SELECT semana, dia FROM estado WHERE user_id=?", (user_id,))
    return (row["semana"], row["dia"]) if row else (1, "pendiente")


def upsert_estado(user_id: int, semana: int, dia: str, **kwargs) -> None:
    obj = kwargs.get("objetivo")
    if obj:
        execute(
            "INSERT INTO estado (user_id, semana, dia, objetivo) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET semana=?, dia=?, objetivo=?",
            (user_id, semana, dia, obj, semana, dia, obj),
        )
    else:
        execute(
            "INSERT INTO estado (user_id, semana, dia) VALUES (?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET semana=?, dia=?",
            (user_id, semana, dia, semana, dia),
        )


def has_plan(user_id: int) -> bool:
    row = fetchone("SELECT 1 FROM rutinas WHERE user_id=? LIMIT 1", (user_id,))
    return row is not None


def clear_plan(user_id: int, keep_swaps: bool = False) -> None:
    with get_db() as conn:
        for tabla in ("rutinas", "progreso", "prioridad_bloques", "sesion_ambiente"):
            conn.execute(f"DELETE FROM {tabla} WHERE user_id=?", (user_id,))
        if not keep_swaps:
            conn.execute("DELETE FROM swaps WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM estado WHERE user_id=?", (user_id,))


# ─── PLAN Y EJERCICIOS ────────────────────────────────────────────────────────

def insert_plan(user_id: int, semanas: list[dict], swaps: list[dict], by_id: dict) -> int:
    swap_map = {s["original_id"]: s["reemplazo_id"] for s in swaps}
    total = 0
    with get_db() as conn:
        for sem in semanas:
            sem_num = sem.get("semana", 1)
            for d in sem.get("dias", []):
                dia   = d.get("dia", "")
                grupo = d.get("grupo", "general")
                for e in d.get("ejercicios", []):
                    eid   = e.get("ejercicio_id", "")
                    eid   = swap_map.get(eid, eid)
                    ej_obj = by_id.get(eid)
                    conn.execute("""
                        INSERT INTO rutinas
                        (user_id, semana, dia, grupo, ejercicio_id, ejercicio,
                         patron, orden, series, reps, notas, emg_score)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        user_id, sem_num, dia, grupo, eid,
                        ej_obj.nombre if ej_obj else e.get("ejercicio", eid),
                        ej_obj.patron if ej_obj else e.get("patron", ""),
                        e.get("orden", 1),
                        e.get("series", 3),
                        str(e.get("reps", "10")),
                        e.get("notas", "")[:100],
                        ej_obj.emg_score if ej_obj else 1,
                    ))
                    total += 1
    return total


def get_ejercicios_dia(user_id: int, semana: int, dia: str) -> list[dict]:
    rows = fetchall("""
        SELECT r.id, r.ejercicio_id, r.ejercicio, r.series, r.reps,
               r.notas, r.completado, r.patron, r.grupo, r.orden, r.emg_score
        FROM rutinas r
        WHERE r.user_id=? AND r.semana=? AND r.dia=?
        ORDER BY r.orden
    """, (user_id, semana, dia))
    return [dict(r) for r in rows]


def get_dias_semana(user_id: int, semana: int) -> list[str]:
    rows = fetchall("""
        SELECT DISTINCT dia FROM rutinas
        WHERE user_id=? AND semana=?
        ORDER BY CASE dia
            WHEN 'lunes'    THEN 1 WHEN 'martes'   THEN 2
            WHEN 'miercoles' THEN 3 WHEN 'jueves'   THEN 4
            WHEN 'viernes'  THEN 5 WHEN 'sabado'   THEN 6
            WHEN 'domingo'  THEN 7 ELSE 8 END
    """, (user_id, semana))
    return [r["dia"] for r in rows]


def toggle_ejercicio(user_id: int, semana: int, dia: str, ejercicio_id: str) -> bool:
    row = fetchone(
        "SELECT completado FROM rutinas WHERE user_id=? AND semana=? AND dia=? AND ejercicio_id=?",
        (user_id, semana, dia, ejercicio_id),
    )
    nuevo = 0 if (row and row["completado"]) else 1
    execute(
        "UPDATE rutinas SET completado=? WHERE user_id=? AND semana=? AND dia=? AND ejercicio_id=?",
        (nuevo, user_id, semana, dia, ejercicio_id),
    )
    return bool(nuevo)


def rutina_completa(user_id: int, semana: int, dia: str) -> bool:
    row = fetchone("""
        SELECT COUNT(*) as total, SUM(completado) as hechos
        FROM rutinas WHERE user_id=? AND semana=? AND dia=?
    """, (user_id, semana, dia))
    return bool(row and row["total"] and int(row["total"] or 0) == int(row["hechos"] or 0))


def semana_completa(user_id: int, semana: int) -> bool:
    dias = get_dias_semana(user_id, semana)
    return all(rutina_completa(user_id, semana, d) for d in dias) if dias else False


def avanzar_dia(user_id: int, semana: int, dia: str, max_semana: int = 4) -> tuple[int, str]:
    dias = get_dias_semana(user_id, semana)
    if not dias:
        return semana, "fin"
    try:
        idx = dias.index(dia)
    except ValueError:
        return semana, dias[0]
    if idx + 1 < len(dias):
        return semana, dias[idx + 1]
    if semana < max_semana:
        nueva_sem   = semana + 1
        dias_nuevos = get_dias_semana(user_id, nueva_sem)
        return (nueva_sem, dias_nuevos[0]) if dias_nuevos else (nueva_sem + 1, "fin")
    return semana + 1, "fin"


# ─── PROGRESO ─────────────────────────────────────────────────────────────────

def save_progreso_sesion(
    user_id: int, semana: int, dia: str,
    rir=None, progresion=None, fatiga=None, ejercicio_id=None
) -> None:
    row = fetchone(
        "SELECT id FROM progreso WHERE user_id=? AND semana=? AND dia=? AND ejercicio_id IS NULL LIMIT 1",
        (user_id, semana, dia),
    )
    if row:
        with get_db() as conn:
            if rir is not None:
                conn.execute("UPDATE progreso SET rir_reportado=? WHERE id=?",     (rir, row["id"]))
            if progresion is not None:
                conn.execute("UPDATE progreso SET progreso_reportado=? WHERE id=?", (progresion, row["id"]))
            if fatiga is not None:
                conn.execute("UPDATE progreso SET fatiga_reportada=? WHERE id=?",  (fatiga, row["id"]))
    else:
        execute("""
            INSERT INTO progreso (user_id,semana,dia,ejercicio_id,rir_reportado,progreso_reportado,fatiga_reportada)
            VALUES (?,?,?,?,?,?,?)
        """, (user_id, semana, dia, ejercicio_id, rir, progresion, fatiga))


def get_historial_sesiones(user_id: int, grupo: str | None = None, limit: int = 6) -> list[dict]:
    if grupo:
        rows = fetchall("""
            SELECT p.semana, p.dia, p.rir_reportado, p.progreso_reportado, p.fatiga_reportada
            FROM progreso p
            WHERE p.user_id=? AND p.fatiga_reportada IS NOT NULL
              AND EXISTS (SELECT 1 FROM rutinas r WHERE r.user_id=p.user_id
                         AND r.semana=p.semana AND r.dia=p.dia AND r.grupo=?)
            ORDER BY p.semana DESC, p.id DESC LIMIT ?
        """, (user_id, grupo, limit))
    else:
        rows = fetchall("""
            SELECT semana, dia, rir_reportado, progreso_reportado, fatiga_reportada
            FROM progreso WHERE user_id=? AND fatiga_reportada IS NOT NULL
            ORDER BY semana DESC, id DESC LIMIT ?
        """, (user_id, limit))
    return [dict(r) for r in rows]


def get_stats(user_id: int) -> dict:
    total = fetchone("SELECT COUNT(*) as n FROM rutinas WHERE user_id=? AND completado=1", (user_id,))
    ruts  = fetchone("""
        SELECT COUNT(*) as n FROM (
            SELECT semana, dia FROM rutinas WHERE user_id=? AND completado=1
            GROUP BY semana, dia
            HAVING COUNT(*) = (
                SELECT COUNT(*) FROM rutinas r2
                WHERE r2.user_id=? AND r2.semana=rutinas.semana AND r2.dia=rutinas.dia
            )
        )
    """, (user_id, user_id))
    return {
        "total_ejercicios":  int(total["n"] if total else 0),
        "rutinas_completas": int(ruts["n"]  if ruts  else 0),
    }


# ─── SWAPS ────────────────────────────────────────────────────────────────────

def get_swaps(user_id: int) -> list[dict]:
    rows = fetchall("SELECT original_id, reemplazo_id, grupo, rol FROM swaps WHERE user_id=?", (user_id,))
    return [dict(r) for r in rows]


def save_swap(user_id: int, original: str, reemplazo: str, grupo: str, rol: str) -> None:
    execute(
        "INSERT INTO swaps (user_id, original_id, reemplazo_id, grupo, rol) VALUES (?,?,?,?,?)",
        (user_id, original, reemplazo, grupo, rol),
    )


# ─── MILESTONES ───────────────────────────────────────────────────────────────

def check_milestone(user_id: int, key: str) -> bool:
    row = fetchone("SELECT 1 FROM milestones WHERE user_id=? AND key=?", (user_id, key))
    if row:
        return False
    execute("INSERT OR IGNORE INTO milestones (user_id, key) VALUES (?,?)", (user_id, key))
    return True


# ─── AJUSTE SERIES ────────────────────────────────────────────────────────────

def adjust_series(user_id: int, semana: int, dia: str, delta: int, solo_accesorios: bool = False) -> None:
    filtro = "AND orden > 1" if solo_accesorios else ""
    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT id, series FROM rutinas
            WHERE user_id=? AND semana=? AND dia=? {filtro}
            AND ejercicio_id NOT LIKE 'CAR%'
        """, (user_id, semana, dia)).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE rutinas SET series=? WHERE id=?",
                (max(2, min(6, int(row["series"] or 3) + delta)), row["id"]),
            )

