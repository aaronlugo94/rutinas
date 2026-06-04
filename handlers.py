"""
handlers.py — Bot de Telegram Coach.

Arquitectura de una sola ventana:
- /start instala teclado persistente + abre menú inline
- Todo navega por edit_message_text dentro de esa ventana
- El teclado persistente (abajo) siempre funciona como acceso rápido
- Los mensajes del scheduler son nuevos mensajes (inevitables)

Flujo onboarding separado en dos partes:
  GYM:       objetivo_vida → experiencia → limitacion → ambiente → dias+hora
  NUTRICIÓN: tipo_dieta → restricciones → (plan generado)

Flujo sesión:
  preview → ejercicio 1..N → cardio → feedback → menú
"""
from __future__ import annotations

import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

import catalog as cat
import database as db
import gamification as gam
import renderer as ren

logger = logging.getLogger(__name__)
ADMIN_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "1557254587"))

# ── Objetivos de vida real ────────────────────────────────────────────────────
OBJETIVOS = {
    "bajar_grasa":    ("🔥 Bajar grasa / perder peso",         "peso"),
    "ganar_musculo":  ("💪 Ganar músculo y fuerza",            "mamado"),
    "recomposicion":  ("⚡ Bajar grasa Y ganar músculo",       "general"),
    "gluteo_pierna":  ("🍑 Glúteo y pierna específico",        "gluteo"),
    "salud":          ("🏃 Estar saludable y con energía",     "general"),
    "powerlifting":   ("🏆 Fisicoculturismo / powerlifting",   "mamado"),
}

DIETAS = {
    "omnivoro":  "🍗 Como de todo — sin restricciones",
    "saludable": "🥗 Trato de comer sano",
    "vegano":    "🌱 Vegetariano o vegano",
    "proteina":  "🍖 Alta en proteína / carnívora",
}

RESTRICCIONES = {
    "ninguna":  "✅ Ninguna — como de todo",
    "lacteos":  "🥛 Sin lácteos",
    "gluten":   "🌾 Sin gluten / celíaco",
    "mariscos": "🦐 Sin mariscos / mariscos",
}


# ══════════════════════════════════════════════════════════════════════════════
# UTILS
# ══════════════════════════════════════════════════════════════════════════════

async def check_auth(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    if uid in db.get_allowed_users():
        return True
    await (update.message or update.callback_query.message).reply_text(
        "No tienes acceso. Escribe al administrador."
    )
    return False


def _grupo_del_dia(user_id: int, semana: int, dia: str) -> str:
    rows = db.get_ejercicios_dia(user_id, semana, dia)
    return rows[0].get("grupo", "") if rows else ""


async def _menu_principal_texto(uid: int, nombre: str = "") -> str:
    """Texto del menú principal — estado rápido de los 3 pilares."""
    racha      = gam.get_racha(uid)
    semana, dia = db.get_estado(uid)
    grupo_hoy  = _grupo_del_dia(uid, semana, dia)

    GRUPO_ICON = {"empuje":"💪","tiron":"🏋️","pierna":"🦵",
                  "gluteo":"🍑","core":"🎯","cardio":"🏃"}

    if racha >= 7:   racha_str = f"🔥 <b>{racha} días de racha</b>"
    elif racha >= 3: racha_str = f"🔥 {racha} días de racha"
    elif racha == 1: racha_str = "⚡ Primer día de racha"
    else:            racha_str = ""

    icon    = GRUPO_ICON.get(grupo_hoy, "💪")
    hoy_str = f"{icon} Hoy: {grupo_hoy.upper()}" if grupo_hoy else "🌿 Hoy: Descanso"

    # Peso si hay pesaje reciente
    pesaje = db.get_ultimo_pesaje()
    cuerpo_str = ""
    if pesaje:
        import cuerpo as corp
        score, _ = corp.calcular_score(pesaje)
        cuerpo_str = f"\n⚖️ Score: {score}/100 · {pesaje.get('Grasa_Porcentaje','?')}% grasa"

    n = nombre.split()[0] if nombre else ""
    saludo = f"Hola {n} 👋\n" if n else ""

    sep = "  ·  " if racha_str else ""
    return f"{saludo}{racha_str}{sep}{hoy_str}{cuerpo_str}"


# ══════════════════════════════════════════════════════════════════════════════
# ONBOARDING
# ══════════════════════════════════════════════════════════════════════════════

async def _onboarding_bienvenida(update: Update, nombre: str = "") -> None:
    """Primer mensaje — explicación clara de qué hace el bot."""
    n = nombre.split()[0] if nombre else "ahí"
    texto = (
        f"Hola {n} 👋\n\n"
        "<b>Coach</b> — tu entrenador y nutriólogo personal.\n\n"
        "Tres cosas en un solo lugar:\n"
        "💪 <b>Rutina de gym</b> — plan de 4 semanas que sube los pesos automáticamente\n"
        "⚖️ <b>Composición corporal</b> — análisis diario desde tu báscula\n"
        "🥗 <b>Nutrición</b> — plan semanal calculado con IA según tus datos reales\n\n"
        "Primero dime tu objetivo:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Bajar grasa / perder peso",    callback_data="vida:bajar_grasa")],
        [InlineKeyboardButton("💪 Ganar músculo y fuerza",       callback_data="vida:ganar_musculo")],
        [InlineKeyboardButton("⚡ Bajar grasa Y ganar músculo",  callback_data="vida:recomposicion")],
        [InlineKeyboardButton("🍑 Glúteo y pierna",             callback_data="vida:gluteo_pierna")],
        [InlineKeyboardButton("🏃 Estar saludable y con energía", callback_data="vida:salud")],
        [InlineKeyboardButton("🏆 Nivel competitivo / powerlifting", callback_data="vida:powerlifting")],
    ])
    await update.message.reply_text(texto, reply_markup=kb, parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid    = update.effective_user.id
    nombre = update.effective_user.first_name or ""

    if not db.has_plan(uid):
        await _onboarding_bienvenida(update, nombre)
        return

    texto = await _menu_principal_texto(uid, nombre)
    # Instalar teclado persistente
    await update.message.reply_text(
        texto,
        reply_markup=ren.TECLADO_PERSISTENTE,
        parse_mode="HTML",
    )
    # Abrir menú inline
    await update.message.reply_text(
        "¿Qué hacemos? 👇",
        reply_markup=ren.MENU_PRINCIPAL,
    )


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid   = update.effective_user.id
    token = db.create_login_token(uid)
    url   = f"{ren.WEB_URL}/auth?token={token}"
    await update.message.reply_text(
        "Toca el botón para entrar a la web 👇\n<i>Link válido 5 minutos.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Entrar a Coach", url=url)
        ]])
    )


