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
    allow_origins=["*"],
    allow_credentials=False,
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


class TelegramAuthRequest(BaseModel):
    id:         int
    first_name: str    = ""
    last_name:  str    = ""
    username:   str    = ""
    photo_url:  str    = ""
    auth_date:  int    = 0
    hash:       str    = ""


@app.post("/auth/telegram")
def login_telegram(req: TelegramAuthRequest):
    """
    Login via Telegram Login Widget.
    Verifica la firma de Telegram para garantizar autenticidad.
    El usuario solo necesita tocar el botón en la web — sin ID ni PIN.
    """
    import time, hashlib, hmac

    bot_token = os.environ.get("TELEGRAM_TOKEN", "")
    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token no configurado")

    # Verificar que el auth_date no sea muy viejo (24 horas)
    if abs(time.time() - req.auth_date) > 86400:
        raise HTTPException(status_code=401, detail="Autenticación expirada. Intenta de nuevo.")

    # Verificar firma de Telegram
    data_check = {k: v for k, v in req.dict().items() if k != "hash" and v}
    data_str   = "\n".join(f"{k}={v}" for k, v in sorted(data_check.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected   = hmac.new(secret_key, data_str.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, req.hash):
        raise HTTPException(status_code=401, detail="Firma inválida — intenta de nuevo")

    uid = req.id

    # Crear usuario si no existe
    db.execute("""
        INSERT OR IGNORE INTO usuarios (user_id, nombre)
        VALUES (?, ?)
    """, (uid, req.first_name))

    # Agregar a allowed_users si no está
    db.execute("""
        INSERT OR IGNORE INTO allowed_users (user_id, activo)
        VALUES (?, 1)
    """, (uid,))

    token  = create_token(uid)
    perfil = db.get_perfil(uid)
    tiene_plan = db.fetchone(
        "SELECT COUNT(*) as n FROM rutinas WHERE user_id=?", (uid,)
    )
    return {
        "token":      token,
        "nombre":     perfil.get("nombre", req.first_name),
        "tiene_plan": (tiene_plan["n"] > 0) if tiene_plan else False,
    }


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
    stored_pin = row["pin"] if row["pin"] else None
    if not stored_pin:
        raise HTTPException(status_code=400, detail="Configura tu PIN en el bot de Telegram: /setpin 1234")
    if stored_pin != req.pin:
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

@app.get("/auth/token")
def auth_token(token: str):
    """
    Valida un magic link token del bot.
    El frontend llama esto cuando el usuario llega desde /login.
    """
    uid = db.consume_login_token(token)
    if not uid:
        raise HTTPException(
            status_code=401,
            detail="Link inválido o expirado. Escribe /login al bot para obtener uno nuevo."
        )
    # Asegurar que el usuario existe
    db.execute("INSERT OR IGNORE INTO usuarios (user_id) VALUES (?)", (uid,))
    db.execute("INSERT OR IGNORE INTO allowed_users (user_id, activo) VALUES (?,1)", (uid,))

    jwt_token = create_token(uid)
    perfil    = db.get_perfil(uid)
    tiene_plan = db.fetchone(
        "SELECT COUNT(*) as n FROM rutinas WHERE user_id=?", (uid,)
    )
    return {
        "token":      jwt_token,
        "nombre":     perfil.get("nombre", ""),
        "tiene_plan": (tiene_plan["n"] > 0) if tiene_plan else False,
    }


@app.get("/analisis/historial")
def get_analisis_historial(uid: int = Depends(get_current_user)) -> dict:
    """Historial de análisis guardados."""
    rows = db.fetchall("""
        SELECT fecha, texto, tipo FROM analisis_historial
        WHERE user_id=? ORDER BY fecha DESC LIMIT 14
    """, (uid,))
    return {"historial": [dict(r) for r in rows] if rows else []}


@app.get("/analisis")
async def get_analisis(uid: int = Depends(get_current_user)) -> dict:
    """Análisis con Gemini de la semana actual."""
    import os
    from google import genai as gai

    semana, dia = db.get_estado(uid)
    perfil      = db.get_perfil(uid)

    # Recopilar datos de la semana
    rows = db.fetchall("""
        SELECT p.ejercicio_id, r.ejercicio, r.grupo,
               MAX(p.peso_lbs) as peso_max,
               LAG(MAX(p.peso_lbs)) OVER (PARTITION BY p.ejercicio_id ORDER BY p.semana) as peso_ant
        FROM pesos p
        JOIN rutinas r ON r.user_id=p.user_id AND r.ejercicio_id=p.ejercicio_id
        WHERE p.user_id=? AND p.peso_lbs IS NOT NULL
        GROUP BY p.ejercicio_id, p.semana
        ORDER BY p.semana DESC
        LIMIT 20
    """, (uid,))

    if not rows:
        return {"texto": None, "tiene_datos": False}

    pesos_str = "\n".join(
        f"- {r['ejercicio']}: {r['peso_max']:g} lbs"
        + (f" (antes: {r['peso_ant']:g} lbs)" if r['peso_ant'] else " (primera vez)")
        for r in rows[:8]
    )

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        return {"texto": None, "tiene_datos": True}

    try:
        client = gai.Client(api_key=gemini_key)
        resp   = client.models.generate_content(
            model    = "gemini-2.0-flash",
            contents = f"""Eres un coach de gym. Analiza estos datos en 2-3 líneas cortas y directas.
Sin frases motivacionales genéricas. Solo observaciones específicas con números.

Datos de entrenamiento:
{pesos_str}

Nivel: {perfil.get('nivel','intermedio')} | Objetivo: {perfil.get('objetivo','general')}

Responde en español. Máximo 3 líneas. Sin bullets, en párrafo."""
        )
        return {"texto": resp.text.strip(), "tiene_datos": True}
    except Exception as e:
        logger.warning("Gemini analisis: %s", e)
        return {"texto": None, "tiene_datos": True}


# ── CUERPO ────────────────────────────────────────────────────────────────────

@app.get("/cuerpo")
def get_cuerpo(uid: int = Depends(get_current_user)) -> dict:
    """Último pesaje + score + proyección a meta."""
    import cuerpo as corp
    data = corp.get_resumen_cuerpo()
    if not data:
        return {"tiene_datos": False}
    return {"tiene_datos": True, **data}


@app.get("/cuerpo/historial")
def get_cuerpo_historial(uid: int = Depends(get_current_user)) -> dict:
    """Historial de pesajes para la gráfica de tendencia."""
    historial = db.get_historial_pesajes(dias=90)
    return {"historial": [dict(r) for r in historial]}


# ── NUTRICIÓN ─────────────────────────────────────────────────────────────────

@app.get("/nutricion/plan")
def get_plan_nutricion(uid: int = Depends(get_current_user)) -> dict:
    """Plan semanal actual."""
    import nutricion as nut
    plan = nut.get_plan_actual()
    if not plan:
        return {"tiene_plan": False}
    return {"tiene_plan": True, **plan}


@app.get("/nutricion/macros")
def get_macros(uid: int = Depends(get_current_user)) -> dict:
    """Macros del día según último pesaje y multiplicador actual."""
    import nutricion as nut
    macros = nut.get_macros_hoy()
    if not macros:
        return {"tiene_datos": False}
    return {"tiene_datos": True, **macros}


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0"}


# ── STARTUP ───────────────────────────────────────────────────────────────────

@app.on_event("startup")  # noqa
async def startup():
    db.init_db()
    for sql in [
        "ALTER TABLE usuarios ADD COLUMN pin TEXT",
        "ALTER TABLE usuarios ADD COLUMN hora_recordatorio TEXT",
        """CREATE TABLE IF NOT EXISTS login_tokens (
            token TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, used INTEGER DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS pesajes (
            Fecha TEXT PRIMARY KEY, Timestamp INTEGER UNIQUE,
            Peso_kg REAL, Grasa_Porcentaje REAL, Agua REAL,
            Musculo_Pct REAL, Musculo_kg REAL, BMR INTEGER, VisFat REAL,
            BMI REAL, EdadMetabolica INTEGER, FatFreeWeight REAL,
            Proteina REAL, MasaOsea REAL)""",
        """CREATE TABLE IF NOT EXISTS historico_dietas (
            fecha TEXT PRIMARY KEY, score_comp INTEGER, estado_mimo TEXT,
            kcal_mult REAL, calorias INTEGER, proteina INTEGER,
            carbs INTEGER, grasas INTEGER, dieta_html TEXT, delta_peso REAL)""",
        "CREATE TABLE IF NOT EXISTS config_nutricion (clave TEXT PRIMARY KEY, valor TEXT)",
        "INSERT OR IGNORE INTO config_nutricion (clave, valor) VALUES ('kcal_mult','1.0')",
        "CREATE TABLE IF NOT EXISTS analisis_historial (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, fecha TEXT NOT NULL, texto TEXT NOT NULL, tipo TEXT DEFAULT 'nocturno')",
        """CREATE TABLE IF NOT EXISTS sesion_activa (
            user_id INTEGER PRIMARY KEY, semana INTEGER, dia TEXT,
            ej_idx INTEGER DEFAULT 0, fase TEXT DEFAULT 'ejercicio',
            updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS peso_flow (
            user_id INTEGER PRIMARY KEY, semana INTEGER, dia TEXT,
            ejercicios TEXT, idx INTEGER DEFAULT 0,
            updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    ]:
        try:
            db.execute(sql)
        except Exception:
            pass
    logger.info("GymCoach API lista")

    # Arrancar el bot de Telegram como tarea asyncio en el mismo event loop
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        import asyncio
        asyncio.create_task(_run_bot(token))
        logger.info("Bot de Telegram arrancado como tarea asyncio")
    else:
        logger.warning("TELEGRAM_TOKEN no encontrado — bot no arrancado")


async def _run_bot(token: str) -> None:
    """Corre el bot de Telegram en el mismo event loop que FastAPI."""
    import handlers as h
    from telegram.ext import Application

    h.load_allowed_users()
    bot_app = Application.builder().token(token).build()
    h.register_handlers(bot_app)

    import notificaciones as notif

    async def recordatorios(ctx) -> None:
        import pytz
        from datetime import datetime
        import cuerpo as corp
        import nutricion as nut

        tz   = pytz.timezone("America/Phoenix")
        hora = datetime.now(tz).strftime("%H:%M")

        # Recordatorios gym + análisis nocturno
        await notif.check_y_enviar(bot_app.bot, hora)

        # Renpho check — corre entre 12pm y 6pm hora local
        hora_int = int(hora.replace(":",""))
        if 1200 <= hora_int <= 1800:
            try:
                # Obtener datos gym para análisis cruzado
                from gamification import get_racha
                uid_principal = int(os.environ.get("ADMIN_TELEGRAM_ID", "1557254587"))
                racha = get_racha(uid_principal)
                datos_gym = {"racha": racha}
                await corp.ejecutar_diario(
                    bot=bot_app.bot,
                    chat_id=uid_principal,
                    datos_gym=datos_gym,
                )
            except Exception as e:
                logger.warning("Renpho check: %s", e)

        # Job dominical — corre solo domingos
        import pytz as _tz
        if datetime.now(_tz.timezone("America/Phoenix")).weekday() == 6:
            try:
                uid_principal = int(os.environ.get("ADMIN_TELEGRAM_ID", "1557254587"))
                await nut.ejecutar_dominical(
                    bot=bot_app.bot,
                    chat_id=uid_principal,
                )
            except Exception as e:
                logger.warning("Job dominical: %s", e)

    jq = bot_app.job_queue
    if jq:
        jq.run_repeating(recordatorios, interval=60, first=10)

    # Usar initialize/start/run en lugar de run_polling()
    # run_polling() intenta manejar signals — no funciona fuera del main thread
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot polling activo")
    # Mantener corriendo indefinidamente
    import asyncio
    while True:
        await asyncio.sleep(3600)
