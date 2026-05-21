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
import progreso as prog
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
    if racha >= 7:
        racha_str = f"\n🔥 <b>{racha} días de racha</b> — no lo rompas hoy."
    elif racha >= 3:
        racha_str = f"\n🔥 {racha} días seguidos."
    elif racha == 1:
        racha_str = "\n⚡ Primer día de racha."
    else:
        racha_str = ""
    header = f"{saludo}{racha_str}\n\n"

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


async def cmd_progreso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid = update.effective_user.id
    texto, ejercicios = prog.msg_lista_ejercicios(uid)

    if not ejercicios:
        await update.message.reply_text(texto, parse_mode="HTML",
                                         reply_markup=ren.MENU_PRINCIPAL)
        return

    # Build inline keyboard — one button per exercise
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    filas = []
    for e in ejercicios[:20]:  # max 20
        filas.append([InlineKeyboardButton(
            e["ejercicio"][:40],
            callback_data=f"prog_ej:{e['ejercicio_id']}"
        )])
    filas.append([InlineKeyboardButton(
        "📊 Ver resumen global", callback_data="prog_resumen"
    )])
    filas.append([InlineKeyboardButton("🔙 Menú", callback_data="menu:main")])

    await update.message.reply_text(
        texto,
        reply_markup=InlineKeyboardMarkup(filas),
        parse_mode="HTML",
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
        "/progreso — Historial de pesos por ejercicio\n"
        "/stats — Badges y racha\n"
        "/resumen — Resumen de la semana\n"
        "/plan — Plan completo\n"
        "/reset_plan — Crear nuevo plan\n"
        "  (tu historial de pesos se conserva)\n"
        "/setpin 1234 — Configura acceso a la web app\n\n"

        "<b>¿Qué es RIR?</b>\n"
        "Reps In Reserve — cuántas reps te sobraban\n"
        "RIR 0 = lo diste todo\n"
        "RIR 2 = podías hacer 2 más pero paraste\n"
        "RIR 3+ = estaba demasiado fácil, sube el peso"
    )
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=ren.MENU_PRINCIPAL)


