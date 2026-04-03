"""
gemini.py — Generación de planes con Gemini 2.0 Flash.

Novedades:
  - Prompt especializado para glúteo con periodización ondulatoria
  - Soporte para ambiente gym / home / band
  - Orden de ejercicios guiado por EMG score en el prompt
  - Cardio zona 2 siempre al final, nunca HIIT
  - Instrucciones específicas por género
"""
from __future__ import annotations

import json
import asyncio
import logging
from typing import Any

from google import genai
from google.genai import types

import catalog as cat
from catalog import ROTACION_ONDULATORIO, SESION_GLUTEO
from science import validar_y_corregir_dia

logger = logging.getLogger(__name__)

MODEL       = "gemini-2.0-flash"
MAX_TOKENS  = 2800
TEMPERATURE = 0.1
TIMEOUT     = 50

PALABRAS_BLOQUEADAS = frozenset({
    "rutina", "plan", "ejercicio", "series", "repeticion", "reps",
    "semana", "programa", "generar", "crear", "dame", "hazme",
    "cuantas", "cuántas", "cuantos", "cuántos",
})

DIAS_POR_N = {
    3: ["lunes", "miercoles", "viernes"],
    4: ["lunes", "martes", "jueves", "viernes"],
    5: ["lunes", "martes", "miercoles", "jueves", "viernes"],
}


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _series_reps_base(nivel: str, semana: int) -> tuple[int, str, int]:
    """Retorna (series_base, reps_str, rir) para la semana y nivel dado."""
    tabla = {
        "principiante": {
            1: (3, "12-15", 3), 2: (3, "10-12", 2),
            3: (3, "10-12", 2), 4: (2, "12-15", 4),
        },
        "intermedio": {
            1: (4, "10-12", 2), 2: (4, "8-10", 2),
            3: (4, "6-8",   1), 4: (3, "10-12", 4),
        },
        "avanzado": {
            1: (5, "8-10", 1), 2: (5, "6-8", 1),
            3: (5, "5-8",  0), 4: (4, "8-10", 3),
        },
    }
    row = tabla.get(nivel, tabla["intermedio"]).get(semana, tabla["intermedio"][1])
    return row


def _catalogo_comprimido(ambiente: str) -> str:
    """Catálogo en formato comprimido filtrado por ambiente."""
    grupos = ["gluteo", "pierna", "empuje", "tiron", "core", "cardio"]
    lines  = []
    for g in grupos:
        ids = cat.ids_por_grupo(g, ambiente=ambiente)
        if ids:
            lines.append(f"{g.upper()}: {' '.join(ids)}")
    return "\n".join(lines)


def _split_desc(objetivo: str, dias: int, genero: str) -> tuple[list[str], list[str]]:
    """
    Retorna (dias_nombres, grupos_por_dia).
    Para glúteo femenino: 3 días de glúteo si días ≥ 3.
    """
    dias_nombres = DIAS_POR_N.get(dias, DIAS_POR_N[3])
    es_gluteo    = "gluteo" in objetivo or "nalg" in objetivo.lower()

    if es_gluteo and genero == "mujer":
        # Split glúteo especializado (Contreras 2015 — frecuencia 3x/semana)
        splits = {
            3: ["gluteo", "tiron",  "gluteo"],
            4: ["gluteo", "empuje", "gluteo", "tiron"],
            5: ["gluteo", "empuje", "tiron",  "gluteo", "pierna"],
        }
    elif "peso" in objetivo:
        splits = {
            3: ["pierna", "empuje", "tiron"],
            4: ["pierna", "empuje", "pierna", "tiron"],
            5: ["pierna", "empuje", "tiron",  "pierna", "empuje"],
        }
    else:
        splits = {
            3: ["pierna", "empuje", "tiron"],
            4: ["pierna", "empuje", "tiron",  "pierna"],
            5: ["pierna", "empuje", "tiron",  "pierna", "tiron"],
        }

    grupos = splits.get(dias, splits[3])
    return dias_nombres, grupos


def _tipo_sesion_gluteo(semana: int, num_dia_gluteo: int) -> dict:
    """Retorna el tipo de sesión de glúteo según periodización ondulatoria."""
    rotacion = ROTACION_ONDULATORIO.get(semana, ROTACION_ONDULATORIO[1])
    clave    = f"g{num_dia_gluteo}"
    tipo     = rotacion.get(clave, "hipertrofia")
    return SESION_GLUTEO.get(tipo, SESION_GLUTEO["hipertrofia"])


