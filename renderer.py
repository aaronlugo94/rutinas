"""
renderer.py — Mensajes HTML y teclados Telegram.

Diseño: impacto visual máximo dentro de Telegram HTML.
Integra: racha, XP, tipo de sesión glúteo, calentamiento, nutrición, barra de progreso.
"""
from __future__ import annotations

import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import database as db
import catalog as cat
import gamification as gam
import personality as p
from catalog import ROTACION_ONDULATORIO, SESION_GLUTEO


def safe(text: str) -> str:
    return html.escape(str(text), quote=True)


def _estimar_duracion(ejercicios: list[dict]) -> int:
    minutos = 10
    for e in ejercicios:
        try:
            series = int(e.get("series", 3))
        except (TypeError, ValueError):
            series = 3
        minutos += 22 if e.get("ejercicio_id", "").startswith("CAR") else series * 3
    return minutos


def _num_dia_gluteo(user_id: int, semana: int, dia: str) -> int:
    dias = db.get_dias_semana(user_id, semana)
    contador = 0
    for d in dias:
        row = db.fetchone(
            "SELECT grupo FROM rutinas WHERE user_id=? AND semana=? AND dia=? LIMIT 1",
            (user_id, semana, d),
        )
        if row and row["grupo"] == "gluteo":
            contador += 1
            if d == dia:
                return contador
    return 0


def _tipo_sesion_gluteo(semana: int, num_g: int) -> dict | None:
    rotacion = ROTACION_ONDULATORIO.get(semana, ROTACION_ONDULATORIO[1])
    clave    = f"g{num_g}"
    tipo     = rotacion.get(clave)
    return SESION_GLUTEO.get(tipo) if tipo else None


def _tipo_key(ses_info: dict) -> str:
    for k, v in SESION_GLUTEO.items():
        if v is ses_info:
            return k
    return "hipertrofia"


# ══════════════════════════════════════════════════════════════════════════════
# RUTINA DEL DÍA
# ══════════════════════════════════════════════════════════════════════════════

def rutina_html(user_id: int, semana: int, dia: str) -> tuple[str, InlineKeyboardMarkup | None]:
    ejercicios = db.get_ejercicios_dia(user_id, semana, dia)

    if not ejercicios:
        if semana > 4:
            return _msg_plan_completo(user_id), MENU_PRINCIPAL
        return _msg_dia_libre(dia), None

    grupo_dia = ejercicios[0].get("grupo", "general")
    dur       = _estimar_duracion(ejercicios)
    icon      = cat.GRUPO_ICON.get(grupo_dia, "💪")
    perfil    = db.get_perfil(user_id)
    ambiente  = perfil.get("ambiente_preferido", "gym")
    amb_tag   = "🏠 Casa" if ambiente in ("home", "band") else "🏋️ Gym"

    racha    = gam.get_racha(user_id)
    xp_total = gam.get_xp(user_id)
    nivel    = gam.get_nivel(xp_total)

    num_g    = _num_dia_gluteo(user_id, semana, dia) if grupo_dia == "gluteo" else 0
    ses_info = _tipo_sesion_gluteo(semana, num_g) if num_g else None
    tipo_icons = {
        "fuerza":      "🏋️ FUERZA",
        "hipertrofia": "💪 HIPERTROFIA",
        "metabolico":  "🔥 METABÓLICO",
    }

    # HEADER
    tipo_str = ""
    if ses_info:
        tkey = _tipo_key(ses_info)
        tipo_labels = {"fuerza": "Fuerza", "hipertrofia": "Hipertrofia", "metabolico": "Metabólico"}
        tipo_str = f"  {tipo_labels.get(tkey, '')} · {ses_info['reps']} reps · RIR {ses_info.get('rir', 2)}\n"

    msg = (
        f"<b>S{semana} · {dia.capitalize()}</b>  {amb_tag}  ~{dur} min\n"
        f"{tipo_str}"
        f"Racha {p.barra_racha(racha)} · {nivel}\n\n"
    )

    # CALENTAMIENTO
    cal_items = cat.CALENTAMIENTO.get(grupo_dia, cat.CALENTAMIENTO.get("cardio", []))
    if cal_items:
        msg += "<b>Calentamiento</b> (8-10 min)\n"
        for nc, sc, nota in cal_items:
            msg += f"  {nc} — {sc}\n"
        msg += "\n"

    # EJERCICIOS
    msg += "<b>Ejercicios</b>\n"

    keyboard  = []
    hechos    = 0

    for idx, ex in enumerate(ejercicios, 1):
        eid       = ex["ejercicio_id"]
        ej        = cat.BY_ID.get(eid)
        es_cardio = ej.es_cardio() if ej else eid.startswith("CAR")
        hecho     = bool(ex["completado"])
        if hecho:
            hechos += 1

        check = "✅" if hecho else "⬜"
        nex   = safe(ex["ejercicio"])

        msg += f"\n{check} <b>{idx}. {nex}</b>\n"

        if es_cardio:
            t = ex["reps"] if "min" in str(ex["reps"]) else "20min"
            msg += f"   {t} · Zona 2 (120-135 bpm)\n"
        else:
            msg += f"   📌 <b>{ex['series']} × {safe(ex['reps'])} reps</b>\n"
            if ex.get("notas"):
                msg += f"   💡 <i>{safe(ex['notas'])}</i>\n"

        if not es_cardio:
            keyboard.append([
                InlineKeyboardButton(
                    f"{check} {nex[:30]}",
                    callback_data=f"chk:{eid}:{semana}:{dia}",
                ),
                InlineKeyboardButton("🔄", callback_data=f"swp_ask:{eid}:{semana}:{dia}"),
            ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    f"{check} {safe(ex['ejercicio'])[:32]}",
                    callback_data=f"chk:{eid}:{semana}:{dia}",
                ),
            ])

    # BARRA DE PROGRESO SESIÓN
    msg += f"\n{p.barra_progreso(hechos, len(ejercicios))}\n"

    # NUTRICIÓN
    obj_key = "gluteo" if grupo_dia == "gluteo" else ("peso" if "peso" in grupo_dia else "general")
    nutr    = cat.NUTRICION.get(obj_key, cat.NUTRICION["general"])
    msg += (
        f"\n<b>Hoy</b>\n"
        f"  {nutr['pre']}\n"
        f"  {nutr['post']}\n"
    )

    keyboard += [
        [InlineKeyboardButton("📋 Plan completo",      callback_data=f"plan:{semana}")],
        [InlineKeyboardButton("📊 Mi progreso",        callback_data="ver_stats")],
        [InlineKeyboardButton("🏁 ¡Terminé la rutina!", callback_data=f"finish:{semana}:{dia}")],
    ]

    return msg, InlineKeyboardMarkup(keyboard)