async def cmd_sethorario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    await update.message.reply_text(
        "⏰ ¿A qué hora quieres tu recordatorio?",
        reply_markup=_kb_horario(),
    )


async def cmd_reset_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid = update.effective_user.id
    await update.message.reply_text(
        "¿Qué quieres cambiar?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💪 Nueva rutina de gym",   callback_data="reset:gym")],
            [InlineKeyboardButton("🥗 Nuevo plan de dieta",   callback_data="reset:dieta")],
            [InlineKeyboardButton("🔄 Los dos",               callback_data="reset:todo")],
            [InlineKeyboardButton("❌ Cancelar",              callback_data="menu:main")],
        ])
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    await update.message.reply_text(
        "❓ <b>Comandos</b>\n\n"
        "<code>/start</code> — Menú principal\n"
        "<code>/login</code> — Entrar a la web app\n"
        "<code>/sethorario</code> — Cambiar hora de recordatorio\n"
        "<code>/reset_plan</code> — Cambiar rutina o dieta",
        parse_mode="HTML",
        reply_markup=ren.AYUDA_KB,
    )


async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Uso: /adduser <user_id>")
        return
    new_uid = int(context.args[0])
    db.add_allowed_user(new_uid)
    await update.message.reply_text(f"✅ Usuario {new_uid} agregado.")


# ══════════════════════════════════════════════════════════════════════════════
# HANDLER DE TEXTO (teclado persistente + pesos durante sesión)
# ══════════════════════════════════════════════════════════════════════════════

async def handler_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid   = update.effective_user.id
    texto = (update.message.text or "").strip()

    # ── Botones del teclado persistente ──────────────────────────────────────
    BOTONES = {
        "💪 Rutina de hoy": "hoy",
        "⚖️ Mi cuerpo":     "cuerpo",
        "🥗 Mi dieta":      "dieta",
        "🆕 Nuevo plan":    "nuevo",
    }
    if texto in BOTONES:
        await _accion_menu(uid, BOTONES[texto], update.message)
        return

    # ── Durante sesión: procesar número como peso ─────────────────────────────
    sesion = db.get_sesion_activa(uid)
    if sesion and sesion.get("fase") == "peso":
        await _procesar_peso_texto(uid, texto, update, context)
        return

    # ── Sesión activa: recordar al usuario ───────────────────────────────────
    if sesion:
        semana, dia = sesion["semana"], sesion["dia"]
        idx = sesion["ej_idx"]
        await update.message.reply_text(
            "Estás en medio de tu sesión 💪",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶ Continuar", callback_data=f"ej_resume:{semana}:{dia}:{idx}")],
                [InlineKeyboardButton("🏠 Menú",     callback_data="menu:main")],
            ])
        )
        return

    # ── Fallback: mostrar menú ───────────────────────────────────────────────
    nombre = update.effective_user.first_name or ""
    texto_menu = await _menu_principal_texto(uid, nombre)
    await update.message.reply_text(
        texto_menu,
        reply_markup=ren.MENU_PRINCIPAL,
        parse_mode="HTML",
    )


async def _accion_menu(uid: int, accion: str, msg) -> None:
    """Ejecutar una acción del menú principal."""
    semana, dia = db.get_estado(uid)

    if accion == "hoy":
        sesion = db.get_sesion_activa(uid)
        if sesion and sesion["semana"] == semana and sesion["dia"] == dia:
            txt, kb = ren.render_ejercicio(uid, semana, dia, sesion["ej_idx"])
        else:
            txt, kb = ren.rutina_preview(uid, semana, dia)
        await msg.reply_text(txt, reply_markup=kb, parse_mode="HTML")

    elif accion == "cuerpo":
        import cuerpo as corp
        resumen = corp.get_resumen_cuerpo()
        if not resumen:
            await msg.reply_text(
                "⚖️ Sin pesajes aún.\n\nPésate en ayunas (6-9am) — el sistema lo detecta automáticamente.",
                reply_markup=ren.BTN_MENU,
            )
        else:
            score    = resumen["score"]; desc = resumen["score_desc"]
            mimo     = resumen.get("estado_mimo") or "—"
            emoji    = {"RECOMPOSICION":"🟣","CUTTING_LIMPIO":"🟢","CATABOLISMO":"🔴","ESTANCAMIENTO":"🟡"}.get(mimo,"⚪")
            kg_f     = resumen.get("kg_a_perder", 0)
            eta      = resumen.get("semanas_eta", 0)
            meta_str = f"\nMeta 22%: faltan <b>{kg_f} kg</b> (~{eta} sem)" if kg_f and kg_f > 0 else ""
            await msg.reply_text(
                f"⚖️ <b>{resumen['fecha']}</b>  Score: {score}/100 — {desc}\n"
                f"{emoji} {mimo.replace('_',' ')}\n\n"
                f"Peso: {resumen['peso_kg']} kg  |  Grasa: {resumen['grasa_pct']}%\n"
                f"Músculo: {resumen['musculo_pct']}%  |  BMR: {resumen['bmr']} kcal"
                f"{meta_str}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🌐 Ver tendencia →", url=f"{ren.WEB_URL}/cuerpo")
                ]])
            )

    elif accion == "dieta":
        import nutricion as nut
        macros = nut.get_macros_hoy()
        plan   = nut.get_plan_actual()
        if not macros:
            await msg.reply_text(
                "🥗 Sin datos aún.\n\nPésate en ayunas para que calcule tus macros.",
                reply_markup=ren.BTN_MENU,
            )
        else:
            mimo_str = ""
            if plan and plan.get("estado_mimo"):
                em = {"RECOMPOSICION":"🟣","CUTTING_LIMPIO":"🟢","CATABOLISMO":"🔴","ESTANCAMIENTO":"🟡"}.get(plan["estado_mimo"],"⚪")
                mimo_str = f"{em} {plan['estado_mimo'].replace('_',' ')}\n\n"
            await msg.reply_text(
                f"🥗 <b>Hoy</b>\n{mimo_str}"
                f"🔥 {macros['calorias']} kcal\n"
                f"🥩 {macros['proteina']}g proteína  "
                f"🍞 {macros['carbs']}g carbs  "
                f"🥑 {macros['grasas']}g grasas",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🌐 Ver plan semanal →", url=f"{ren.WEB_URL}/nutricion")
                ]])
            )

    elif accion == "nuevo":
        await msg.reply_text(
            "¿Qué quieres cambiar?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💪 Nueva rutina de gym",   callback_data="reset:gym")],
                [InlineKeyboardButton("🥗 Nuevo plan de dieta",   callback_data="reset:dieta")],
                [InlineKeyboardButton("🔄 Los dos",               callback_data="reset:todo")],
                [InlineKeyboardButton("❌ Cancelar",              callback_data="menu:main")],
            ])
        )


