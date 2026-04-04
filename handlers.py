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
    stats     = db.get_stats(uid)
    racha     = gam.get_racha(uid)
    grupo_hoy = _grupo_del_dia(uid, semana, dia)
    saludo    = p.saludo_inicio(
        nombre          = nombre,
        racha           = racha,
        genero          = perfil.get("genero", "mujer"),
        grupo_hoy       = grupo_hoy,
        rutinas_totales = stats["rutinas_completas"],
    )
    racha_str = f"  🔥 {racha}d" if racha > 0 else ""
    header    = f"{saludo}{racha_str}\n\n"

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


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    texto = (
        "<b>GymCoach</b>\n\n"

        "<b>Flujo básico</b>\n"
        "1. /start → ver rutina del día\n"
        "2. Entrena todos los ejercicios\n"
        "3. Toca ✅ Terminé\n"
        "4. Registra cuántas lbs usaste (escribe el número)\n"
        "5. Dinos cómo estuvo la sesión\n"
        "→ La siguiente semana el bot te dice cuánto subir\n\n"

        "<b>Botones en la rutina</b>\n"
        "🔄 — Cambiar ese ejercicio por otro\n"
        "✅ Terminé — Marcar sesión completa\n"
        "📊 Stats — Ver progreso y badges\n"
        "📋 Plan — Ver las 4 semanas\n\n"

        "<b>Comandos</b>\n"
        "/start — Rutina de hoy\n"
        "/stats — Progreso y badges\n"
        "/resumen — Resumen de la semana\n"
        "/plan — Plan completo\n"
        "/reset_plan — Crear nuevo plan\n"
        "  (tu historial de pesos se conserva)\n\n"

        "<b>¿Qué es RIR?</b>\n"
        "Reps In Reserve — cuántas reps te sobraban\n"
        "RIR 0 = lo diste todo\n"
        "RIR 2 = podías hacer 2 más pero paraste\n"
        "RIR 3+ = estaba demasiado fácil, sube el peso"
    )
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=ren.MENU_PRINCIPAL)


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

async def _mostrar_peso_prompt(
    uid: int, semana: int, dia: str,
    ej_row: list, idx: int,
    query=None, update=None,
) -> None:
    """Muestra el prompt de peso para el ejercicio idx. Texto mínimo."""
    fuerza  = [e for e in ej_row if not e["ejercicio_id"].startswith("CAR")]
    if idx >= len(fuerza):
        return
    ex      = fuerza[idx]
    eid     = ex["ejercicio_id"]
    ej_obj  = cat.BY_ID.get(eid)
    nombre  = (ej_obj.nombre if ej_obj else ex["ejercicio"])[:32]
    ultimo  = db.get_ultimo_peso(uid, eid)
    sug     = db.get_peso_sugerido(uid, eid)

    if ultimo and ultimo.get("peso_lbs"):
        prev = f"{ultimo['peso_lbs']:g}"
        hint = f"Última: {prev} lbs"
        if sug and sug != prev:
            hint += f"  →  hoy: {sug} lbs"
    else:
        hint = "Primera vez"

    texto = (
        f"<b>{idx+1}/{len(fuerza)}  {nombre}</b>\n"
        f"{ex['series']}×{ex['reps']}\n"
        f"<i>{hint}</i>\n\n"
        "¿Cuántas lbs?  (0 = saltar)"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Saltar resto", callback_data=f"skip_pesos:{semana}:{dia}")
    ]])
    if query:
        await query.edit_message_text(texto, parse_mode="HTML", reply_markup=kb)
    elif update:
        await update.message.reply_text(texto, parse_mode="HTML", reply_markup=kb)


async def _post_pesos(uid: int, semana: int, dia: str, query, context) -> None:
    """Post registro de pesos — una sola pregunta que captura todo."""
    db.clear_peso_flow(uid)
    resultado_gam = gam.procesar_fin_sesion(
        user_id   = uid,
        semana    = semana,
        dia       = dia,
        progresion = "si",
        grupo     = _grupo_del_dia(uid, semana, dia),
    )
    msg_wow = ren.msg_fin_sesion(resultado_gam)
    # Una sola pregunta: combina RIR + fatiga en 4 opciones claras
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Intenso — sin reserva",   callback_data=f"sesion:{semana}:{dia}:0:5")],
        [InlineKeyboardButton("💪 Bien — quedaban 1-2 reps", callback_data=f"sesion:{semana}:{dia}:2:3")],
        [InlineKeyboardButton("😌 Fácil — podía más",       callback_data=f"sesion:{semana}:{dia}:3:2")],
        [InlineKeyboardButton("😓 Muy cansado hoy",         callback_data=f"sesion:{semana}:{dia}:2:4")],
    ])
    await query.edit_message_text(
        msg_wow + "\n\n<b>¿Cómo estuvo la sesión?</b>",
        reply_markup=teclado,
        parse_mode="HTML",
    )