def build_prompt(perfil: dict, num_semana: int, ambiente: str = "gym") -> str:
    nivel   = perfil.get("nivel",        "principiante")
    obj     = perfil.get("objetivo",     "general")
    dias    = int(perfil.get("dias",     3))
    lim     = perfil.get("limitaciones", "ninguna")
    genero  = perfil.get("genero",       "mujer")
    dur     = int(perfil.get("duracion_min", 60))

    series_base, reps_base, rir_base = _series_reps_base(nivel, num_semana)
    catalogo   = _catalogo_comprimido(ambiente)
    dias_nombres, grupos = _split_desc(obj, dias, genero)
    es_gluteo  = "gluteo" in obj or "nalg" in obj.lower()
    es_deload  = num_semana == 4

    # IDs de cardio disponibles en este ambiente
    cardio_ids = " ".join(cat.ids_por_grupo("cardio", ambiente=ambiente))

    # Contar días de glúteo para periodización ondulatoria
    contador_gluteo = 0
    sesiones_gluteo = []
    for g in grupos:
        if g == "gluteo":
            contador_gluteo += 1
            tipo_ses = _tipo_sesion_gluteo(num_semana, contador_gluteo)
            sesiones_gluteo.append(tipo_ses)
        else:
            sesiones_gluteo.append(None)

    # Construir descripción del split con tipo de sesión de glúteo
    split_lines = []
    for i, (dia_n, grupo) in enumerate(zip(dias_nombres, grupos)):
        if grupo == "gluteo" and sesiones_gluteo[i]:
            ses = sesiones_gluteo[i]
            split_lines.append(
                f"  {dia_n}: grupo=gluteo · tipo={ses['desc']} · reps={ses['reps']} · RIR={ses.get('rir',2)}"
            )
        else:
            split_lines.append(f"  {dia_n}: grupo={grupo}")

    # Protocolo de nivel
    nivel_protocolo = {
        "principiante": "SOLO máquinas guiadas (gym) o ejercicios peso corporal (casa). "
                        "PROHIBIDO: barra libre, sentadilla búlgara, RIR 0.",
        "intermedio":   "Mancuernas libres, poleas, unilaterales básicos. "
                        "Sentadilla goblet o Smith. RIR mínimo 1.",
        "avanzado":     "Barra libre, sentadilla búlgara, unilaterales avanzados. "
                        "PROHIBIDO: >12 reps en ejercicios principales.",
    }.get(nivel, "")

    # Protocolo objetivo
    if es_gluteo:
        obj_protocolo = """PROTOCOLO GLÚTEO — Contreras (2015) + Nippard (2023):
  ORDEN POR EMG (obligatorio):
    Pos 1: puente_cadera o puente_cadera_unilateral (EMG score 5 — 200% MVIC)
    Pos 2: bisagra_cadera o desplante_unilateral    (EMG score 4-5)
    Pos 3: sentadilla o prensa                      (EMG score 3-4)
    Pos 4: patada o abduccion                       (EMG score 2-3 — aislamiento)
    Pos 5: CARDIO zona 2 — NUNCA HIIT post-glúteo
  CARDIO GLÚTEO: Caminata inclinada o step aeróbico — activa glúteo en cada paso.
                 PROHIBIDO trote o bicicleta intensa en día de glúteo."""
    elif "peso" in obj:
        obj_protocolo = """PROTOCOLO PÉRDIDA GRASA — ACSM 2021:
  Compuestos multiarticulares primero (mayor EPOC).
  Cardio zona 2 al final: 20-30 min, FC 120-135 bpm, NO zona 4-5."""
    else:
        obj_protocolo = """PROTOCOLO TONIFICACIÓN — Schoenfeld 2017:
  Balance empuje:tirón 1:1.5. Core estabilidad > flexión (McGill 2010)."""

    # Protocolo género
    genero_protocolo = (
        """MUJER — Nippard / Contreras:
  Prioridad absoluta: glúteo + pierna tonificada.
  Upper body: tonificación sin volumen excesivo.
  Volumen glúteo: 12-20 series/semana (Contreras 2015).
  Cardio: zona 2 SIEMPRE — preserva músculo mientras quema grasa."""
        if genero == "mujer" else
        """HOMBRE — Schoenfeld / Nippard:
  Pecho, espalda, hombros, brazos. Más press y remo.
  Lower: sentadilla pesada + peso muerto. Sin exceso de aislamiento glúteo."""
    )

    # Limitaciones
    lim_protocolo = {
        "rodilla": "PROHIBIDO: sentadilla búlgara, desplante caminando. USA: prensa pies altos, hip thrust, goblet.",
        "espalda": "PROHIBIDO: peso muerto convencional, good morning. USA: prensa, jalón, hip thrust, remo en máquina.",
        "hombro":  "PROHIBIDO: press militar. USA: press inclinado 45°, face pull, jalón neutro.",
        "ninguna": "",
    }.get(lim, "")

    deload_nota = (
        "DELOAD SEMANA 4: Mismos ejercicios que S1, carga al 60%, RIR alto (3-4). "
        "El objetivo es recuperación, no estímulo."
        if es_deload else ""
    )

    ambiente_nota = {
        "gym":  "AMBIENTE: Gimnasio completo — máquinas, poleas, mancuernas.",
        "home": "AMBIENTE: Casa — peso corporal y equipo mínimo (silla, escalón, botellas).",
        "band": "AMBIENTE: Banda elástica — todos los ejercicios deben ser con banda.",
    }.get(ambiente, "")

    ejemplo = (
        '{"semana":1,"dias":[{"dia":"lunes","grupo":"gluteo","ejercicios":'
        '[{"ejercicio_id":"GLU_G02","orden":1,"series":4,"reps":"10-12","notas":"pausa 1s arriba"}]}]}'
    )

    return f"""INSTRUCCION: Responde SOLO con JSON puro. Sin texto. Sin markdown. Solo el objeto JSON.

CATALOGO — usa SOLO estos IDs exactos:
{catalogo}

TAREA: Genera semana {num_semana}/4.
  Nivel: {nivel} | Objetivo: {obj} | Género: {genero}
  Días: {dias} ({', '.join(dias_nombres)}) | Duración: {dur}min | Limitaciones: {lim}

{ambiente_nota}

SPLIT Y GRUPOS:
{chr(10).join(split_lines)}

PROTOCOLO SEMANA {num_semana}:
  Series base: {series_base} | Reps: {reps_base} | RIR: {rir_base}
  {deload_nota}

ESTRUCTURA POR DÍA — exactamente 5 ejercicios:
  Los ejercicios deben ordenarse de MAYOR a MENOR EMG score del músculo objetivo.
  Pos 5: CARDIO zona 2 SIEMPRE al final ({cardio_ids})
         series=1, reps="20min", NUNCA HIIT, NUNCA >zona 3

{obj_protocolo}

{genero_protocolo}

NIVEL — dificultad y selección de ejercicios:
  {nivel_protocolo}
{lim_protocolo}

REGLAS BIOMECÁNICAS (el backend rechaza violaciones):
  - Máx 1 sentadilla por día (fatiga cuádriceps)
  - Máx 1 bisagra de cadera por día
  - Máx 1 jalón vertical por día
  - Cardio: series=1, reps="20min" — nunca series=3
  - reps siempre string: "15" "8-10" "20min" — NUNCA número
  - Notas: máx 5 palabras, sin comillas internas
  - S2-S3: mismos ejercicios S1, más carga o menos RIR
  - S4 DELOAD: mismos ejercicios S1, 60% carga, RIR alto

FORMATO EXACTO (solo JSON):
{ejemplo}

JSON:"""