async def _procesar_peso_texto(uid: int, texto: str, update, context) -> None:
    """Procesa texto enviado como peso durante sesión activa."""
    try:
        peso = float(texto.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Solo escribe el número. Ej: 135  (0 para saltar)")
        return

    sesion = db.get_sesion_activa(uid)
    if not sesion:
        return

    semana  = sesion["semana"]
    dia     = sesion["dia"]
    ej_idx  = sesion["ej_idx"]
    rows    = [r for r in db.get_ejercicios_dia(uid, semana, dia) if not r.get("es_cardio")]

    if ej_idx < len(rows):
        ej = rows[ej_idx]
        if peso > 0:
            db.save_peso(uid, ej["ejercicio_id"], semana, dia, peso,
                         ej.get("series"), ej.get("reps"))

    # Avanzar al siguiente ejercicio
    siguiente = ej_idx + 1
    db.save_sesion_activa(uid, semana, dia, siguiente, "ejercicio")
    txt, kb = ren.render_ejercicio(uid, semana, dia, siguiente)
    await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query  = update.callback_query
    data   = query.data or ""
    uid    = query.from_user.id
    nombre = query.from_user.first_name or ""

    if not (uid in db.get_allowed_users()):
        await query.answer("Sin acceso.")
        return

    try:
        await query.answer()
    except Exception:
        pass

    try:
        semana, dia = db.get_estado(uid)
    except Exception:
        semana, dia = 1, "lunes"

    try:
        await _callback_handler(update, context, query, data, uid, nombre, semana, dia)
    except Exception as e:
        err_str = str(e)
        # Ignorar error inofensivo de Telegram — mismo contenido
        if "Message is not modified" in err_str:
            return
        logger.error("callback_router error [%s]: %s", data, e, exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ Algo salió mal. Escribe /start para reintentar.",
            )
        except Exception:
            pass


async def _callback_handler(update, context, query, data, uid, nombre, semana, dia):
    """Maneja todos los callbacks. Separado para capturar errores correctamente."""

    # ── MENÚ PRINCIPAL ────────────────────────────────────────────────────────
    if data.startswith("menu:"):
        accion = data.split(":")[1]
        if accion == "main":
            texto = await _menu_principal_texto(uid, nombre)
            await query.edit_message_text(
                texto, reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML"
            )
        elif accion == "hoy":
            sesion = db.get_sesion_activa(uid)
            if sesion and sesion["semana"] == semana and sesion["dia"] == dia:
                txt, kb = ren.render_ejercicio(uid, semana, dia, sesion["ej_idx"])
            else:
                txt, kb = ren.rutina_preview(uid, semana, dia)
            await query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
        elif accion == "cuerpo":
            import cuerpo as corp
            resumen = corp.get_resumen_cuerpo()
            if not resumen:
                await query.edit_message_text(
                    "⚖️ Sin pesajes aún.\nPésate en ayunas (6-9am) — se detecta automáticamente.",
                    reply_markup=ren.BTN_MENU,
                )
            else:
                score    = resumen["score"]; desc = resumen["score_desc"]
                mimo     = resumen.get("estado_mimo") or "—"
                emoji    = {"RECOMPOSICION":"🟣","CUTTING_LIMPIO":"🟢","CATABOLISMO":"🔴","ESTANCAMIENTO":"🟡"}.get(mimo,"⚪")
                kg_f     = resumen.get("kg_a_perder", 0)
                eta      = resumen.get("semanas_eta", 0)
                meta_str = f"\n\nMeta 22%: faltan <b>{kg_f} kg</b> (~{eta} sem)" if kg_f and kg_f > 0 else ""
                await query.edit_message_text(
                    f"⚖️ <b>{resumen['fecha']}</b>  Score: {score}/100 — {desc}\n"
                    f"{emoji} {mimo.replace('_',' ')}\n\n"
                    f"Peso: {resumen['peso_kg']} kg  |  Grasa: {resumen['grasa_pct']}%\n"
                    f"Músculo: {resumen['musculo_pct']}%  |  BMR: {resumen['bmr']} kcal"
                    f"{meta_str}",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🌐 Ver tendencia →", url=f"{ren.WEB_URL}/cuerpo")],
                        [InlineKeyboardButton("🏠 Menú",            callback_data="menu:main")],
                    ])
                )
        elif accion == "dieta":
            import nutricion as nut
            macros = nut.get_macros_hoy(user_id=uid)
            if not macros:
                await query.edit_message_text(
                    "🥗 Sin datos aún — pésate para calcular tus macros.",
                    reply_markup=ren.BTN_MENU,
                )
            else:
                nota = f"\n<i>{macros['nota']}</i>" if macros.get("nota") else ""
                tdee = f"\nTDEE: {macros.get('tdee', '')} kcal/día" if macros.get("tdee") else ""
                await query.edit_message_text(
                    f"🥗 <b>Macros de hoy</b>\n"
                    f"🔥 {macros['calorias']} kcal{tdee}\n"
                    f"🥩 {macros['proteina']}g prot  🍞 {macros['carbs']}g carbs  🥑 {macros['grasas']}g grasas"
                    f"{nota}",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🌐 Ver plan completo →", url=f"{ren.WEB_URL}/nutricion")],
                        [InlineKeyboardButton("🔄 Regenerar dieta",     callback_data="dieta:regenerar")],
                        [InlineKeyboardButton("🏠 Menú",                callback_data="menu:main")],
                    ])
                )
        elif accion == "nuevo":
            await query.edit_message_text(
                "¿Qué quieres cambiar?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💪 Nueva rutina de gym",   callback_data="reset:gym")],
                    [InlineKeyboardButton("🥗 Nuevo plan de dieta",   callback_data="reset:dieta")],
                    [InlineKeyboardButton("🔄 Los dos",               callback_data="reset:todo")],
                    [InlineKeyboardButton("❌ Cancelar",              callback_data="menu:main")],
                ])
            )
        return

    # ── RESET ─────────────────────────────────────────────────────────────────
    if data.startswith("reset:"):
        tipo = data.split(":")[1]
        if tipo in ("gym", "todo"):
            db.clear_plan(uid)
            await query.edit_message_text(
                "💪 <b>¿Cuál es tu objetivo?</b>\n\n"
                "Sé honesto — el plan se ajusta completamente a esto:",
                reply_markup=_kb_objetivos(),
                parse_mode="HTML",
            )
        elif tipo == "dieta":
            await query.edit_message_text(
                "🥗 <b>¿Cómo describes tu alimentación?</b>",
                reply_markup=_kb_dieta(),
                parse_mode="HTML",
            )
        return

    # ── ONBOARDING GYM ────────────────────────────────────────────────────────
    if data.startswith("vida:"):
        objetivo_vida = data.split(":")[1]
        _, objetivo_gym = OBJETIVOS.get(objetivo_vida, ("", "general"))
        db.upsert_perfil(uid, objetivo=objetivo_gym, objetivo_vida=objetivo_vida)
        desc = OBJETIVOS.get(objetivo_vida, ("",))[0]
        await query.edit_message_text(
            f"<b>Objetivo: {desc} ✅</b>\n\n"
            f"<b>¿Cuánto tiempo llevas entrenando con pesas?</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌱 Soy nuevo — menos de 1 año",      callback_data="niv:principiante")],
                [InlineKeyboardButton("💪 1 a 3 años entrenando",           callback_data="niv:intermedio")],
                [InlineKeyboardButton("🔥 Más de 3 años — nivel avanzado",  callback_data="niv:avanzado")],
                [InlineKeyboardButton("← Atrás",                             callback_data="vida:back")],
            ]),
            parse_mode="HTML",
        )
        return

    if data == "vida:back":
        await query.edit_message_text(
            "💪 <b>¿Cuál es tu objetivo?</b>",
            reply_markup=_kb_objetivos(),
            parse_mode="HTML",
        )
        return

    if data.startswith("niv:"):
        nivel = data.split(":")[1]
        if nivel == "back":
            perfil = db.get_perfil(uid)
            desc   = OBJETIVOS.get(perfil.get("objetivo_vida",""), ("tu objetivo",))[0]
            await query.edit_message_text(
                f"<b>Objetivo: {desc} ✅</b>\n\n<b>¿Cuánto tiempo llevas entrenando?</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌱 Menos de 1 año",    callback_data="niv:principiante")],
                    [InlineKeyboardButton("💪 1 a 3 años",        callback_data="niv:intermedio")],
                    [InlineKeyboardButton("🔥 Más de 3 años",     callback_data="niv:avanzado")],
                    [InlineKeyboardButton("← Atrás",              callback_data="vida:back")],
                ]),
                parse_mode="HTML",
            )
            return
        db.upsert_perfil(uid, nivel=nivel)
        await query.edit_message_text(
            "<b>¿Tienes alguna lesión o limitación física?</b>\n\n"
            "<i>El plan evita ejercicios que puedan empeorarla.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Ninguna — estoy bien",                    callback_data="lim:ninguna")],
                [InlineKeyboardButton("🦵 Rodilla — evitar sentadilla profunda",    callback_data="lim:rodilla")],
                [InlineKeyboardButton("🔙 Espalda baja — evitar peso muerto",       callback_data="lim:espalda")],
                [InlineKeyboardButton("💪 Hombro — evitar press militar",           callback_data="lim:hombro")],
                [InlineKeyboardButton("← Atrás",                                    callback_data="niv:back")],
            ]),
            parse_mode="HTML",
        )
        return

    if data.startswith("lim:"):
        lim = data.split(":")[1]
        db.upsert_perfil(uid, limitaciones=lim)
        await query.edit_message_text(
            "<b>¿Dónde entrenas?</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏋️ Gimnasio — máquinas y barras",     callback_data="amb:gym")],
                [InlineKeyboardButton("🏠 Casa — peso corporal",              callback_data="amb:home")],
                [InlineKeyboardButton("🦺 Casa con banda elástica",           callback_data="amb:band")],
                [InlineKeyboardButton("← Atrás",                              callback_data="niv:back")],
            ]),
            parse_mode="HTML",
        )
        return

    if data.startswith("amb:"):
        ambiente = data.split(":")[1]
        if ambiente == "back":
            await query.edit_message_text(
                "<b>¿Tienes alguna lesión?</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Ninguna",      callback_data="lim:ninguna")],
                    [InlineKeyboardButton("🦵 Rodilla",      callback_data="lim:rodilla")],
                    [InlineKeyboardButton("🔙 Espalda baja", callback_data="lim:espalda")],
                    [InlineKeyboardButton("💪 Hombro",       callback_data="lim:hombro")],
                ]),
                parse_mode="HTML",
            )
            return
        db.upsert_perfil(uid, ambiente_preferido=ambiente)
        await query.edit_message_text(
            "<b>¿Cuántos días a la semana puedes entrenar?</b>\n\n"
            "<i>4 días es el punto óptimo para la mayoría — suficiente frecuencia sin sobreentrenarte.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("3 días", callback_data="dias:3"),
                 InlineKeyboardButton("4 días", callback_data="dias:4")],
                [InlineKeyboardButton("5 días", callback_data="dias:5"),
                 InlineKeyboardButton("6 días", callback_data="dias:6")],
                [InlineKeyboardButton("← Atrás", callback_data="amb:back")],
            ]),
            parse_mode="HTML",
        )
        return

    if data.startswith("dias:"):
        dias_s = data.split(":")[1]
        if dias_s == "back":
            await query.edit_message_text("<b>¿Dónde entrenas?</b>", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏋️ Gimnasio",        callback_data="amb:gym")],
                [InlineKeyboardButton("🏠 Casa",             callback_data="amb:home")],
                [InlineKeyboardButton("🦺 Banda elástica",   callback_data="amb:band")],
            ]), parse_mode="HTML")
            return
        db.upsert_perfil(uid, dias=int(dias_s))
        await query.edit_message_text(
            f"<b>{dias_s} días por semana ✅</b>\n\n"
            "<b>¿A qué hora quieres tu recordatorio diario?</b>",
            reply_markup=_kb_horario(back="dias:back"),
            parse_mode="HTML",
        )
        return

    if data.startswith("rec:"):
        hora_val = data.split(":")[1]
        if hora_val == "none":
            hora = None
        elif hora_val == "back":
            await query.edit_message_text("<b>¿Cuántos días?</b>", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("3 días", callback_data="dias:3"),
                 InlineKeyboardButton("4 días", callback_data="dias:4")],
                [InlineKeyboardButton("5 días", callback_data="dias:5"),
                 InlineKeyboardButton("6 días", callback_data="dias:6")],
            ]), parse_mode="HTML")
            return
        else:
            hora = f"{hora_val[:2]}:{hora_val[2:]}" if ":" not in hora_val else hora_val
        db.upsert_perfil(uid, hora_recordatorio=hora)

        # Paso siguiente: datos físicos para BMR real
        await query.edit_message_text(
            "✅ ¡Casi listo! Solo 3 datos más.\n\n"
            "<b>¿Cuántos años tienes?</b>\n\n"
            "Lo necesito para calcular tu metabolismo basal correctamente "
            "(fórmula Mifflin-St Jeor — la más precisa según la ciencia):",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("18-24 años", callback_data="edad:21"),
                 InlineKeyboardButton("25-34 años", callback_data="edad:30")],
                [InlineKeyboardButton("35-44 años", callback_data="edad:40"),
                 InlineKeyboardButton("45-54 años", callback_data="edad:50")],
                [InlineKeyboardButton("55+ años",   callback_data="edad:60")],
                [InlineKeyboardButton("← Atrás",    callback_data="rec:back")],
            ]),
            parse_mode="HTML",
        )
        return

    # ── ONBOARDING NUTRICIÓN ──────────────────────────────────────────────────
    if data.startswith("edad:"):
        edad = int(data.split(":")[1])
        db.upsert_perfil(uid, edad=edad)
        await query.edit_message_text(
            f"<b>Edad: {edad} años ✅</b>\n\n"
            "<b>¿Cuál es tu sexo biológico?</b>\n\n"
            "<i>Afecta directamente el cálculo de tu metabolismo y composición corporal.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👨 Hombre", callback_data="sexo:hombre")],
                [InlineKeyboardButton("👩 Mujer",  callback_data="sexo:mujer")],
                [InlineKeyboardButton("← Atrás",   callback_data="edad:back")],
            ]),
            parse_mode="HTML",
        )
        return

    if data == "edad:back":
        await query.edit_message_text(
            "⏰ ¿A qué hora quieres tu recordatorio?",
            reply_markup=_kb_horario(),
            parse_mode="HTML",
        )
        return

    if data.startswith("sexo:"):
        sexo = data.split(":")[1]
        db.upsert_perfil(uid, sexo=sexo)
        await query.edit_message_text(
            f"<b>Sexo: {'Hombre' if sexo=='hombre' else 'Mujer'} ✅</b>\n\n"
            "<b>¿Cuánto pesas aproximadamente? (kg)</b>\n\n"
            "<i>Si no sabes exactamente, pon un estimado — después la báscula lo corrige.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("50-60 kg", callback_data="peso_est:55"),
                 InlineKeyboardButton("60-70 kg", callback_data="peso_est:65")],
                [InlineKeyboardButton("70-80 kg", callback_data="peso_est:75"),
                 InlineKeyboardButton("80-90 kg", callback_data="peso_est:85")],
                [InlineKeyboardButton("90-100 kg", callback_data="peso_est:95"),
                 InlineKeyboardButton("100-115 kg", callback_data="peso_est:107")],
                [InlineKeyboardButton("115-130 kg", callback_data="peso_est:122"),
                 InlineKeyboardButton("130+ kg",    callback_data="peso_est:140")],
                [InlineKeyboardButton("← Atrás",   callback_data="sexo:back")],
            ]),
            parse_mode="HTML",
        )
        return

    if data == "sexo:back":
        perfil = db.get_perfil(uid)
        edad   = perfil.get("edad", 30)
        await query.edit_message_text(
            f"<b>Edad: {edad} años ✅</b>\n\n<b>¿Cuál es tu sexo biológico?</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👨 Hombre", callback_data="sexo:hombre")],
                [InlineKeyboardButton("👩 Mujer",  callback_data="sexo:mujer")],
            ]),
            parse_mode="HTML",
        )
        return

    if data.startswith("peso_est:"):
        peso_est = float(data.split(":")[1])
        db.upsert_perfil(uid, peso_kg_estimado=peso_est)

        # ── Calcular BMR real con Mifflin-St Jeor ────────────────────────────
        perfil = db.get_perfil(uid)
        edad   = perfil.get("edad", 30)
        sexo   = perfil.get("sexo", "hombre")
        # Altura estimada por sexo si no tenemos dato real
        altura_est = 175 if sexo == "hombre" else 163

        # Mifflin-St Jeor
        if sexo == "hombre":
            bmr_est = round(10 * peso_est + 6.25 * altura_est - 5 * edad + 5)
        else:
            bmr_est = round(10 * peso_est + 6.25 * altura_est - 5 * edad - 161)
        db.upsert_perfil(uid, bmr_estimado=bmr_est)

        # ── Nivel de actividad ────────────────────────────────────────────────
        await query.edit_message_text(
            f"<b>Peso: ~{peso_est}kg ✅</b>\n"
            f"<b>Tu BMR estimado: {bmr_est} kcal/día</b>\n\n"
            "<b>¿Qué tan activo eres fuera del gym?</b>\n\n"
            "🪑 <b>Sedentario</b> — trabajo de oficina, poco movimiento\n"
            "🚶 <b>Moderado</b> — caminas 30+ min/día o trabajo de pie\n"
            "🏃 <b>Activo</b> — trabajo físico, 10k+ pasos diarios",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🪑 Sedentario — oficina",     callback_data="act:sedentario")],
                [InlineKeyboardButton("🚶 Moderado — algo de movimiento", callback_data="act:moderado")],
                [InlineKeyboardButton("🏃 Activo — trabajo físico",  callback_data="act:activo")],
                [InlineKeyboardButton("← Atrás",                     callback_data="peso_est:back")],
            ]),
            parse_mode="HTML",
        )
        return

    if data == "peso_est:back":
        await query.edit_message_text(
            "<b>¿Cuál es tu sexo biológico?</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👨 Hombre", callback_data="sexo:hombre")],
                [InlineKeyboardButton("👩 Mujer",  callback_data="sexo:mujer")],
            ]),
            parse_mode="HTML",
        )
        return

    if data.startswith("act:"):
        actividad = data.split(":")[1]
        db.upsert_perfil(uid, actividad_nivel=actividad)

        # TDEE = BMR × factor actividad
        factor = {"sedentario": 1.2, "moderado": 1.375, "activo": 1.55}.get(actividad, 1.2)
        perfil = db.get_perfil(uid)
        bmr_est = perfil.get("bmr_estimado", 2000)
        tdee = round(bmr_est * factor)
        db.upsert_perfil(uid, tdee_estimado=tdee)

        await query.edit_message_text(
            f"<b>Gasto calórico total estimado: {tdee} kcal/día</b>\n\n"
            "Ahora <b>tu alimentación</b>:\n\n"
            "¿Cómo describes tu dieta normalmente?",
            reply_markup=_kb_dieta(back="act:back"),
            parse_mode="HTML",
        )
        return

    if data == "act:back":
        perfil   = db.get_perfil(uid)
        peso_est = perfil.get("peso_kg_estimado", 90)
        await query.edit_message_text(
            f"<b>Peso: ~{peso_est}kg ✅</b>\n\n<b>¿Qué tan activo eres fuera del gym?</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🪑 Sedentario",  callback_data="act:sedentario")],
                [InlineKeyboardButton("🚶 Moderado",    callback_data="act:moderado")],
                [InlineKeyboardButton("🏃 Activo",      callback_data="act:activo")],
            ]),
            parse_mode="HTML",
        )
        return

    if data.startswith("nut:"):
        tipo = data.split(":")[1]
        db.upsert_perfil(uid, tipo_dieta=tipo)
        desc = DIETAS.get(tipo, tipo)
        await query.edit_message_text(
            f"<b>Dieta: {desc} ✅</b>\n\n"
            "<b>¿Hay algo que no puedas comer o quieras evitar?</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Ninguna — como de todo",   callback_data="alerg:ninguna")],
                [InlineKeyboardButton("🥛 Sin lácteos",              callback_data="alerg:lacteos")],
                [InlineKeyboardButton("🌾 Sin gluten / celíaco",     callback_data="alerg:gluten")],
                [InlineKeyboardButton("🦐 Sin mariscos",             callback_data="alerg:mariscos")],
                [InlineKeyboardButton("← Atrás",                     callback_data="nut:back")],
            ]),
            parse_mode="HTML",
        )
        return

    if data == "nut:back":
        await query.edit_message_text(
            "¿Cómo describes tu dieta?",
            reply_markup=_kb_dieta(),
            parse_mode="HTML",
        )
        return

    if data.startswith("alerg:"):
        alerg = data.split(":")[1]
        db.upsert_perfil(uid, alergias=alerg)

        # ── Generar plan de gym ───────────────────────────────────────────────
        await query.edit_message_text(
            "⚙️ <b>Creando tu plan...</b>\n\n<i>Analizando tu perfil. Tarda unos segundos.</i>",
            parse_mode="HTML",
        )
        try:
            perfil = db.get_perfil(uid)
            import planner as pl
            swaps  = db.get_swaps(uid)
            plan   = pl.generar_plan(
                nivel      = perfil.get("nivel", "intermedio"),
                objetivo   = perfil.get("objetivo", "general"),
                dias       = int(perfil.get("dias") or 4),
                ambiente   = perfil.get("ambiente_preferido", "gym"),
                limitacion = perfil.get("limitaciones", "ninguna"),
            )
            by_id  = cat.BY_ID
            n_ej   = db.insert_plan(uid, plan, swaps, by_id)
            primera_sem = plan[0]["semana"]
            primer_dia  = plan[0]["dias"][0]["dia"]
            db.upsert_estado(uid, primera_sem, primer_dia)

            # Recomendación calórica basada en objetivo
            obj      = perfil.get("objetivo", "general")
            peso_est = float(perfil.get("peso_kg_estimado") or 90)
            tdee_est = int(perfil.get("tdee_estimado") or round(peso_est * 30))
            rec = {
                "peso":    f"Para bajar grasa: ~{round(tdee_est*0.82)} kcal/día · {round(peso_est*2.2)}g proteína",
                "mamado":  f"Para ganar músculo: ~{round(tdee_est*1.10)} kcal/día · {round(peso_est*2.2)}g proteína",
                "general": f"Para recomposición: ~{round(tdee_est*0.90)} kcal/día · {round(peso_est*2.2)}g proteína",
                "gluteo":  f"Prioriza proteína: {round(peso_est*2.2)}g/día · ~{round(tdee_est*0.90)} kcal",
            }.get(obj, f"~{tdee_est} kcal/día · {round(peso_est*2.2)}g proteína")

            txt_rutina, kb_rutina = ren.rutina_preview(uid, primera_sem, primer_dia)
            await query.edit_message_text(
                f"✅ <b>Plan listo</b> — {n_ej} ejercicios · 4 semanas\n\n"
                f"💡 {rec}\n"
                f"<i>El plan de nutrición detallado llega el próximo domingo con tus datos de la báscula.</i>\n\n"
                f"{txt_rutina}",
                reply_markup=kb_rutina,
                parse_mode="HTML",
            )
            # Instalar teclado persistente
            await context.bot.send_message(
                chat_id      = query.message.chat_id,
                text         = "Los botones de abajo siempre están disponibles 👇",
                reply_markup = ren.TECLADO_PERSISTENTE,
            )
        except Exception as e:
            logger.error("Error generando plan: %s", e, exc_info=True)
            try:
                await query.edit_message_text(
                    f"❌ Error: {str(e)[:200]}\n\nEscribe /start para reintentar.",
                )
            except Exception:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"❌ Error: {str(e)[:200]}\n\nEscribe /start.",
                )
        return

    # ── DIETA: REGENERAR ─────────────────────────────────────────────────────
    if data == "dieta:regenerar":
        await query.edit_message_text(
            "🥗 <b>Regenerar plan de dieta</b>\n\n"
            "¿Cambió algo en tu alimentación?",
            reply_markup=_kb_dieta(back="menu:dieta"),
            parse_mode="HTML",
        )
        return

    # ── EJERCICIO POR EJERCICIO ───────────────────────────────────────────────
    if data.startswith("ej_start:"):
        _, sem_s, dia_s = data.split(":")
        sem = int(sem_s)
        db.save_sesion_activa(uid, sem, dia_s, 0, "ejercicio")
        txt, kb = ren.render_ejercicio(uid, sem, dia_s, 0)
        await query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
        return

    if data.startswith("ej_resume:"):
        _, sem_s, dia_s, idx_s = data.split(":")
        txt, kb = ren.render_ejercicio(uid, int(sem_s), dia_s, int(idx_s))
        await query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
        return

    if data.startswith("ej_hecho:"):
        _, sem_s, dia_s, idx_s = data.split(":")
        sem = int(sem_s); idx = int(idx_s)
        siguiente = idx + 1
        db.save_sesion_activa(uid, sem, dia_s, siguiente, "ejercicio")
        txt, kb = ren.render_ejercicio(uid, sem, dia_s, siguiente)
        await query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
        return

    if data.startswith("ej_done:"):
        _, sem_s, dia_s = data.split(":")
        sem = int(sem_s)
        db.clear_sesion_activa(uid)
        with db.get_db() as conn:
            conn.execute(
                "UPDATE rutinas SET completado=1 WHERE user_id=? AND semana=? AND dia=?",
                (uid, sem, dia_s),
            )
        resultado = gam.procesar_fin_sesion(
            user_id=uid, semana=sem, dia=dia_s,
            progresion="si", grupo=_grupo_del_dia(uid, sem, dia_s),
        )
        msg_wow = ren.msg_fin_sesion(resultado)
        kb_feedback = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Intenso — sin reserva",    callback_data=f"sesion:{sem}:{dia_s}:0:5")],
            [InlineKeyboardButton("💪 Bien — quedaban 1-2 reps", callback_data=f"sesion:{sem}:{dia_s}:2:3")],
            [InlineKeyboardButton("😌 Fácil — podía más",        callback_data=f"sesion:{sem}:{dia_s}:3:2")],
            [InlineKeyboardButton("😓 Muy cansado hoy",          callback_data=f"sesion:{sem}:{dia_s}:2:4")],
        ])
        try:
            await query.edit_message_text(
                msg_wow + "\n\n<b>¿Cómo estuvo la sesión?</b>",
                reply_markup=kb_feedback, parse_mode="HTML",
            )
        except Exception:
            await context.bot.send_message(
                chat_id      = query.message.chat_id,
                text         = msg_wow + "\n\n<b>¿Cómo estuvo la sesión?</b>",
                reply_markup = kb_feedback, parse_mode = "HTML",
            )
        return

    if data.startswith("sesion:"):
        parts = data.split(":")
        sem, dia_s, rir, fatiga = int(parts[1]), parts[2], int(parts[3]), int(parts[4])
        db.save_progreso_sesion(uid, sem, dia_s, rir=rir, fatiga=fatiga)
        nueva_sem, nuevo_dia = db.avanzar_dia(uid, sem, dia_s)
        db.upsert_estado(uid, nueva_sem, nuevo_dia)
        racha = gam.get_racha(uid)
        racha_str = f"🔥 {racha} días de racha\n\n" if racha >= 3 else ""

        # Preguntar sueño — dato clave para el análisis de Gemini
        try:
            await query.edit_message_text(
                f"💾 Sesión guardada. {racha_str}"
                f"Una última pregunta — ¿cuántas horas dormiste anoche?\n\n"
                f"<i>El sueño es donde crece el músculo. Gemini lo considera en tu análisis.</i>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("😴 Menos de 6h", callback_data=f"sueño:{sem}:{dia_s}:5.5"),
                     InlineKeyboardButton("😊 6-7h",        callback_data=f"sueño:{sem}:{dia_s}:6.5")],
                    [InlineKeyboardButton("✅ 7-8h",         callback_data=f"sueño:{sem}:{dia_s}:7.5"),
                     InlineKeyboardButton("🌟 8h+",          callback_data=f"sueño:{sem}:{dia_s}:8.5")],
                    [InlineKeyboardButton("Saltar →",        callback_data=f"sueño:{sem}:{dia_s}:0")],
                ]),
                parse_mode="HTML",
            )
        except Exception:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"💾 Sesión guardada.{racha_str}\n¿Cuántas horas dormiste?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("< 6h",  callback_data=f"sueño:{sem}:{dia_s}:5.5"),
                     InlineKeyboardButton("7-8h",  callback_data=f"sueño:{sem}:{dia_s}:7.5")],
                    [InlineKeyboardButton("8h+",   callback_data=f"sueño:{sem}:{dia_s}:8.5"),
                     InlineKeyboardButton("Saltar", callback_data=f"sueño:{sem}:{dia_s}:0")],
                ])
            )
        return

    if data.startswith("sueño:"):
        _, sem_s, dia_s, horas_s = data.split(":")
        horas = float(horas_s)
        if horas > 0:
            db.upsert_perfil(uid, sueño_horas=horas)
            aviso = ""
            if horas < 6:
                aviso = "\n\n⚠️ <b>Menos de 6h es crítico para la recuperación.</b> El cortisol sube, el músculo no crece bien. Prioriza dormir hoy."
            elif horas < 7:
                aviso = "\n\n💤 6-7h es el mínimo. Trata de llegar a 7-8h para optimizar recuperación."
        else:
            aviso = ""

        racha = gam.get_racha(uid)
        try:
            await query.edit_message_text(
                f"{'⚠️ Poco sueño registrado.' if horas and horas < 7 else '✅ Registrado.'}"
                f"{aviso}\n\n"
                f"{'🔥 ' + str(racha) + ' días de racha — ' if racha >= 3 else ''}"
                f"El análisis llega esta noche 🧠",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💪 Ver siguiente sesión", callback_data="menu:hoy")],
                    [InlineKeyboardButton("🌐 Ver progreso →",       url=ren.WEB_URL)],
                    [InlineKeyboardButton("🏠 Menú",                 callback_data="menu:main")],
                ]),
                parse_mode="HTML",
            )
        except Exception:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="✅ Todo guardado.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💪 Siguiente sesión", callback_data="menu:hoy")],
                    [InlineKeyboardButton("🏠 Menú",            callback_data="menu:main")],
                ])
            )
        return

    # ── SWAP ─────────────────────────────────────────────────────────────────
    if data.startswith("swp_ask:"):
        parts   = data.split(":")
        eid, sem_s, dia_s = parts[1], parts[2], parts[3]
        pagina  = int(parts[4]) if len(parts) > 4 else 0
        perfil  = db.get_perfil(uid)
        ej_row  = db.fetchone("SELECT grupo, rol FROM rutinas WHERE user_id=? AND ejercicio_id=?", (uid, eid))
        if not ej_row:
            return
        alts = [
            {"id": e.id, "nombre": e.nombre, "emg_score": e.emg_score}
            for e in cat.EJERCICIOS
            if e.grupo == ej_row["grupo"] and e.rol == ej_row["rol"] and e.id != eid
            and perfil.get("ambiente_preferido", "gym") in (e.ambientes or ["gym"])
        ]
        txt, kb = ren.render_swap(eid, int(sem_s), dia_s, alts, pagina)
        await query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
        return

    if data.startswith("swp_do:"):
        _, id_orig, id_nuevo, sem_s, dia_s = data.split(":")
        sem = int(sem_s)
        ej_new = cat.BY_ID.get(id_nuevo)
        ej_orig = cat.BY_ID.get(id_orig)
        if ej_new and ej_orig:
            with db.get_db() as conn:
                conn.execute(
                    "UPDATE rutinas SET ejercicio_id=?, ejercicio=?, patron=? WHERE user_id=? AND ejercicio_id=?",
                    (id_nuevo, ej_new.nombre, ej_new.patron, uid, id_orig),
                )
            db.save_swap(uid, id_orig, id_nuevo, ej_orig.grupo, ej_orig.rol)
            sesion = db.get_sesion_activa(uid)
            if sesion and sesion["semana"] == sem and sesion["dia"] == dia_s:
                txt, kb = ren.render_ejercicio(uid, sem, dia_s, sesion["ej_idx"])
            else:
                txt, kb = ren.rutina_preview(uid, sem, dia_s)
            await query.edit_message_text(
                f"✅ <b>{ej_new.nombre}</b> reemplaza a {ej_orig.nombre}\n\n{txt}",
                reply_markup=kb, parse_mode="HTML",
            )
        return

    if data.startswith("swp_cancel:"):
        _, sem_s, dia_s = data.split(":")
        sesion = db.get_sesion_activa(uid)
        if sesion:
            txt, kb = ren.render_ejercicio(uid, int(sem_s), dia_s, sesion["ej_idx"])
        else:
            txt, kb = ren.rutina_preview(uid, int(sem_s), dia_s)
        await query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
        return

    # ── SKIP DAY ─────────────────────────────────────────────────────────────
    if data.startswith("skip_day:"):
        _, sem_s, dia_s = data.split(":")
        sem = int(sem_s)
        db.clear_sesion_activa(uid)
        nueva_sem, nuevo_dia = db.avanzar_dia(uid, sem, dia_s)
        db.upsert_estado(uid, nueva_sem, nuevo_dia)
        texto_menu = await _menu_principal_texto(uid, nombre)
        await query.edit_message_text(
            f"Día saltado 👍\n\n{texto_menu}",
            reply_markup=ren.MENU_PRINCIPAL,
            parse_mode="HTML",
        )
        return

    # ── AYUDA ─────────────────────────────────────────────────────────────────
    if data == "ver_ayuda":
        await query.edit_message_text(
            "❓ <b>¿Qué necesitas?</b>\n\n"
            "Comandos:\n"
            "<code>/start</code> — Menú principal\n"
            "<code>/login</code> — Entrar a la web\n"
            "<code>/sethorario</code> — Cambiar recordatorio\n"
            "<code>/reset_plan</code> — Cambiar rutina o dieta",
            parse_mode="HTML",
            reply_markup=ren.AYUDA_KB,
        )
        return

    if data == "ayuda:horario":
        await query.edit_message_text(
            "⏰ ¿A qué hora quieres el recordatorio?",
            reply_markup=_kb_horario(back="ver_ayuda"),
        )
        return

    if data == "ayuda:login":
        token = db.create_login_token(uid)
        url   = f"{ren.WEB_URL}/auth?token={token}"
        await query.edit_message_text(
            "Toca el botón para entrar a la web 👇\n<i>Link válido 5 minutos.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Entrar a Coach", url=url)],
                [InlineKeyboardButton("← Atrás",           callback_data="ver_ayuda")],
            ])
        )
        return

    if data == "ayuda:pausa":
        await query.edit_message_text(
            "✈️ <b>Modo viaje / Pausa</b>\n\n"
            "¿Cuántos días pausar las notificaciones?\n"
            "<i>Tu plan y tus pesos te esperan cuando vuelvas.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("3 días",  callback_data="pausa:3"),
                 InlineKeyboardButton("7 días",  callback_data="pausa:7")],
                [InlineKeyboardButton("14 días", callback_data="pausa:14"),
                 InlineKeyboardButton("30 días", callback_data="pausa:30")],
                [InlineKeyboardButton("← Atrás", callback_data="ver_ayuda")],
            ])
        )
        return

    if data.startswith("pausa:"):
        dias = int(data.split(":")[1])
        from datetime import datetime, timedelta
        fecha_ret = (datetime.now() + timedelta(days=dias)).strftime("%d/%m/%Y")
        db.execute("UPDATE usuarios SET hora_recordatorio=? WHERE user_id=?",
                   (f"PAUSA:{fecha_ret}", uid))
        await query.edit_message_text(
            f"✈️ <b>Pausa — {dias} días</b>\n\n"
            f"Sin notificaciones hasta el <b>{fecha_ret}</b>.\n"
            f"Para reactivar: /sethorario",
            parse_mode="HTML",
            reply_markup=ren.BTN_MENU,
        )
        return

    # ── HORARIO (desde sethorario o ayuda) ────────────────────────────────────
    if data.startswith("horario:"):
        hora_val = data.split(":")[1]
        hora     = None if hora_val == "none" else hora_val
        db.upsert_perfil(uid, hora_recordatorio=hora)
        msg = f"⏰ Recordatorio a las <b>{hora}</b> ✅" if hora else "❌ Recordatorio desactivado"
        try:
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=ren.BTN_MENU)
        except Exception:
            await context.bot.send_message(chat_id=query.message.chat_id, text=msg, parse_mode="HTML")
        return

    logger.debug("Callback no manejado: %s", data)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _kb_objetivos() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Bajar grasa / perder peso",      callback_data="vida:bajar_grasa")],
        [InlineKeyboardButton("💪 Ganar músculo y fuerza",         callback_data="vida:ganar_musculo")],
        [InlineKeyboardButton("⚡ Bajar grasa Y ganar músculo",    callback_data="vida:recomposicion")],
        [InlineKeyboardButton("🍑 Glúteo y pierna",               callback_data="vida:gluteo_pierna")],
        [InlineKeyboardButton("🏃 Salud y energía",               callback_data="vida:salud")],
        [InlineKeyboardButton("🏆 Nivel competitivo",             callback_data="vida:powerlifting")],
    ])


