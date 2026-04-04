"""
planner.py — Generador de planes determinístico. Sin Gemini.

Ciencia aplicada:
  - Schoenfeld (2016, 2017): frecuencia 2x/semana por músculo = máxima hipertrofia
  - Israetel (RP Hypertrophy Bible): MEV/MAV/MRV por grupo muscular
  - Contreras (2015): orden por EMG, compuestos primero
  - Helms (2015): periodización lineal con deload semana 4
  - ACSM (2021): cardio zona 2 post-fuerza

Splits disponibles:
  PPL (Push/Pull/Legs) — el más efectivo para hipertrofia
  Upper/Lower          — para 4 días, frecuencia 2x
  Full body            — para 3 días principiante

Objetivos:
  "mamado"  → PPL 5-6 días, volumen MAV, barras libres, técnicas avanzadas
  "gluteo"  → Lower heavy 3x/semana + upper 1-2x
  "peso"    → Upper/Lower moderado + cardio
  "general" → Upper/Lower balanceado
"""
from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Literal

import catalog as cat
from catalog import (
    BY_ID, BY_GRUPO, SESION_GLUTEO, ROTACION_ONDULATORIO,
    MAX_POR_PATRON, MAX_POR_PATRON_DEFAULT, COMPUESTOS,
)

# ══════════════════════════════════════════════════════════════════════════════
# SPLITS
# ══════════════════════════════════════════════════════════════════════════════

DIAS_NOMBRES: dict[int, list[str]] = {
    3: ["lunes",   "miercoles", "viernes"],
    4: ["lunes",   "martes",    "jueves",   "viernes"],
    5: ["lunes",   "martes",    "miercoles","jueves",  "viernes"],
    6: ["lunes",   "martes",    "miercoles","jueves",  "viernes", "sabado"],
}