# ─── PARSING ──────────────────────────────────────────────────────────────────

def _limpiar_raw(text: str) -> str:
    text = text.strip()
    for prefix in ("```json", "```JSON", "```"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    if text.endswith("```"):
        text = text[:-3]
    text  = text.strip()
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1]
    raise ValueError("No se encontró JSON válido en la respuesta")


def _normalizar_ejercicio(e: dict, ambiente: str = "gym") -> dict | None:
    eid = str(e.get("ejercicio_id", ""))
    if not cat.is_valid(eid):
        logger.warning("ID inválido en respuesta Gemini: %s", eid)
        return None

    ej = cat.BY_ID[eid]

    # Verificar que el ejercicio existe en el ambiente solicitado
    if ambiente not in ej.ambiente and not (ambiente == "gym" and ej.es_gym()):
        # Buscar equivalente en el ambiente correcto
        equiv = cat.equivalente_casa(eid) if ambiente != "gym" else None
        if equiv:
            ej  = equiv
            eid = equiv.id
        else:
            logger.warning("Ejercicio %s no disponible en ambiente %s", eid, ambiente)
            return None

    result = dict(e)
    result["ejercicio_id"] = eid
    result["ejercicio"]    = ej.nombre
    result["patron"]       = ej.patron
    result["emg_score"]    = ej.emg_score

    if ej.es_cardio():
        result["series"] = 1
        reps = str(result.get("reps", "20min"))
        result["reps"] = reps if "min" in reps else "20min"
    else:
        try:
            s = int(result.get("series", 3))
            result["series"] = max(2, min(6, s))
        except (TypeError, ValueError):
            result["series"] = 3
        result["reps"] = str(result.get("reps", "10"))

    # Cue técnico del catálogo (fuente de verdad)
    result["notas"] = ej.cue if ej.cue else str(result.get("notas", "")).strip()[:50]
    return result