def _msg_dia_libre(dia: str) -> str:
    return (
        f"🌿 <b>{dia.capitalize()} — Día de descanso activo</b>\n\n"
        "El descanso no es opcional. Es donde crece el músculo.\n\n"
        "✔ Duerme 7-9 horas — ahí ocurre la síntesis proteica\n"
        "✔ Proteína alta aunque no entrenes (1.6-2.2g/kg)\n"
        "✔ Caminata 20-30 min activa la recuperación sin fatiga\n\n"
        "<i>Tu cuerpo se está volviendo más fuerte hoy. 💚</i>"
    )


def _msg_plan_completo(user_id: int) -> str:
    stats    = db.get_stats(user_id)
    racha    = gam.get_racha(user_id)
    xp_total = gam.get_xp(user_id)
    nivel    = gam.get_nivel(xp_total)
    return (
        f"🎉 <b>¡PLAN COMPLETADO!</b> 🎉\n\n"
        f"💪 <b>{stats['rutinas_completas']}</b> rutinas terminadas\n"
        f"🔥 Racha: <b>{racha} días</b>\n"
        f"⚡ <b>{nivel}</b> · {xp_total} XP\n\n"
        "Lo que la mayoría nunca hace: tú lo terminaste.\n\n"
        "¿Creamos un plan nuevo más retador? 👇"
    )


# ══════════════════════════════════════════════════════════════════════════════
# MENSAJE FIN DE SESIÓN
# ══════════════════════════════════════════════════════════════════════════════

def msg_fin_sesion(resultado: dict) -> str:
    celeb         = resultado["celebracion"]
    racha         = resultado["racha"]
    xp_ganado     = resultado["xp_ganado"]
    nivel         = resultado["nivel"]
    barra_xp      = resultado["barra_xp"]
    badges_nuevos = resultado["badges_nuevos"]
    es_record     = resultado["es_record"]

    msg = celeb + "\n\n"
    msg += f"Racha: {p.barra_racha(racha)}"
    if es_record:
        msg += " — nuevo récord"
    msg += f"\n+{xp_ganado} XP · {nivel}\n{barra_xp}\n"

    if badges_nuevos:
        msg += "\n" + "  ".join(p.badge_html(k) for k in badges_nuevos if k in p.BADGES) + "\n"

    if resultado.get("semana_perfecta"):
        msg += "\nSemana completa. +150 XP\n"

    return msg


# ══════════════════════════════════════════════════════════════════════════════
# PLAN COMPLETO — paginado
# ══════════════════════════════════════════════════════════════════════════════

