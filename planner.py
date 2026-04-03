"""
planner.py — Generador de planes determinístico. Sin Gemini.

Lógica:
  1. Determina el split según objetivo, días y género
  2. Para cada día selecciona ejercicios por rol y patrón
  3. Aplica restricciones de nivel y limitaciones
  4. Asigna series/reps según semana (periodización lineal)
  5. Rota ejercicios entre semanas para variedad

Sin timeouts. Sin costos de API. Sin sorpresas.
Gemini queda solo para el coach conversacional en texto libre.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

import catalog as cat
from catalog import (
    Ejercicio, BY_ID, BY_GRUPO, CALENTAMIENTO,
    SESION_GLUTEO, ROTACION_ONDULATORIO,
    MAX_POR_PATRON, MAX_POR_PATRON_DEFAULT, COMPUESTOS,
)

Nivel      = Literal["principiante", "intermedio", "avanzado"]
Objetivo   = Literal["gluteo", "peso", "general"]
Ambiente   = Literal["gym", "home", "band"]
Limitacion = Literal["ninguna", "rodilla", "espalda", "hombro"]


# ══════════════════════════════════════════════════════════════════════════════
# SPLITS — qué grupo muscular va cada día
# ══════════════════════════════════════════════════════════════════════════════

SPLITS: dict[str, dict[int, list[str]]] = {
    "gluteo": {
        3: ["gluteo",  "empuje",  "gluteo"],
        4: ["gluteo",  "empuje",  "gluteo",  "tiron"],
        5: ["gluteo",  "empuje",  "tiron",   "gluteo",  "pierna"],
    },
    "peso": {
        3: ["pierna",  "empuje",  "tiron"],
        4: ["pierna",  "empuje",  "tiron",   "pierna"],
        5: ["pierna",  "empuje",  "tiron",   "pierna",  "empuje"],
    },
    "general": {
        3: ["pierna",  "empuje",  "tiron"],
        4: ["pierna",  "empuje",  "tiron",   "pierna"],
        5: ["pierna",  "empuje",  "tiron",   "pierna",  "tiron"],
    },
}

DIAS_NOMBRES: dict[int, list[str]] = {
    3: ["lunes",   "miercoles", "viernes"],
    4: ["lunes",   "martes",    "jueves",   "viernes"],
    5: ["lunes",   "martes",    "miercoles","jueves",  "viernes"],
}


# ══════════════════════════════════════════════════════════════════════════════
# PLANTILLAS POR GRUPO — qué rol va en cada posición del día
# ══════════════════════════════════════════════════════════════════════════════

# Cada entrada: (rol, restriccion_patron_opcional)
# El generador rellena posición 1-4 con fuerza, posición 5 siempre cardio

PLANTILLAS: dict[str, list[tuple[str, str | None]]] = {
    "gluteo": [
        # Orden por EMG: puente_cadera primero (200% MVIC), bisagra después, etc.
        ("principal",   "puente_cadera"),          # hip thrust, glute bridge
        ("principal",   "bisagra_cadera"),          # RDL, good morning
        ("principal",   "desplante_unilateral"),    # búlgara, step-up, desplante
        ("aislamiento", None),                      # patada, abducción, curl femoral
    ],
    "pierna": [
        ("principal",   "sentadilla"),              # sentadilla, prensa, hack — mayor EMG
        ("aislamiento", "curl_femoral"),            # curl femoral — isquiotibial siempre
        ("principal",   "prensa"),                  # prensa como compuesto secundario
        ("aislamiento", None),                      # extensión cuád, pantorrilla, curl pie
    ],
    "empuje": [
        ("principal",   "press_horizontal"),        # press pecho
        ("principal",   "press_inclinado"),         # press inclinado
        ("principal",   "press_vertical"),          # press hombro
        ("aislamiento", None),                      # lateral, tríceps, aperturas
    ],
    "tiron": [
        ("principal",   "jalon_vertical"),          # jalón
        ("principal",   "remo_horizontal"),         # remo
        ("aislamiento", "hombro_posterior"),        # face pull — siempre (salud hombro)
        ("aislamiento", "biceps"),                  # curl bíceps o martillo
    ],
    "core": [
        ("core_estabilidad", None),
        ("core_dinamico",    None),
        ("core_estabilidad", None),
        ("core_dinamico",    None),
    ],
    # fallback para splits no definidos
    "general": [
        ("principal",   None),
        ("secundario",  None),
        ("aislamiento", None),
        ("aislamiento", None),
    ],
}

# Ejercicios prohibidos por limitación física
PROHIBIDOS_POR_LIMITACION: dict[str, set[str]] = {
    "rodilla": {
        "GLU_G06",  # búlgara
        "PIE_G01",  # sentadilla libre
        "PIE_G08",  # desplante caminando
        "PIE_H04",  # búlgara home
        "GLU_H06",  # búlgara home
    },
    "espalda": {
        "GLU_G04",  # RDL barra
        "GLU_G12",  # good morning
        "PIE_G01",  # sentadilla libre
        "GLU_H04",  # buenos días home
    },
    "hombro": {
        "EMP_G05",  # press hombro
        "EMP_G08",  # press arnold
        "EMP_H05",  # press hombro home
        "EMP_H08",  # press hombro banda
    },
    "ninguna": set(),
}

# Cardio preferido por objetivo
CARDIO_PREFERIDO: dict[str, dict[str, list[str]]] = {
    "gluteo": {
        "gym":  ["CAR_G01", "CAR_G03"],   # caminata inclinada activa glúteo
        "home": ["CAR_H05", "CAR_H01"],   # step, caminata
        "band": ["CAR_H01", "CAR_H03"],
    },
    "peso": {
        "gym":  ["CAR_G01", "CAR_G02", "CAR_G03"],
        "home": ["CAR_H01", "CAR_H02", "CAR_H03"],
        "band": ["CAR_H01", "CAR_H03"],
    },
    "general": {
        "gym":  ["CAR_G02", "CAR_G03", "CAR_G05"],
        "home": ["CAR_H01", "CAR_H03", "CAR_H04"],
        "band": ["CAR_H01", "CAR_H02"],
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# SERIES / REPS POR SEMANA
# Periodización lineal clásica — S4 siempre deload
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    series_principal:   int
    series_secundario:  int
    series_aislamiento: int
    reps_compuesto:     str
    reps_accesorio:     str
    rir:                int
    es_deload:          bool = False


CONFIGS_POR_SEMANA: dict[str, dict[int, Config]] = {
    "principiante": {
        1: Config(3, 3, 3, "12-15", "15",   3),
        2: Config(3, 3, 3, "10-12", "12-15", 2),
        3: Config(3, 3, 3, "10-12", "12-15", 2),
        4: Config(2, 2, 2, "12-15", "15",   4, es_deload=True),
    },
    "intermedio": {
        1: Config(4, 3, 3, "10-12", "12-15", 2),
        2: Config(4, 4, 3, "8-10",  "12",    2),
        3: Config(4, 4, 3, "6-8",   "10-12", 1),
        4: Config(3, 2, 2, "10-12", "15",    4, es_deload=True),
    },
    "avanzado": {
        1: Config(5, 4, 3, "8-10",  "12",    2),
        2: Config(5, 4, 3, "6-8",   "10-12", 1),
        3: Config(5, 4, 4, "5-6",   "8-10",  1),
        4: Config(3, 3, 2, "10-12", "15",    4, es_deload=True),
    },
}


def _config(nivel: str, semana: int) -> Config:
    return CONFIGS_POR_SEMANA.get(nivel, CONFIGS_POR_SEMANA["intermedio"]).get(
        semana, CONFIGS_POR_SEMANA["intermedio"][1]
    )


# ══════════════════════════════════════════════════════════════════════════════
# SELECCIÓN DE EJERCICIOS
# ══════════════════════════════════════════════════════════════════════════════

def _candidatos(
    grupo: str,
    rol: str,
    patron_req: str | None,
    ambiente: str,
    nivel: str,
    prohibidos: set[str],
    ya_usados_patron: dict[str, int],
    ya_usados_ids: set[str],
    semana: int,
    rotacion_seed: int,
) -> Ejercicio | None:
    """
    Selecciona el mejor ejercicio para una posición dada.
    Criterios en orden: patron_req > EMG > nivel > rotación entre semanas.
    """
    NIVEL_ORDEN = {"principiante": 0, "intermedio": 1, "avanzado": 2}
    nivel_num   = NIVEL_ORDEN.get(nivel, 1)

    pool = [
        e for e in BY_GRUPO.get(grupo, [])
        if e.rol == rol
        and ambiente in e.ambiente
        and e.id not in prohibidos
        and e.id not in ya_usados_ids
        and NIVEL_ORDEN.get(e.nivel_min, 0) <= nivel_num
        and (patron_req is None or e.patron == patron_req)
        and ya_usados_patron.get(e.patron, 0) < MAX_POR_PATRON.get(e.patron, MAX_POR_PATRON_DEFAULT)
    ]

    if not pool:
        # Relajar restricción de patrón si no hay candidatos
        if patron_req:
            return _candidatos(grupo, rol, None, ambiente, nivel,
                               prohibidos, ya_usados_patron, ya_usados_ids,
                               semana, rotacion_seed)
        return None

    # Ordenar: EMG descendente, luego rotar entre semanas para variedad
    pool.sort(key=lambda e: (-e.emg_score, e.id))

    # Rotación entre semanas: semana 1→2→3 usan ejercicios diferentes del pool
    # Semana 4 (deload) vuelve a semana 1
    sem_idx = (semana - 1) % 3
    idx     = (rotacion_seed + sem_idx) % len(pool)
    return pool[idx]


def _seleccionar_cardio(objetivo: str, ambiente: str, semana: int) -> dict:
    prefs = CARDIO_PREFERIDO.get(objetivo, CARDIO_PREFERIDO["general"])
    ids   = prefs.get(ambiente, prefs.get("gym", ["CAR_G01"]))
    # Rota el cardio entre semanas también
    eid   = ids[(semana - 1) % len(ids)]
    ej    = BY_ID.get(eid)
    if not ej:
        eid = "CAR_G01"
        ej  = BY_ID[eid]
    return {
        "ejercicio_id": eid,
        "ejercicio":    ej.nombre,
        "patron":       ej.patron,
        "emg_score":    ej.emg_score,
        "orden":        5,
        "series":       1,
        "reps":         "20min",
        "notas":        ej.cue[:60] if ej.cue else "Zona 2 — si puedes hablar, estás bien",
        "completado":   0,
    }


def _tipo_sesion_gluteo(semana: int, num_dia_gluteo: int) -> tuple[str, dict]:
    rotacion = ROTACION_ONDULATORIO.get(semana, ROTACION_ONDULATORIO[1])
    clave    = f"g{num_dia_gluteo}"
    tipo     = rotacion.get(clave, "hipertrofia")
    return tipo, SESION_GLUTEO.get(tipo, SESION_GLUTEO["hipertrofia"])


def _generar_dia(
    dia_nombre: str,
    grupo: str,
    nivel: str,
    objetivo: str,
    ambiente: str,
    limitacion: str,
    semana: int,
    num_dia_gluteo: int = 0,   # solo relevante si grupo == "gluteo"
    seed_base: int = 0,
) -> dict:
    """Genera un día completo con 5 ejercicios."""

    prohibidos  = PROHIBIDOS_POR_LIMITACION.get(limitacion, set())
    cfg         = _config(nivel, semana)
    plantilla   = PLANTILLAS.get(grupo, PLANTILLAS["general"])

    ya_patron: dict[str, int] = {}
    ya_ids:    set[str]       = set()
    ejercicios: list[dict]    = []

    # Config especial para sesión de glúteo (periodización ondulatoria)
    tipo_gluteo = ""
    if grupo == "gluteo" and num_dia_gluteo > 0:
        tipo_gluteo, ses_info = _tipo_sesion_gluteo(semana, num_dia_gluteo)
        reps_glut = ses_info["reps"]
        rir_glut  = ses_info.get("rir", cfg.rir)
    else:
        reps_glut = None
        rir_glut  = cfg.rir

    for orden_idx, (rol, patron_req) in enumerate(plantilla, 1):
        seed = seed_base + orden_idx
        ej   = _candidatos(
            grupo, rol, patron_req, ambiente, nivel,
            prohibidos, ya_patron, ya_ids, semana, seed,
        )
        if not ej:
            continue

        ya_patron[ej.patron] = ya_patron.get(ej.patron, 0) + 1
        ya_ids.add(ej.id)

        # Series según rol
        if ej.es_principal():
            series = cfg.series_principal
        elif rol == "secundario":
            series = cfg.series_secundario
        else:
            series = cfg.series_aislamiento

        # Reps
        if ej.patron in COMPUESTOS:
            reps = reps_glut if (grupo == "gluteo" and reps_glut) else cfg.reps_compuesto
        else:
            reps = cfg.reps_accesorio

        ejercicios.append({
            "ejercicio_id": ej.id,
            "ejercicio":    ej.nombre,
            "patron":       ej.patron,
            "emg_score":    ej.emg_score,
            "orden":        orden_idx,
            "series":       series,
            "reps":         reps,
            "notas":        ej.cue[:70] if ej.cue else "",
            "completado":   0,
        })

    # Cardio siempre al final
    ejercicios.append(_seleccionar_cardio(objetivo, ambiente, semana))
    for i, e in enumerate(ejercicios, 1):
        e["orden"] = i

    return {
        "dia":        dia_nombre,
        "grupo":      grupo,
        "ejercicios": ejercicios,
    }


# ══════════════════════════════════════════════════════════════════════════════
# API PÚBLICA
# ══════════════════════════════════════════════════════════════════════════════

def generar_plan(
    nivel:      str = "intermedio",
    objetivo:   str = "general",
    dias:       int = 4,
    ambiente:   str = "gym",
    limitacion: str = "ninguna",
) -> list[dict]:
    """
    Genera 4 semanas de plan de entrenamiento.
    Retorna lista de dicts compatible con db.insert_plan().
    """
    dias  = max(3, min(5, dias))
    split = SPLITS.get(objetivo, SPLITS["general"]).get(dias, SPLITS["general"][4])
    nombres = DIAS_NOMBRES.get(dias, DIAS_NOMBRES[4])

    semanas = []
    for num_semana in range(1, 5):
        dias_semana = []
        contador_gluteo = 0
        for dia_nombre, grupo in zip(nombres, split):
            if grupo == "gluteo":
                contador_gluteo += 1
                num_g = contador_gluteo
            else:
                num_g = 0

            # seed distinto por semana+día para rotar ejercicios
            seed = num_semana * 100 + nombres.index(dia_nombre) * 10

            dia_data = _generar_dia(
                dia_nombre   = dia_nombre,
                grupo        = grupo,
                nivel        = nivel,
                objetivo     = objetivo,
                ambiente     = ambiente,
                limitacion   = limitacion,
                semana       = num_semana,
                num_dia_gluteo = num_g,
                seed_base    = seed,
            )
            dias_semana.append(dia_data)

        semanas.append({"semana": num_semana, "dias": dias_semana})

    return semanas


def preview_plan(
    nivel:      str = "intermedio",
    objetivo:   str = "general",
    dias:       int = 4,
    ambiente:   str = "gym",
    limitacion: str = "ninguna",
) -> str:
    """Texto legible del plan para depuración."""
    semanas = generar_plan(nivel, objetivo, dias, ambiente, limitacion)
    lines   = []
    for sem in semanas:
        lines.append(f"\n{'='*40}")
        lines.append(f"SEMANA {sem['semana']}")
        lines.append(f"{'='*40}")
        for dia in sem["dias"]:
            lines.append(f"\n  {dia['dia'].upper()} — {dia['grupo'].upper()}")
            for e in dia["ejercicios"]:
                marker = "🏃" if e["ejercicio_id"].startswith("CAR") else "  "
                lines.append(
                    f"  {marker} {e['orden']}. {e['ejercicio']}"
                    f" — {e['series']}×{e['reps']}"
                    f"  (EMG:{e['emg_score']})"
                )
    return "\n".join(lines)
