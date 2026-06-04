"""
renderer.py — Mensajes y teclados del bot.

Principios de diseño:
- Una sola ventana (edit_message_text siempre)
- Teclado persistente siempre visible abajo
- Inline keyboard solo para flujos temporales
- Mensajes cortos y directos
"""
from __future__ import annotations
import os
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
import database as db
import personality as p

WEB_URL = os.environ.get("FRONTEND_URL", "https://rutinas-nine.vercel.app")

# ── Teclado persistente (siempre visible en la barra de texto) ────────────────
TECLADO_PERSISTENTE = ReplyKeyboardMarkup(
    [
        ["💪 Rutina de hoy",  "⚖️ Mi cuerpo"],
        ["🥗 Mi dieta",       "❓ Ayuda"],
    ],
    resize_keyboard  = True,
    is_persistent    = True,
    input_field_placeholder = "Escribe o usa los botones 👇",
)

# ── Menú principal inline ─────────────────────────────────────────────────────
MENU_PRINCIPAL = InlineKeyboardMarkup([
    [InlineKeyboardButton("💪 Rutina de hoy",   callback_data="menu:hoy")],
    [InlineKeyboardButton("⚖️ Mi cuerpo",        callback_data="menu:cuerpo"),
     InlineKeyboardButton("🥗 Mi dieta",         callback_data="menu:dieta")],
    [InlineKeyboardButton("🌐 Ver todo →",       url=WEB_URL),
     InlineKeyboardButton("❓ Ayuda",            callback_data="ver_ayuda")],
])

# ── Ayuda ─────────────────────────────────────────────────────────────────────
AYUDA_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("💪 Mi rutina de hoy",    callback_data="menu:hoy")],
    [InlineKeyboardButton("🔄 Cambiar mi rutina",   callback_data="menu:nuevo")],
    [InlineKeyboardButton("🥗 Regenerar mi dieta",  callback_data="dieta:regenerar")],
    [InlineKeyboardButton("⏰ Cambiar recordatorio", callback_data="ayuda:horario")],
    [InlineKeyboardButton("✈️ Modo viaje / Pausa",  callback_data="ayuda:pausa")],
    [InlineKeyboardButton("🌐 Entrar a la web",     callback_data="ayuda:login")],
    [InlineKeyboardButton("🏠 Menú",               callback_data="menu:main")],
])

# ── Botón de regreso simple ───────────────────────────────────────────────────
BTN_MENU = InlineKeyboardMarkup([[
    InlineKeyboardButton("🏠 Menú", callback_data="menu:main")
]])

BTN_MENU_Y_WEB = InlineKeyboardMarkup([
    [InlineKeyboardButton("🌐 Ver en la web →", url=WEB_URL)],
    [InlineKeyboardButton("🏠 Menú",            callback_data="menu:main")],
])


# ══════════════════════════════════════════════════════════════════════════════
# RUTINA
# ══════════════════════════════════════════════════════════════════════════════

