"""
renderer.py — Mensajes HTML y teclados Telegram.

Diseño: impacto visual máximo dentro de Telegram HTML.
Integra: racha, XP, tipo de sesión glúteo, calentamiento, nutrición, barra de progreso.
"""
from __future__ import annotations
import os

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
    from catalog import COMPUESTOS
    for e in ejercicios:
        eid = e.get("ejercicio_id", "")
        if eid.startswith("CAR"):
            # Cardio: leer duración real del campo reps
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
            patron = e.get("patron", "")
            # Compuestos: ~2.5 min/serie (set + descanso)
            # Accesorios: ~2 min/serie
            minutos += series * (3 if patron in COMPUESTOS else 2)
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

def rutina_preview(user_id: int, semana: int, dia: str) -> tuple[str, InlineKeyboardMarkup]:
    """
    Vista completa de la rutina con botón Empezar.
    El usuario revisa qué toca, luego toca Empezar para ir ejercicio por ejercicio.
    """
    ejercicios = db.get_ejercicios_dia(user_id, semana, dia)
    if not ejercicios:
        msg, kb = _msg_dia_libre(dia)
        return msg, kb

    grupo   = ejercicios[0].get("grupo", "general")
    dur     = _estimar_duracion(ejercicios)
    icon    = cat.GRUPO_ICON.get(grupo, "💪")
    perfil  = db.get_perfil(user_id)
    ambiente = perfil.get("ambiente_preferido", "gym")
    amb_tag = "🏠 Casa" if ambiente in ("home", "band") else "🏋️ Gym"
    racha   = gam.get_racha(user_id)

    # Header
    from catalog import CALENTAMIENTO
    cal = CALENTAMIENTO.get(grupo, [("5 min caminata o bici suave", "")])[0]

    racha_str = f"🔥 {racha} días de racha\n" if racha >= 3 else ""
    msg = (
        f"<b>S{semana} · {dia.capitalize()}</b>  {amb_tag}  ~{dur} min\n"
        f"{racha_str}"
        f"\n🔥 <b>Calentamiento:</b> {cal[0]}\n\n"
        f"<b>Rutina de hoy:</b>\n"
    )

    fuerza = [e for e in ejercicios if not e["ejercicio_id"].startswith("CAR")]
    cardio = next((e for e in ejercicios if e["ejercicio_id"].startswith("CAR")), None)

    for i, ej in enumerate(fuerza, 1):
        ultimo = db.get_ultimo_peso(user_id, ej["ejercicio_id"])
        sug    = db.get_peso_sugerido(user_id, ej["ejercicio_id"])
        peso_str = ""
        if sug:
            peso_str = f"  <i>→ {sug} lbs</i>"
        elif ultimo and ultimo.get("peso_lbs"):
            peso_str = f"  <i>última: {ultimo['peso_lbs']:g} lbs</i>"
        msg += f"{i}. {safe(ej['ejercicio'])}  {ej['series']}×{ej['reps']}{peso_str}\n"

    if cardio:
        msg += f"🏃 {safe(cardio['ejercicio'])}  {cardio['reps']} · Zona 2\n"

    msg += "\nRevisa las máquinas y toca <b>Empezar</b> cuando estés listo 👇"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶ Empezar sesión", callback_data=f"ej_start:{semana}:{dia}")],
        [InlineKeyboardButton("⏭ Saltar este día", callback_data=f"skip_day:{semana}:{dia}"),
         InlineKeyboardButton("❓ Ayuda",           callback_data="ver_ayuda")],
    ])
    return msg, kb


