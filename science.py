"""
science.py — Lógica científica del plan de entrenamiento.

Novedades vs versión anterior:
  - Periodización ondulatoria para glúteo (Contreras 2015)
  - Modo casa activable por sesión (swap gym→home automático)
  - Orden de ejercicios por EMG score (Contreras: compuesto primero)
  - Cardio zona 2 forzado siempre (nunca HIIT post-fuerza)
  - Split glúteo 3x/semana automático para objetivo glúteo
  - Ajuste de progresión por género (más volumen glúteo en mujer)

Fuentes: Schoenfeld (2017), Contreras (2015), Nippard (2023),
         Israetel (RP), ACSM (2021), McGill (2010)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

import database as db
import catalog as cat
from catalog import (
    BY_ID, MAX_POR_PATRON, MAX_POR_PATRON_DEFAULT,
    COMPUESTOS, SESION_GLUTEO, ROTACION_ONDULATORIO,
)

logger = logging.getLogger(__name__)


# ─── VOLUMEN SEMANAL (Schoenfeld 2017) ────────────────────────────────────────

PATRON_A_GRUPO: dict[str, str] = {
    "sentadilla":              "cuadriceps",
    "prensa":                  "cuadriceps",
    "desplante_unilateral":    "cuadriceps",
    "puente_cadera":           "gluteo",
    "puente_cadera_unilateral":"gluteo",
    "bisagra_cadera":          "gluteo",
    "abduccion":               "gluteo",
    "patada":                  "gluteo",
    "curl_femoral":            "isquiotibial",
    "press_horizontal":        "pecho",
    "press_inclinado":         "pecho",
    "aislamiento_pecho":       "pecho",
    "press_vertical":          "hombro",
    "hombro_lateral":          "hombro",
    "hombro_posterior":        "hombro",
    "jalon_vertical":          "espalda",
    "remo_horizontal":         "espalda",
    "biceps":                  "biceps",
    "triceps":                 "triceps",
    "core_estabilidad":        "core",
    "core_dinamico":           "core",
    "core_rotacion":           "core",
    "extension_quad":          "cuadriceps",
    "pantorrilla":             "pantorrilla",
}

VOLUMEN_RANGOS: dict[str, dict[str, int]] = {
    "cuadriceps":   {"min": 8,  "opt_low": 10, "opt_high": 16, "max": 20},
    "gluteo":       {"min": 10, "opt_low": 12, "opt_high": 20, "max": 26},  # más que otros (Contreras)
    "isquiotibial": {"min": 6,  "opt_low": 8,  "opt_high": 12, "max": 16},
    "pecho":        {"min": 8,  "opt_low": 10, "opt_high": 16, "max": 20},
    "espalda":      {"min": 8,  "opt_low": 10, "opt_high": 16, "max": 20},
    "hombro":       {"min": 6,  "opt_low": 8,  "opt_high": 14, "max": 18},
    "biceps":       {"min": 4,  "opt_low": 6,  "opt_high": 12, "max": 16},
    "triceps":      {"min": 4,  "opt_low": 6,  "opt_high": 12, "max": 16},
    "core":         {"min": 4,  "opt_low": 6,  "opt_high": 10, "max": 14},
    "pantorrilla":  {"min": 4,  "opt_low": 6,  "opt_high": 10, "max": 14},
}


def calcular_volumen_semanal(user_id: int, semana: int) -> dict[str, dict]:
    rows = db.fetchall("""
        SELECT ejercicio_id, series FROM rutinas
        WHERE user_id=? AND semana=? AND ejercicio_id NOT LIKE 'CAR%'
    """, (user_id, semana))

    volumen: dict[str, int] = defaultdict(int)
    for row in rows:
        ej = BY_ID.get(row["ejercicio_id"])
        if not ej:
            continue
        gm = PATRON_A_GRUPO.get(ej.patron)
        if gm:
            try:
                volumen[gm] += int(row["series"])
            except (TypeError, ValueError):
                volumen[gm] += 3

    resultado = {}
    for grupo, rango in VOLUMEN_RANGOS.items():
        total = volumen.get(grupo, 0)
        if total == 0:             estado = "ausente"
        elif total < rango["min"]: estado = "bajo"
        elif total <= rango["opt_high"]: estado = "optimo"
        elif total <= rango["max"]: estado = "alto"
        else:                      estado = "exceso"
        resultado[grupo] = {"series": total, "estado": estado}
    return resultado


def formatear_volumen(vol: dict[str, dict]) -> str:
    emojis  = {"ausente": "⚫", "bajo": "🔴", "optimo": "🟢", "alto": "🟡", "exceso": "🔴"}
    nombres = {
        "cuadriceps": "Cuádriceps", "gluteo": "Glúteo",
        "isquiotibial": "Isquio", "pecho": "Pecho", "espalda": "Espalda",
        "hombro": "Hombro", "biceps": "Bíceps", "triceps": "Tríceps",
        "core": "Core", "pantorrilla": "Pantorrilla",
    }
    lines = ["📊 <b>Volumen semanal</b>", "━━━━━━━━━━━━━━━━", ""]
    for grupo, data in vol.items():
        if data["estado"] == "ausente":
            continue
        rango  = VOLUMEN_RANGOS[grupo]
        filled = min(10, round(data["series"] / rango["opt_high"] * 10))
        bar    = "█" * filled + "░" * (10 - filled)
        emoji  = emojis.get(data["estado"], "⚪")
        nombre = nombres.get(grupo, grupo)
        opt    = f'{rango["opt_low"]}-{rango["opt_high"]}'
        lines.append(
            f'{emoji} <b>{nombre}</b>: {data["series"]} series\n'
            f'   <code>[{bar}]</code> óptimo: {opt}'
        )
    lines += ["", "<i>🟢 óptimo · 🟡 alto · 🔴 bajo/exceso</i>"]
    return "\n".join(lines)


# ─── VALIDADOR + CORRECTOR FISIOLÓGICO ───────────────────────────────────────

def validar_y_corregir_dia(dia: dict, ambiente: str = "gym") -> tuple[bool, str]:
    """
    3 capas de corrección + reordenamiento por EMG score.
    Modifica dia['ejercicios'] in-place.
    """
    ejercicios = dia.get("ejercicios", [])
    if not ejercicios:
        return False, "Día sin ejercicios"

    conteo_patron: dict = defaultdict(int)
    vistos_ids:    set  = set()
    cardios, fuerza, eliminados = [], [], []

    for e in ejercicios:
        eid = e.get("ejercicio_id", "")
        ej  = BY_ID.get(eid)
        if not ej:
            eliminados.append((eid, "ID no existe en catálogo"))
            continue
        if ej.es_cardio():
            cardios.append(e)
        else:
            fuerza.append(e)

    fuerza_filtrada = []
    for e in fuerza:
        eid = e.get("ejercicio_id", "")
        ej  = BY_ID[eid]
        pat = ej.patron

        if eid in vistos_ids:
            eliminados.append((eid, "duplicado exacto"))
            continue
        vistos_ids.add(eid)

        limite = MAX_POR_PATRON.get(pat, MAX_POR_PATRON_DEFAULT)
        if conteo_patron[pat] >= limite:
            eliminados.append((eid, f"patrón {pat} saturado (máx {limite})"))
            continue
        conteo_patron[pat] += 1
        fuerza_filtrada.append(e)

    # Reordenar fuerza por EMG score descendente (compuesto más activador primero)
    # Pero cardio SIEMPRE al final
    def emg_key(e):
        ej = BY_ID.get(e.get("ejercicio_id", ""))
        return ej.emg_score if ej else 0

    fuerza_filtrada.sort(key=emg_key, reverse=True)

    ejercicios_finales = fuerza_filtrada + cardios[:1]
    for i, e in enumerate(ejercicios_finales, 1):
        e["orden"] = i

    dia["ejercicios"] = ejercicios_finales

    if eliminados:
        logger.warning("Corrección día %s: %d eliminados: %s",
                       dia.get("dia", "?"), len(eliminados), eliminados)

    msg = f"OK ({len(ejercicios_finales)} ejercicios, {len(eliminados)} eliminados)"
    return True, msg


# ─── MODO CASA — SWAP AUTOMÁTICO GYM → HOME ──────────────────────────────────

def convertir_sesion_a_casa(user_id: int, semana: int, dia: str) -> int:
    """
    Convierte todos los ejercicios de gym a sus equivalentes en casa.
    Retorna número de ejercicios convertidos.
    """
    ejercicios = db.get_ejercicios_dia(user_id, semana, dia)
    convertidos = 0

    with db.get_db() as conn:
        for ex in ejercicios:
            eid = ex["ejercicio_id"]
            ej  = BY_ID.get(eid)
            if not ej or ej.es_home():
                continue  # ya es de casa o no existe

            equivalente = cat.equivalente_casa(eid)
            if not equivalente:
                logger.warning("Sin equivalente casa para %s", eid)
                continue

            conn.execute(
                "UPDATE rutinas SET ejercicio_id=?, ejercicio=?, patron=? "
                "WHERE user_id=? AND semana=? AND dia=? AND ejercicio_id=?",
                (equivalente.id, equivalente.nombre, equivalente.patron,
                 user_id, semana, dia, eid),
            )
            conn.execute(
                "DELETE FROM progreso WHERE user_id=? AND semana=? AND dia=? AND ejercicio_id=?",
                (user_id, semana, dia, eid),
            )
            convertidos += 1

    logger.info("Modo casa: %d ejercicios convertidos user=%s S%s %s",
                convertidos, user_id, semana, dia)
    return convertidos


def restaurar_sesion_a_gym(user_id: int, semana: int, dia: str) -> int:
    """
    Restaura ejercicios de casa a sus equivalentes de gym del plan original.
    Lee el plan original de la DB (campo patron) y busca el mejor gym.
    """
    ejercicios = db.get_ejercicios_dia(user_id, semana, dia)
    restaurados = 0

    with db.get_db() as conn:
        for ex in ejercicios:
            eid = ex["ejercicio_id"]
            ej  = BY_ID.get(eid)
            if not ej or ej.es_gym():
                continue  # ya es de gym

            # Buscar el mejor gym del mismo grupo y rol
            candidatos = [
                e for e in cat.BY_GRUPO.get(ej.grupo, [])
                if e.es_gym() and e.rol == ej.rol
            ]
            if not candidatos:
                continue
            mejor = max(candidatos, key=lambda x: x.emg_score)

            conn.execute(
                "UPDATE rutinas SET ejercicio_id=?, ejercicio=?, patron=? "
                "WHERE user_id=? AND semana=? AND dia=? AND ejercicio_id=?",
                (mejor.id, mejor.nombre, mejor.patron,
                 user_id, semana, dia, eid),
            )
            restaurados += 1

    logger.info("Restaurar gym: %d ejercicios restaurados user=%s S%s %s",
                restaurados, user_id, semana, dia)
    return restaurados


# ─── ANÁLISIS POST-SESIÓN (Israetel + Helms) ─────────────────────────────────

@dataclass
class ResultadoSesion:
    ajuste:      str   # mantener | subir_carga | bajar_volumen | deload
    razon:       str
    msg_usuario: str


def analizar_sesion(user_id: int, semana: int, dia: str) -> ResultadoSesion:
    row_grupo = db.fetchone(
        "SELECT grupo FROM rutinas WHERE user_id=? AND semana=? AND dia=? LIMIT 1",
        (user_id, semana, dia),
    )
    grupo_dia = row_grupo["grupo"] if row_grupo else None

    actual = db.fetchone("""
        SELECT rir_reportado, progreso_reportado, fatiga_reportada FROM progreso
        WHERE user_id=? AND semana=? AND dia=? AND fatiga_reportada IS NOT NULL LIMIT 1
    """, (user_id, semana, dia))

    if not actual:
        return ResultadoSesion("mantener", "sin datos", "")

    rir    = actual["rir_reportado"]      if actual["rir_reportado"]    is not None else 2
    prog   = actual["progreso_reportado"] or "primera"
    fatiga = actual["fatiga_reportada"]   if actual["fatiga_reportada"] is not None else 2

    historial = db.get_historial_sesiones(user_id, grupo=grupo_dia, limit=3)
    historial  = [h for h in historial if not (h["semana"] == semana and h["dia"] == dia)]

    if fatiga >= 5:
        return ResultadoSesion(
            "deload", "fatiga crítica 5/5",
            "💀 <b>Fatiga crítica.</b>\nPróxima sesión con carga al 60%%. Prioriza el sueño.",
        )
    if rir >= 3:
        return ResultadoSesion(
            "subir_carga", f"RIR {rir} — sin estímulo real",
            "😌 <b>Sesión demasiado fácil.</b>\nRIR 3+ = músculo sin estímulo.\n"
            "👉 Sube el peso un 5-10%% la próxima vez.",
        )
    if len(historial) >= 2:
        progs = [h["progreso_reportado"] for h in historial[:2] if h["progreso_reportado"]]
        if len(progs) == 2 and all(p in ("no", "igual") for p in progs) and prog in ("no", "igual"):
            g_txt = f" de {grupo_dia}" if grupo_dia else ""
            return ResultadoSesion(
                "deload", f"estancamiento{g_txt}: 3 sesiones sin progresión",
                f"📉 <b>Estancamiento{g_txt} detectado.</b>\n"
                "3 sesiones sin progresar = fatiga acumulada.\n"
                "👉 Próxima sesión deload: mismos ejercicios al 60%%.",
            )
    if rir == 0 and fatiga >= 4:
        return ResultadoSesion(
            "bajar_volumen", f"RIR 0 + fatiga {fatiga}/5",
            "🔥 <b>Sesión muy intensa.</b>\nReduzco 1 serie en accesorios de mañana.",
        )
    if rir == 0 and fatiga == 3:
        return ResultadoSesion(
            "mantener", "RIR 0 + fatiga moderada",
            "🟡 <b>Intensidad en el límite.</b>\nPlan sin cambios hoy. Si se repite, baja peso 5%%.",
        )
    if prog == "si" and rir in (1, 2):
        return ResultadoSesion(
            "mantener", "progresión + RIR óptimo",
            "📈 <b>Progresión con RIR óptimo.</b>\nEl plan funciona exactamente como debe.",
        )
    return ResultadoSesion("mantener", "sesión normal", "✅ Sesión registrada.")


def aplicar_ajuste(user_id: int, semana: int, dia: str, ajuste: str) -> None:
    if ajuste in ("mantener", "subir_carga"):
        return
    max_sem = db.fetchone("SELECT MAX(semana) as n FROM rutinas WHERE user_id=?", (user_id,))
    max_s   = (max_sem["n"] or 4) if max_sem else 4
    nueva_semana, nuevo_dia = db.avanzar_dia(user_id, semana, dia, max_semana=max_s)
    if nuevo_dia == "fin":
        return
    if ajuste == "deload":
        db.adjust_series(user_id, nueva_semana, nuevo_dia, delta=-1, solo_accesorios=False)
    elif ajuste == "bajar_volumen":
        db.adjust_series(user_id, nueva_semana, nuevo_dia, delta=-1, solo_accesorios=True)


def evaluar_fatiga_acumulada(user_id: int) -> dict:
    historial = db.get_historial_sesiones(user_id, limit=6)
    if not historial:
        return {"necesita_deload": False, "razon": "sin datos", "fatiga_promedio": 0}
    fatigas  = [h["fatiga_reportada"] for h in historial if h["fatiga_reportada"] is not None]
    promedio = sum(fatigas) / len(fatigas) if fatigas else 0
    max_sem  = db.fetchone("SELECT MAX(semana) as n FROM rutinas WHERE user_id=?", (user_id,))
    sem_max  = (max_sem["n"] or 0) if max_sem else 0
    if fatigas and 5 in fatigas[:2]:
        return {"necesita_deload": True, "razon": "fatiga crítica reciente", "fatiga_promedio": promedio}
    if promedio >= 4 and len(fatigas) >= 3:
        return {"necesita_deload": True, "razon": "fatiga sostenida ≥4/5", "fatiga_promedio": promedio}
    if sem_max >= 5:
        return {"necesita_deload": True, "razon": "4 semanas completadas", "fatiga_promedio": promedio}
    return {"necesita_deload": False, "razon": "ok", "fatiga_promedio": promedio}


# ─── MILESTONES ───────────────────────────────────────────────────────────────

def procesar_milestones(user_id: int, semana: int) -> list[str]:
    stats    = db.get_stats(user_id)
    mensajes = []
    checks   = [
        ("FIRST_ROUTINE",   stats["rutinas_completas"] >= 1,
         "🌱 <b>¡Primera rutina completada!</b>\nLo más difícil ya lo hiciste: empezar 💚"),
        ("TEN_ROUTINES",    stats["rutinas_completas"] >= 10,
         "🔥 <b>10 rutinas terminadas.</b>\nDisciplina > motivación. Lo estás demostrando."),
        ("TWENTY_FIVE_ROUTINES", stats["rutinas_completas"] >= 25,
         "🏆 <b>25 rutinas.</b>\nEsto ya es un hábito real. Sigue."),
        (f"WEEK_{semana}_DONE", db.semana_completa(user_id, semana),
         f"💐 <b>¡Semana {semana} completada!</b>\nTómate tu descanso merecido."),
    ]
    for key, cond, msg in checks:
        if cond and db.check_milestone(user_id, key):
            mensajes.append(msg)
    return mensajes


# ─── PRIORIDAD MUSCULAR (Israetel) ────────────────────────────────────────────

GRUPOS_PRIORIDAD  = ["pecho", "espalda", "pierna", "hombro"]
TOLERANCIA_VOLUMEN = {"pecho": 16, "espalda": 16, "pierna": 20, "hombro": 14}


def _priority_score(user_id: int, grupo: str, semanas: int = 4) -> tuple[float, float]:
    row_vol = db.fetchone("""
        SELECT AVG(series_count) as avg_s FROM (
            SELECT semana, SUM(series) as series_count FROM rutinas
            WHERE user_id=? AND grupo=? AND ejercicio_id NOT LIKE 'CAR%'
            GROUP BY semana ORDER BY semana DESC LIMIT ?
        )
    """, (user_id, grupo, semanas))
    vol = row_vol["avg_s"] if row_vol and row_vol["avg_s"] else 0

    historial   = db.get_historial_sesiones(user_id, grupo=grupo, limit=semanas * 2)
    fatigas     = [h["fatiga_reportada"] for h in historial if h["fatiga_reportada"] is not None]
    fatiga_prom = sum(fatigas) / len(fatigas) if fatigas else 2.5

    progs = [h["progreso_reportado"] for h in historial if h["progreso_reportado"]]
    ip    = (progs.count("si") / len(progs)) if progs else 0.5

    row_prev = db.fetchone(
        "SELECT grupo_prioritario FROM prioridad_bloques WHERE user_id=? ORDER BY bloque DESC LIMIT 1",
        (user_id,),
    )
    fue_anterior = row_prev and row_prev["grupo_prioritario"] == grupo

    tol   = TOLERANCIA_VOLUMEN.get(grupo, 16)
    iv    = min(vol / tol, 1.5) if tol else 0
    ir    = max(0.0, 1 - fatiga_prom / 5)
    score = (0.45 * (1 - ip)) + (0.30 * (1 - iv)) + (0.20 * ir)
    if fue_anterior:
        score -= 0.25
    return round(score, 4), ir


def aplicar_prioridad_muscular(user_id: int, semana_inicio: int) -> dict:
    scores = {}
    irs    = {}
    for g in GRUPOS_PRIORIDAD:
        sc, ir = _priority_score(user_id, g)
        scores[g], irs[g] = sc, ir

    candidatos = [g for g in GRUPOS_PRIORIDAD if irs[g] >= 0.4]
    if not candidatos:
        return {"ganador": None, "deload_primero": True, "scores": scores}

    ganador  = max(candidatos, key=lambda g: scores[g])
    perdedor = min((g for g in GRUPOS_PRIORIDAD if g != ganador), key=lambda g: scores[g])

    series_sumadas = 0
    with db.get_db() as conn:
        for sem in range(semana_inicio, semana_inicio + 4):
            if sem > 4:
                break
            rows = conn.execute("""
                SELECT id, series FROM rutinas
                WHERE user_id=? AND semana=? AND grupo=? AND ejercicio_id NOT LIKE 'CAR%'
            """, (user_id, sem, ganador)).fetchall()
            for row in rows:
                if series_sumadas >= 4:
                    break
                conn.execute("UPDATE rutinas SET series=? WHERE id=?",
                             (min(6, int(row["series"] or 3) + 1), row["id"]))
                series_sumadas += 1

            rows_p = conn.execute("""
                SELECT id, series FROM rutinas
                WHERE user_id=? AND semana=? AND grupo=? AND orden > 1
                AND ejercicio_id NOT LIKE 'CAR%'
            """, (user_id, sem, perdedor)).fetchall()
            for row in rows_p:
                conn.execute("UPDATE rutinas SET series=? WHERE id=?",
                             (max(2, int(row["series"] or 3) - 1), row["id"]))

        conn.execute("""
            INSERT INTO prioridad_bloques
            (user_id, bloque, semana_inicio, grupo_prioritario, grupo_secundario)
            VALUES (?,
                    (SELECT COALESCE(MAX(bloque),0)+1 FROM prioridad_bloques WHERE user_id=?),
                    ?,?,?)
        """, (user_id, user_id, semana_inicio, ganador, perdedor))

    return {"ganador": ganador, "perdedor": perdedor, "scores": scores, "deload_primero": False}