def plan_html_paginas(user_id: int) -> list[str]:
    from collections import defaultdict
    rows = db.fetchall(
        "SELECT semana, dia, grupo, ejercicio_id, ejercicio, series, reps, notas, completado "
        "FROM rutinas WHERE user_id=? ORDER BY semana, id, orden",
        (user_id,),
    )
    if not rows:
        return []

    plan: dict = defaultdict(lambda: defaultdict(list))
    for row in rows:
        plan[row["semana"]][row["dia"]].append(dict(row))

    semana_actual, _ = db.get_estado(user_id)
    paginas = []

    for sem_num in sorted(plan.keys()):
        marker = " ◀ <b>aquí</b>" if sem_num == semana_actual else ""
        dias_sem = plan[sem_num]
        total_sem  = sum(len(v) for v in dias_sem.values())
        hechos_sem = sum(sum(1 for e in v if e["completado"]) for v in dias_sem.values())

        txt = (
            f"📅 <b>SEMANA {sem_num}/4</b>{marker}\n"
            f"   {p.barra_progreso(hechos_sem, total_sem, ancho=8)}\n"
            "\n"
        )
        for dia_nombre, ejercs in dias_sem.items():
            if not ejercs:
                continue
            grupo    = ejercs[0]["grupo"]
            icon_g   = cat.GRUPO_ICON.get(grupo, "💪")
            hechos_d = sum(1 for e in ejercs if e["completado"])
            txt += f"{icon_g} <b>{dia_nombre.capitalize()}</b> · <i>{grupo.upper()}</i> · {hechos_d}/{len(ejercs)}\n"
            for e in ejercs:
                done = "✅" if e["completado"] else "⬜"
                ej   = cat.BY_ID.get(e["ejercicio_id"])
                if e["ejercicio_id"].startswith("CAR"):
                    t = e["reps"] if "min" in str(e["reps"]) else "20min"
                    txt += f"  {done} 🏃 {safe(e['ejercicio'])} — {t}\n"
                else:
                    emg = f" ⚡{ej.emg_score}" if ej else ""
                    txt += f"  {done} {safe(e['ejercicio'])} — {e['series']}×{e['reps']}{emg}\n"
            txt += "\n"
        paginas.append(txt)

    return paginas


# ══════════════════════════════════════════════════════════════════════════════
# TECLADOS
# ══════════════════════════════════════════════════════════════════════════════

def kb_rir(semana: int, dia: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Sin reserva — di todo",         callback_data=f"rir:{semana}:{dia}:0")],
        [InlineKeyboardButton("💪 RIR 1 — muy intenso",           callback_data=f"rir:{semana}:{dia}:1")],
        [InlineKeyboardButton("✅ RIR 2 — zona dorada perfecta",  callback_data=f"rir:{semana}:{dia}:2")],
        [InlineKeyboardButton("😌 RIR 3+ — demasiado fácil",     callback_data=f"rir:{semana}:{dia}:3")],
    ])


def kb_progresion(semana: int, dia: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Sí — más peso o más reps",       callback_data=f"prg:{semana}:{dia}:si")],
        [InlineKeyboardButton("➡️ Igual que la semana pasada",     callback_data=f"prg:{semana}:{dia}:igual")],
        [InlineKeyboardButton("📉 No — tuve que bajar",            callback_data=f"prg:{semana}:{dia}:no")],
        [InlineKeyboardButton("🌱 Primera vez con este ejercicio", callback_data=f"prg:{semana}:{dia}:primera")],
    ])


def kb_fatiga(semana: int, dia: str, incluir_saltar: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("😊 Fresco (1)", callback_data=f"fat:{semana}:{dia}:1"),
         InlineKeyboardButton("🙂 Leve (2)",   callback_data=f"fat:{semana}:{dia}:2")],
        [InlineKeyboardButton("😐 Moderada (3)", callback_data=f"fat:{semana}:{dia}:3"),
         InlineKeyboardButton("😓 Alta (4)",     callback_data=f"fat:{semana}:{dia}:4")],
        [InlineKeyboardButton("💀 Crítica (5)", callback_data=f"fat:{semana}:{dia}:5")],
    ]
    if incluir_saltar:
        rows.append([InlineKeyboardButton("⏭ Saltar por ahora", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


MENU_PRINCIPAL = InlineKeyboardMarkup([
    [InlineKeyboardButton("💪 Rutina de hoy",          callback_data="menu:hoy")],
    [InlineKeyboardButton("📊 Mi progreso y badges",   callback_data="ver_stats")],
    [InlineKeyboardButton("📈 Resumen de la semana",   callback_data="ver_resumen")],
    [InlineKeyboardButton("📅 Plan completo",          callback_data="menu:plan")],
    [InlineKeyboardButton("😴 Estoy muy cansado",      callback_data="ver_fatiga")],
    [InlineKeyboardButton("🆕 Nuevo plan",             callback_data="menu:nuevo")],
])