async def handler_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid     = update.effective_user.id
    texto   = update.message.text.strip()

    # ── FLUJO DE REGISTRO DE PESOS ──────────────────────────────────────────
    flow = db.get_peso_flow(uid)
    if flow:
        semana = flow["semana"]
        dia    = flow["dia"]
        ejs    = flow["ejercicios"]
        idx    = flow["idx"]
        eid    = ejs[idx]

        try:
            val = float(texto.replace(",", "."))
            val = None if val == 0 else val
        except ValueError:
            # Palabras clave para saltar
            if any(w in texto.lower() for w in ["saltar","skip","no","0","paso","omitir","s"]):
                val = None
            else:
                await update.message.reply_text("Solo el número. Ej: 135  —  escribe 0 para saltar.")
                return

        ej_row  = db.get_ejercicios_dia(uid, semana, dia)
        ej_data = next((e for e in ej_row if e["ejercicio_id"] == eid), None)
        db.save_peso(uid, eid, semana, dia,
                     peso_lbs = val,
                     series   = ej_data["series"] if ej_data else None,
                     reps     = ej_data["reps"]   if ej_data else None)

        idx += 1
        if idx >= len(ejs):
            db.clear_peso_flow(uid)
            class FQ:
                message   = update.message
                from_user = update.effective_user
                async def edit_message_text(self, *a, **kw):
                    await update.message.reply_text(*a, **kw)
                async def answer(self): pass
            await _post_pesos(uid, semana, dia, FQ(), context)
        else:
            db.save_peso_flow(uid, semana, dia, ejs, idx)
            await _mostrar_peso_prompt(uid, semana, dia, ej_row, idx, None, update)
        return
    # ── FIN FLUJO PESOS ─────────────────────────────────────────────────────

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
            texto, teclado = ren.rutina_html(uid, semana, dia)
            await query.edit_message_text(
                texto, reply_markup=teclado,
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
                [InlineKeyboardButton("💪 Ponerme mamado / hipertrofia", callback_data="obj:mamado")],
                [InlineKeyboardButton("🍑 Glúteo y pierna",              callback_data="obj:gluteo")],
                [InlineKeyboardButton("🔥 Perder grasa",                 callback_data="obj:peso")],
                [InlineKeyboardButton("⚡ Cuerpo completo / general",    callback_data="obj:general")],
            ])
            await query.edit_message_text(
                "<b>1 de 6</b> — ¿Cuál es tu objetivo principal?",
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
            p.bienvenida_objetivo(objetivo, genero) +
            "\n\n<b>3 de 6 — ¿Cuánto tiempo llevas entrenando con pesas?</b>\n\n"
            "🌱 <b>Menos de 1 año</b> — empiezas de cero o llevas poco tiempo\n"
            "💪 <b>1 a 3 años</b> — ya haces sentadilla y peso muerto con forma\n"
            "🔥 <b>Más de 3 años</b> — entrenas con barra libre regularmente",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌱 Menos de 1 año", callback_data="niv:principiante")],
                [InlineKeyboardButton("💪 1 a 3 años",     callback_data="niv:intermedio")],
                [InlineKeyboardButton("🔥 Más de 3 años",  callback_data="niv:avanzado")],
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
            f"<b>6/6</b> — ¿Días por semana?"
            f"<i>Plan para {amb_desc}</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("3️⃣ 3 días", callback_data="dias:3")],
                [InlineKeyboardButton("4️⃣ 4 días", callback_data="dias:4")],
                [InlineKeyboardButton("5️⃣ 5 días", callback_data="dias:5")],
                [InlineKeyboardButton("6️⃣ 6 días", callback_data="dias:6")],
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

        await query.edit_message_text("Generando tu plan...", parse_mode="HTML")

        import planner
        semanas = planner.generar_plan(
            nivel      = perfil.get("nivel", "intermedio"),
            objetivo   = objetivo,
            dias       = dias,
            ambiente   = ambiente,
            limitacion = perfil.get("limitaciones", "ninguna"),
        )

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
            f"<b>Plan listo.</b> {n} ejercicios · {dias} días · {amb_desc}\n\n"
            "¿A qué hora entrenas normalmente?\n"
            "<i>Te mando un recordatorio 30 min antes.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("06:00", callback_data="rec:06:00"),
                 InlineKeyboardButton("07:00", callback_data="rec:07:00"),
                 InlineKeyboardButton("08:00", callback_data="rec:08:00")],
                [InlineKeyboardButton("12:00", callback_data="rec:12:00"),
                 InlineKeyboardButton("17:00", callback_data="rec:17:00"),
                 InlineKeyboardButton("18:00", callback_data="rec:18:00")],
                [InlineKeyboardButton("19:00", callback_data="rec:19:00"),
                 InlineKeyboardButton("20:00", callback_data="rec:20:00"),
                 InlineKeyboardButton("21:00", callback_data="rec:21:00")],
                [InlineKeyboardButton("Sin recordatorio", callback_data="rec:none")],
            ]),
            parse_mode="HTML",
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

    # checkboxes removed — finish marks all at once

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
        await query.answer()
        # Marcar toda la sesión como completada de una sola vez
        with db.get_db() as conn:
            conn.execute(
                "UPDATE rutinas SET completado=1 WHERE user_id=? AND semana=? AND dia=?",
                (uid, sem, dia),
            )
        # Arrancar flujo de registro de pesos
        ejercicios = db.get_ejercicios_dia(uid, sem, dia)
        fuerza     = [e for e in ejercicios if not e["ejercicio_id"].startswith("CAR")]
        if fuerza:
            ids = [e["ejercicio_id"] for e in fuerza]
            db.save_peso_flow(uid, sem, dia, ids, 0)
            await _mostrar_peso_prompt(uid, sem, dia, fuerza, 0, query=query)
        else:
            await _post_pesos(uid, sem, dia, query, context)
        return

    if data.startswith("skip_pesos:"):
        await query.answer()
        _, sem_s, dia = data.split(":")
        db.clear_peso_flow(uid)
        await _post_pesos(uid, int(sem_s), dia, query, context)
        return

    if data.startswith("sesion:"):
        # sesion:{semana}:{dia}:{rir}:{fatiga}
        await query.answer()
        parts  = data.split(":")
        sem, dia_s, rir_s, fat_s = int(parts[1]), parts[2], int(parts[3]), int(parts[4])

        db.save_progreso_sesion(uid, sem, dia_s, rir=rir_s, progresion="si", fatiga=fat_s)

        import science as sci
        resultado_sci = sci.analizar_sesion(uid, sem, dia_s)
        sci.aplicar_ajuste(uid, sem, dia_s, resultado_sci.ajuste)

        # Avanzar al siguiente día automáticamente
        max_sem  = db.fetchone("SELECT MAX(semana) as n FROM rutinas WHERE user_id=?", (uid,))
        max_s    = (max_sem["n"] or 4) if max_sem else 4
        nueva_sem, nuevo_dia = db.avanzar_dia(uid, sem, dia_s, max_semana=max_s)
        db.upsert_estado(uid, nueva_sem, nuevo_dia)

        if nueva_sem > sem:
            try:
                sci.aplicar_prioridad_muscular(uid, nueva_sem)
            except Exception as e:
                logger.warning("Prioridad muscular: %s", e)

        # Mensaje corto de cierre
        msgs_cierre = {
            "🔥 Intenso":  "Descansa bien. El músculo crece en recuperación.",
            "💪 Bien":     "Perfecto. Progresión registrada.",
            "😌 Fácil":    "Sube el peso la próxima vez.",
            "😓 Cansado":  "Reduzco el volumen de tu próxima sesión.",
        }
        nota_sci = resultado_sci.msg_usuario if resultado_sci.msg_usuario else ""
        cierre   = f"✅ Sesión guardada.\n{nota_sci}" if nota_sci else "✅ Sesión guardada."

        await query.edit_message_text(
            cierre,
            reply_markup=ren.MENU_PRINCIPAL,
            parse_mode="HTML",
        )
        return

    if data.startswith("rec:"):
        await query.answer()
        hora = data.split(":")[1:]
        hora_str = ":".join(hora) if hora[0] != "none" else None
        db.upsert_perfil(uid, hora_recordatorio=hora_str)
        msg = (
            f"Recordatorio configurado a las {hora_str}."
            if hora_str else
            "Sin recordatorio."
        )
        # Primero: confirmación plan
        await query.edit_message_text(
            msg + "\n\nToca <b>Rutina de hoy</b> para empezar.",
            reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML",
        )
        # Segundo: tutorial de uso (solo la primera vez)
        tutorial = (
            "📖 <b>Cómo funciona</b>\n\n"
            "1️⃣ Abre la rutina del día\n"
            "2️⃣ Entrena todos los ejercicios\n"
            "3️⃣ Toca <b>✅ Terminé</b> cuando acabes\n"
            "4️⃣ Registra cuántas lbs usaste en cada ejercicio\n"
            "   → La siguiente semana el bot te dice cuánto subir\n\n"
            "🔄 <b>¿No te gusta un ejercicio?</b>\n"
            "Toca el botón 🔄 al lado para cambiarlo\n\n"
            "❓ <b>¿Qué es RIR?</b>\n"
            "Reps que te sobraban al terminar el último set\n"
            "RIR 2 = podías hacer 2 más pero paraste\n\n"
            "/help para ver esto de nuevo"
        )
        await context.bot.send_message(
            chat_id = query.message.chat_id,
            text    = tutorial,
            parse_mode = "HTML",
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
    app.add_handler(CommandHandler("help",       cmd_help))
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