# grupo por día según objetivo y días disponibles
SPLITS: dict[str, dict[int, list[str]]] = {
    # PPL — Push/Pull/Legs — el estándar para hipertrofia seria
    # Frecuencia 2x por músculo (Schoenfeld 2016)
    "mamado": {
        # Frecuencia 2x por músculo — Schoenfeld (2016)
        3: ["empuje",  "tiron",   "pierna"],
        4: ["empuje",  "tiron",   "pierna",  "tiron"],    # 2x tirón, 1x pierna
        5: ["empuje",  "tiron",   "pierna",  "empuje",  "tiron"],
        6: ["empuje",  "tiron",   "pierna",  "empuje",  "tiron",  "pierna"],
    },
    "gluteo": {
        3: ["gluteo",  "empuje",  "gluteo"],
        4: ["gluteo",  "empuje",  "gluteo",  "tiron"],
        5: ["gluteo",  "empuje",  "tiron",   "gluteo",  "pierna"],
        6: ["gluteo",  "empuje",  "tiron",   "gluteo",  "pierna", "empuje"],
    },
    "peso": {
        3: ["pierna",  "empuje",  "tiron"],
        4: ["pierna",  "empuje",  "tiron",   "pierna"],
        5: ["pierna",  "empuje",  "tiron",   "pierna",  "empuje"],
        6: ["pierna",  "empuje",  "tiron",   "pierna",  "empuje", "tiron"],
    },
    "general": {
        3: ["pierna",  "empuje",  "tiron"],
        4: ["pierna",  "empuje",  "tiron",   "pierna"],
        5: ["pierna",  "empuje",  "tiron",   "pierna",  "tiron"],
        6: ["pierna",  "empuje",  "tiron",   "pierna",  "empuje", "tiron"],
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# PLANTILLAS POR GRUPO
# Cada posición: (rol, patron_requerido_o_None, ids_preferidos_o_None)
# ids_preferidos: el planner los usa antes que el pool general
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Slot:
    rol:         str
    patron:      str | None = None
    preferidos:  tuple[str, ...] = ()   # IDs preferidos en orden de prioridad
    solo_nivel:  str | None = None      # solo para este nivel o superior


PLANTILLAS: dict[str, dict[str, list[Slot]]] = {

    # ── EMPUJE ────────────────────────────────────────────────────────────────
    # Frecuencia alta de pecho + hombros + tríceps
    # Israetel: pecho MAV 10-16 series/sem → en 2 días = 5-8 por día
    "empuje": {
        "principiante": [
            Slot("principal",   "press_horizontal", ("EMP_G03", "EMP_G01")),
            Slot("principal",   "press_inclinado",  ("EMP_G02",)),
            Slot("principal",   "press_vertical",   ("EMP_G05",)),
            Slot("aislamiento", "hombro_lateral",   ("EMP_G06",)),
        ],
        "intermedio": [
            Slot("principal",   "press_horizontal", ("EMP_G01", "EMP_G03")),
            Slot("principal",   "press_inclinado",  ("EMP_G02",)),
            Slot("principal",   "press_vertical",   ("EMP_G05", "EMP_G08")),
            Slot("aislamiento", "hombro_lateral",   ("EMP_G09", "EMP_G06")),
        ],
        "avanzado": [
            # Día A: press barra (seed par) / Día B: fondos o mancuernas (seed impar)
            # La rotación ocurre via seed que incluye el índice del día
            Slot("principal",   "press_horizontal", ("EMP_G12", "EMP_G10", "EMP_G01"), solo_nivel="avanzado"),
            Slot("principal",   "press_inclinado",  ("EMP_G13", "EMP_G02"), solo_nivel="avanzado"),
            Slot("principal",   "press_vertical",   ("EMP_G14", "EMP_G05"), solo_nivel="avanzado"),
            Slot("aislamiento", None,               ("EMP_G09", "EMP_G06")),   # lateral polea > mancuerna
        ],
    },

    # ── TIRÓN ────────────────────────────────────────────────────────────────
    # Espalda + bíceps
    # Israetel: espalda MAV 10-16 series/sem
    "tiron": {
        "principiante": [
            Slot("principal",   "jalon_vertical",   ("TIR_G01",)),
            Slot("principal",   "remo_horizontal",  ("TIR_G02", "TIR_G05")),
            Slot("aislamiento", "hombro_posterior", ("TIR_G07",)),  # face pull — salud hombro
            Slot("aislamiento", "biceps",           ("TIR_G06", "TIR_G08")),
        ],
        "intermedio": [
            Slot("principal",   "jalon_vertical",   ("TIR_G11", "TIR_G01")),  # dominadas primero
            Slot("principal",   "remo_horizontal",  ("TIR_G03", "TIR_G02")),
            Slot("aislamiento", "hombro_posterior", ("TIR_G07",)),
            Slot("aislamiento", "biceps",           ("TIR_G08", "TIR_G06")),  # martillo primero
        ],
        "avanzado": [
            Slot("principal",   "jalon_vertical",   ("TIR_G10", "TIR_G11"), solo_nivel="avanzado"),
            Slot("principal",   "remo_horizontal",  ("TIR_G12", "TIR_G03"), solo_nivel="avanzado"),
            Slot("secundario",  "remo_horizontal",  ("TIR_G13", "TIR_G02")),  # remo accesorio
            Slot("aislamiento", "hombro_posterior", ("TIR_G07",)),
        ],
    },

    # ── PIERNA ────────────────────────────────────────────────────────────────
    # Cuádriceps + isquiotibiales + glúteo + pantorrilla
    # La sentadilla libre es el ancla — máximo reclutamiento
    "pierna": {
        "principiante": [
            Slot("principal",   "sentadilla",   ("PIE_G02", "PIE_G06")),    # Smith o hack
            Slot("aislamiento", "curl_femoral", ("PIE_G05",)),               # isquio siempre
            Slot("principal",   "prensa",       ("PIE_G03",)),               # prensa como volumen
            Slot("aislamiento", None,           ("PIE_G04", "PIE_G07")),    # extensión o pantorrilla
        ],
        "intermedio": [
            Slot("principal",   "sentadilla",       ("PIE_G06", "PIE_G02")),  # hack antes que Smith
            Slot("principal",   "bisagra_cadera",   ("PIE_G12",)),            # RDL barra
            Slot("principal",   "prensa",           ("PIE_G14", "PIE_G03")),  # pies altos
            Slot("aislamiento", "curl_femoral",     ("PIE_G05", "PIE_G10")),
        ],
        "avanzado": [
            Slot("principal",   "sentadilla",       ("PIE_G01",), solo_nivel="avanzado"),  # barra libre
            Slot("principal",   "bisagra_cadera",   ("PIE_G11", "PIE_G12"), solo_nivel="avanzado"),  # peso muerto
            Slot("principal",   "desplante_unilateral", ("PIE_G13", "PIE_G08"), solo_nivel="avanzado"),
            Slot("aislamiento", "curl_femoral",     ("PIE_G05",)),
        ],
    },

    # ── GLÚTEO ────────────────────────────────────────────────────────────────
    "gluteo": {
        "principiante": [
            Slot("principal",   "puente_cadera",           ("GLU_G02", "GLU_G03")),
            Slot("principal",   "bisagra_cadera",          ("GLU_G05",)),
            Slot("secundario",  None,                      ("GLU_G07", "GLU_G15")),
            Slot("aislamiento", None,                      ("GLU_G09", "GLU_G08")),
        ],
        "intermedio": [
            Slot("principal",   "puente_cadera",           ("GLU_G01", "GLU_G02")),
            Slot("principal",   "bisagra_cadera",          ("GLU_G04", "GLU_G05")),
            Slot("principal",   "desplante_unilateral",    ("GLU_G06", "GLU_G14")),
            Slot("aislamiento", None,                      ("GLU_G09", "GLU_G10")),
        ],
        "avanzado": [
            Slot("principal",   "puente_cadera",           ("GLU_G01",)),
            Slot("principal",   "puente_cadera_unilateral",("GLU_G11",)),
            Slot("principal",   "bisagra_cadera",          ("GLU_G04",)),
            Slot("aislamiento", None,                      ("GLU_G09", "GLU_G10")),
        ],
    },

    # ── CORE ──────────────────────────────────────────────────────────────────
    "core": {
        "principiante": [
            Slot("core_estabilidad", None, ("COR_01", "COR_04")),
            Slot("core_dinamico",    None, ("COR_05", "COR_06")),
            Slot("core_estabilidad", None, ("COR_02",)),
            Slot("core_dinamico",    None, ("COR_09",)),
        ],
        "intermedio": [
            Slot("core_estabilidad", None, ("COR_08", "COR_01")),
            Slot("core_dinamico",    None, ("COR_06", "COR_05")),
            Slot("core_estabilidad", None, ("COR_11",)),
            Slot("core_dinamico",    None, ("COR_09",)),
        ],
        "avanzado": [
            Slot("core_estabilidad", None, ("COR_08",)),
            Slot("core_dinamico",    None, ("COR_06",)),
            Slot("core_estabilidad", None, ("COR_11",)),
            Slot("core_dinamico",    None, ("COR_09",)),
        ],
    },
}

# Para home: remap de slots avanzados a equivalentes casa
PLANTILLAS_HOME_FALLBACK: dict[str, dict[str, list[Slot]]] = {
    "empuje": {
        "intermedio": [
            Slot("principal", "press_horizontal", ("EMP_H01", "EMP_H11")),
            Slot("principal", "press_inclinado",  ("EMP_H03",)),
            Slot("principal", "press_vertical",   ("EMP_H12",)),
            Slot("aislamiento", None,             ("EMP_H06",)),
        ],
        "avanzado": [
            Slot("principal", "press_horizontal", ("EMP_H10", "EMP_H01")),
            Slot("principal", "press_inclinado",  ("EMP_H03",)),
            Slot("principal", "press_vertical",   ("EMP_H12",)),
            Slot("aislamiento", None,             ("EMP_H04",)),
        ],
    },
    "tiron": {
        "intermedio": [
            Slot("principal", "jalon_vertical",   ("TIR_G11", "TIR_H03")),  # dominadas si puede
            Slot("principal", "remo_horizontal",  ("TIR_H01", "TIR_H02")),
            Slot("aislamiento", "hombro_posterior",("TIR_H05",)),
            Slot("aislamiento", "biceps",          ("TIR_H04",)),
        ],
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# PERIODIZACIÓN — series, reps y RIR por semana
# Helms (2015): progresión lineal + deload S4
# Israetel: volumen dentro de MAV
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PeriodConfig:
    series_comp:  int    # compuestos principales
    series_acc:   int    # accesorios y aislamiento
    reps_comp:    str    # rango de reps compuesto
    reps_acc:     str    # rango de reps accesorio
    rir:          int
    deload:       bool = False


PERIODIZACION: dict[str, dict[int, PeriodConfig]] = {
    "principiante": {
        1: PeriodConfig(3, 3, "12-15", "15",    rir=3),
        2: PeriodConfig(3, 3, "10-12", "12-15", rir=2),
        3: PeriodConfig(3, 3, "10-12", "12-15", rir=2),
        4: PeriodConfig(2, 2, "12-15", "15",    rir=4, deload=True),
    },
    "intermedio": {
        1: PeriodConfig(4, 3, "10-12", "12-15", rir=2),
        2: PeriodConfig(4, 3, "8-10",  "12",    rir=2),
        3: PeriodConfig(4, 4, "6-8",   "10-12", rir=1),
        4: PeriodConfig(3, 2, "10-12", "15",    rir=4, deload=True),
    },
    "avanzado": {
        # Volumen dentro del MAV de Israetel: 10-16 series/semana por grupo
        # Con 2 días × 5 series = 10 series mínimo ✓
        1: PeriodConfig(5, 3, "8-10",  "12",    rir=2),
        2: PeriodConfig(5, 4, "6-8",   "10-12", rir=1),
        3: PeriodConfig(6, 4, "4-6",   "8-10",  rir=1),
        4: PeriodConfig(3, 2, "10-12", "15",    rir=4, deload=True),
    },
}

def _periodo(nivel: str, semana: int) -> PeriodConfig:
    tabla = PERIODIZACION.get(nivel, PERIODIZACION["intermedio"])
    return tabla.get(semana, tabla[1])


# ══════════════════════════════════════════════════════════════════════════════
# RESTRICCIONES POR LIMITACIÓN
# ══════════════════════════════════════════════════════════════════════════════

PROHIBIDOS: dict[str, frozenset[str]] = {
    "rodilla": frozenset({
        "PIE_G01",   # sentadilla libre
        "PIE_G13",   # búlgara barra
        "GLU_G06",   # búlgara mancuerna
        "PIE_G08",   # desplante caminando
        "GLU_H06",
        "PIE_H04",
    }),
    "espalda": frozenset({
        "PIE_G11",   # peso muerto conv
        "PIE_G12",   # RDL barra
        "TIR_G12",   # remo Pendlay
        "GLU_G04",   # RDL barra glúteo
        "GLU_G12",   # good morning
        "PIE_G01",   # sentadilla libre
    }),
    "hombro": frozenset({
        "EMP_G14",   # press militar barra
        "EMP_G05",   # press hombro mancuerna
        "EMP_G08",   # press Arnold
        "EMP_H05",
        "EMP_H08",
        "EMP_H12",   # pike push-up
    }),
    "ninguna": frozenset(),
}

# Cardio por objetivo y ambiente
CARDIO: dict[str, dict[str, list[str]]] = {
    "mamado":   {"gym": ["CAR_G01"],                     "home": ["CAR_H01"], "band": ["CAR_H01"]},
    "gluteo":   {"gym": ["CAR_G01", "CAR_G03"],          "home": ["CAR_H05", "CAR_H01"], "band": ["CAR_H01"]},
    "peso":     {"gym": ["CAR_G01", "CAR_G02", "CAR_G03"],"home": ["CAR_H01","CAR_H02"], "band": ["CAR_H01"]},
    "general":  {"gym": ["CAR_G02", "CAR_G03"],           "home": ["CAR_H01","CAR_H03"], "band": ["CAR_H01"]},
}

# Para mamado: cardio mínimo (15 min, preservar músculo)
CARDIO_DURACION: dict[str, str] = {
    "mamado":  "15min",
    "gluteo":  "20min",
    "peso":    "25min",
    "general": "20min",
}


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR DE SELECCIÓN
# ══════════════════════════════════════════════════════════════════════════════

NIVEL_NUM = {"principiante": 0, "intermedio": 1, "avanzado": 2}

def _resolver_slot(
    slot:        Slot,
    grupo:       str,
    ambiente:    str,
    nivel:       str,
    prohibidos:  frozenset[str],
    ya_ids:      set[str],
    ya_patron:   dict[str, int],
    semana:      int,
    seed:        int,
) -> cat.Ejercicio | None:
    nivel_n = NIVEL_NUM.get(nivel, 1)

    # Intentar preferidos primero (en orden, rotando por semana)
    if slot.preferidos:
        # Rotar entre preferidos según semana para variedad
        prefs_disponibles = [
            eid for eid in slot.preferidos
            if eid in BY_ID
            and eid not in prohibidos
            and eid not in ya_ids
            and ambiente in BY_ID[eid].ambiente
            and NIVEL_NUM.get(BY_ID[eid].nivel_min, 0) <= nivel_n
            and ya_patron.get(BY_ID[eid].patron, 0) < MAX_POR_PATRON.get(BY_ID[eid].patron, MAX_POR_PATRON_DEFAULT)
        ]
        if prefs_disponibles:
            idx = (semana - 1) % len(prefs_disponibles)
            return BY_ID[prefs_disponibles[idx]]

    # Pool general del catálogo
    pool = [
        e for e in BY_GRUPO.get(grupo, [])
        if e.rol == slot.rol
        and ambiente in e.ambiente
        and e.id not in prohibidos
        and e.id not in ya_ids
        and NIVEL_NUM.get(e.nivel_min, 0) <= nivel_n
        and (slot.patron is None or e.patron == slot.patron)
        and ya_patron.get(e.patron, 0) < MAX_POR_PATRON.get(e.patron, MAX_POR_PATRON_DEFAULT)
    ]
    if not pool:
        # Relajar patrón
        pool = [
            e for e in BY_GRUPO.get(grupo, [])
            if e.rol == slot.rol
            and ambiente in e.ambiente
            and e.id not in prohibidos
            and e.id not in ya_ids
            and NIVEL_NUM.get(e.nivel_min, 0) <= nivel_n
            and ya_patron.get(e.patron, 0) < MAX_POR_PATRON.get(e.patron, MAX_POR_PATRON_DEFAULT)
        ]
    if not pool:
        return None

    pool.sort(key=lambda e: (-e.emg_score, e.id))
    idx = (seed + (semana - 1)) % len(pool)
    return pool[idx]


def _cardio_ej(objetivo: str, ambiente: str, semana: int, duracion: str) -> dict:
    ids  = CARDIO.get(objetivo, CARDIO["general"]).get(ambiente, ["CAR_G01"])
    eid  = ids[(semana - 1) % len(ids)]
    ej   = BY_ID.get(eid) or BY_ID.get("CAR_G01")
    return {
        "ejercicio_id": ej.id,
        "ejercicio":    ej.nombre,
        "patron":       ej.patron,
        "emg_score":    ej.emg_score,
        "orden":        5,
        "series":       1,
        "reps":         duracion,
        "notas":        "Zona 2 — si puedes hablar, estás en la zona correcta",
        "completado":   0,
    }


def _tipo_sesion_gluteo(semana: int, num_g: int) -> tuple[str, dict]:
    rot  = ROTACION_ONDULATORIO.get(semana, ROTACION_ONDULATORIO[1])
    tipo = rot.get(f"g{num_g}", "hipertrofia")
    return tipo, SESION_GLUTEO.get(tipo, SESION_GLUTEO["hipertrofia"])


# ══════════════════════════════════════════════════════════════════════════════
# GENERADOR DE DÍA
# ══════════════════════════════════════════════════════════════════════════════

def _generar_dia(
    dia_nombre:     str,
    grupo:          str,
    nivel:          str,
    objetivo:       str,
    ambiente:       str,
    limitacion:     str,
    semana:         int,
    num_dia_gluteo: int = 0,
    seed_base:      int = 0,
) -> dict:
    prohbs  = PROHIBIDOS.get(limitacion, frozenset())
    cfg     = _periodo(nivel, semana)
    dur_car = CARDIO_DURACION.get(objetivo, "20min")

    # Seleccionar plantilla correcta
    nivel_key = nivel if nivel in ("principiante", "intermedio", "avanzado") else "intermedio"

    # Para home/band usar plantilla home si existe, sino la gym
    if ambiente in ("home", "band") and grupo in PLANTILLAS_HOME_FALLBACK:
        fallback = PLANTILLAS_HOME_FALLBACK[grupo]
        # usar el nivel más cercano disponible
        plantilla = fallback.get(nivel_key) or fallback.get("intermedio") or PLANTILLAS[grupo].get(nivel_key, [])
    else:
        plantilla = PLANTILLAS.get(grupo, {}).get(nivel_key, [])

    if not plantilla:
        plantilla = PLANTILLAS.get(grupo, {}).get("intermedio", [])

    # Config especial glúteo (periodización ondulatoria)
    tipo_glut, ses_glut = ("", {})
    if grupo == "gluteo" and num_dia_gluteo > 0:
        tipo_glut, ses_glut = _tipo_sesion_gluteo(semana, num_dia_gluteo)

    ya_ids:    set[str]      = set()
    ya_patron: dict[str,int] = {}
    ejercicios: list[dict]   = []

    for orden_idx, slot in enumerate(plantilla, 1):
        # Saltar slot si el nivel no alcanza
        if slot.solo_nivel:
            req_n = NIVEL_NUM.get(slot.solo_nivel, 0)
            if NIVEL_NUM.get(nivel, 1) < req_n:
                # Degradar al slot intermedio equivalente si existe
                continue

        ej = _resolver_slot(
            slot, grupo, ambiente, nivel,
            prohbs, ya_ids, ya_patron, semana, seed_base + orden_idx,
        )
        if not ej:
            continue

        ya_ids.add(ej.id)
        ya_patron[ej.patron] = ya_patron.get(ej.patron, 0) + 1

        # Series
        if ej.patron in COMPUESTOS and slot.rol == "principal":
            series = cfg.series_comp
        else:
            series = cfg.series_acc

        # Reps — glúteo usa periodización ondulatoria
        if grupo == "gluteo" and ses_glut and ej.patron in COMPUESTOS:
            reps = ses_glut.get("reps", cfg.reps_comp)
        elif ej.patron in COMPUESTOS:
            reps = cfg.reps_comp
        else:
            reps = cfg.reps_acc

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

    # Rellenar si quedaron menos de 4 ejercicios (por restricciones)
    if len(ejercicios) < 4:
        _rellenar(ejercicios, grupo, ambiente, nivel, prohbs, ya_ids, ya_patron, cfg, semana)

    # Cardio al final — siempre posición 5
    ejercicios.append(_cardio_ej(objetivo, ambiente, semana, dur_car))
    for i, e in enumerate(ejercicios, 1):
        e["orden"] = i

    return {"dia": dia_nombre, "grupo": grupo, "ejercicios": ejercicios}


def _rellenar(
    ejercicios: list[dict], grupo: str, ambiente: str, nivel: str,
    prohbs: frozenset, ya_ids: set, ya_patron: dict,
    cfg: PeriodConfig, semana: int,
) -> None:
    """Rellena hasta 4 ejercicios si las restricciones dejaron huecos."""
    nivel_n = NIVEL_NUM.get(nivel, 1)
    while len(ejercicios) < 4:
        candidatos = [
            e for e in BY_GRUPO.get(grupo, [])
            if ambiente in e.ambiente
            and e.id not in prohbs
            and e.id not in ya_ids
            and NIVEL_NUM.get(e.nivel_min, 0) <= nivel_n
            and ya_patron.get(e.patron, 0) < MAX_POR_PATRON.get(e.patron, MAX_POR_PATRON_DEFAULT)
        ]
        if not candidatos:
            break
        candidatos.sort(key=lambda e: -e.emg_score)
        ej = candidatos[0]
        ya_ids.add(ej.id)
        ya_patron[ej.patron] = ya_patron.get(ej.patron, 0) + 1
        ejercicios.append({
            "ejercicio_id": ej.id,
            "ejercicio":    ej.nombre,
            "patron":       ej.patron,
            "emg_score":    ej.emg_score,
            "orden":        len(ejercicios) + 1,
            "series":       cfg.series_acc,
            "reps":         cfg.reps_acc,
            "notas":        ej.cue[:70] if ej.cue else "",
            "completado":   0,
        })


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
    Genera 4 semanas. Retorna lista compatible con db.insert_plan().
    """
    dias  = max(3, min(6, dias))
    split = SPLITS.get(objetivo, SPLITS["general"]).get(dias)
    if not split:
        split = SPLITS["general"].get(4, ["pierna","empuje","tiron","pierna"])
    nombres = DIAS_NOMBRES.get(dias, DIAS_NOMBRES[4])[:len(split)]

    semanas = []
    for num_semana in range(1, 5):
        dias_sem    = []
        cnt_gluteo  = 0
        for i, (dia_n, grupo) in enumerate(zip(nombres, split)):
            if grupo == "gluteo":
                cnt_gluteo += 1
                num_g = cnt_gluteo
            else:
                num_g = 0
            seed = num_semana * 100 + i * 10
            dia_data = _generar_dia(
                dia_nombre     = dia_n,
                grupo          = grupo,
                nivel          = nivel,
                objetivo       = objetivo,
                ambiente       = ambiente,
                limitacion     = limitacion,
                semana         = num_semana,
                num_dia_gluteo = num_g,
                seed_base      = seed,
            )
            dias_sem.append(dia_data)
        semanas.append({"semana": num_semana, "dias": dias_sem})
    return semanas


def preview_plan(
    nivel:      str = "intermedio",
    objetivo:   str = "general",
    dias:       int = 4,
    ambiente:   str = "gym",
    limitacion: str = "ninguna",
) -> str:
    semanas = generar_plan(nivel, objetivo, dias, ambiente, limitacion)
    lines   = []
    for sem in semanas:
        lines.append(f"\n{'='*50}")
        lines.append(f"SEMANA {sem['semana']}")
        lines.append(f"{'='*50}")
        for dia in sem["dias"]:
            lines.append(f"\n  {dia['dia'].upper()} — {dia['grupo'].upper()}")
            for e in dia["ejercicios"]:
                m = "🏃" if e["ejercicio_id"].startswith("CAR") else "  "
                lines.append(
                    f"  {m} {e['orden']}. {e['ejercicio']:<45}"
                    f" {e['series']}×{e['reps']:<6}  EMG:{e['emg_score']}"
                )
    return "\n".join(lines)
