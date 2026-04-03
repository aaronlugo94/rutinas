"""
handlers.py — Handlers de Telegram.

Integra: personality.py, gamification.py, renderer.py.
Flujo WOW: onboarding → plan → rutinas → feedback → celebración → resumen semanal.
"""
from __future__ import annotations

import os
import asyncio
import logging

from google import genai
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    MessageHandler, filters, ContextTypes,
)

import database as db
import science as sci
import gemini as gem
import renderer as ren
import catalog as cat
import gamification as gam
import personality as p

logger = logging.getLogger(__name__)

_ALLOWED: set[int] = set()
ADMIN_ID = int(os.environ.get("ADMIN_ID", "1557254587"))


def load_allowed_users() -> None:
    global _ALLOWED
    try:
        _ALLOWED = db.get_allowed_users()
        if not _ALLOWED:
            _ALLOWED = {ADMIN_ID}
        logger.info("Usuarios permitidos: %s", _ALLOWED)
    except Exception as e:
        _ALLOWED = {ADMIN_ID}
        logger.warning("Fallback ALLOWED_USERS: %s", e)


async def check_auth(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    if uid not in _ALLOWED:
        if update.message:
            await update.message.reply_text("⛔ Este bot es privado.")
        return False
    return True


def _client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


# ── COMANDOS ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid    = update.effective_user.id
    nombre = update.effective_user.first_name or ""
    if not db.has_plan(uid):
        await _onboarding_inicio(update, nombre)
        return

    semana, dia = db.get_estado(uid)
    perfil      = db.get_perfil(uid)
    stats       = db.get_stats(uid)
    racha       = gam.get_racha(uid)
    xp          = gam.get_xp(uid)
    nivel       = gam.get_nivel(xp)
    grupo_hoy   = _grupo_del_dia(uid, semana, dia)

    saludo = p.saludo_inicio(
        nombre          = nombre,
        racha           = racha,
        genero          = perfil.get("genero", "mujer"),
        grupo_hoy       = grupo_hoy,
        rutinas_totales = stats["rutinas_completas"],
    )
    header = (
        f"⚡ {nivel}  ·  🔥 {p.barra_racha(racha)}  ·  💪 {stats['rutinas_completas']} rutinas\n\n"
        f"{saludo}\n\n"
    )

    texto, teclado = ren.rutina_html(uid, semana, dia)
    await update.message.reply_text(
        header + texto,
        reply_markup=teclado, parse_mode="HTML", disable_web_page_preview=True,
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid = update.effective_user.id
    await update.message.reply_text(
        gam.stats_completos_html(uid),
        reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML",
    )


async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid    = update.effective_user.id
    semana, _ = db.get_estado(uid)
    await update.message.reply_text(
        gam.generar_resumen_semanal(uid, semana),
        reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML",
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    await update.message.reply_text(
        "🏋️ <b>GymCoach</b>", reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML",
    )


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    paginas = ren.plan_html_paginas(update.effective_user.id)
    if not paginas:
        await update.message.reply_text("No tienes plan activo. Usa /start para crear uno.")
        return
    for pg in paginas:
        await update.message.reply_text(pg, parse_mode="HTML")


async def cmd_reset_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    db.clear_plan(update.effective_user.id, keep_swaps=True)
    await update.message.reply_text(
        "🧹 Plan borrado. Tus swaps y progreso se conservaron.\n"
        "Usa /start para crear uno nuevo.", parse_mode="HTML",
    )


async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Solo el admin.")
        return
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("Uso: /adduser <ID>")
        return
    nuevo_id = int(args[0])
    db.add_allowed_user(nuevo_id)
    _ALLOWED.add(nuevo_id)
    await update.message.reply_text(f"✅ Usuario {nuevo_id} añadido.")


# ── ONBOARDING ─────────────────────────────────────────────────────────────────

async def _onboarding_inicio(update: Update, nombre: str = "") -> None:
    teclado = InlineKeyboardMarkup([[
        InlineKeyboardButton("🚀 ¡Quiero mi plan!", callback_data="obj:inicio")
    ]])
    await update.message.reply_text(
        p.BIENVENIDA, reply_markup=teclado, parse_mode="HTML",
    )


def _grupo_del_dia(user_id: int, semana: int, dia: str) -> str:
    row = db.fetchone(
        "SELECT grupo FROM rutinas WHERE user_id=? AND semana=? AND dia=? LIMIT 1",
        (user_id, semana, dia),
    )
    return row["grupo"] if row else "general"


# ── COACH CONVERSACIONAL ──────────────────────────────────────────────────────

async def handler_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid     = update.effective_user.id
    texto   = update.message.text
    semana, dia = db.get_estado(uid)
    perfil  = db.get_perfil(uid)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        respuesta = await gem.coach_response(
            _client(), texto,
            perfil.get("nivel", "principiante"),
            perfil.get("limitaciones", "ninguna"),
            semana, dia,
            genero=perfil.get("genero", "mujer"),
        )
        if respuesta is None:
            await update.message.reply_text(
                "💪 Para ver o modificar tu rutina usa el menú 👇",
                reply_markup=ren.MENU_PRINCIPAL,
            )
        else:
            await update.message.reply_text(respuesta)
    except asyncio.TimeoutError:
        await update.message.reply_text("⏱ Tardé demasiado. Intenta de nuevo.")
    except Exception:
        logger.exception("Error en coach")
        await update.message.reply_text("Usa el menú ❤️", reply_markup=ren.MENU_PRINCIPAL)


# ── CALLBACKS DE FEEDBACK POST-SESIÓN ────────────────────────────────────────

async def cb_rir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, sem_s, dia, rir_s = query.data.split(":")
    sem, rir = int(sem_s), int(rir_s)
    db.save_progreso_sesion(query.from_user.id, sem, dia, rir=rir)
    await query.edit_message_text(
        f"{p.msg_rir(rir)}\n\n"
        "<b>2 de 3 — ¿Progresaste vs la semana pasada?</b>\n"
        "<i>Más peso, más reps, o técnica notablemente mejor.</i>",
        reply_markup=ren.kb_progresion(sem, dia), parse_mode="HTML",
    )


async def cb_progresion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, sem_s, dia, prog = query.data.split(":")
    sem = int(sem_s)
    db.save_progreso_sesion(query.from_user.id, sem, dia, progresion=prog)
    DESCS = {
        "si":      "📈 ¡Progresaste! El músculo recibió el mensaje.",
        "igual":   "➡️ Igual que la semana pasada. Consistencia es válida.",
        "no":      "📉 Bajaste — puede ser fatiga acumulada. Lo monitoreo.",
        "primera": "🌱 Primera vez con este ejercicio. Referencia establecida.",
    }
    await query.edit_message_text(
        f"{DESCS.get(prog, '')}\n\n"
        "<b>3 de 3 — ¿Cómo quedó tu cuerpo?</b>\n"
        "<i>Fatiga muscular + energía general.</i>",
        reply_markup=ren.kb_fatiga(sem, dia, incluir_saltar=True), parse_mode="HTML",
    )


async def cb_fatiga(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query  = update.callback_query
    await query.answer()
    uid    = query.from_user.id
    partes = query.data.split(":")
    semana, dia, nivel_f = int(partes[1]), partes[2], int(partes[3])

    db.save_progreso_sesion(uid, semana, dia, fatiga=nivel_f)

    # Leer progresión de esta sesión
    row_prog = db.fetchone(
        "SELECT progreso_reportado FROM progreso WHERE user_id=? AND semana=? AND dia=? LIMIT 1",
        (uid, semana, dia),
    )
    progresion = row_prog["progreso_reportado"] if row_prog else "primera"
    grupo      = _grupo_del_dia(uid, semana, dia)
    perfil     = db.get_perfil(uid)
    nombre     = perfil.get("nombre", update.effective_user.first_name or "")

    # Análisis científico
    resultado_sci = sci.analizar_sesion(uid, semana, dia)
    sci.aplicar_ajuste(uid, semana, dia, resultado_sci.ajuste)

    # Gamificación — el momento WOW
    resultado_gam = gam.procesar_fin_sesion(
        user_id   = uid,
        semana    = semana,
        dia       = dia,
        progresion = progresion,
        grupo     = grupo,
    )

    # Construir el mensaje épico
    msg_wow = ren.msg_fin_sesion(resultado_gam)

    # Añadir nota científica si hay ajuste
    if resultado_sci.msg_usuario:
        msg_wow += f"\n\n{resultado_sci.msg_usuario}"

    # Evaluación de fatiga acumulada
    eval_fatiga = sci.evaluar_fatiga_acumulada(uid)
    if eval_fatiga["necesita_deload"] and nivel_f >= 4:
        msg_wow += f"\n\n{p.DELOAD_MSG}"

    await query.edit_message_text(
        msg_wow, parse_mode="HTML", reply_markup=ren.MENU_PRINCIPAL,
    )


async def cb_ver_fatiga(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    semana, dia = db.get_estado(uid)
    await query.edit_message_text(
        "💬 <b>¿Cómo estás hoy?</b>\n"
        "<i>Esto me ayuda a calibrar tu plan para que siempre sea el nivel correcto.</i>",
        reply_markup=ren.kb_fatiga(semana, dia), parse_mode="HTML",
    )


async def cb_ver_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    await query.edit_message_text(
        gam.stats_completos_html(uid),
        reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML",
    )


async def cb_ver_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    semana, _ = db.get_estado(uid)
    await query.edit_message_text(
        gam.generar_resumen_semanal(uid, semana),
        reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML",
    )


async def cb_ver_volumen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    semana, _ = db.get_estado(uid)
    vol   = sci.calcular_volumen_semanal(uid, semana)
    await query.edit_message_text(
        sci.formatear_volumen(vol), parse_mode="HTML", reply_markup=ren.MENU_PRINCIPAL,
    )


# ── ROUTER MAESTRO ────────────────────────────────────────────────────────────

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data  = query.data
    uid   = query.from_user.id

    # ── MENÚ ──────────────────────────────────────────────────────────────────
    if data.startswith("menu:"):
        accion = data.split(":")[1]
        await query.answer()

        if accion == "hoy":
            semana, dia = db.get_estado(uid)
            stats  = db.get_stats(uid)
            racha  = gam.get_racha(uid)
            nivel  = gam.get_nivel(gam.get_xp(uid))
            header = (
                f"⚡ {nivel}  ·  🔥 {p.barra_racha(racha)}  ·  "
                f"💪 {stats['rutinas_completas']} rutinas\n\n"
            )
            texto, teclado = ren.rutina_html(uid, semana, dia)
            await query.edit_message_text(
                header + texto, reply_markup=teclado,
                parse_mode="HTML", disable_web_page_preview=True,
            )

        elif accion == "plan":
            paginas = ren.plan_html_paginas(uid)
            if not paginas:
                await query.edit_message_text("No tienes plan activo.")
                return
            await query.edit_message_text(paginas[0], parse_mode="HTML")
            for pg in paginas[1:]:
                await context.bot.send_message(query.message.chat_id, pg, parse_mode="HTML")
            await context.bot.send_message(
                query.message.chat_id, "👆 Plan completo", reply_markup=ren.MENU_PRINCIPAL,
            )

        elif accion == "main":
            await query.edit_message_text(
                "🏋️ <b>GymCoach</b>", reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML",
            )

        elif accion == "nuevo":
            db.clear_plan(uid, keep_swaps=True)
            teclado = InlineKeyboardMarkup([
                [InlineKeyboardButton("🍑 Glúteo y pierna",          callback_data="obj:gluteo")],
                [InlineKeyboardButton("🔥 Perder grasa",             callback_data="obj:peso")],
                [InlineKeyboardButton("💪 Cuerpo completo",          callback_data="obj:general")],
            ])
            await query.edit_message_text(
                "🆕 <b>1 de 6</b> — ¿Cuál es tu objetivo principal?",
                reply_markup=teclado, parse_mode="HTML",
            )
        return

    # ── ONBOARDING ────────────────────────────────────────────────────────────
    if data.startswith("obj:"):
        await query.answer()
        objetivo = data.split(":")[1]
        if objetivo == "inicio":
            teclado = InlineKeyboardMarkup([
                [InlineKeyboardButton("🍑 Glúteo y pierna",  callback_data="obj:gluteo")],
                [InlineKeyboardButton("🔥 Perder grasa",     callback_data="obj:peso")],
                [InlineKeyboardButton("💪 Cuerpo completo",  callback_data="obj:general")],
            ])
            await query.edit_message_text(
                "🆕 <b>1 de 6</b> — ¿Cuál es tu objetivo principal?",
                reply_markup=teclado, parse_mode="HTML",
            )
        else:
            db.upsert_estado(uid, 1, "pendiente", objetivo=objetivo)
            teclado = InlineKeyboardMarkup([
                [InlineKeyboardButton("👩 Mujer",  callback_data="gen:mujer")],
                [InlineKeyboardButton("👨 Hombre", callback_data="gen:hombre")],
            ])
            await query.edit_message_text(
                "<b>2 de 6</b> — ¿Eres hombre o mujer?\n"
                "<i>El plan ajusta split, volumen de glúteo y progresión.</i>",
                reply_markup=teclado, parse_mode="HTML",
            )
        return

    if data.startswith("gen:"):
        await query.answer()
        genero  = data.split(":")[1]
        db.upsert_perfil(uid, genero=genero)
        row_obj = db.fetchone("SELECT objetivo FROM estado WHERE user_id=?", (uid,))
        objetivo = row_obj["objetivo"] if row_obj else "general"
        await query.edit_message_text(
            p.bienvenida_objetivo(objetivo, genero) + "\n\n<b>3 de 6 — ¿Cuál es tu nivel?</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌱 Principiante — máquinas y peso corporal", callback_data="niv:principiante")],
                [InlineKeyboardButton("💪 Intermedio — mancuernas y unilaterales",  callback_data="niv:intermedio")],
                [InlineKeyboardButton("🔥 Avanzado — barra libre y búlgara",        callback_data="niv:avanzado")],
            ]),
            parse_mode="HTML",
        )
        return

    if data.startswith("niv:"):
        await query.answer()
        nivel = data.split(":")[1]
        db.upsert_perfil(uid, nivel=nivel)
        await query.edit_message_text(
            "<b>4 de 6</b> — ¿Tienes alguna limitación física?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Sin limitaciones",  callback_data="lim:ninguna")],
                [InlineKeyboardButton("🦵 Rodilla delicada", callback_data="lim:rodilla")],
                [InlineKeyboardButton("🔙 Espalda baja",     callback_data="lim:espalda")],
                [InlineKeyboardButton("💪 Hombro lesionado", callback_data="lim:hombro")],
            ]),
            parse_mode="HTML",
        )
        return

    if data.startswith("lim:"):
        await query.answer()
        lim = data.split(":")[1]
        db.upsert_perfil(uid, limitaciones=lim)
        await query.edit_message_text(
            "<b>5 de 6</b> — ¿Dónde entrenas normalmente?\n\n"
            "🏋️ <b>Gimnasio</b> — máquinas, poleas, mancuernas, barras\n"
            "🏠 <b>Casa</b> — peso corporal, silla, escalón, botellas\n"
            "🦺 <b>Banda elástica</b> — ejercicios solo con banda",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏋️ Voy al gimnasio",       callback_data="amb:gym")],
                [InlineKeyboardButton("🏠 Entreno en casa",        callback_data="amb:home")],
                [InlineKeyboardButton("🦺 Casa con banda elástica", callback_data="amb:band")],
            ]),
            parse_mode="HTML",
        )
        return

    if data.startswith("amb:"):
        await query.answer()
        ambiente = data.split(":")[1]
        db.upsert_perfil(uid, ambiente_preferido=ambiente)
        amb_desc = {"gym": "gimnasio 🏋️", "home": "casa 🏠", "band": "banda elástica 🦺"}.get(ambiente, ambiente)
        await query.edit_message_text(
            f"<b>6 de 6</b> — ¿Cuántos días por semana?\n\n"
            f"<i>Plan para {amb_desc} · 4 días consistentes > 5 irregulares.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("3️⃣ 3 días", callback_data="dias:3")],
                [InlineKeyboardButton("4️⃣ 4 días", callback_data="dias:4")],
                [InlineKeyboardButton("5️⃣ 5 días", callback_data="dias:5")],
            ]),
            parse_mode="HTML",
        )
        return

    # ── GENERACIÓN DEL PLAN ───────────────────────────────────────────────────
    if data.startswith("dias:"):
        await query.answer()
        dias = int(data.split(":")[1])
        if db.has_plan(uid):
            await query.edit_message_text("Ya tienes un plan activo. Usa /start.")
            return

        row_obj  = db.fetchone("SELECT objetivo FROM estado WHERE user_id=?", (uid,))
        objetivo = row_obj["objetivo"] if row_obj else "general"
        perfil   = db.get_perfil(uid)
        perfil.update({"objetivo": objetivo, "dias": dias})
        ambiente = perfil.get("ambiente_preferido", "gym")

        # Guardar nombre del usuario
        nombre = getattr(query.from_user, "first_name", "") or ""
        if nombre:
            db.upsert_perfil(uid, nombre=nombre)

        pasos = [
            "🧠 <b>Analizando tu perfil...</b>",
            "🔬 <b>Aplicando ciencia EMG (Contreras 2015)...</b>",
            "🍑 <b>Optimizando split de glúteo...</b>",
            "✍️ <b>Generando tu plan personalizado...</b>",
        ]
        for paso in pasos:
            await query.edit_message_text(paso, parse_mode="HTML")
            await asyncio.sleep(2.2)

        client = _client()

        async def on_progress(num: int) -> None:
            icons = ["🧠", "📊", "🏗", "✍️"]
            await query.edit_message_text(
                f"{icons[num-1]} <b>Generando semana {num}/4...</b>", parse_mode="HTML",
            )

        semanas, error = await gem.generar_plan_completo(
            client, perfil, ambiente=ambiente, on_progress=on_progress,
        )

        if error or not semanas:
            await query.edit_message_text(
                f"❌ <b>Error:</b> {error}\n\nIntenta de nuevo.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Reintentar", callback_data="menu:nuevo")
                ]]),
                parse_mode="HTML",
            )
            return

        swaps = db.get_swaps(uid)
        n     = db.insert_plan(uid, semanas, swaps, cat.BY_ID)
        primer_dia = semanas[0]["dias"][0]["dia"] if semanas and semanas[0].get("dias") else "lunes"
        db.upsert_estado(uid, 1, primer_dia)

        try:
            sci.aplicar_prioridad_muscular(uid, 1)
        except Exception as e:
            logger.warning("Prioridad muscular: %s", e)

        perfil_final = db.get_perfil(uid)
        genero       = perfil_final.get("genero", "mujer")
        amb_desc     = {"gym": "Gym 🏋️", "home": "Casa 🏠", "band": "Banda 🦺"}.get(ambiente, ambiente)

        await query.edit_message_text(
            f"🎉 <b>¡Tu plan está listo!</b>\n\n"
            f"📋 <b>{n} ejercicios</b> · {perfil.get('nivel','').capitalize()} · {objetivo} · {dias} días\n"
            f"📍 {amb_desc}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{'Recuerda: ' if genero == 'mujer' else ''}"
            f"{'El hip thrust es el ejercicio #1 para glúteo. RIR 1-2 siempre.' if objetivo == 'gluteo' else 'Progresión semanal = resultado garantizado.'}\n\n"
            f"<i>👇 Toca <b>Rutina de hoy</b> para empezar tu primera sesión</i>",
            reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML",
        )
        return

    # ── PLAN ──────────────────────────────────────────────────────────────────
    if data.startswith("plan:"):
        await query.answer()
        paginas = ren.plan_html_paginas(uid)
        if not paginas:
            await query.edit_message_text("No hay plan activo.")
            return
        await query.edit_message_text(paginas[0], parse_mode="HTML")
        for pg in paginas[1:]:
            await context.bot.send_message(query.message.chat_id, pg, parse_mode="HTML")
        await context.bot.send_message(
            query.message.chat_id, "👆 Plan completo",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Volver", callback_data="back_hoy")
            ]]),
        )
        return

    if data == "back_hoy":
        await query.answer()
        semana, dia = db.get_estado(uid)
        texto, teclado = ren.rutina_html(uid, semana, dia)
        await query.edit_message_text(
            texto, reply_markup=teclado, parse_mode="HTML", disable_web_page_preview=True,
        )
        return

    # ── CHECK / UNCHECK ───────────────────────────────────────────────────────
    if data.startswith("chk:"):
        await query.answer()
        _, eid, sem_s, dia = data.split(":")
        sem = int(sem_s)
        db.toggle_ejercicio(uid, sem, dia, eid)
        texto, teclado = ren.rutina_html(uid, sem, dia)
        await query.edit_message_text(
            texto, reply_markup=teclado, parse_mode="HTML", disable_web_page_preview=True,
        )
        return

    # ── SWAP ──────────────────────────────────────────────────────────────────
    if data.startswith("swp_ask:"):
        _, eid, sem_s, dia = data.split(":")
        sem     = int(sem_s)
        excluir = {e["ejercicio_id"] for e in db.get_ejercicios_dia(uid, sem, dia)}
        perfil  = db.get_perfil(uid)
        ambiente = perfil.get("ambiente_preferido", "gym")
        alts    = cat.alternativas(eid, excluir, ambiente=ambiente)
        if not alts:
            await query.answer("No hay alternativas disponibles 😅", show_alert=True)
            return
        await query.answer()
        original = cat.BY_ID[eid].nombre if cat.is_valid(eid) else eid
        teclado  = InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                f"⚡{a.emg_score} {a.nombre}",
                callback_data=f"swp_do:{eid}:{a.id}:{sem_s}:{dia}",
            )] for a in alts]
            + [[InlineKeyboardButton("❌ Cancelar", callback_data=f"swp_cancel:{sem_s}:{dia}")]]
        )
        await query.edit_message_text(
            f"🔄 <b>Cambiar:</b> {ren.safe(original)}\n\n"
            "Ordenadas por activación muscular (EMG ⚡):",
            reply_markup=teclado, parse_mode="HTML",
        )
        return

    if data.startswith("swp_do:"):
        _, id_orig, id_nuevo, sem_s, dia = data.split(":")
        sem = int(sem_s)
        await query.answer("✅ Ejercicio actualizado en todo el plan")
        ej_orig = cat.BY_ID.get(id_orig)
        ej_new  = cat.BY_ID.get(id_nuevo)
        if ej_orig and ej_new:
            with db.get_db() as conn:
                conn.execute(
                    "UPDATE rutinas SET ejercicio_id=?, ejercicio=?, patron=? "
                    "WHERE user_id=? AND ejercicio_id=?",
                    (id_nuevo, ej_new.nombre, ej_new.patron, uid, id_orig),
                )
                conn.execute(
                    "DELETE FROM progreso WHERE user_id=? AND ejercicio_id=?", (uid, id_orig),
                )
            db.save_swap(uid, id_orig, id_nuevo, ej_orig.grupo, ej_orig.rol)
        texto, teclado = ren.rutina_html(uid, sem, dia)
        await query.edit_message_text(
            texto, reply_markup=teclado, parse_mode="HTML", disable_web_page_preview=True,
        )
        return

    if data.startswith("swp_cancel:"):
        await query.answer()
        _, sem_s, dia = data.split(":")
        texto, teclado = ren.rutina_html(uid, int(sem_s), dia)
        await query.edit_message_text(
            texto, reply_markup=teclado, parse_mode="HTML", disable_web_page_preview=True,
        )
        return

    # ── TERMINAR RUTINA ───────────────────────────────────────────────────────
    if data.startswith("finish:"):
        _, sem_s, dia = data.split(":")
        sem = int(sem_s)
        if not db.rutina_completa(uid, sem, dia):
            await query.answer(
                "¡Faltan ejercicios por marcar! Marca todos los ✅ primero 💪",
                show_alert=True,
            )
            return
        await query.answer()
        await query.edit_message_text(
            "🏁 <b>¡Rutina terminada!</b>\n\n"
            "<b>1 de 3 — ¿Cuántas reps te sobraban al terminar el último set?</b>\n\n"
            "<i>RIR = Reps In Reserve. Es la métrica más honesta de intensidad real.</i>",
            reply_markup=ren.kb_rir(sem, dia), parse_mode="HTML",
        )
        return

    if data.startswith("adv_yes:"):
        await query.answer()
        _, sem_s, dia = data.split(":")
        sem = int(sem_s)
        max_sem = db.fetchone("SELECT MAX(semana) as n FROM rutinas WHERE user_id=?", (uid,))
        max_s   = (max_sem["n"] or 4) if max_sem else 4
        nueva_semana, nuevo_dia = db.avanzar_dia(uid, sem, dia, max_semana=max_s)
        db.upsert_estado(uid, nueva_semana, nuevo_dia)
        if nueva_semana > sem:
            try:
                sci.aplicar_prioridad_muscular(uid, nueva_semana)
            except Exception as e:
                logger.warning("Prioridad muscular: %s", e)
        texto, teclado = ren.rutina_html(uid, nueva_semana, nuevo_dia)
        await query.edit_message_text(
            f"✅ Avanzado a S{nueva_semana} · {nuevo_dia}\n\n" + texto,
            reply_markup=teclado, parse_mode="HTML", disable_web_page_preview=True,
        )
        return

    await query.answer()


