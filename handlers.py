"""
handlers.py — Handlers de Telegram.

Integra: personality.py, gamification.py, renderer.py.
Flujo WOW: onboarding → plan → rutinas → feedback → celebración → resumen semanal.
"""
from __future__ import annotations

import os
import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    MessageHandler, filters, ContextTypes,
)

import database as db
import science as sci
import renderer as ren
import catalog as cat
import gamification as gam
import progreso as prog
import personality as p

logger = logging.getLogger(__name__)

_ALLOWED: set[int] = set()
ADMIN_ID = int(os.environ.get("ADMIN_ID", "1557254587"))


async def handler_comando_desconocido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cuando el usuario escribe un comando que no existe."""
    if not await check_auth(update):
        return
    uid = update.effective_user.id
    nombre = update.effective_user.first_name or ""
    texto  = await _texto_menu_principal(uid, nombre)
    await update.message.reply_text(
        texto, reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML",
    )


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
    if uid is None:
        return False

    # Si ya está permitido — adelante
    if uid in _ALLOWED:
        return True

    # Bot abierto: agregar automáticamente a cualquier usuario nuevo
    nombre = update.effective_user.first_name if update.effective_user else ""
    try:
        db.execute(
            "INSERT OR IGNORE INTO usuarios (user_id, nombre) VALUES (?, ?)",
            (uid, nombre)
        )
        db.add_allowed_user(uid)
        _ALLOWED.add(uid)
        logger.info("Nuevo usuario agregado: %s (%s)", uid, nombre)
    except Exception as e:
        logger.warning("Error agregando usuario %s: %s", uid, e)
        if update.message:
            await update.message.reply_text("Hubo un error. Intenta de nuevo.")
        return False
    return True





# ── COMANDOS ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Punto de entrada único. Manda UNA ventana con el menú principal.
    Todo lo demás ocurre dentro de esa ventana via edit_message_text.
    """
    if not await check_auth(update):
        return
    uid    = update.effective_user.id
    nombre = update.effective_user.first_name or ""

    if not db.has_plan(uid):
        await _onboarding_inicio(update, nombre)
        return

    # Una sola ventana — el menú principal
    texto = await _texto_menu_principal(uid, nombre)
    await update.message.reply_text(
        texto,
        reply_markup=ren.MENU_PRINCIPAL,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def _texto_menu_principal(uid: int, nombre: str = "") -> str:
    """Texto del menú principal — estado rápido de los 3 pilares."""
    racha   = gam.get_racha(uid)
    semana, dia = db.get_estado(uid)
    grupo_hoy   = _grupo_del_dia(uid, semana, dia)

    # Racha
    if racha >= 7:
        racha_str = f"🔥 <b>{racha} días de racha</b>"
    elif racha >= 3:
        racha_str = f"🔥 {racha} días de racha"
    elif racha == 1:
        racha_str = "⚡ Primer día de racha"
    else:
        racha_str = ""

    # Hoy
    from catalog import GRUPO_ICON
    icon = GRUPO_ICON.get(grupo_hoy, "💪") if grupo_hoy else "🌿"
    hoy_str = f"{icon} Hoy: {grupo_hoy.upper()}" if grupo_hoy else "🌿 Hoy: Recovery"

    # Cuerpo — último pesaje
    import cuerpo as corp
    resumen = corp.get_resumen_cuerpo()
    cuerpo_str = ""
    if resumen:
        cuerpo_str = f"\n⚖️ Score: {resumen['score']}/100 · {resumen['grasa_pct']}% grasa"

    n = nombre.split()[0] if nombre else ""
    saludo = f"Hola {n} 👋\n" if n else ""

    return (
        f"{saludo}"
        f"{racha_str}{'  ·  ' if racha_str else ''}{hoy_str}"
        f"{cuerpo_str}"
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    from renderer import WEB_URL
    await update.message.reply_text(
        f"Tus stats están en la web 👇\n{WEB_URL}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Ver stats →", url=WEB_URL)
        ]]),
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
    uid    = update.effective_user.id
    nombre = update.effective_user.first_name or ""
    texto  = await _texto_menu_principal(uid, nombre)
    await update.message.reply_text(
        texto, reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML"
    )


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


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Genera un link mágico de un solo clic para entrar a la web."""
    if not await check_auth(update):
        return
    uid   = update.effective_user.id
    token = db.create_login_token(uid)
    from renderer import WEB_URL
    url   = f"{WEB_URL}/auth?token={token}"
    await update.message.reply_text(
        "Toca el botón para entrar a la web 👇\n"
        "<i>El link expira en 5 minutos y es de un solo uso.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Entrar a GymCoach", url=url)
        ]])
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
        "/start — Menú principal\n"
        "/login — Entrar a la web\n"
        "/sethorario — Cambiar hora de recordatorio\n"
        "/reset_plan — Crear nuevo plan\n\n"

        "<b>¿Qué es RIR?</b>\n"
        "Reps In Reserve — cuántas reps te sobraban\n"
        "RIR 0 = lo diste todo\n"
        "RIR 2 = podías hacer 2 más pero paraste\n"
        "RIR 3+ = estaba demasiado fácil, sube el peso"
    )
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=ren.MENU_PRINCIPAL)


async def cmd_sethorario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cambia la hora de notificación sin resetear el plan."""
    if not await check_auth(update):
        return
    uid = update.effective_user.id
    await update.message.reply_text(
        "⏰ ¿A qué hora quieres recibir el recordatorio matutino?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🌅 6:00 AM", callback_data="rec:06:00"),
             InlineKeyboardButton("🌅 7:00 AM", callback_data="rec:07:00"),
             InlineKeyboardButton("🌅 8:00 AM", callback_data="rec:08:00")],
            [InlineKeyboardButton("☀️ 12:00 PM", callback_data="rec:12:00"),
             InlineKeyboardButton("🌆 5:00 PM",  callback_data="rec:17:00"),
             InlineKeyboardButton("🌆 6:00 PM",  callback_data="rec:18:00")],
            [InlineKeyboardButton("🌙 7:00 PM",  callback_data="rec:19:00"),
             InlineKeyboardButton("🌙 8:00 PM",  callback_data="rec:20:00"),
             InlineKeyboardButton("🌙 9:00 PM",  callback_data="rec:21:00")],
            [InlineKeyboardButton("❌ Sin recordatorio", callback_data="rec:none")],
        ])
    )


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
    uid = update.effective_user.id
    texto = (
        f"<b>Coach</b> — tu entrenador personal\n\n"
        f"{saludo}Tres cosas en un solo lugar:\n"
        f"💪 <b>Gym</b> — rutina diaria y progreso de pesos\n"
        f"⚖️ <b>Cuerpo</b> — composición corporal desde tu báscula\n"
        f"🥗 <b>Nutrición</b> — plan semanal calculado con IA\n\n"
        f"Empieza por tu plan de entrenamiento 👇"
    )
    teclado = InlineKeyboardMarkup([[
        InlineKeyboardButton("💪 Crear mi plan de gym", callback_data="obj:inicio")
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
        f"<b>{idx+1} de {len(fuerza)} — {nombre}</b>\n"
        f"{ex['series']} series × {ex['reps']} reps\n"
        f"<i>{hint}</i>\n\n"
        "¿Cuánto peso usaste? (en lbs, 0 = saltar) 👇"
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
        f"Día saltado 👍{saved_msg}\n\n" + texto,
        reply_markup=teclado,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


def _kb_ayuda_contextual(uid: int) -> InlineKeyboardMarkup:
    """
    Teclado de ayuda contextual según el estado del usuario.
    Si tiene plan → muestra rutina + progreso.
    Si no tiene plan → muestra crear plan.
    """
    try:
        semana, dia = db.get_estado(uid)
        tiene_plan  = semana is not None and semana > 0
    except Exception:
        tiene_plan = False

    if tiene_plan:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("💪 Ver mi rutina de hoy", callback_data="menu:hoy")],
            [InlineKeyboardButton("🌐 Mi progreso →",        callback_data="ver_stats")],
            [InlineKeyboardButton("🆕 Cambiar mi plan",      callback_data="menu:nuevo")],
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Crear mi plan ahora",  callback_data="obj:inicio")],
        ])


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