def render_ejercicio(user_id: int, semana: int, dia: str, idx: int) -> tuple[str, InlineKeyboardMarkup]:
    """
    Render de un solo ejercicio durante la sesión.
    Muestra: ejercicio actual + preview del siguiente.
    """
    ejercicios = db.get_ejercicios_dia(user_id, semana, dia)
    fuerza     = [e for e in ejercicios if not e["ejercicio_id"].startswith("CAR")]
    cardio     = next((e for e in ejercicios if e["ejercicio_id"].startswith("CAR")), None)
    total      = len(fuerza)

    if idx >= total:
        # Cardio o fin
        if cardio:
            msg = (
                f"🏃 <b>Cardio — último paso</b>\n\n"
                f"{safe(cardio['ejercicio'])}\n"
                f"{cardio['reps']} · Zona 2 (120-135 bpm)\n\n"
                f"Cuando termines toca <b>Terminé</b> 👇"
            )
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Terminé la sesión", callback_data=f"ej_done:{semana}:{dia}")
            ]])
        else:
            msg = "✅ Todos los ejercicios completados. Toca <b>Terminé</b> 👇"
            kb  = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Terminé la sesión", callback_data=f"ej_done:{semana}:{dia}")
            ]])
        return msg, kb

    ej     = fuerza[idx]
    eid    = ej["ejercicio_id"]
    nombre = safe(ej["ejercicio"])
    ultimo = db.get_ultimo_peso(user_id, eid)
    sug    = db.get_peso_sugerido(user_id, eid)

    # Peso hint
    if sug and ultimo and ultimo.get("peso_lbs"):
        peso_line = f"<s>{ultimo['peso_lbs']:g} lbs</s>  →  <b>{sug} lbs hoy</b>"
    elif ultimo and ultimo.get("peso_lbs"):
        peso_line = f"Última vez: {ultimo['peso_lbs']:g} lbs"
    else:
        peso_line = "<i>Primera vez — pon un peso que puedas controlar</i>"

    # Preview siguiente
    if idx + 1 < total:
        sig = fuerza[idx + 1]
        siguiente_str = f"<i>Siguiente: {safe(sig['ejercicio'])}</i>"
    elif cardio:
        siguiente_str = f"<i>Siguiente: {safe(cardio['ejercicio'])} — cardio</i>"
    else:
        siguiente_str = "\n<i>Último ejercicio</i>"

    notas = ej.get("notas", "")

    notas_str = f"\n<i>{safe(notas)}</i>" if notas else ""

    # Lista de lo que falta
    pendientes = fuerza[idx+1:]
    if pendientes:
        falta_str = "\n\n<b>Falta:</b>\n" + "\n".join(
            f"  · {safe(e['ejercicio'][:28])}" for e in pendientes
        )
        if cardio:
            falta_str += f"\n  · 🏃 {safe(cardio['ejercicio'][:25])}"
    elif cardio:
        falta_str = f"\n\n<b>Falta:</b>\n  · 🏃 {safe(cardio['ejercicio'][:25])}"
    else:
        falta_str = "\n\n<i>Último ejercicio</i>"

    msg = (
        f"<b>{idx+1}/{total} — {nombre}</b>\n"
        f"{ej['series']} series × {ej['reps']} reps\n"
        f"{peso_line}"
        f"{notas_str}"
        f"{falta_str}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Cambiar ejercicio", callback_data=f"swp_ask:{eid}:{semana}:{dia}"),],
        [InlineKeyboardButton("✅ Hecho", callback_data=f"ej_hecho:{semana}:{dia}:{idx}")],
    ])
    return msg, kb


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
    )

    # CALENTAMIENTO
    cal_items = cat.CALENTAMIENTO.get(grupo_dia, cat.CALENTAMIENTO.get("cardio", []))
    cal_items = cat.CALENTAMIENTO.get(grupo_dia, cat.CALENTAMIENTO.get("cardio", []))
    if cal_items:
        nombre_cal, nota_cal = cal_items[0]
        msg += f"🔥 <b>Calentamiento:</b> {nombre_cal}\n<i>{nota_cal}</i>\n\n"

    # EJERCICIOS
    msg += "<b>Ejercicios</b>  <i>↓ Haz todos, luego toca Terminé</i>\n"

    keyboard  = []

    for idx, ex in enumerate(ejercicios, 1):
        eid       = ex["ejercicio_id"]
        ej        = cat.BY_ID.get(eid)
        es_cardio = ej.es_cardio() if ej else eid.startswith("CAR")
        nex = safe(ex["ejercicio"])
        msg += f"\n<b>{idx}. {nex}</b>\n"

        if es_cardio:
            t = ex["reps"] if "min" in str(ex["reps"]) else "20min"
            msg += f"   {t} · Zona 2 (120-135 bpm)\n"
        else:
            msg += f"   {ex['series']} × {safe(ex['reps'])} reps\n"
            # Peso sugerido basado en historial real
            ultimo   = db.get_ultimo_peso(user_id, eid)
            peso_sug = db.get_peso_sugerido(user_id, eid)
            if ultimo and ultimo.get("peso_lbs"):
                ult_kg  = f"{ultimo['peso_lbs']:g}"
                ult_rep = ultimo.get("reps_hechas") or ex["reps"]
                if peso_sug and peso_sug != ult_kg:
                    msg += f"   Última: {ult_kg} lbs → <b>Hoy: {peso_sug} lbs</b>\n"
                else:
                    msg += f"   Última: {ult_kg} lbs × {ex['series']}×{ult_rep}\n"
            elif ex.get("notas"):
                msg += f"   <i>{safe(ex['notas'])}</i>\n"

        if not es_cardio:
            # Solo botón de swap — los checks ya no son necesarios
            keyboard.append([
                InlineKeyboardButton(
                    f"🔄 No me gusta — cambiar {nex[:20]}",
                    callback_data=f"swp_ask:{eid}:{semana}:{dia}",
                ),
            ])





    keyboard += [
        [InlineKeyboardButton("✅ Terminé — registré todo", callback_data=f"finish:{semana}:{dia}")],
        [InlineKeyboardButton("⏭ Saltar este día",          callback_data=f"skip_day:{semana}:{dia}"),
         InlineKeyboardButton("❓ Ayuda",                    callback_data="ver_ayuda")],
    ]

    return msg, InlineKeyboardMarkup(keyboard)


def _msg_dia_libre(dia: str) -> tuple[str, InlineKeyboardMarkup]:
    opts_texto = (
        f"<b>{dia.capitalize()} — Día de descanso</b>\n\n"
        "Elige tu recovery de hoy 👇"
    )
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧘 Movilidad (15 min)",       callback_data="recovery:movilidad")],
        [InlineKeyboardButton("🚶 Caminata suave (30 min)",  callback_data="recovery:caminata")],
        [InlineKeyboardButton("🚴 Bici zona 1 (30 min)",     callback_data="recovery:bici")],
        [InlineKeyboardButton("🎯 Core ligero (plancha+abs)", callback_data="recovery:core")],
        [InlineKeyboardButton("😴 Solo descansar hoy",       callback_data="recovery:descanso")],
    ])
    return opts_texto, teclado


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


WEB_URL = os.environ.get("FRONTEND_URL", "https://gymcoach.vercel.app")

MENU_PRINCIPAL = InlineKeyboardMarkup([
    [InlineKeyboardButton("💪 Mi rutina de hoy",          callback_data="menu:hoy")],
    [InlineKeyboardButton("🌐 Ver progreso y stats →",    url=WEB_URL)],
    [InlineKeyboardButton("🆕 Nuevo plan",                callback_data="menu:nuevo")],
])