async def cmd_setpin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Configura el PIN de 4 dígitos para acceder a la web app."""
    if not await check_auth(update):
        return
    uid  = update.effective_user.id
    args = context.args or []
    if not args or not args[0].isdigit() or len(args[0]) != 4:
        await update.message.reply_text(
            "Uso: /setpin 1234\nEl PIN de 4 dígitos te permite entrar a la web app.\nCámbialo cuando quieras."
        )
        return
    pin = args[0]
    db.execute("UPDATE usuarios SET pin=? WHERE user_id=?", (pin, uid))
    await update.message.reply_text(
        f"✅ PIN configurado.\n\n"
        f"Entra a la web con:\n"
        f"  Tu Telegram ID: <code>{uid}</code>\n"
        f"  Tu PIN: <code>{pin}</code>\n\n"
        f"<i>Guarda tu ID — lo necesitas para entrar a la web.</i>",
        parse_mode="HTML",
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
    n = nombre.split()[0] if nombre else ""
    saludo = f"Hola {n}. " if n else ""
    texto = (
        f"<b>GymCoach</b>\n\n"
        f"{saludo}Plan de entrenamiento basado en ciencia. "
        f"Se ajusta cada semana según cómo te fue.\n\n"

        "<b>Cómo funciona</b>\n"
        "1. Abre la rutina del día\n"
        "2. Entrena todos los ejercicios\n"
        "3. Toca <b>✅ Terminé</b> al acabar\n"
        "4. Registra cuántas lbs usaste\n"
        "   → La siguiente semana el bot te dice cuánto subir\n\n"

        "<b>Botones en la rutina</b>\n"
        "🔄 — Cambiar ese ejercicio por otro\n"
        "✅ Terminé — Cerrar la sesión\n"
        "📊 Stats — Tu progreso\n\n"

        "¿Listo? 6 preguntas y tu plan está listo en segundos."
    )
    teclado = InlineKeyboardMarkup([[
        InlineKeyboardButton("💪 Crear mi plan", callback_data="obj:inicio")
    ]])
    await update.message.reply_text(texto, reply_markup=teclado, parse_mode="HTML")


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


async def _do_skip_day(
    uid: int, semana: int, dia: str, query, context, save: bool = False
) -> None:
    """Salta el día actual y avanza al siguiente."""
    db.clear_peso_flow(uid)
    if not save:
        # Reset completados del día
        with db.get_db() as conn:
            conn.execute(
                "UPDATE rutinas SET completado=0 WHERE user_id=? AND semana=? AND dia=?",
                (uid, semana, dia),
            )
    max_sem = db.fetchone("SELECT MAX(semana) as n FROM rutinas WHERE user_id=?", (uid,))
    max_s   = (max_sem["n"] or 4) if max_sem else 4
    nueva_sem, nuevo_dia = db.avanzar_dia(uid, semana, dia, max_semana=max_s)
    db.upsert_estado(uid, nueva_sem, nuevo_dia)
    if nueva_sem > semana:
        try:
            import science as sci
            sci.aplicar_prioridad_muscular(uid, nueva_sem)
        except Exception as e:
            logger.warning("Prioridad: %s", e)
    saved_msg = " Lo que hiciste quedó guardado." if save else ""
    texto, teclado = ren.rutina_html(uid, nueva_sem, nuevo_dia)
    await query.edit_message_text(
        f"Día saltado.{saved_msg}\n\n" + texto,
        reply_markup=teclado,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


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


async def cb_ver_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    texto = (
        "<b>Cómo usar GymCoach</b>\n\n"
        "1️⃣ Entrena todos los ejercicios de la rutina\n"
        "2️⃣ Toca <b>✅ Terminé</b> al acabar\n"
        "3️⃣ Escribe cuántas lbs usaste en cada ejercicio\n"
        "   (escribe 0 para saltar uno)\n"
        "4️⃣ Dinos cómo estuvo la sesión\n\n"
        "<b>Botones</b>\n"
        "🔄 — Cambiar ese ejercicio por otro\n"
        "✅ Terminé — Cerrar la sesión\n"
        "📊 Stats — Tu progreso\n"
        "📋 Plan — Ver las 4 semanas\n\n"
        "<b>¿Qué es RIR?</b>\n"
        "Reps que te sobraban al terminar el último set\n"
        "RIR 0 = lo diste todo\n"
        "RIR 2 = podías hacer 2 más\n"
        "RIR 3+ = estaba fácil, sube el peso\n\n"
        "<b>¿Qué pasa si salto un día?</b>\n"
        "Nada. Vuelve cuando puedas, el plan sigue donde lo dejaste."
    )
    await query.edit_message_text(
        texto, reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML",
    )


async def cb_ver_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    texto = (
        "<b>Cómo usar GymCoach</b>\n\n"

        "<b>Flujo básico</b>\n"
        "1. Toca <b>💪 Rutina de hoy</b>\n"
        "2. Entrena todos los ejercicios\n"
        "3. Toca <b>✅ Terminé</b>\n"
        "4. Escribe cuántas lbs usaste en cada ejercicio\n"
        "   (escribe 0 para saltar un ejercicio)\n"
        "5. Dinos cómo estuvo la sesión\n"
        "→ La semana siguiente el bot te dice cuánto subir\n\n"

        "<b>Botones en la rutina</b>\n"
        "🔄 — Cambiar ese ejercicio por otro\n"
        "✅ Terminé — Marca la sesión como completada\n"
        "📊 Stats — Tu progreso y badges\n"
        "📋 Plan — Las 4 semanas completas\n\n"

        "<b>¿Qué es RIR?</b>\n"
        "Reps que te sobraban al terminar el último set\n"
        "RIR 0 = lo diste todo · RIR 3+ = estaba muy fácil\n\n"

        "<b>¿Quieres un plan nuevo?</b>\n"
        "Toca 🆕 Nuevo plan en el menú\n"
        "Tu historial de pesos siempre se conserva"
    )
    await query.edit_message_text(
        texto, reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML",
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
            await query.edit_message_text(
                "<b>2/6</b> — ¿Género?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👩 Mujer",  callback_data="gen:mujer")],
                    [InlineKeyboardButton("👨 Hombre", callback_data="gen:hombre")],
                    [InlineKeyboardButton("← Atrás",   callback_data="obj:inicio")],
                ]),
                parse_mode="HTML",
            )
        return

    if data.startswith("gen:"):
        await query.answer()
        genero_val = data.split(":")[1]
        if genero_val == "back":
            # Back to objetivo
            teclado = InlineKeyboardMarkup([
                [InlineKeyboardButton("💪 Ponerme mamado / hipertrofia", callback_data="obj:mamado")],
                [InlineKeyboardButton("🍑 Glúteo y pierna",              callback_data="obj:gluteo")],
                [InlineKeyboardButton("🔥 Perder grasa",                 callback_data="obj:peso")],
                [InlineKeyboardButton("⚡ Cuerpo completo / general",    callback_data="obj:general")],
            ])
            await query.edit_message_text(
                "<b>1/6</b> — Objetivo", reply_markup=teclado, parse_mode="HTML",
            )
            return
        genero  = genero_val
        db.upsert_perfil(uid, genero=genero)
        row_obj = db.fetchone("SELECT objetivo FROM estado WHERE user_id=?", (uid,))
        objetivo = row_obj["objetivo"] if row_obj else "general"
        await query.edit_message_text(
            p.bienvenida_objetivo(objetivo, genero) +
            "\n\n<b>3/6 — ¿Cuánto tiempo llevas entrenando con pesas?</b>\n\n"
            "🌱 <b>Menos de 1 año</b> — empiezas de cero o llevas poco tiempo\n"
            "💪 <b>1 a 3 años</b> — ya haces sentadilla y peso muerto con forma\n"
            "🔥 <b>Más de 3 años</b> — entrenas con barra libre regularmente",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌱 Menos de 1 año", callback_data="niv:principiante")],
                [InlineKeyboardButton("💪 1 a 3 años",     callback_data="niv:intermedio")],
                [InlineKeyboardButton("🔥 Más de 3 años",  callback_data="niv:avanzado")],
                [InlineKeyboardButton("← Atrás",          callback_data="obj:inicio")],
            ]),
            parse_mode="HTML",
        )
        return

    if data.startswith("niv:"):
        await query.answer()
        nivel_val = data.split(":")[1]
        if nivel_val == "back":
            # Back to gender
            await query.edit_message_text(
                "<b>2/6</b> — ¿Género?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👩 Mujer",  callback_data="gen:mujer")],
                    [InlineKeyboardButton("👨 Hombre", callback_data="gen:hombre")],
                    [InlineKeyboardButton("← Atrás",   callback_data="obj:inicio")],
                ]),
                parse_mode="HTML",
            )
            return
        nivel = nivel_val
        db.upsert_perfil(uid, nivel=nivel)
        await query.edit_message_text(
            "<b>4/6</b> — ¿Tienes alguna limitación física?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Sin limitaciones",  callback_data="lim:ninguna")],
                [InlineKeyboardButton("🦵 Rodilla delicada", callback_data="lim:rodilla")],
                [InlineKeyboardButton("🔙 Espalda baja",     callback_data="lim:espalda")],
                [InlineKeyboardButton("💪 Hombro lesionado", callback_data="lim:hombro")],
                [InlineKeyboardButton("← Atrás",            callback_data="gen:back")],
            ]),
            parse_mode="HTML",
        )
        return

    if data.startswith("lim:"):
        await query.answer()
        lim = data.split(":")[1]
        db.upsert_perfil(uid, limitaciones=lim)
        await query.edit_message_text(
            "<b>5/6</b> — ¿Dónde entrenas?\n\n"
            "🏋️ <b>Gimnasio</b> — máquinas, poleas, mancuernas, barras\n"
            "🏠 <b>Casa</b> — peso corporal, silla, escalón, botellas\n"
            "🦺 <b>Banda elástica</b> — ejercicios solo con banda",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏋️ Voy al gimnasio",        callback_data="amb:gym")],
                [InlineKeyboardButton("🏠 Entreno en casa",         callback_data="amb:home")],
                [InlineKeyboardButton("🦺 Casa con banda elástica", callback_data="amb:band")],
                [InlineKeyboardButton("← Atrás",                   callback_data="niv:back")],
            ]),
            parse_mode="HTML",
        )
        return

    if data.startswith("amb:"):
        await query.answer()
        ambiente = data.split(":")[1]
        if ambiente == "back":
            # Back to limitaciones
            await query.edit_message_text(
                "<b>4/6</b> — ¿Limitación física?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Sin limitaciones",  callback_data="lim:ninguna")],
                    [InlineKeyboardButton("🦵 Rodilla delicada", callback_data="lim:rodilla")],
                    [InlineKeyboardButton("🔙 Espalda baja",     callback_data="lim:espalda")],
                    [InlineKeyboardButton("💪 Hombro lesionado", callback_data="lim:hombro")],
                    [InlineKeyboardButton("← Atrás",            callback_data="niv:back")],
                ]),
                parse_mode="HTML",
            )
            return
        db.upsert_perfil(uid, ambiente_preferido=ambiente)
        amb_desc = {"gym": "gimnasio 🏋️", "home": "casa 🏠", "band": "banda elástica 🦺"}.get(ambiente, ambiente)
        await query.edit_message_text(
            f"<b>6/6</b> — ¿Días por semana?\n\n"
            f"<i>Plan para {amb_desc}</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("3️⃣ 3 días", callback_data="dias:3")],
                [InlineKeyboardButton("4️⃣ 4 días", callback_data="dias:4")],
                [InlineKeyboardButton("5️⃣ 5 días", callback_data="dias:5")],
                [InlineKeyboardButton("6️⃣ 6 días", callback_data="dias:6")],
                [InlineKeyboardButton("← Atrás",   callback_data="amb:back")],
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
        parts   = data.split(":")
        eid, sem_s, dia = parts[1], parts[2], parts[3]
        pagina  = int(parts[4]) if len(parts) > 4 else 0
        sem     = int(sem_s)
        excluir = {e["ejercicio_id"] for e in db.get_ejercicios_dia(uid, sem, dia)}
        perfil  = db.get_perfil(uid)
        ambiente = perfil.get("ambiente_preferido", "gym")
        alts    = cat.alternativas(eid, excluir, ambiente=ambiente)
        if not alts:
            await query.answer("No hay más alternativas 😅", show_alert=True)
            return
        await query.answer()
        original  = cat.BY_ID[eid].nombre if cat.is_valid(eid) else eid
        por_pagina = 4
        inicio    = pagina * por_pagina
        pagina_alts = alts[inicio:inicio + por_pagina]
        hay_mas   = len(alts) > inicio + por_pagina
        filas = [[InlineKeyboardButton(
            f"⚡{a.emg_score} {a.nombre}",
            callback_data=f"swp_do:{eid}:{a.id}:{sem_s}:{dia}",
        )] for a in pagina_alts]
        nav = []
        if pagina > 0:
            nav.append(InlineKeyboardButton("← Anteriores", callback_data=f"swp_ask:{eid}:{sem_s}:{dia}:{pagina-1}"))
        if hay_mas:
            nav.append(InlineKeyboardButton("Ver más →", callback_data=f"swp_ask:{eid}:{sem_s}:{dia}:{pagina+1}"))
        if nav:
            filas.append(nav)
        filas.append([InlineKeyboardButton("❌ Cancelar", callback_data=f"swp_cancel:{sem_s}:{dia}")])
        total_str = f" ({inicio+1}-{min(inicio+por_pagina, len(alts))} de {len(alts)})"
        await query.edit_message_text(
            f"🔄 <b>Cambiar:</b> {ren.safe(original)}{total_str}\n"
            "Por activación muscular (EMG ⚡):",
            reply_markup=InlineKeyboardMarkup(filas), parse_mode="HTML",
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

    if data.startswith("skip_day:"):
        await query.answer()
        _, sem_s, dia = data.split(":")
        sem = int(sem_s)
        # Check if partially done
        ejs = db.get_ejercicios_dia(uid, sem, dia)
        hechos = sum(1 for e in ejs if e["completado"])
        if hechos > 0:
            # Already started — ask what to do
            await query.edit_message_text(
                f"Llevas {hechos}/{len(ejs)} ejercicios marcados.\n\n"
                "¿Qué hacemos?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "⏭ Saltar sin guardar",
                        callback_data=f"skip_confirm:{sem}:{dia}:discard"
                    )],
                    [InlineKeyboardButton(
                        "💾 Guardar lo que hice y saltar",
                        callback_data=f"skip_confirm:{sem}:{dia}:save"
                    )],
                    [InlineKeyboardButton(
                        "🔙 Volver a la rutina",
                        callback_data="menu:hoy"
                    )],
                ]),
                parse_mode="HTML",
            )
        else:
            # Nothing done — skip directly
            await _do_skip_day(uid, sem, dia, query, context, save=False)
        return

    if data.startswith("skip_confirm:"):
        await query.answer()
        _, sem_s, dia, modo = data.split(":")
        sem = int(sem_s)
        await _do_skip_day(uid, sem, dia, query, context, save=(modo == "save"))
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

        # Resumen del día de hoy
        ejs_hoy   = db.get_ejercicios_dia(uid, sem, dia_s)
        fuerza_hoy = [e for e in ejs_hoy if not e["ejercicio_id"].startswith("CAR")]
        pesos_hoy  = []
        for e in fuerza_hoy:
            p_row = db.get_ultimo_peso(uid, e["ejercicio_id"])
            if p_row and p_row.get("peso_lbs"):
                pesos_hoy.append(f"  {e['ejercicio'][:22]}: {p_row['peso_lbs']:g} lbs")

        resumen_hoy = ""
        if pesos_hoy:
            resumen_hoy = "\n<b>Hoy:</b>\n" + "\n".join(pesos_hoy[:4])

        # Preview de mañana
        max_sem2 = db.fetchone("SELECT MAX(semana) as n FROM rutinas WHERE user_id=?", (uid,))
        max_s2   = (max_sem2["n"] or 4) if max_sem2 else 4
        prox_sem, prox_dia = db.avanzar_dia(uid, sem, dia_s, max_semana=max_s2)
        preview_manana = ""
        if prox_dia != "fin":
            ejs_man = db.get_ejercicios_dia(uid, prox_sem, prox_dia)
            if ejs_man:
                grupo_man = ejs_man[0].get("grupo", "general")
                icon_man  = {"gluteo":"🍑","pierna":"🦵","empuje":"💪","tiron":"🏋️","core":"🎯"}.get(grupo_man,"💪")
                nombres_man = [e["ejercicio"][:20] for e in ejs_man
                               if not e["ejercicio_id"].startswith("CAR")][:3]
                preview_manana = (
                    f"\n\n<b>Mañana — {prox_dia.capitalize()}:</b>\n"
                    f"{icon_man} {grupo_man.upper()}\n"
                    + "\n".join(f"  · {n}" for n in nombres_man)
                )
            else:
                preview_manana = f"\n\n<b>Mañana:</b> 🌿 Día de recovery activo"

        nota_str = f"\n{nota_sci}" if nota_sci else ""
        cierre = f"✅ Sesión guardada.{nota_str}{resumen_hoy}{preview_manana}"

        await query.edit_message_text(
            cierre,
            reply_markup=ren.MENU_PRINCIPAL,
            parse_mode="HTML",
        )
        return

    if data.startswith("prog_ej:"):
        await query.answer()
        eid  = data.split(":", 1)[1]
        msg  = prog.msg_progresion_ejercicio(uid, eid)
        # Back button to list
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("← Lista", callback_data="prog_lista")],
            [InlineKeyboardButton("📊 Resumen", callback_data="prog_resumen")],
        ])
        await query.edit_message_text(msg, reply_markup=teclado, parse_mode="HTML")
        return

    if data.startswith("recovery:"):
        await query.answer()
        tipo = data.split(":")[1]
        descripciones = {
            "movilidad": "🧘 <b>Movilidad — 15 min</b>\n\nEstiramientos dinámicos. Caderas, hombros, columna.\nMejora el rango de movimiento para el siguiente entrenamiento.",
            "caminata":  "🚶 <b>Caminata — 30 min</b>\n\nRitmo cómodo, zona 1. Si puedes cantar, estás bien.\nActiva la recuperación sin fatigar.",
            "bici":      "🚴 <b>Bici zona 1 — 30 min</b>\n\nResistencia muy baja, FC < 110 bpm.\nFlujo sanguíneo al músculo = recuperación más rápida.",
            "core":      "🎯 <b>Core ligero</b>\n\nPlancha 3×30s · Dead bug 3×10 · Bird dog 3×10.\nSin peso, técnica perfecta. No es un entrenamiento — es mantenimiento.",
            "descanso":  "😴 <b>Descanso completo</b>\n\nTambién es parte del plan. Duerme 7-9 hrs, proteína alta aunque no entrenes.\nEl músculo crece en recuperación, no en el gym.",
        }
        msg = descripciones.get(tipo, "Buen recovery 💚")
        await query.edit_message_text(
            msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Volver", callback_data="menu:hoy")
            ]]),
        )
        return

    if data == "prog_lista":
        await query.answer()
        texto, ejercicios = prog.msg_lista_ejercicios(uid)
        filas = []
        for e in ejercicios[:20]:
            filas.append([InlineKeyboardButton(
                e["ejercicio"][:40],
                callback_data=f"prog_ej:{e['ejercicio_id']}"
            )])
        filas.append([InlineKeyboardButton("📊 Resumen global", callback_data="prog_resumen")])
        filas.append([InlineKeyboardButton("🔙 Menú", callback_data="menu:main")])
        await query.edit_message_text(
            texto,
            reply_markup=InlineKeyboardMarkup(filas),
            parse_mode="HTML",
        )
        return

    if data == "prog_resumen":
        await query.answer()
        msg = prog.msg_resumen_global(uid)
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("← Lista ejercicios", callback_data="prog_lista")],
            [InlineKeyboardButton("🔙 Menú", callback_data="menu:main")],
        ])
        await query.edit_message_text(msg, reply_markup=teclado, parse_mode="HTML")
        return

    if data.startswith("tip:"):
        await query.answer()
        paso = data.split(":")[1]
        if paso == "2":
            await query.edit_message_text(
                "Paso 2 de 3 — Registrar pesos\n\n"
                "Después de tocar Terminé, el bot te pregunta cuántas <b>lbs</b> usaste en cada ejercicio.\n\n"
                "La siguiente semana te dice cuánto subir. Escribe <b>0</b> para saltar un ejercicio.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("← Atrás", callback_data="tip:1"),
                    InlineKeyboardButton("Siguiente →", callback_data="tip:3"),
                ]]),
            )
        elif paso == "3":
            await query.edit_message_text(
                "Paso 3 de 3 — Cambiar ejercicios y RIR\n\n"
                "🔄 Si no te gusta un ejercicio, toca el botón de cambiar al lado.\n\n"
                "Al final te pregunto <b>RIR</b> — cuántas reps te sobraban al terminar.\n"
                "  · RIR 0 = lo diste todo\n"
                "  · RIR 2 = quedaban 2 reps\n"
                "  · RIR 3+ = sube el peso la próxima vez",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("← Atrás", callback_data="tip:2")],
                    [InlineKeyboardButton("💪 Ver mi rutina", callback_data="menu:hoy")],
                ]),
            )
        elif paso == "1":
            await query.edit_message_text(
                "Paso 1 de 3 — Entrenar\n\nAbre tu rutina, haz los ejercicios, toca <b>✅ Terminé</b> al acabar.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Siguiente →", callback_data="tip:2")
                ]]),
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
        # Paso 1 del mini-tutorial — con botón para continuar
        await context.bot.send_message(
            chat_id    = query.message.chat_id,
            text       = "Paso 1 de 3 — Entrenar\n\nAbre tu rutina, haz los ejercicios, toca <b>✅ Terminé</b> al acabar.",
            parse_mode = "HTML",
            reply_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("Siguiente →", callback_data="tip:2")
            ]]),
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
    app.add_handler(CommandHandler("progreso",   cmd_progreso))
    app.add_handler(CommandHandler("menu",       cmd_menu))
    app.add_handler(CommandHandler("plan",       cmd_plan))
    app.add_handler(CommandHandler("stats",      cmd_stats))
    app.add_handler(CommandHandler("resumen",    cmd_resumen))
    app.add_handler(CommandHandler("reset_plan", cmd_reset_plan))
    app.add_handler(CommandHandler("setpin",     cmd_setpin))
    app.add_handler(CommandHandler("adduser",    cmd_adduser))

    app.add_handler(CallbackQueryHandler(cb_rir,         pattern="^rir:"))
    app.add_handler(CallbackQueryHandler(cb_progresion,  pattern="^prg:"))
    app.add_handler(CallbackQueryHandler(cb_fatiga,      pattern="^fat:"))
    app.add_handler(CallbackQueryHandler(cb_ver_ayuda,   pattern="^ver_ayuda$"))
    app.add_handler(CallbackQueryHandler(cb_ver_fatiga,  pattern="^ver_fatiga$"))
    app.add_handler(CallbackQueryHandler(cb_ver_ayuda,   pattern="^ver_ayuda$"))
    app.add_handler(CallbackQueryHandler(cb_ver_stats,   pattern="^ver_stats$"))
    app.add_handler(CallbackQueryHandler(cb_ver_resumen, pattern="^ver_resumen$"))
    app.add_handler(CallbackQueryHandler(cb_ver_volumen, pattern="^ver_volumen$"))
    app.add_handler(CallbackQueryHandler(callback_router))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler_texto))