async def _handle_peso_texto(uid: int, texto: str, update, context) -> None:
    """Procesa un número enviado como peso durante la sesión activa."""
    flow = db.get_peso_flow(uid)
    if not flow:
        return
    ejs    = flow["ejercicios"]
    idx    = flow["idx"]
    semana = flow["semana"]
    dia    = flow["dia"]
    if idx >= len(ejs):
        db.clear_peso_flow(uid)
        return
    eid    = ejs[idx]
    ej_row = db.get_ejercicios_dia(uid, semana, dia)
    ej_data = next((e for e in ej_row if e["ejercicio_id"] == eid), None)
    try:
        peso = float(texto.replace(",", "."))
    except ValueError:
        await update.message.reply_text(
            "Solo el número. Ej: 135  —  escribe 0 para saltar."
        )
        return
    if peso > 0 and ej_data:
        db.save_peso(uid, eid, semana, dia,
                     peso_lbs=peso,
                     series=ej_data.get("series"),
                     reps=ej_data.get("reps"))
    idx += 1
    db.clear_peso_flow(uid)
    sesion = db.get_sesion_activa(uid)
    if sesion and sesion.get("fase") == "peso":
        ej_idx    = sesion["ej_idx"]
        siguiente = ej_idx + 1
        db.save_sesion_activa(uid, semana, dia, siguiente, "ejercicio")
        texto_ej, teclado_ej = ren.render_ejercicio(uid, semana, dia, siguiente)
        await update.message.reply_text(
            texto_ej, reply_markup=teclado_ej, parse_mode="HTML"
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
        db.clear_peso_flow(uid)

        # Check if in exercise-by-exercise mode
        sesion = db.get_sesion_activa(uid)
        if sesion and sesion["fase"] == "peso":
            ej_idx    = sesion["ej_idx"]
            siguiente = ej_idx + 1
            db.save_sesion_activa(uid, semana, dia, siguiente, "ejercicio")
            texto_ej, teclado_ej = ren.render_ejercicio(uid, semana, dia, siguiente)
            await update.message.reply_text(
                texto_ej, reply_markup=teclado_ej, parse_mode="HTML"
            )
        elif idx >= len(ejs):
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

    # Sin Gemini — menú principal en mensaje nuevo (no hay ventana previa)
    nombre = update.effective_user.first_name or ""
    texto  = await _texto_menu_principal(uid, nombre)
    await update.message.reply_text(
        texto,
        reply_markup=ren.MENU_PRINCIPAL,
        parse_mode="HTML",
    )


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
    from renderer import WEB_URL
    await query.edit_message_text(
        f"Tus stats y progreso están en la web 👇\n{WEB_URL}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Abrir →", url=WEB_URL)],
            [InlineKeyboardButton("🔙 Volver",  callback_data="menu:hoy")],
        ]),
        parse_mode="HTML",
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

        if accion == "main":
            await query.answer()
            uid    = query.from_user.id
            nombre = query.from_user.first_name or ""
            texto  = await _texto_menu_principal(uid, nombre)
            await query.edit_message_text(
                texto,
                reply_markup=ren.MENU_PRINCIPAL,
                parse_mode="HTML",
            )
            return

        if accion == "cuerpo":
            await query.answer()
            import cuerpo as corp
            resumen = corp.get_resumen_cuerpo()
            if not resumen:
                await query.edit_message_text(
                    "⚖️ <b>Sin pesajes aún</b>\n\n"
                    "Pésate mañana en ayunas (6-9am) y el sistema lo detecta automáticamente.\n\n"
                    "Mientras tanto puedes ver tus métricas en la web 👇",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🌐 Ver en la web →", url=ren.WEB_URL)],
                        [InlineKeyboardButton("🏠 Menú", callback_data="menu:main")],
                    ])
                )
                return

            score     = resumen["score"]
            desc      = resumen["score_desc"]
            grasa     = resumen["grasa_pct"]
            musculo   = resumen["musculo_pct"]
            peso      = resumen["peso_kg"]
            visceral  = resumen["visceral"]
            mimo      = resumen.get("estado_mimo") or "—"
            eta       = resumen.get("semanas_eta", 0)
            kg_faltan = resumen.get("kg_a_perder", 0)

            mimo_emoji = {"RECOMPOSICION":"🟣","CUTTING_LIMPIO":"🟢",
                          "CATABOLISMO":"🔴","ESTANCAMIENTO":"🟡"}.get(mimo,"⚪")

            msg = (
                f"⚖️ <b>Composición corporal</b>\n"
                f"<i>{resumen['fecha']}</i>\n\n"
                f"<b>Score:</b> {score}/100 — {desc}\n"
                f"<b>Estado:</b> {mimo_emoji} {mimo.replace('_',' ')}\n\n"
                f"<b>Peso:</b> {peso} kg\n"
                f"<b>Grasa:</b> {grasa}%\n"
                f"<b>Músculo:</b> {musculo}%\n"
                f"<b>Visceral:</b> {visceral}\n\n"
            )
            if kg_faltan and kg_faltan > 0:
                msg += f"<b>Meta 22% grasa:</b> faltan {kg_faltan} kg (~{eta} semanas)\n\n"
            msg += "<i>Gráfica de tendencia y más detalles en la web 👇</i>"

            await query.edit_message_text(
                msg, parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌐 Ver tendencia →", url=f"{ren.WEB_URL}/cuerpo")],
                    [InlineKeyboardButton("🏠 Menú", callback_data="menu:main")],
                ])
            )
            return

        if accion == "dieta":
            await query.answer()
            import nutricion as nut
            macros = nut.get_macros_hoy()
            plan   = nut.get_plan_actual()

            if not macros:
                await query.edit_message_text(
                    "🥗 <b>Sin datos de nutrición aún</b>\n\n"
                    "Pésate en ayunas para que calcule tus macros y tu plan semanal.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 Menú", callback_data="menu:main")
                    ]])
                )
                return

            mimo_txt = ""
            if plan and plan.get("estado_mimo"):
                mimo_emoji = {"RECOMPOSICION":"🟣","CUTTING_LIMPIO":"🟢",
                              "CATABOLISMO":"🔴","ESTANCAMIENTO":"🟡"}.get(plan["estado_mimo"],"⚪")
                mimo_txt = f"Estado: {mimo_emoji} {plan['estado_mimo'].replace('_',' ')}\n\n"

            msg = (
                f"🥗 <b>Tu nutrición de hoy</b>\n\n"
                f"{mimo_txt}"
                f"🔥 <b>{macros['calorias']} kcal</b>\n"
                f"🥩 Proteína: <b>{macros['proteina']}g</b>\n"
                f"🍞 Carbs: <b>{macros['carbs']}g</b>\n"
                f"🥑 Grasas: <b>{macros['grasas']}g</b>\n\n"
                f"<i>Plan semanal completo en la web 👇</i>"
            )
            await query.edit_message_text(
                msg, parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌐 Ver plan semanal →", url=f"{ren.WEB_URL}/nutricion")],
                    [InlineKeyboardButton("🏠 Menú", callback_data="menu:main")],
                ])
            )
            return

        if accion == "hoy":
            await query.answer()
            semana, dia = db.get_estado(uid)
            sesion = db.get_sesion_activa(uid)
            if sesion and sesion["semana"] == semana and sesion["dia"] == dia:
                texto, teclado = ren.render_ejercicio(uid, semana, dia, sesion["ej_idx"])
            else:
                texto, teclado = ren.rutina_preview(uid, semana, dia)
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
                "<b>2/5</b> — ¿Cuánto tiempo llevas entrenando?\n\n"
                "🌱 <b>Menos de 1 año</b> — empiezas o llevas poco\n"
                "💪 <b>1 a 3 años</b> — ya dominas los básicos\n"
                "🔥 <b>Más de 3 años</b> — entrenas con barra libre regularmente",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌱 Menos de 1 año", callback_data="niv:principiante")],
                    [InlineKeyboardButton("💪 1 a 3 años",     callback_data="niv:intermedio")],
                    [InlineKeyboardButton("🔥 Más de 3 años",  callback_data="niv:avanzado")],
                    [InlineKeyboardButton("← Atrás",           callback_data="obj:inicio")],
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
                "<b>2/5</b> — ¿Cuánto tiempo llevas entrenando?\n\n"
                "🌱 <b>Menos de 1 año</b> — empiezas o llevas poco\n"
                "💪 <b>1 a 3 años</b> — ya dominas los básicos\n"
                "🔥 <b>Más de 3 años</b> — entrenas con barra libre regularmente",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌱 Menos de 1 año", callback_data="niv:principiante")],
                    [InlineKeyboardButton("💪 1 a 3 años",     callback_data="niv:intermedio")],
                    [InlineKeyboardButton("🔥 Más de 3 años",  callback_data="niv:avanzado")],
                    [InlineKeyboardButton("← Atrás",           callback_data="obj:inicio")],
                ]),
                parse_mode="HTML",
            )
            return
        nivel = nivel_val
        db.upsert_perfil(uid, nivel=nivel)
        await query.edit_message_text(
            "<b>3/5</b> — ¿Tienes alguna limitación física?",
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
            "<b>4/5</b> — ¿Dónde entrenas?\n\n"
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
                "<b>3/5</b> — ¿Limitación física?",
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
            f"<b>5/5</b> — ¿Días por semana?\n\n"
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
        dias_val = data.split(":")[1]

        # dias:back → volver a ambiente
        if dias_val == "back":
            await query.edit_message_text(
                "<b>4/5</b> — ¿Dónde entrenas?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏋️ Voy al gimnasio",        callback_data="amb:gym")],
                    [InlineKeyboardButton("🏠 Entreno en casa",         callback_data="amb:home")],
                    [InlineKeyboardButton("🦺 Casa con banda elástica", callback_data="amb:band")],
                    [InlineKeyboardButton("← Atrás",                   callback_data="lim:back")],
                ]),
                parse_mode="HTML",
            )
            return

        dias = int(dias_val)
        # Guardar días en perfil temporalmente
        db.upsert_perfil(uid, dias=dias)
        nombre = getattr(query.from_user, "first_name", "") or ""
        if nombre:
            db.upsert_perfil(uid, nombre=nombre)

        # Paso 7/7 — Hora de notificaciones (aquí, dentro del onboarding)
        await query.edit_message_text(
            "<b>5/5</b> — ¿A qué hora sueles ir al gym?\n\nTe mando un recordatorio esa mañana y un resumen por la noche 🌙",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌅 6:00 AM", callback_data="rec:06:00"),
                 InlineKeyboardButton("🌅 7:00 AM", callback_data="rec:07:00"),
                 InlineKeyboardButton("🌅 8:00 AM", callback_data="rec:08:00")],
                [InlineKeyboardButton("☀️ 12:00 PM", callback_data="rec:12:00"),
                 InlineKeyboardButton("🌆 5:00 PM",  callback_data="rec:17:00"),
                 InlineKeyboardButton("🌆 6:00 PM",  callback_data="rec:18:00")],
                [InlineKeyboardButton("🌙 7:00 PM",  callback_data="rec:19:00"),
                 InlineKeyboardButton("🌙 8:00 PM",  callback_data="rec:20:00"),
                 InlineKeyboardButton("🌙 9:00 PM",  callback_data="rec:21:00")],
                [InlineKeyboardButton("← Atrás",     callback_data="dias:back_from_rec"),
                 InlineKeyboardButton("Sin notificaciones", callback_data="rec:none")],
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
        parts    = data.split(":")
        eid      = parts[1]
        sem_s    = parts[2]
        dia      = parts[3]
        pagina   = int(parts[4]) if len(parts) > 4 else 0
        sem      = int(sem_s)
        excluir  = {e["ejercicio_id"] for e in db.get_ejercicios_dia(uid, sem, dia)}
        perfil   = db.get_perfil(uid)
        ambiente = perfil.get("ambiente_preferido", "gym")
        alts     = cat.alternativas(eid, excluir, ambiente=ambiente)
        if not alts:
            await query.answer("No hay más alternativas disponibles", show_alert=True)
            return
        await query.answer()
        original  = cat.BY_ID[eid].nombre if cat.is_valid(eid) else eid
        por_pagina = 5
        inicio     = pagina * por_pagina
        pagina_alts = alts[inicio:inicio + por_pagina]
        hay_mas    = len(alts) > inicio + por_pagina
        total      = len(alts)

        filas = [[InlineKeyboardButton(
            f"⚡{a.emg_score}  {a.nombre}",
            callback_data=f"swp_do:{eid}:{a.id}:{sem_s}:{dia}",
        )] for a in pagina_alts]

        nav = []
        if pagina > 0:
            nav.append(InlineKeyboardButton("← Atrás", callback_data=f"swp_ask:{eid}:{sem_s}:{dia}:{pagina-1}"))
        if hay_mas:
            nav.append(InlineKeyboardButton(f"Ver más ({inicio+por_pagina+1}-{min(inicio+por_pagina*2, total)}) →",
                                            callback_data=f"swp_ask:{eid}:{sem_s}:{dia}:{pagina+1}"))
        if nav:
            filas.append(nav)
        filas.append([
            InlineKeyboardButton("✖ Cancelar", callback_data=f"swp_cancel:{sem_s}:{dia}"),
            InlineKeyboardButton("🏠 Menú",    callback_data="menu:main"),
        ])

        await query.edit_message_text(
            f"Cambiar: <b>{ren.safe(original)}</b>\n<i>Opciones {inicio+1}-{min(inicio+por_pagina, total)} de {total}</i>",
            reply_markup=InlineKeyboardMarkup(filas),
            parse_mode="HTML",
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

    if data.startswith("ej_start:"):
        # Usuario toca Empezar — mostrar ejercicio 1
        await query.answer()
        _, sem_s, dia = data.split(":")
        sem = int(sem_s)
        db.save_sesion_activa(uid, sem, dia, 0, "ejercicio")
        texto, teclado = ren.render_ejercicio(uid, sem, dia, 0)
        await query.edit_message_text(texto, reply_markup=teclado,
                                       parse_mode="HTML")
        return

    if data.startswith("ej_hecho:"):
        # Usuario terminó un ejercicio — preguntar peso y avanzar
        await query.answer()
        _, sem_s, dia, idx_s = data.split(":")
        sem = int(sem_s)
        idx = int(idx_s)

        ejercicios = db.get_ejercicios_dia(uid, sem, dia)
        fuerza     = [e for e in ejercicios if not e["ejercicio_id"].startswith("CAR")]
        ej         = fuerza[idx] if idx < len(fuerza) else None
        if not ej:
            return

        eid    = ej["ejercicio_id"]
        nombre = ej["ejercicio"][:28]
        ultimo = db.get_ultimo_peso(uid, eid)
        sug    = db.get_peso_sugerido(uid, eid)
        hint   = f"Última: {ultimo['peso_lbs']:g} lbs  →  sugerido: {sug} lbs" if (
            sug and ultimo and ultimo.get("peso_lbs")
        ) else ("Última: " + f"{ultimo['peso_lbs']:g} lbs" if ultimo and ultimo.get("peso_lbs") else "Primera vez")

        # Guardar estado: esperando peso
        db.save_sesion_activa(uid, sem, dia, idx, "peso")
        # Guardar qué ejercicio espera peso en peso_flow
        db.save_peso_flow(uid, sem, dia, [eid], 0)

        await query.edit_message_text(
            f"<b>{nombre}</b>\n"
            f"{ej['series']}×{ej['reps']}\n"
            f"<i>{hint}</i>\n\n"
            f"¿Cuántas lbs usaste? (0 = saltar) 👇",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Saltar", callback_data=f"ej_skip_peso:{sem}:{dia}:{idx}")
            ]])
        )
        return

    if data.startswith("ej_skip_peso:"):
        # Saltó el peso — avanzar al siguiente ejercicio
        await query.answer()
        _, sem_s, dia, idx_s = data.split(":")
        sem  = int(sem_s)
        idx  = int(idx_s)
        db.clear_peso_flow(uid)
        siguiente = idx + 1
        db.save_sesion_activa(uid, sem, dia, siguiente, "ejercicio")
        texto, teclado = ren.render_ejercicio(uid, sem, dia, siguiente)
        await query.edit_message_text(texto, reply_markup=teclado, parse_mode="HTML")
        return

    if data.startswith("ej_resume:"):
        await query.answer()
        _, sem_s, dia, idx_s = data.split(":")
        sem = int(sem_s); idx = int(idx_s)
        texto, teclado = ren.render_ejercicio(uid, sem, dia, idx)
        await query.edit_message_text(texto, reply_markup=teclado, parse_mode="HTML")
        return

    if data.startswith("ej_done:"):
        # Usuario terminó todos los ejercicios
        await query.answer()
        _, sem_s, dia = data.split(":")
        sem = int(sem_s)
        db.clear_sesion_activa(uid)
        db.clear_peso_flow(uid)
        # Marcar sesión completa
        with db.get_db() as conn:
            conn.execute(
                "UPDATE rutinas SET completado=1 WHERE user_id=? AND semana=? AND dia=?",
                (uid, sem, dia),
            )
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
                    [InlineKeyboardButton("↩ Volver a la rutina", callback_data="menu:hoy")],
                    [InlineKeyboardButton("🏠 Menú principal",   callback_data="menu:main")],
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
        racha_fin = gam.get_racha(uid)
        if racha_fin >= 7:
            racha_msg = f"\n\n🔥 <b>{racha_fin} días de racha</b> — sigue así."
        elif racha_fin >= 3:
            racha_msg = f"\n\n🔥 {racha_fin} días seguidos."
        else:
            racha_msg = ""
        cierre = f"✅ ¡Listo! Sesión guardada.{nota_str}{racha_msg}{resumen_hoy}{preview_manana}"

        from renderer import WEB_URL
        teclado_fin = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Ver progreso →",   url=WEB_URL)],
            [InlineKeyboardButton("💪 Siguiente rutina", callback_data="menu:hoy")],
            [InlineKeyboardButton("🏠 Menú principal",   callback_data="menu:main")],
        ])
        await query.edit_message_text(
            cierre,
            reply_markup=teclado_fin,
            parse_mode="HTML",
        )
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
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💪 Volver a la rutina", callback_data="menu:hoy")],
                [InlineKeyboardButton("🏠 Menú principal",     callback_data="menu:main")],
            ]),
        )
        return



    if data.startswith("rec:"):
        await query.answer()
        partes   = data.split(":")
        hora_key = partes[1]

        # rec:back — volver a elegir días
        if hora_key == "back":
            perfil_b  = db.get_perfil(uid)
            amb_b     = perfil_b.get("ambiente_preferido", "gym")
            amb_desc_b = {"gym": "Gym 🏋️", "home": "Casa 🏠", "band": "Banda 🦺"}.get(amb_b, amb_b)
            await query.edit_message_text(
                f"<b>5/5</b> — ¿Cuántos días por semana?\n\n<i>Plan para {amb_desc_b}</i>",
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

        hora_str = ":".join(partes[1:]) if hora_key != "none" else None
        db.upsert_perfil(uid, hora_recordatorio=hora_str)

        # Generar el plan aquí
        perfil   = db.get_perfil(uid)
        obj_row  = db.fetchone("SELECT objetivo FROM estado WHERE user_id=?", (uid,))
        objetivo = obj_row["objetivo"] if obj_row else "general"
        dias     = int(perfil.get("dias") or 4)
        ambiente = perfil.get("ambiente_preferido", "gym")

        await query.edit_message_text("Creando tu plan... 💪", parse_mode="HTML")

        import planner
        semanas = planner.generar_plan(
            nivel      = perfil.get("nivel", "intermedio"),
            objetivo   = objetivo,
            dias       = dias,
            ambiente   = ambiente,
            limitacion = perfil.get("limitaciones", "ninguna"),
        )
        swaps = db.get_swaps(uid)
        db.insert_plan(uid, semanas, swaps, cat.BY_ID)
        primer_dia = semanas[0]["dias"][0]["dia"] if semanas and semanas[0].get("dias") else "lunes"
        db.upsert_estado(uid, 1, primer_dia)
        try:
            sci.aplicar_prioridad_muscular(uid, 1)
        except Exception as e:
            logger.warning("Prioridad muscular: %s", e)

        hora_msg = f"🔔 Recordatorio a las {hora_str}" if hora_str else "Sin notificaciones."

        await query.edit_message_text(
            f"✅ <b>Plan listo.</b>\n\n"
            f"{hora_msg}\n"
            f"🌙 Resumen nocturno a las 9:00 PM\n\n"
            f"<b>Cómo funciona:</b>\n"
            f"1️⃣ Abre tu rutina y entrena\n"
            f"2️⃣ Toca <b>✅ Terminé</b> al acabar\n"
            f"3️⃣ Registra cuántas lbs usaste\n"
            f"→ La siguiente semana te digo cuánto subir\n\n"
            f"¿Listo? 👇",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💪 Ver mi rutina de hoy", callback_data="menu:hoy")
            ]]),
            parse_mode="HTML",
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
    app.add_handler(CommandHandler("login",      cmd_login))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("progreso",   cmd_progreso))
    app.add_handler(CommandHandler("menu",       cmd_menu))
    app.add_handler(CommandHandler("plan",       cmd_plan))
    app.add_handler(CommandHandler("stats",      cmd_stats))
    app.add_handler(CommandHandler("resumen",    cmd_resumen))
    app.add_handler(CommandHandler("reset_plan", cmd_reset_plan))
    app.add_handler(CommandHandler("sethorario",  cmd_sethorario))
    app.add_handler(CommandHandler("setpin",      cmd_setpin))
    app.add_handler(CommandHandler("adduser",    cmd_adduser))

    app.add_handler(CallbackQueryHandler(cb_rir,         pattern="^rir:"))
    app.add_handler(CallbackQueryHandler(cb_progresion,  pattern="^prg:"))
    app.add_handler(CallbackQueryHandler(cb_fatiga,      pattern="^fat:"))
    app.add_handler(CallbackQueryHandler(cb_ver_ayuda,   pattern="^ver_ayuda$"))
    # ver_fatiga removed — replaced by contextual help
    app.add_handler(CallbackQueryHandler(cb_ver_ayuda,   pattern="^ver_ayuda$"))
    app.add_handler(CallbackQueryHandler(cb_ver_stats,   pattern="^ver_stats$"))
    app.add_handler(CallbackQueryHandler(cb_ver_resumen, pattern="^ver_resumen$"))
    app.add_handler(CallbackQueryHandler(cb_ver_volumen, pattern="^ver_volumen$"))
    app.add_handler(CallbackQueryHandler(callback_router))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler_texto))
    app.add_handler(MessageHandler(filters.COMMAND, handler_comando_desconocido))