def rutina_preview(user_id: int, semana: int, dia: str) -> tuple[str, InlineKeyboardMarkup]:
    """Preview de la rutina del día antes de empezar."""
    rows = db.get_ejercicios_dia(user_id, semana, dia)
    if not rows:
        return (
            f"No hay rutina para {dia}.\nUsa <b>🆕 Nuevo plan</b> para crear una.",
            BTN_MENU,
        )

    fuerza = [r for r in rows if not r.get("es_cardio")]
    cardio  = next((r for r in rows if r.get("es_cardio")), None)
    grupo   = fuerza[0].get("grupo", "") if fuerza else ""
    duracion = 60 + len(fuerza) * 5
    es_deload = semana == 4

    GRUPO_ICON = {
        "empuje": "💪", "tiron": "🏋️", "pierna": "🦵",
        "gluteo": "🍑", "core": "🎯", "cardio": "🏃",
    }
    icon = GRUPO_ICON.get(grupo, "💪")

    deload_banner = ""
    if es_deload:
        deload_banner = "\n♻️ <b>Semana de deload</b> — volumen reducido 40%, mismos ejercicios. El cuerpo se recupera y supercompensa. No subas los pesos esta semana.\n"

    lines = [
        f"<b>S{semana} · {dia.capitalize()} {icon} Gym  ~{duracion} min</b>",
        deload_banner,
    ]

    # Calentamiento
    cal = db.fetchone(
        "SELECT notas FROM rutinas WHERE user_id=? AND semana=? AND dia=? AND rol='calentamiento' LIMIT 1",
        (user_id, semana, dia)
    )
    if cal and cal["notas"]:
        lines.append(f"🔥 <b>Calentamiento:</b> {cal['notas']}\n")

    lines.append("<b>Rutina de hoy:</b>")
    for i, r in enumerate(fuerza, 1):
        peso_sug = db.get_peso_sugerido(user_id, r["ejercicio_id"])
        sug_str = f" → <i>{peso_sug} lbs</i>" if peso_sug else ""
        lines.append(f"{i}. {r['ejercicio']}  {r['series']}×{r['reps']}{sug_str}")

    if cardio:
        lines.append(f"🏃 {cardio['ejercicio']}  {cardio['reps']} · Zona 2")

    lines.append("\nRevisa las máquinas y toca <b>Empezar</b> cuando estés listo 👇")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶ Empezar sesión",  callback_data=f"ej_start:{semana}:{dia}")],
        [InlineKeyboardButton("⏭ Saltar este día", callback_data=f"skip_day:{semana}:{dia}"),
         InlineKeyboardButton("❓ Ayuda",           callback_data="ver_ayuda")],
        [InlineKeyboardButton("🆕 Nuevo plan",      callback_data="menu:nuevo"),
         InlineKeyboardButton("🏠 Menú",           callback_data="menu:main")],
    ])

    return "\n".join(lines), kb


def render_ejercicio(user_id: int, semana: int, dia: str, idx: int) -> tuple[str, InlineKeyboardMarkup]:
    """Pantalla de un ejercicio durante la sesión."""
    rows   = [r for r in db.get_ejercicios_dia(user_id, semana, dia) if not r.get("es_cardio")]
    cardio = next((r for r in db.get_ejercicios_dia(user_id, semana, dia) if r.get("es_cardio")), None)

    if idx >= len(rows):
        # Cardio o fin
        if cardio:
            return render_cardio(semana, dia, cardio)
        return _render_fin(user_id, semana, dia)

    ej   = rows[idx]
    eid  = ej["ejercicio_id"]
    rest = [r["ejercicio"] for r in rows[idx+1:]]
    if cardio:
        rest.append(f"🏃 {cardio['ejercicio']}")

    peso_ant = db.get_ultimo_peso(user_id, eid)
    peso_sug = db.get_peso_sugerido(user_id, eid)

    prog_line = ""
    if peso_ant and peso_ant.get("peso_lbs"):
        if peso_sug and peso_sug != peso_ant["peso_lbs"]:
            prog_line = f"\n<s>{peso_ant['peso_lbs']} lbs</s> → <b>{peso_sug} lbs hoy</b>"
        else:
            prog_line = f"\n→ {peso_ant['peso_lbs']} lbs (igual que antes)"
    elif peso_sug:
        prog_line = f"\nPrimera vez — empieza con <b>{peso_sug} lbs</b>"

    falta_str = ""
    if rest:
        falta_str = "\n\n<b>Falta:</b>\n" + "\n".join(f"· {e}" for e in rest[:3])
        if len(rest) > 3:
            falta_str += f"\n· +{len(rest)-3} más"

    texto = (
        f"<b>{idx+1}/{len(rows)} — {ej['ejercicio']}</b>\n"
        f"{ej['series']} series × {ej['reps']} reps"
        f"{prog_line}"
    )
    if ej.get("notas"):
        texto += f"\n<i>{ej['notas']}</i>"
    texto += falta_str

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Cambiar ejercicio", callback_data=f"swp_ask:{eid}:{semana}:{dia}:0")],
        [InlineKeyboardButton("✅ Hecho",              callback_data=f"ej_hecho:{semana}:{dia}:{idx}")],
        [InlineKeyboardButton("⏭ Saltar día",         callback_data=f"skip_day:{semana}:{dia}"),
         InlineKeyboardButton("🏠 Menú",              callback_data="menu:main")],
    ])
    return texto, kb