def parsear_semana(raw: str, num_semana: int, ambiente: str = "gym") -> tuple[dict | None, str | None]:
    try:
        json_str = _limpiar_raw(raw)
        data: Any = json.loads(json_str)
    except (ValueError, json.JSONDecodeError) as e:
        logger.error("JSON no parseable S%s: %s | Raw: %r", num_semana, e, raw[:300])
        return None, f"JSON malformado: {e}"

    if isinstance(data, list):
        data = data[0] if data else {}
    if "semanas" in data and isinstance(data["semanas"], list):
        data = data["semanas"][0] if data["semanas"] else {}
    if "dias" not in data:
        for v in data.values():
            if isinstance(v, dict) and "dias" in v:
                data = v
                break
    if "dias" not in data:
        return None, f"Falta campo 'dias'. Claves: {list(data.keys())}"
    if not data["dias"]:
        return None, "dias vacío"

    for d in data["dias"]:
        validos = []
        for e in d.get("ejercicios", []):
            norm = _normalizar_ejercicio(e, ambiente=ambiente)
            if norm:
                validos.append(norm)

        d["ejercicios"] = validos
        if not validos:
            return None, f"Día {d.get('dia','?')} sin ejercicios válidos"

        if not d.get("grupo"):
            ej0 = cat.BY_ID.get(validos[0].get("ejercicio_id", ""))
            d["grupo"] = ej0.grupo if ej0 else "general"

        ok, msg = validar_y_corregir_dia(d, ambiente=ambiente)
        if not ok:
            logger.warning("Coherencia fallida S%s %s: %s", num_semana, d.get("dia"), msg)

        n_fuerza = sum(1 for e in d["ejercicios"] if not e["ejercicio_id"].startswith("CAR"))
        if n_fuerza < 3:
            return None, f"Día {d.get('dia','?')}: solo {n_fuerza} ejercicios de fuerza"

    data["semana"] = num_semana
    return data, None


# ─── GENERACIÓN ASYNC ─────────────────────────────────────────────────────────

async def generar_semana(
    client: genai.Client,
    perfil: dict,
    num_semana: int,
    ambiente: str = "gym",
    reintentos: int = 2,
) -> tuple[dict | None, str | None]:
    prompt = build_prompt(perfil, num_semana, ambiente=ambiente)
    loop   = asyncio.get_event_loop()

    for intento in range(1, reintentos + 1):
        try:
            resp = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda p=prompt: client.models.generate_content(
                        model=MODEL,
                        contents=p,
                        config=types.GenerateContentConfig(
                            system_instruction=(
                                "Eres un generador JSON puro. NUNCA texto explicativo. "
                                "NUNCA markdown. SOLO el objeto JSON pedido."
                            ),
                            max_output_tokens=MAX_TOKENS,
                            temperature=TEMPERATURE,
                        ),
                    ),
                ),
                timeout=TIMEOUT,
            )
            sem_data, err = parsear_semana(resp.text, num_semana, ambiente=ambiente)
            if sem_data:
                return sem_data, None
            logger.warning("S%s intento %s: %s", num_semana, intento, err)

        except asyncio.TimeoutError:
            logger.error("Timeout S%s intento %s", num_semana, intento)
        except Exception:
            logger.exception("Error generando S%s intento %s", num_semana, intento)

    return None, f"No se pudo generar semana {num_semana} tras {reintentos} intentos"


async def generar_plan_completo(
    client: genai.Client,
    perfil: dict,
    ambiente: str = "gym",
    on_progress=None,
) -> tuple[list[dict] | None, str | None]:
    semanas = []
    for num in range(1, 5):
        if on_progress:
            await on_progress(num)
        sem, err = await generar_semana(client, perfil, num, ambiente=ambiente)
        if not sem:
            return None, err
        semanas.append(sem)
    return semanas, None


async def coach_response(
    client: genai.Client,
    texto: str,
    nivel: str,
    limitaciones: str,
    semana: int,
    dia: str,
    genero: str = "mujer",
) -> str | None:
    if any(w in texto.lower() for w in PALABRAS_BLOQUEADAS):
        return None

    system = (
        f"Eres un coach de fitness experto, motivador y cercano. "
        f"Usuario: nivel={nivel}, limitaciones={limitaciones}, género={genero}, "
        f"Semana {semana} día {dia}. "
        f"Responde en máximo 3 oraciones con base científica. "
        f"Cita fuentes cuando aplique (Contreras, Schoenfeld, Nippard). "
        f"Si menciona dolor, dile que pare y consulte médico. "
        f"No inventes rutinas — dile que use el menú."
    )
    loop = asyncio.get_event_loop()
    resp = await asyncio.wait_for(
        loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=MODEL,
                contents=texto,
                config=types.GenerateContentConfig(system_instruction=system),
            ),
        ),
        timeout=20,
    )
    return resp.text
