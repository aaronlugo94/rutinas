"""
api.py — FastAPI backend para la web app de GymCoach.

Endpoints:
  POST /auth/login          → token JWT
  GET  /rutina/hoy          → rutina del día con pesos sugeridos
  GET  /plan                → plan completo 4 semanas
  GET  /progreso            → lista ejercicios con historial
  GET  /progreso/{eid}      → historial semana a semana de un ejercicio
  GET  /stats               → racha, XP, badges, totales
  GET  /resumen             → resumen semanal
  POST /pesos               → guardar peso de un ejercicio
  POST /sesion/completar    → marcar sesión como completada

Auth: JWT simple. El user_id se guarda en el token.
CORS: abierto para Vercel.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import JWTError, jwt

import database as db
import catalog as cat
import gamification as gam
import progreso as prog
import science as sci
from planner import RECOVERY_OPCIONES

logger = logging.getLogger(__name__)

# ── CONFIG ────────────────────────────────────────────────────────────────────

SECRET_KEY  = os.environ.get("JWT_SECRET", "gymcoach-dev-secret-change-in-prod")
ALGORITHM   = "HS256"
TOKEN_HOURS = 24 * 30   # 30 días

app = FastAPI(title="GymCoach API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.vercel.app",
        os.environ.get("FRONTEND_URL", ""),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer = HTTPBearer()


# ── AUTH ──────────────────────────────────────────────────────────────────────

def create_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> int:
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    return uid


class LoginRequest(BaseModel):
    user_id: int
    pin:     str   # pin de 4 dígitos configurado en el bot con /setpin


@app.post("/auth/login")
def login(req: LoginRequest):
    """
    Login con user_id de Telegram + PIN de 4 dígitos.
    El PIN se configura en el bot con /setpin 1234
    """
    row = db.fetchone(
        "SELECT pin FROM usuarios WHERE user_id=?", (req.user_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado. Usa el bot primero.")
    if not row["pin"]:
        raise HTTPException(status_code=400, detail="Configura tu PIN en el bot: /setpin 1234")
    if row["pin"] != req.pin:
        raise HTTPException(status_code=401, detail="PIN incorrecto")

    token = create_token(req.user_id)
    perfil = db.get_perfil(req.user_id)
    return {
        "token":  token,
        "nombre": perfil.get("nombre", ""),
        "nivel":  perfil.get("nivel", ""),
    }


# ── RUTINA HOY ────────────────────────────────────────────────────────────────

@app.get("/rutina/hoy")
def rutina_hoy(uid: int = Depends(get_current_user)) -> dict:
    semana, dia = db.get_estado(uid)
    ejercicios  = db.get_ejercicios_dia(uid, semana, dia)

    if not ejercicios:
        # Día libre → recovery activo
        return {
            "tipo":     "recovery",
            "dia":      dia,
            "semana":   semana,
            "opciones": [
                {"emoji": o[0], "nombre": o[1], "desc": o[2]}
                for o in RECOVERY_OPCIONES
            ],
        }

    grupo = ejercicios[0].get("grupo", "general")
    cal   = cat.CALENTAMIENTO.get(grupo, [("5 min caminata o bici", "")])[0]

    ejs_out = []
    for e in ejercicios:
        ej_obj   = cat.BY_ID.get(e["ejercicio_id"])
        ultimo   = db.get_ultimo_peso(uid, e["ejercicio_id"])
        sug      = db.get_peso_sugerido(uid, e["ejercicio_id"])
        ejs_out.append({
            "ejercicio_id": e["ejercicio_id"],
            "nombre":       e["ejercicio"],
            "patron":       e.get("patron", ""),
            "grupo":        e.get("grupo", ""),
            "series":       e["series"],
            "reps":         e["reps"],
            "notas":        e.get("notas", ""),
            "emg_score":    e.get("emg_score", 1),
            "es_cardio":    e["ejercicio_id"].startswith("CAR"),
            "completado":   bool(e["completado"]),
            "ultimo_peso":  float(ultimo["peso_lbs"]) if ultimo and ultimo.get("peso_lbs") else None,
            "peso_sugerido": float(sug) if sug else None,
        })

    racha    = gam.get_racha(uid)
    xp_total = gam.get_xp(uid)
    nivel_gam = gam.get_nivel(xp_total)

    return {
        "tipo":         "rutina",
        "semana":       semana,
        "dia":          dia,
        "grupo":        grupo,
        "duracion_min": _estimar_duracion(ejercicios),
        "calentamiento": {"nombre": cal[0], "nota": cal[1]},
        "ejercicios":   ejs_out,
        "racha":        racha,
        "nivel":        nivel_gam,
        "xp":           xp_total,
    }


def _estimar_duracion(ejercicios: list) -> int:
    from catalog import COMPUESTOS
    minutos = 0
    for e in ejercicios:
        eid = e.get("ejercicio_id", "")
        if eid.startswith("CAR"):
            reps_str = str(e.get("reps", "20min"))
            try:
                minutos += int("".join(filter(str.isdigit, reps_str)))
            except (ValueError, TypeError):
                minutos += 20
        else:
            try:
                series = int(e.get("series", 3))
            except (TypeError, ValueError):
                series = 3
            patron  = e.get("patron", "")
            minutos += series * (3 if patron in COMPUESTOS else 2)
    return minutos


# ── PLAN COMPLETO ─────────────────────────────────────────────────────────────

@app.get("/plan")
def get_plan(uid: int = Depends(get_current_user)) -> dict:
    semana_actual, dia_actual = db.get_estado(uid)
    rows = db.fetchall("""
        SELECT semana, dia, grupo, ejercicio_id, ejercicio,
               series, reps, notas, completado, emg_score
        FROM rutinas WHERE user_id=?
        ORDER BY semana, id, orden
    """, (uid,))

    from collections import defaultdict
    plan: dict = defaultdict(lambda: defaultdict(list))
    for row in rows:
        plan[row["semana"]][row["dia"]].append(dict(row))

    semanas_out = []
    for sem_num in sorted(plan.keys()):
        dias_out = []
        for dia_nombre, ejs in plan[sem_num].items():
            total = len(ejs)
            hechos = sum(1 for e in ejs if e["completado"])
            grupo  = ejs[0]["grupo"] if ejs else "general"
            dias_out.append({
                "dia":       dia_nombre,
                "grupo":     grupo,
                "total":     total,
                "completado": hechos,
                "es_hoy":    sem_num == semana_actual and dia_nombre == dia_actual,
                "ejercicios": [{
                    "ejercicio_id": e["ejercicio_id"],
                    "nombre":       e["ejercicio"],
                    "series":       e["series"],
                    "reps":         e["reps"],
                    "emg_score":    e.get("emg_score", 1),
                    "es_cardio":    e["ejercicio_id"].startswith("CAR"),
                    "completado":   bool(e["completado"]),
                } for e in ejs],
            })
        semanas_out.append({
            "semana":   sem_num,
            "es_actual": sem_num == semana_actual,
            "dias":     dias_out,
        })

    return {"semanas": semanas_out, "semana_actual": semana_actual}


# ── PROGRESO ──────────────────────────────────────────────────────────────────

@app.get("/progreso")
def get_progreso(uid: int = Depends(get_current_user)) -> dict:
    ejercicios = db.get_ejercicios_con_historial(uid)
    resumen    = db.get_resumen_progresion(uid)

    ejs_out = []
    for e in ejercicios:
        res = resumen.get(e["ejercicio_id"], {})
        ej_obj = cat.BY_ID.get(e["ejercicio_id"])
        ejs_out.append({
            "ejercicio_id":      e["ejercicio_id"],
            "nombre":            e["ejercicio"],
            "grupo":             e["grupo"],
            "emg_score":         ej_obj.emg_score if ej_obj else 1,
            "peso_maximo":       float(e["peso_maximo"]) if e["peso_maximo"] else None,
            "semanas_registradas": e["semanas_registradas"],
            "ganancia_total":    round(float(res["ultimo_peso"]) - float(res["primer_peso"]), 1)
                                 if res else 0,
        })

    return {"ejercicios": ejs_out}


@app.get("/progreso/{ejercicio_id}")
def get_historial(ejercicio_id: str, uid: int = Depends(get_current_user)) -> dict:
    ej_obj = cat.BY_ID.get(ejercicio_id)
    if not ej_obj:
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado")

    historial = db.get_progresion_ejercicio(uid, ejercicio_id)
    sug       = db.get_peso_sugerido(uid, ejercicio_id)

    semanas_out = []
    pesos = [float(r["mejor_peso"]) for r in historial if r["mejor_peso"]]
    for row in historial:
        semanas_out.append({
            "semana":      row["semana"],
            "peso":        float(row["mejor_peso"]) if row["mejor_peso"] else None,
            "series":      row["series_hechas"],
            "reps":        row["reps_hechas"],
        })

    ganancia = 0.0
    if len(pesos) >= 2:
        ganancia = round(pesos[-1] - pesos[0], 1)

    return {
        "ejercicio_id":   ejercicio_id,
        "nombre":         ej_obj.nombre,
        "grupo":          ej_obj.grupo,
        "emg_score":      ej_obj.emg_score,
        "historial":      semanas_out,
        "ganancia_total": ganancia,
        "peso_sugerido":  float(sug) if sug else None,
        "tendencia":      "up" if ganancia > 0 else ("down" if ganancia < 0 else "flat"),
    }


# ── STATS ─────────────────────────────────────────────────────────────────────

@app.get("/stats")
def get_stats(uid: int = Depends(get_current_user)) -> dict:
    stats     = db.get_stats(uid)
    racha     = gam.get_racha(uid)
    xp_total  = gam.get_xp(uid)
    nivel     = gam.get_nivel(xp_total)
    badges    = gam.get_badges(uid)

    row_gam = db.fetchone(
        "SELECT racha_maxima FROM gamificacion WHERE user_id=?", (uid,)
    )
    racha_max = int(row_gam["racha_maxima"]) if row_gam else racha

    _, xp_en, xp_para = gam.get_siguiente_nivel(xp_total)

    # Progresiones totales
    row_prog = db.fetchone(
        "SELECT COUNT(*) as n FROM progreso WHERE user_id=? AND progreso_reportado='si'",
        (uid,)
    )
    progresiones = int(row_prog["n"]) if row_prog else 0

    badges_out = []
    for key in badges:
        if key in import_badges():
            emoji, nombre, desc = import_badges()[key]
            badges_out.append({
                "key":    key,
                "emoji":  emoji,
                "nombre": nombre,
                "desc":   desc,
                "ganado": True,
            })

    return {
        "rutinas_totales":  stats["rutinas_completas"],
        "racha_actual":     racha,
        "racha_maxima":     racha_max,
        "progresiones":     progresiones,
        "xp_total":         xp_total,
        "xp_en_nivel":      xp_en,
        "xp_para_nivel":    xp_para,
        "nivel":            nivel,
        "badges":           badges_out,
    }


def import_badges():
    from personality import BADGES
    return BADGES


# ── RESUMEN SEMANAL ───────────────────────────────────────────────────────────

@app.get("/resumen")
def get_resumen(uid: int = Depends(get_current_user)) -> dict:
    semana, _ = db.get_estado(uid)
    dias      = db.get_dias_semana(uid, semana)
    completadas = sum(1 for d in dias if db.rutina_completa(uid, semana, d))
    programadas = len(dias)

    rows_fat = db.fetchall(
        "SELECT fatiga_reportada FROM progreso WHERE user_id=? AND semana=? AND fatiga_reportada IS NOT NULL",
        (uid, semana)
    )
    fatigas = [int(r["fatiga_reportada"]) for r in rows_fat]
    fat_prom = round(sum(fatigas) / len(fatigas), 1) if fatigas else None

    progs_peso = db.get_progresiones_con_peso(uid, semana)
    progresiones_out = []
    for p in progs_peso:
        ej_obj = cat.BY_ID.get(p["ejercicio_id"])
        progresiones_out.append({
            "ejercicio_id": p["ejercicio_id"],
            "nombre":       p["ejercicio"][:30],
            "peso_anterior": float(p["peso_anterior"]) if p.get("peso_anterior") else None,
            "peso_actual":  float(p["peso_actual"]),
            "ganancia":     round(float(p["peso_actual"]) - float(p["peso_anterior"]), 1)
                            if p.get("peso_anterior") else None,
        })

    return {
        "semana":         semana,
        "completadas":    completadas,
        "programadas":    programadas,
        "pct":            round(completadas / max(programadas, 1) * 100),
        "fatiga_promedio": fat_prom,
        "progresiones":   progresiones_out,
        "racha":          gam.get_racha(uid),
    }


# ── GUARDAR PESO ──────────────────────────────────────────────────────────────

class PesoRequest(BaseModel):
    ejercicio_id: str
    peso_lbs:     float
    semana:       int
    dia:          str
    series:       int   = None
    reps:         str   = None


@app.post("/pesos")
def guardar_peso(req: PesoRequest, uid: int = Depends(get_current_user)) -> dict:
    if not cat.is_valid(req.ejercicio_id):
        raise HTTPException(status_code=400, detail="ejercicio_id inválido")
    if req.peso_lbs < 0 or req.peso_lbs > 2000:
        raise HTTPException(status_code=400, detail="Peso fuera de rango")

    db.save_peso(uid, req.ejercicio_id, req.semana, req.dia,
                 peso_lbs=req.peso_lbs, series=req.series, reps=req.reps)

    sug = db.get_peso_sugerido(uid, req.ejercicio_id)
    return {
        "ok":            True,
        "peso_guardado": req.peso_lbs,
        "peso_sugerido": float(sug) if sug else None,
    }


# ── COMPLETAR SESIÓN ──────────────────────────────────────────────────────────

class SesionRequest(BaseModel):
    semana:  int
    dia:     str
    rir:     int   = 2
    fatiga:  int   = 2


@app.post("/sesion/completar")
def completar_sesion(req: SesionRequest, uid: int = Depends(get_current_user)) -> dict:
    # Marcar todos los ejercicios como completados
    with db.get_db() as conn:
        conn.execute(
            "UPDATE rutinas SET completado=1 WHERE user_id=? AND semana=? AND dia=?",
            (uid, req.semana, req.dia),
        )

    db.save_progreso_sesion(uid, req.semana, req.dia,
                            rir=req.rir, progresion="si", fatiga=req.fatiga)

    resultado_sci = sci.analizar_sesion(uid, req.semana, req.dia)
    sci.aplicar_ajuste(uid, req.semana, req.dia, resultado_sci.ajuste)

    resultado_gam = gam.procesar_fin_sesion(
        user_id=uid, semana=req.semana, dia=req.dia,
        progresion="si", grupo=_grupo_del_dia(uid, req.semana, req.dia),
    )

    # Avanzar al siguiente día
    max_sem = db.fetchone("SELECT MAX(semana) as n FROM rutinas WHERE user_id=?", (uid,))
    max_s   = (max_sem["n"] or 4) if max_sem else 4
    nueva_sem, nuevo_dia = db.avanzar_dia(uid, req.semana, req.dia, max_semana=max_s)
    db.upsert_estado(uid, nueva_sem, nuevo_dia)

    if nueva_sem > req.semana:
        try:
            sci.aplicar_prioridad_muscular(uid, nueva_sem)
        except Exception as e:
            logger.warning("Prioridad muscular: %s", e)

    return {
        "ok":            True,
        "xp_ganado":     resultado_gam["xp_ganado"],
        "racha":         resultado_gam["racha"],
        "badges_nuevos": resultado_gam["badges_nuevos"],
        "semana_perfecta": resultado_gam["semana_perfecta"],
        "ajuste":        resultado_sci.ajuste,
        "siguiente_dia": {"semana": nueva_sem, "dia": nuevo_dia},
    }


def _grupo_del_dia(user_id: int, semana: int, dia: str) -> str:
    row = db.fetchone(
        "SELECT grupo FROM rutinas WHERE user_id=? AND semana=? AND dia=? LIMIT 1",
        (user_id, semana, dia),
    )
    return row["grupo"] if row else "general"


# ── SWAP EJERCICIO ────────────────────────────────────────────────────────────

@app.get("/ejercicio/{eid}/alternativas")
def get_alternativas(eid: str, uid: int = Depends(get_current_user)) -> dict:
    if not cat.is_valid(eid):
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado")
    semana, dia = db.get_estado(uid)
    perfil      = db.get_perfil(uid)
    ambiente    = perfil.get("ambiente_preferido", "gym")
    excluir     = {e["ejercicio_id"] for e in db.get_ejercicios_dia(uid, semana, dia)}
    alts        = cat.alternativas(eid, excluir, ambiente=ambiente)
    return {
        "alternativas": [{
            "ejercicio_id": a.id,
            "nombre":       a.nombre,
            "emg_score":    a.emg_score,
            "cue":          a.cue,
        } for a in alts]
    }


class SwapRequest(BaseModel):
    ejercicio_id_original: str
    ejercicio_id_nuevo:    str


@app.post("/ejercicio/swap")
def swap_ejercicio(req: SwapRequest, uid: int = Depends(get_current_user)) -> dict:
    if not cat.is_valid(req.ejercicio_id_original) or not cat.is_valid(req.ejercicio_id_nuevo):
        raise HTTPException(status_code=400, detail="ID inválido")
    ej_orig = cat.BY_ID[req.ejercicio_id_original]
    ej_new  = cat.BY_ID[req.ejercicio_id_nuevo]
    with db.get_db() as conn:
        conn.execute(
            "UPDATE rutinas SET ejercicio_id=?, ejercicio=?, patron=? "
            "WHERE user_id=? AND ejercicio_id=?",
            (ej_new.id, ej_new.nombre, ej_new.patron, uid, ej_orig.id),
        )
        conn.execute(
            "DELETE FROM progreso WHERE user_id=? AND ejercicio_id=?",
            (uid, ej_orig.id),
        )
    db.save_swap(uid, ej_orig.id, ej_new.id, ej_orig.grupo, ej_orig.rol)
    return {"ok": True, "nuevo_ejercicio": {"id": ej_new.id, "nombre": ej_new.nombre}}


# ── SET PIN (también disponible desde el bot) ─────────────────────────────────

class PinRequest(BaseModel):
    user_id: int
    pin:     str
    token_bot: str   # token del bot como verificación extra


@app.post("/auth/setpin")
def set_pin(req: PinRequest) -> dict:
    """Solo accesible con el token del bot — el bot llama esto al hacer /setpin."""
    if req.token_bot != os.environ.get("TELEGRAM_TOKEN", ""):
        raise HTTPException(status_code=403, detail="No autorizado")
    if len(req.pin) != 4 or not req.pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN debe ser 4 dígitos")
    db.execute("UPDATE usuarios SET pin=? WHERE user_id=?", (req.pin, req.user_id))
    return {"ok": True}


# ── HEALTH CHECK ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0"}


# ── STARTUP ───────────────────────────────────────────────────────────────────

@app.on_event("startup")  # noqa
def startup():
    db.init_db()
    # Agregar columna pin si no existe (migración suave)
    try:
        db.execute("ALTER TABLE usuarios ADD COLUMN pin TEXT")
    except Exception:
        pass   # ya existe
    logger.info("GymCoach API lista")