def render_cardio(semana: int, dia: str, cardio: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Pantalla de cardio al final de la sesión."""
    texto = (
        f"🏃 <b>{cardio['ejercicio']}</b>\n"
        f"{cardio['reps']} · Zona 2 · 120-135 bpm\n\n"
        f"<i>Mantén un ritmo donde puedas hablar con frases cortas.</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Terminé la sesión", callback_data=f"ej_done:{semana}:{dia}")],
        [InlineKeyboardButton("🏠 Menú",              callback_data="menu:main")],
    ])
    return texto, kb


def _render_fin(user_id: int, semana: int, dia: str) -> tuple[str, InlineKeyboardMarkup]:
    """Pantalla de fin de sesión si no hay cardio."""
    texto = "✅ <b>Todos los ejercicios completados</b>\n\n¿Cómo estuvo la sesión?"
    kb    = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Intenso — sin reserva",    callback_data=f"sesion:{semana}:{dia}:0:5")],
        [InlineKeyboardButton("💪 Bien — quedaban 1-2 reps", callback_data=f"sesion:{semana}:{dia}:2:3")],
        [InlineKeyboardButton("😌 Fácil — podía más",        callback_data=f"sesion:{semana}:{dia}:3:2")],
        [InlineKeyboardButton("😓 Muy cansado hoy",          callback_data=f"sesion:{semana}:{dia}:2:4")],
    ])
    return texto, kb


def render_swap(ejercicio_id: str, semana: int, dia: str,
                alternativas: list, pagina: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    """Lista de ejercicios alternativos para swap."""
    POR_PAG = 4
    total   = len(alternativas)
    inicio  = pagina * POR_PAG
    alts    = alternativas[inicio:inicio + POR_PAG]

    ej_actual = db.fetchone(
        "SELECT ejercicio FROM rutinas WHERE user_id IS NOT NULL AND ejercicio_id=? LIMIT 1",
        (ejercicio_id,)
    )
    nombre_actual = ej_actual["ejercicio"] if ej_actual else ejercicio_id

    texto = f"<b>Cambiar:</b> {nombre_actual}\n<i>Opciones {inicio+1}-{min(inicio+POR_PAG, total)} de {total}</i>"

    botones = []
    for a in alts:
        botones.append([InlineKeyboardButton(
            f"⚡{a.get('emg_score','?')}  {a['nombre']}",
            callback_data=f"swp_do:{ejercicio_id}:{a['id']}:{semana}:{dia}",
        )])

    nav = []
    if pagina > 0:
        nav.append(InlineKeyboardButton("← Anterior", callback_data=f"swp_ask:{ejercicio_id}:{semana}:{dia}:{pagina-1}"))
    if inicio + POR_PAG < total:
        nav.append(InlineKeyboardButton(f"Ver más ({min(inicio+POR_PAG+1, total)}-{min(inicio+POR_PAG*2, total)}) →",
                                        callback_data=f"swp_ask:{ejercicio_id}:{semana}:{dia}:{pagina+1}"))
    if nav:
        botones.append(nav)

    botones.append([InlineKeyboardButton("✖ Cancelar — volver", callback_data=f"swp_cancel:{semana}:{dia}")])
    return texto, InlineKeyboardMarkup(botones)


def msg_fin_sesion(resultado: dict) -> str:
    """Mensaje de cierre de sesión con XP y racha."""
    racha    = resultado.get("racha", 0)
    xp       = resultado.get("xp_ganado", 0)
    nivel    = resultado.get("nivel", "")
    badges   = resultado.get("badges_nuevos", [])
    record   = resultado.get("es_record", False)

    if racha >= 30:    celeb = "🏆 INCREÍBLE"
    elif racha >= 14:  celeb = "🔥 IMPARABLE"
    elif racha >= 7:   celeb = "⚡ EN RACHA"
    elif racha >= 3:   celeb = "💪 MUY BIEN"
    else:              celeb = "✅ SESIÓN LISTA"

    msg = f"{celeb}\n\n"
    msg += f"Racha: {p.barra_racha(racha)}"
    if record:
        msg += " — nuevo récord 🏆"
    msg += f"\n+{xp} XP · {nivel}\n"

    if badges:
        msg += "\n" + "  ".join(p.badge_html(k) for k in badges if k in p.BADGES) + "\n"

    return msg