def _kb_dieta(back: str | None = "ver_ayuda") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🍗 Como de todo",     callback_data="nut:omnivoro")],
        [InlineKeyboardButton("🥗 Trato de comer sano", callback_data="nut:saludable")],
        [InlineKeyboardButton("🌱 Vegetariano/vegano",  callback_data="nut:vegano")],
        [InlineKeyboardButton("🍖 Alta en proteína",    callback_data="nut:proteina")],
    ]
    if back:
        rows.append([InlineKeyboardButton("← Atrás", callback_data=back)])
    return InlineKeyboardMarkup(rows)


def _kb_horario(back: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🌅 6:00 AM", callback_data="horario:06:00"),
         InlineKeyboardButton("🌅 7:00 AM", callback_data="horario:07:00"),
         InlineKeyboardButton("🌅 8:00 AM", callback_data="horario:08:00")],
        [InlineKeyboardButton("☀️ 12:00 PM", callback_data="horario:12:00"),
         InlineKeyboardButton("🌆 5:00 PM",  callback_data="horario:17:00"),
         InlineKeyboardButton("🌆 6:00 PM",  callback_data="horario:18:00")],
        [InlineKeyboardButton("🌙 7:00 PM",  callback_data="horario:19:00"),
         InlineKeyboardButton("🌙 8:00 PM",  callback_data="horario:20:00"),
         InlineKeyboardButton("🌙 9:00 PM",  callback_data="horario:21:00")],
        [InlineKeyboardButton("❌ Sin recordatorio", callback_data="horario:none")],
    ]
    if back:
        rows.append([InlineKeyboardButton("← Atrás", callback_data=back)])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRO
# ══════════════════════════════════════════════════════════════════════════════

def register(app: Application) -> None:
    allowed = db.get_allowed_users()
    logger.info("Usuarios permitidos: %s", allowed)

    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("login",       cmd_login))
    app.add_handler(CommandHandler("sethorario",  cmd_sethorario))
    app.add_handler(CommandHandler("reset_plan",  cmd_reset_plan))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("adduser",     cmd_adduser))

    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler_texto))