# ── REGISTRO ──────────────────────────────────────────────────────────────────

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("menu",       cmd_menu))
    app.add_handler(CommandHandler("plan",       cmd_plan))
    app.add_handler(CommandHandler("stats",      cmd_stats))
    app.add_handler(CommandHandler("resumen",    cmd_resumen))
    app.add_handler(CommandHandler("reset_plan", cmd_reset_plan))
    app.add_handler(CommandHandler("adduser",    cmd_adduser))

    app.add_handler(CallbackQueryHandler(cb_rir,         pattern="^rir:"))
    app.add_handler(CallbackQueryHandler(cb_progresion,  pattern="^prg:"))
    app.add_handler(CallbackQueryHandler(cb_fatiga,      pattern="^fat:"))
    app.add_handler(CallbackQueryHandler(cb_ver_fatiga,  pattern="^ver_fatiga$"))
    app.add_handler(CallbackQueryHandler(cb_ver_stats,   pattern="^ver_stats$"))
    app.add_handler(CallbackQueryHandler(cb_ver_resumen, pattern="^ver_resumen$"))
    app.add_handler(CallbackQueryHandler(cb_ver_volumen, pattern="^ver_volumen$"))
    app.add_handler(CallbackQueryHandler(callback_router))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler_texto))
    
