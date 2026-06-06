"""
handlers.py — Bot Coach. Reescrito limpio.

Reglas de diseño:
- Comandos (/start, /reset_plan, etc) usan reply_text (crean mensaje nuevo)
- Callbacks de menú usan edit_message_text (editan el mensaje donde está el botón)
- Onboarding: SIEMPRE delete+send_message para evitar "Message not modified"
- Todos los :back handlers van ANTES de su startswith() correspondiente
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

logger   = logging.getLogger(__name__)
ADMIN_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "1557254587"))

OBJETIVOS = {
    "bajar_grasa":   ("🔥 Bajar grasa / perder peso",       "peso"),
    "ganar_musculo": ("💪 Ganar músculo y fuerza",          "mamado"),
    "recomposicion": ("⚡ Bajar grasa Y ganar músculo",     "general"),
    "gluteo_pierna": ("🍑 Glúteo y pierna",                 "gluteo"),
    "salud":         ("🏃 Estar saludable y con energía",   "general"),
    "powerlifting":  ("🏆 Nivel competitivo / powerlifting","mamado"),
}
DIETAS = {
    "omnivoro":  "🍗 Como de todo",
    "saludable": "🥗 Trato de comer sano",
    "vegano":    "🌱 Vegetariano/vegano",
    "proteina":  "🍖 Alta en proteína",
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

async def check_auth(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    if uid in db.get_allowed_users():
        return True
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if msg:
        await msg.reply_text("Sin acceso.")
    return False


def _grupo_del_dia(uid, semana, dia):
    rows = db.get_ejercicios_dia(uid, semana, dia)
    return rows[0].get("grupo", "") if rows else ""


async def _menu_texto(uid, nombre=""):
    racha      = gam.get_racha(uid)
    semana, dia = db.get_estado(uid)
    grupo      = _grupo_del_dia(uid, semana, dia)
    ICON = {"empuje":"💪","tiron":"🏋️","pierna":"🦵","gluteo":"🍑","core":"🎯","cardio":"🏃"}
    racha_str = f"🔥 {racha} días de racha  ·  " if racha >= 3 else ""
    hoy_str   = f"{ICON.get(grupo,'💪')} Hoy: {grupo.upper()}" if grupo else "🌿 Hoy: Descanso"
    pesaje    = db.get_ultimo_pesaje()
    cuerpo_str = ""
    if pesaje:
        try:
            import cuerpo as corp
            score, _ = corp.calcular_score(pesaje)
            cuerpo_str = f"\n⚖️ Score: {score}/100 · {pesaje.get('Grasa_Porcentaje','?')}% grasa"
        except Exception:
            pass
    n = (nombre.split()[0] if nombre else "")
    return f"{'Hola ' + n + ' 👋' + chr(10) if n else ''}{racha_str}{hoy_str}{cuerpo_str}"


def _kb_objetivos():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Bajar grasa / perder peso",     callback_data="vida:bajar_grasa")],
        [InlineKeyboardButton("💪 Ganar músculo y fuerza",        callback_data="vida:ganar_musculo")],
        [InlineKeyboardButton("⚡ Bajar grasa Y ganar músculo",   callback_data="vida:recomposicion")],
        [InlineKeyboardButton("🍑 Glúteo y pierna",              callback_data="vida:gluteo_pierna")],
        [InlineKeyboardButton("🏃 Salud y energía",              callback_data="vida:salud")],
        [InlineKeyboardButton("🏆 Nivel competitivo",            callback_data="vida:powerlifting")],
    ])


def _kb_dieta(back_cb="ver_ayuda"):
    rows = [
        [InlineKeyboardButton("🍗 Como de todo",        callback_data="nut:omnivoro")],
        [InlineKeyboardButton("🥗 Trato de comer sano", callback_data="nut:saludable")],
        [InlineKeyboardButton("🌱 Vegetariano/vegano",  callback_data="nut:vegano")],
        [InlineKeyboardButton("🍖 Alta en proteína",    callback_data="nut:proteina")],
    ]
    if back_cb:
        rows.append([InlineKeyboardButton("← Atrás", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def _kb_horario(back_cb=None):
    rows = [
        [InlineKeyboardButton("🌅 6 AM", callback_data="horario:06:00"),
         InlineKeyboardButton("🌅 7 AM", callback_data="horario:07:00"),
         InlineKeyboardButton("🌅 8 AM", callback_data="horario:08:00")],
        [InlineKeyboardButton("☀️ 12 PM", callback_data="horario:12:00"),
         InlineKeyboardButton("🌆 5 PM",  callback_data="horario:17:00"),
         InlineKeyboardButton("🌆 6 PM",  callback_data="horario:18:00")],
        [InlineKeyboardButton("🌙 7 PM",  callback_data="horario:19:00"),
         InlineKeyboardButton("🌙 8 PM",  callback_data="horario:20:00"),
         InlineKeyboardButton("🌙 9 PM",  callback_data="horario:21:00")],
        [InlineKeyboardButton("❌ Sin recordatorio", callback_data="horario:none")],
    ]
    if back_cb:
        rows.append([InlineKeyboardButton("← Atrás", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


async def _send_onboarding(chat_id, context, text, kb):
    """Siempre manda mensaje nuevo para el onboarding. Nunca edita."""
    await context.bot.send_message(
        chat_id      = chat_id,
        text         = text,
        reply_markup = kb,
        parse_mode   = "HTML",
    )


def _kb_restricciones(sel: set) -> InlineKeyboardMarkup:
    def btn(emoji, label, key):
        mark = "☑️" if key in sel else "⬜"
        return InlineKeyboardButton(f"{mark} {emoji} {label}", callback_data=f"rtoggle:{key}")
    n = len(sel)
    confirmar = f"✅ Confirmar ({n} seleccionadas)" if n else "✅ Ninguna — continuar"
    return InlineKeyboardMarkup([
        [btn("🥛","Sin lácteos","lacteos"),    btn("🌾","Sin gluten","gluten")],
        [btn("🥜","Sin maní/frutos secos","frutos_secos"), btn("🥚","Sin huevo","huevo")],
        [btn("🦐","Sin mariscos","mariscos"),  btn("🐖","Sin cerdo","cerdo")],
        [btn("🌱","Vegano/vegetariano","vegano"), btn("🌽","Sin maíz","maiz")],
        [InlineKeyboardButton("✏️ Otra restricción...", callback_data="alerg:otra")],
        [InlineKeyboardButton(confirmar, callback_data="alerg:confirmar")],
        [InlineKeyboardButton("← Atrás", callback_data="nut:back")],
    ])


async def _generar_plan_gym(uid, query, context):
    """Genera el plan de gym y muestra confirmación."""
    await query.edit_message_text(
        "⚙️ <b>Creando tu plan...</b>\n<i>Unos segundos.</i>",
        parse_mode="HTML",
    )
    try:
        perfil = db.get_perfil(uid)
        import planner as pl
        plan = pl.generar_plan(
            nivel      = perfil.get("nivel", "intermedio"),
            objetivo   = perfil.get("objetivo", "general"),
            dias       = int(perfil.get("dias") or 4),
            ambiente   = perfil.get("ambiente_preferido", "gym"),
            limitacion = perfil.get("limitaciones", "ninguna"),
        )
        n_ej = db.insert_plan(uid, plan, db.get_swaps(uid))
        primera_sem = plan[0]["semana"]
        primer_dia  = plan[0]["dias"][0]["dia"]
        db.upsert_estado(uid, primera_sem, primer_dia)
        logger.info("Plan generado uid=%s: %d ejercicios, dia=%s", uid, n_ej, primer_dia)

        peso  = float(perfil.get("peso_kg_estimado") or 90)
        tdee  = int(perfil.get("tdee_estimado") or round(peso * 30))
        obj   = perfil.get("objetivo", "general")
        rec   = {
            "peso":   f"~{round(tdee*0.82)} kcal/día · {round(peso*2.2)}g proteína",
            "mamado": f"~{round(tdee*1.10)} kcal/día · {round(peso*2.2)}g proteína",
        }.get(obj, f"~{round(tdee*0.90)} kcal/día · {round(peso*2.2)}g proteína")

        await query.edit_message_text(
            f"✅ <b>Plan creado</b> — {n_ej} ejercicios · 4 semanas\n\n"
            f"💡 {rec}\n\n"
            f"<i>El plan de nutrición llega el domingo.</i>",
            parse_mode   = "HTML",
            reply_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("💪 Ver mi rutina", callback_data="menu:hoy")
            ]])
        )
        await context.bot.send_message(
            chat_id      = query.message.chat_id,
            text         = "Usa los botones 👇",
            reply_markup = ren.TECLADO_PERSISTENTE,
        )
    except Exception as e:
        logger.error("Error generando plan uid=%s: %s", uid, e, exc_info=True)
        await query.edit_message_text(
            f"❌ Error: {str(e)[:200]}\n\nEscribe /start para reintentar.",
        )


# ══════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid    = update.effective_user.id
    nombre = update.effective_user.first_name or ""
    db.clear_sesion_activa(uid)

    if not db.has_plan(uid):
        n = nombre.split()[0] if nombre else "ahí"
        await update.message.reply_text(
            f"Hola {n} 👋  Bienvenido a <b>Coach</b>\n\n"
            "💪 Rutina de gym con progresión automática\n"
            "⚖️ Análisis corporal diario desde tu báscula\n"
            "🥗 Plan de nutrición semanal con IA\n\n"
            "<b>Empecemos — ¿cuál es tu objetivo?</b>",
            reply_markup = _kb_objetivos(),
            parse_mode   = "HTML",
        )
        return

    texto = await _menu_texto(uid, nombre)
    await update.message.reply_text(
        texto,
        reply_markup = ren.TECLADO_PERSISTENTE,
        parse_mode   = "HTML",
    )
    await update.message.reply_text(
        "¿Qué hacemos? 👇",
        reply_markup = ren.MENU_PRINCIPAL,
    )


async def cmd_reset_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    await update.message.reply_text(
        "¿Qué quieres cambiar?",
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💪 Nueva rutina de gym",  callback_data="reset:gym")],
            [InlineKeyboardButton("🥗 Nuevo plan de dieta",  callback_data="reset:dieta")],
            [InlineKeyboardButton("🔄 Los dos",              callback_data="reset:todo")],
            [InlineKeyboardButton("❌ Cancelar",             callback_data="menu:main")],
        ])
    )


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid   = update.effective_user.id
    token = db.create_login_token(uid)
    url   = f"{ren.WEB_URL}/auth?token={token}"
    await update.message.reply_text(
        "Toca para entrar a la web 👇\n<i>Válido 5 minutos.</i>",
        parse_mode   = "HTML",
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Entrar a Coach", url=url)
        ]])
    )


async def cmd_sethorario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    await update.message.reply_text("⏰ ¿A qué hora quieres tu recordatorio?",
                                    reply_markup=_kb_horario())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    await update.message.reply_text(
        "❓ <b>Comandos</b>\n\n"
        "<code>/start</code> — Menú principal\n"
        "<code>/login</code> — Entrar a la web\n"
        "<code>/sethorario</code> — Cambiar recordatorio\n"
        "<code>/reset_plan</code> — Cambiar rutina o dieta",
        parse_mode   = "HTML",
        reply_markup = ren.AYUDA_KB,
    )


async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Uso: /adduser <id>")
        return
    db.add_allowed_user(int(context.args[0]))
    await update.message.reply_text(f"✅ {context.args[0]} agregado.")


# ══════════════════════════════════════════════════════════════════════════════
# TEXT HANDLER (teclado persistente)
# ══════════════════════════════════════════════════════════════════════════════

async def handler_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    uid   = update.effective_user.id
    texto = (update.message.text or "").strip()

    BOTONES = {
        "💪 Rutina de hoy": "hoy",
        "⚖️ Mi cuerpo":     "cuerpo",
        "🥗 Mi dieta":      "dieta",
        "❓ Ayuda":          "ayuda",
    }

    if texto in BOTONES:
        accion  = BOTONES[texto]
        semana, dia = db.get_estado(uid)

        if accion == "hoy":
            sesion = db.get_sesion_activa(uid)
            if sesion and sesion["semana"] == semana and sesion["dia"] == dia:
                txt, kb = ren.render_ejercicio(uid, semana, dia, sesion["ej_idx"])
            else:
                txt, kb = ren.rutina_preview(uid, semana, dia)
            await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")

        elif accion == "cuerpo":
            import cuerpo as corp
            resumen = corp.get_resumen_cuerpo()
            if not resumen:
                await update.message.reply_text(
                    "⚖️ Sin pesajes aún.\nPésate en ayunas (6-9am).",
                    reply_markup=ren.BTN_MENU,
                )
            else:
                mimo  = resumen.get("estado_mimo") or "—"
                emoji = {"RECOMPOSICION":"🟣","CUTTING_LIMPIO":"🟢","CATABOLISMO":"🔴","ESTANCAMIENTO":"🟡"}.get(mimo,"⚪")
                kg_f  = resumen.get("kg_a_perder", 0)
                eta   = resumen.get("semanas_eta", 0)
                meta  = f"\nMeta 22%: faltan <b>{kg_f} kg</b> (~{eta} sem)" if kg_f and kg_f > 0 else ""
                await update.message.reply_text(
                    f"⚖️ <b>{resumen['fecha']}</b>  Score: {resumen['score']}/100\n"
                    f"{emoji} {mimo.replace('_',' ')}\n\n"
                    f"Peso: {resumen['peso_kg']} kg  |  Grasa: {resumen['grasa_pct']}%\n"
                    f"Músculo: {resumen['musculo_pct']}%  |  BMR: {resumen['bmr']} kcal"
                    f"{meta}",
                    parse_mode   = "HTML",
                    reply_markup = InlineKeyboardMarkup([[
                        InlineKeyboardButton("🌐 Ver tendencia →", url=f"{ren.WEB_URL}/cuerpo")
                    ]])
                )

        elif accion == "dieta":
            import nutricion as nut
            macros = nut.get_macros_hoy(user_id=uid)
            if not macros:
                await update.message.reply_text("🥗 Pésate para calcular tus macros.")
            else:
                nota = f"\n<i>{macros['nota']}</i>" if macros.get("nota") else ""
                await update.message.reply_text(
                    f"🥗 <b>Hoy</b>\n🔥 {macros['calorias']} kcal\n"
                    f"🥩 {macros['proteina']}g  🍞 {macros['carbs']}g  🥑 {macros['grasas']}g{nota}",
                    parse_mode   = "HTML",
                    reply_markup = InlineKeyboardMarkup([[
                        InlineKeyboardButton("🌐 Ver plan →", url=f"{ren.WEB_URL}/nutricion")
                    ]])
                )

        elif accion == "ayuda":
            await update.message.reply_text(
                "❓ <b>¿Qué necesitas?</b>\n\n"
                "<code>/start</code> — Menú\n"
                "<code>/login</code> — Entrar a la web\n"
                "<code>/sethorario</code> — Cambiar recordatorio\n"
                "<code>/reset_plan</code> — Nueva rutina o dieta",
                parse_mode   = "HTML",
                reply_markup = ren.AYUDA_KB,
            )
        return

    # Sesión activa esperando peso
    sesion = db.get_sesion_activa(uid)
    if sesion and sesion.get("fase") == "peso":
        try:
            peso = float(texto.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Solo el número. Ej: 45  (0 para saltar)")
            return
        semana, dia = sesion["semana"], sesion["dia"]
        idx = sesion["ej_idx"]
        rows = [r for r in db.get_ejercicios_dia(uid, semana, dia) if not r.get("es_cardio")]
        if idx < len(rows) and peso > 0:
            ej = rows[idx]
            db.save_peso(uid, ej["ejercicio_id"], semana, dia, peso,
                        ej.get("series"), ej.get("reps"))
        siguiente = idx + 1
        db.save_sesion_activa(uid, semana, dia, siguiente, "ejercicio")
        txt, kb = ren.render_ejercicio(uid, semana, dia, siguiente)
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")
        return

    # Onboarding: esperar texto para edad o peso
    step = context.user_data.get("onboard_step")

    if step == "edad":
        try:
            edad = int(texto.strip())
            if not (10 <= edad <= 100):
                raise ValueError
        except ValueError:
            await update.message.reply_text("Escribe solo el número de años. Ej: 28")
            return
        db.upsert_perfil(uid, edad=edad)
        # Pedir peso
        context.user_data["onboard_step"] = "peso"
        await update.message.reply_text(
            f"<b>Edad: {edad} años ✅</b>\n\n"
            "<b>¿Cuánto pesas?</b>\n\n"
            "Escribe tu peso en <b>kg</b> o <b>lbs</b>\n"
            "Ejemplos: <code>85</code> o <code>187 lbs</code>",
            parse_mode = "HTML",
            reply_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("← Atrás", callback_data="horario:back")
            ]])
        )
        return

    if step == "alerg_otra":
        extra = texto.strip()
        context.user_data["alerg_extra"] = extra
        context.user_data["onboard_step"] = None
        sel = context.user_data.get("alerg_sel", set())
        await update.message.reply_text(
            f"<b>Añadido: {extra} ✅</b>\n\n"
            "<b>¿Algo más que no puedas comer?</b>\n<i>Selecciona o confirma:</i>",
            parse_mode   = "HTML",
            reply_markup = _kb_restricciones(sel)
        )
        return

    if step == "peso":
        txt_raw = texto.strip().lower()
        try:
            if "lbs" in txt_raw or "lb" in txt_raw:
                peso = round(float(txt_raw.replace("lbs","").replace("lb","").strip()) * 0.453592, 1)
            else:
                peso = float(txt_raw.replace("kg","").replace(",",".").strip())
            if not (30 <= peso <= 300):
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "No entendí el peso. Escribe algo como <code>85</code> o <code>187 lbs</code>",
                parse_mode="HTML"
            )
            return
        db.upsert_perfil(uid, peso_kg_estimado=peso)
        perfil = db.get_perfil(uid)
        edad   = int(perfil.get("edad") or 30)
        sexo   = perfil.get("sexo", "hombre")
        altura = 175 if sexo == "hombre" else 163
        bmr    = round(10*peso + 6.25*altura - 5*edad + (5 if sexo=="hombre" else -161))
        tdee   = round(bmr * {"sedentario":1.2,"moderado":1.375,"activo":1.55}.get(
                    perfil.get("actividad_nivel","sedentario"), 1.2))
        db.upsert_perfil(uid, bmr_estimado=bmr, tdee_estimado=tdee)
        context.user_data["onboard_step"] = None
        await update.message.reply_text(
            f"<b>Peso: {peso} kg ✅</b>\n\nTu gasto estimado: <b>{tdee} kcal/día</b>\n\n"
            "<b>¿Cómo describes tu alimentación?</b>",
            parse_mode   = "HTML",
            reply_markup = _kb_dieta(back_cb=None)
        )
        return

    # Fallback
    nombre = update.effective_user.first_name or ""
    texto_m = await _menu_texto(uid, nombre)
    await update.message.reply_text(
        texto_m, reply_markup=ren.MENU_PRINCIPAL, parse_mode="HTML"
    )


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACK HANDLER
# ══════════════════════════════════════════════════════════════════════════════

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query  = update.callback_query
    data   = query.data or ""
    uid    = query.from_user.id
    nombre = query.from_user.first_name or ""

    if uid not in db.get_allowed_users():
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

    chat_id = query.message.chat_id

    try:
        # ── HELPERS LOCALES ───────────────────────────────────────────────────
        async def edit(text, kb=None, **kw):
            await query.edit_message_text(text, reply_markup=kb,
                                          parse_mode="HTML",
                                          disable_web_page_preview=True, **kw)

        async def onboard(text, kb):
            """Edit en el mismo mensaje — rápido e instantáneo."""
            await query.edit_message_text(
                text, reply_markup=kb, parse_mode="HTML",
                disable_web_page_preview=True,
            )

        # ── MENÚ PRINCIPAL ────────────────────────────────────────────────────
        if data.startswith("menu:"):
            accion = data.split(":")[1]

            if accion == "main":
                texto = await _menu_texto(uid, nombre)
                await edit(texto, ren.MENU_PRINCIPAL)

            elif accion == "hoy":
                sesion = db.get_sesion_activa(uid)
                if sesion and sesion["semana"] == semana and sesion["dia"] == dia:
                    txt, kb = ren.render_ejercicio(uid, semana, dia, sesion["ej_idx"])
                else:
                    txt, kb = ren.rutina_preview(uid, semana, dia)
                await edit(txt, kb)

            elif accion == "cuerpo":
                import cuerpo as corp
                resumen = corp.get_resumen_cuerpo()
                if not resumen:
                    await edit("⚖️ Sin pesajes aún.\nPésate en ayunas (6-9am).", ren.BTN_MENU)
                else:
                    mimo  = resumen.get("estado_mimo") or "—"
                    emoji = {"RECOMPOSICION":"🟣","CUTTING_LIMPIO":"🟢","CATABOLISMO":"🔴","ESTANCAMIENTO":"🟡"}.get(mimo,"⚪")
                    kg_f  = resumen.get("kg_a_perder", 0)
                    eta   = resumen.get("semanas_eta", 0)
                    meta  = f"\nMeta 22%: faltan <b>{kg_f} kg</b> (~{eta} sem)" if kg_f and kg_f > 0 else ""
                    await edit(
                        f"⚖️ <b>{resumen['fecha']}</b>  Score: {resumen['score']}/100\n"
                        f"{emoji} {mimo.replace('_',' ')}\n\n"
                        f"Peso: {resumen['peso_kg']} kg  |  Grasa: {resumen['grasa_pct']}%\n"
                        f"Músculo: {resumen['musculo_pct']}%  |  BMR: {resumen['bmr']} kcal{meta}",
                        InlineKeyboardMarkup([
                            [InlineKeyboardButton("🌐 Ver tendencia →", url=f"{ren.WEB_URL}/cuerpo")],
                            [InlineKeyboardButton("🏠 Menú", callback_data="menu:main")],
                        ])
                    )

            elif accion == "dieta":
                import nutricion as nut
                macros = nut.get_macros_hoy(user_id=uid)
                if not macros:
                    await edit("🥗 Pésate para calcular tus macros.", ren.BTN_MENU)
                else:
                    nota = f"\n<i>{macros['nota']}</i>" if macros.get("nota") else ""
                    await edit(
                        f"🥗 <b>Hoy</b>\n🔥 {macros['calorias']} kcal\n"
                        f"🥩 {macros['proteina']}g  🍞 {macros['carbs']}g  🥑 {macros['grasas']}g{nota}",
                        InlineKeyboardMarkup([
                            [InlineKeyboardButton("🌐 Ver plan →", url=f"{ren.WEB_URL}/nutricion")],
                            [InlineKeyboardButton("🔄 Regenerar", callback_data="dieta:regenerar")],
                            [InlineKeyboardButton("🏠 Menú",      callback_data="menu:main")],
                        ])
                    )

            elif accion == "nuevo":
                await edit(
                    "¿Qué quieres cambiar?",
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton("💪 Nueva rutina de gym",  callback_data="reset:gym")],
                        [InlineKeyboardButton("🥗 Nuevo plan de dieta",  callback_data="reset:dieta")],
                        [InlineKeyboardButton("🔄 Los dos",              callback_data="reset:todo")],
                        [InlineKeyboardButton("❌ Cancelar",             callback_data="menu:main")],
                    ])
                )
            return

        # ── RESET ─────────────────────────────────────────────────────────────
        if data.startswith("reset:"):
            tipo = data.split(":")[1]
            if tipo in ("gym", "todo"):
                db.clear_plan(uid)
                db.clear_sesion_activa(uid)
                await onboard(
                    "<b>Paso 1/8 — ¿Cuál es tu objetivo?</b>\n\nEl plan se ajusta completamente a esto:",
                    _kb_objetivos()
                )
            elif tipo == "dieta":
                await onboard("🥗 <b>¿Cómo describes tu alimentación?</b>", _kb_dieta())
            return

        # ── ONBOARDING — NOTA: todos usan onboard() que hace delete+send ──────

        # vida:back ANTES de vida:
        if data == "vida:back":
            await onboard(
                "<b>Paso 1/8 — ¿Cuál es tu objetivo?</b>\n\nEl plan se ajusta completamente a esto:",
                _kb_objetivos()
            )
            return

        if data.startswith("vida:"):
            objetivo_vida = data.split(":")[1]
            _, objetivo_gym = OBJETIVOS.get(objetivo_vida, ("", "general"))
            db.upsert_perfil(uid, objetivo=objetivo_gym, objetivo_vida=objetivo_vida)
            desc = OBJETIVOS.get(objetivo_vida, ("",))[0]
            await onboard(
                f"<b>Paso 2/8</b> — Objetivo: {desc} ✅\n\n<b>¿Cuánto tiempo llevas entrenando con pesas?</b>",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌱 Menos de 1 año — soy nuevo",     callback_data="niv:principiante")],
                    [InlineKeyboardButton("💪 1 a 3 años entrenando",          callback_data="niv:intermedio")],
                    [InlineKeyboardButton("🔥 Más de 3 años — nivel avanzado", callback_data="niv:avanzado")],
                    [InlineKeyboardButton("← Atrás",                            callback_data="vida:back")],
                ])
            )
            return

        # niv:back ANTES de niv:
        if data == "niv:back":
            perfil   = db.get_perfil(uid)
            obj_vida = perfil.get("objetivo_vida", "")
            desc     = OBJETIVOS.get(obj_vida, ("tu objetivo",))[0]
            await onboard(
                f"<b>Paso 2/8</b> — Objetivo: {desc} ✅\n\n<b>¿Cuánto tiempo llevas entrenando?</b>",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌱 Menos de 1 año — soy nuevo",     callback_data="niv:principiante")],
                    [InlineKeyboardButton("💪 1 a 3 años entrenando",          callback_data="niv:intermedio")],
                    [InlineKeyboardButton("🔥 Más de 3 años — nivel avanzado", callback_data="niv:avanzado")],
                    [InlineKeyboardButton("← Atrás",                            callback_data="vida:back")],
                ])
            )
            return

        if data.startswith("niv:"):
            nivel = data.split(":")[1]
            db.upsert_perfil(uid, nivel=nivel)
            await onboard(
                "<b>Paso 3/8 — ¿Tienes alguna lesión o limitación?</b>\n\n<i>El plan evita esos ejercicios.</i>",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Ninguna",                              callback_data="lim:ninguna")],
                    [InlineKeyboardButton("🦵 Rodilla — evitar sentadilla profunda", callback_data="lim:rodilla")],
                    [InlineKeyboardButton("🔙 Espalda baja — evitar peso muerto",   callback_data="lim:espalda")],
                    [InlineKeyboardButton("💪 Hombro — evitar press militar",       callback_data="lim:hombro")],
                    [InlineKeyboardButton("← Atrás",                                 callback_data="niv:back")],
                ])
            )
            return

        if data.startswith("lim:"):
            lim = data.split(":")[1]
            db.upsert_perfil(uid, limitaciones=lim)
            await onboard(
                "<b>Paso 4/8 — ¿Dónde entrenas?</b>",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏋️ Gimnasio — máquinas y barras", callback_data="amb:gym")],
                    [InlineKeyboardButton("🏠 Casa — peso corporal",          callback_data="amb:home")],
                    [InlineKeyboardButton("🦺 Casa con banda elástica",       callback_data="amb:band")],
                    [InlineKeyboardButton("← Atrás",                          callback_data="niv:back")],
                ])
            )
            return

        if data.startswith("amb:"):
            ambiente = data.split(":")[1]
            db.upsert_perfil(uid, ambiente_preferido=ambiente)
            await onboard(
                "<b>Paso 5/8 — ¿Cuántos días a la semana?</b>\n\n<i>4 días es el punto óptimo para la mayoría.</i>",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("3 días", callback_data="dias:3"),
                     InlineKeyboardButton("4 días", callback_data="dias:4")],
                    [InlineKeyboardButton("5 días", callback_data="dias:5"),
                     InlineKeyboardButton("6 días", callback_data="dias:6")],
                    [InlineKeyboardButton("← Atrás", callback_data="lim:back")],
                ])
            )
            return

        if data.startswith("dias:"):
            dias_s = data.split(":")[1]
            if dias_s == "back":
                perfil = db.get_perfil(uid)
                lim    = perfil.get("limitaciones", "ninguna")
                await onboard(
                    "<b>Paso 4/8 — ¿Dónde entrenas?</b>",
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏋️ Gimnasio", callback_data="amb:gym")],
                        [InlineKeyboardButton("🏠 Casa",      callback_data="amb:home")],
                        [InlineKeyboardButton("🦺 Banda",     callback_data="amb:band")],
                        [InlineKeyboardButton("← Atrás",      callback_data="niv:back")],
                    ])
                )
                return
            db.upsert_perfil(uid, dias=int(dias_s))
            await onboard(
                f"<b>Paso 6/8</b> — {dias_s} días ✅\n\n<b>⏰ ¿A qué hora quieres tu recordatorio?</b>",
                _kb_horario(back_cb="dias:back")
            )
            return

        if data.startswith("horario:"):
            hora_val = data.split(":")[1]
            hora     = None if hora_val == "none" else ":".join(data.split(":")[1:])
            db.upsert_perfil(uid, hora_recordatorio=hora)
            # Pedir edad exacta — el usuario escribe el número
            context.user_data["onboard_step"] = "edad"
            await onboard(
                "<b>Paso 7/9 — ¿Cuántos años tienes?</b>\n\n"
                "Escribe tu edad (ej: 28):",
                InlineKeyboardMarkup([[InlineKeyboardButton("← Atrás", callback_data="horario:back")]])
            )
            return

        if data.startswith("peso_est:"):
            peso = float(data.split(":")[1])
            db.upsert_perfil(uid, peso_kg_estimado=peso)
            perfil = db.get_perfil(uid)
            sexo   = perfil.get("sexo", "hombre")
            edad   = int(perfil.get("edad") or 30)
            altura = 175 if sexo == "hombre" else 163
            bmr    = round(10*peso + 6.25*altura - 5*edad + (5 if sexo=="hombre" else -161))
            act    = perfil.get("actividad_nivel", "sedentario")
            factor = {"sedentario":1.2,"moderado":1.375,"activo":1.55}.get(act, 1.2)
            tdee   = round(bmr * factor)
            db.upsert_perfil(uid, bmr_estimado=bmr, tdee_estimado=tdee)
            context.user_data["onboard_step"] = None
            await onboard(
                f"<b>Paso 9/9 — Casi listo</b>\n\nTu gasto estimado: <b>{tdee} kcal/día</b>\n\n"
                "<b>¿Cómo describes tu alimentación?</b>",
                _kb_dieta(back_cb=None)
            )
            return

        # nut:back ANTES de nut:
        if data == "nut:back":
            perfil = db.get_perfil(uid)
            peso   = float(perfil.get("peso_kg_estimado") or 90)
            await onboard(
                f"<b>Paso 8/8</b> — Peso: ~{peso}kg ✅\n\n<b>¿Cómo describes tu alimentación?</b>",
                _kb_dieta(back_cb=None)
            )
            return

        if data.startswith("nut:"):
            tipo = data.split(":")[1]
            desc = DIETAS.get(tipo, tipo)
            db.upsert_perfil(uid, tipo_dieta=tipo)
            context.user_data["alerg_sel"] = set()
            await onboard(
                f"<b>Dieta: {desc} ✅</b>\n\n"
                "<b>¿Hay algo que no puedas comer?</b>\n"
                "<i>Selecciona todo lo que aplique:</i>",
                _kb_restricciones(set())
            )
            return

        if data.startswith("rtoggle:"):
            item = data.split(":")[1]
            sel  = context.user_data.get("alerg_sel", set())
            if item in sel:
                sel.discard(item)
            else:
                sel.add(item)
            context.user_data["alerg_sel"] = sel
            await onboard(
                "<b>¿Hay algo que no puedas comer?</b>\n"
                "<i>Selecciona todo lo que aplique:</i>",
                _kb_restricciones(sel)
            )
            return

        if data == "alerg:otra":
            context.user_data["onboard_step"] = "alerg_otra"
            await onboard(
                "✏️ <b>Escribe tu restricción</b>\n\nEj: sin azúcar, sin soya, diabético",
                InlineKeyboardMarkup([[InlineKeyboardButton("← Atrás", callback_data="alerg:volver")]])
            )
            return

        if data == "alerg:volver":
            sel = context.user_data.get("alerg_sel", set())
            context.user_data["onboard_step"] = None
            await onboard(
                "<b>¿Hay algo que no puedas comer?</b>\n<i>Selecciona todo lo que aplique:</i>",
                _kb_restricciones(sel)
            )
            return

        if data == "alerg:confirmar":
            sel   = context.user_data.get("alerg_sel", set())
            extra = context.user_data.get("alerg_extra", "")
            todas = list(sel) + ([extra] if extra else [])
            alerg = ",".join(sorted(todas)) if todas else "ninguna"
            db.upsert_perfil(uid, alergias=alerg)
            await onboard(
                "Cuantame sobre tu alimentacion\n\n"
                "Cuantas comidas haces al dia?",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("1-2 comidas — ayuno intermitente", callback_data="comidas:ayuno")],
                    [InlineKeyboardButton("3 comidas normales",               callback_data="comidas:3")],
                    [InlineKeyboardButton("4-5 comidas pequenas",             callback_data="comidas:5")],
                    [InlineKeyboardButton("Sin horario fijo",                  callback_data="comidas:flexible")],
                ])
            )
            return

        if data.startswith("comidas:"):
            patron = data.split(":")[1]
            if patron == "back":
                sel = context.user_data.get("alerg_sel", set())
                await onboard(
                    "Hay algo que no puedas comer?",
                    _kb_restricciones(sel)
                )
                return
            db.upsert_perfil(uid, patron_comidas=patron)
            if patron == "ayuno":
                await onboard(
                    "Cual es tu ventana de comida?\n\nEl plan respeta tu protocolo.",
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton("12pm-8pm (16:8)", callback_data="ventana:16-8")],
                        [InlineKeyboardButton("1pm-7pm (18:6)",  callback_data="ventana:18-6")],
                        [InlineKeyboardButton("2pm-8pm",         callback_data="ventana:18-6b")],
                        [InlineKeyboardButton("<- Atras",         callback_data="comidas:back")],
                    ])
                )
            else:
                await onboard(
                    "A que hora es tu primera comida del dia?",
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton("Antes de las 8am",    callback_data="ventana:7am")],
                        [InlineKeyboardButton("8am - 10am",          callback_data="ventana:9am")],
                        [InlineKeyboardButton("10am - 12pm",         callback_data="ventana:11am")],
                        [InlineKeyboardButton("Despues del mediodia", callback_data="ventana:1pm")],
                        [InlineKeyboardButton("<- Atras",             callback_data="comidas:back")],
                    ])
                )
            return

        if data.startswith("ventana:"):
            val = data.split(":")[1]
            db.upsert_perfil(uid, primera_comida=val)
            await onboard(
                "Donde comes la mayoria de tus comidas?",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("Cocino en casa casi siempre",   callback_data="donde:casa")],
                    [InlineKeyboardButton("Mitad en casa, mitad fuera",    callback_data="donde:mixto")],
                    [InlineKeyboardButton("Como fuera o pido a domicilio", callback_data="donde:fuera")],
                    [InlineKeyboardButton("<- Atras",                       callback_data="comidas:back")],
                ])
            )
            return

        if data.startswith("donde:"):
            donde = data.split(":")[1]
            if donde == "back":
                await onboard(
                    "A que hora es tu primera comida?",
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton("Antes de las 8am",    callback_data="ventana:7am")],
                        [InlineKeyboardButton("8am - 10am",          callback_data="ventana:9am")],
                        [InlineKeyboardButton("10am - 12pm",         callback_data="ventana:11am")],
                        [InlineKeyboardButton("Despues del mediodia", callback_data="ventana:1pm")],
                        [InlineKeyboardButton("<- Atras",             callback_data="comidas:back")],
                    ])
                )
                return
            db.upsert_perfil(uid, donde_come=donde)
            await onboard(
                "Que tipo de cocina disfrutas mas?\n\n"
                "El plan usara recetas de tu cocina favorita.",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("Mexicana / Latina",         callback_data="cocina:mexicana")],
                    [InlineKeyboardButton("Italiana / Mediterranea",   callback_data="cocina:mediterranea")],
                    [InlineKeyboardButton("Asiatica",                  callback_data="cocina:asiatica")],
                    [InlineKeyboardButton("Americana / Parrilla",      callback_data="cocina:americana")],
                    [InlineKeyboardButton("Variada — me gusta de todo",callback_data="cocina:variada")],
                    [InlineKeyboardButton("<- Atras",                   callback_data="donde:back")],
                ])
            )
            return

        if data == "cocina:back":
            await onboard(
                "Donde comes la mayoria de tus comidas?",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("Cocino en casa casi siempre",   callback_data="donde:casa")],
                    [InlineKeyboardButton("Mitad en casa, mitad fuera",    callback_data="donde:mixto")],
                    [InlineKeyboardButton("Como fuera o pido a domicilio", callback_data="donde:fuera")],
                ])
            )
            return


        if data.startswith("cocina:"):
            cocina = data.split(":")[1]
            db.upsert_perfil(uid, cocina_preferida=cocina)
            await onboard(
                "Tomas algun suplemento actualmente?\n\n"
                "Gemini lo considera en el plan nutricional.",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("Ninguno",              callback_data="suple:ninguno")],
                    [InlineKeyboardButton("Proteina whey",        callback_data="suple:whey")],
                    [InlineKeyboardButton("Creatina",             callback_data="suple:creatina")],
                    [InlineKeyboardButton("Proteina + Creatina",  callback_data="suple:whey_creatina")],
                    [InlineKeyboardButton("Multivitaminico",      callback_data="suple:multi")],
                    [InlineKeyboardButton("Otros suplementos",    callback_data="suple:otros")],
                    [InlineKeyboardButton("<- Atras",              callback_data="cocina:back")],
                ])
            )
            return


        if data.startswith("suple:"):
            suple = data.split(":")[1]
            if suple == "back":
                await onboard(
                    "Que tipo de cocina disfrutas mas?",
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton("Mexicana / Latina",         callback_data="cocina:mexicana")],
                        [InlineKeyboardButton("Italiana / Mediterranea",   callback_data="cocina:mediterranea")],
                        [InlineKeyboardButton("Asiatica",                  callback_data="cocina:asiatica")],
                        [InlineKeyboardButton("Americana / Parrilla",      callback_data="cocina:americana")],
                        [InlineKeyboardButton("Variada",                   callback_data="cocina:variada")],
                    ])
                )
                return
            db.upsert_perfil(uid, suplementos=suple)
            await onboard(
                "Consumes alcohol?\n\n"
                "El alcohol tiene calorias que afectan la composicion corporal.",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("No consumo alcohol",             callback_data="alcohol:no")],
                    [InlineKeyboardButton("Ocasional — 1-2 veces al mes",  callback_data="alcohol:ocasional")],
                    [InlineKeyboardButton("Moderado — fines de semana",    callback_data="alcohol:moderado")],
                    [InlineKeyboardButton("Frecuente — varias veces/sem",  callback_data="alcohol:frecuente")],
                    [InlineKeyboardButton("<- Atras",                        callback_data="suple:back")],
                ])
            )
            return

        if data.startswith("alcohol:"):
            nivel = data.split(":")[1]
            db.upsert_perfil(uid, alcohol=nivel)
            await _generar_plan_gym(uid, query, context)
            return

        if data.startswith("alerg:"):
            alerg = data.split(":")[1]
            db.upsert_perfil(uid, alergias=alerg)
            # Generar plan directamente
            await _generar_plan_gym(uid, query, context)
            return

        # ── DIETA REGENERAR ───────────────────────────────────────────────────
        if data == "dieta:regenerar":
            await onboard("🥗 <b>¿Cómo describes tu alimentación?</b>", _kb_dieta())
            return

        # ── EJERCICIO POR EJERCICIO ───────────────────────────────────────────
        if data.startswith("ej_start:"):
            _, sem_s, dia_s = data.split(":")
            sem = int(sem_s)
            db.save_sesion_activa(uid, sem, dia_s, 0, "ejercicio")
            txt, kb = ren.render_ejercicio(uid, sem, dia_s, 0)
            await edit(txt, kb)
            return

        if data.startswith("ej_resume:"):
            _, sem_s, dia_s, idx_s = data.split(":")
            txt, kb = ren.render_ejercicio(uid, int(sem_s), dia_s, int(idx_s))
            await edit(txt, kb)
            return

        if data.startswith("ej_hecho:"):
            _, sem_s, dia_s, idx_s = data.split(":")
            sem = int(sem_s); idx = int(idx_s)
            db.save_sesion_activa(uid, sem, dia_s, idx+1, "ejercicio")
            txt, kb = ren.render_ejercicio(uid, sem, dia_s, idx+1)
            await edit(txt, kb)
            return

        if data.startswith("ej_done:"):
            _, sem_s, dia_s = data.split(":")
            sem = int(sem_s)
            db.clear_sesion_activa(uid)
            with db.get_db() as conn:
                conn.execute("UPDATE rutinas SET completado=1 WHERE user_id=? AND semana=? AND dia=?",
                             (uid, sem, dia_s))
            resultado = gam.procesar_fin_sesion(uid, sem, dia_s, "si", _grupo_del_dia(uid, sem, dia_s))
            msg_wow   = ren.msg_fin_sesion(resultado)
            kb_feed   = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔥 Sin reserva",    callback_data=f"sesion:{sem}:{dia_s}:0:5")],
                [InlineKeyboardButton("💪 Bien",           callback_data=f"sesion:{sem}:{dia_s}:2:3")],
                [InlineKeyboardButton("😌 Fácil",          callback_data=f"sesion:{sem}:{dia_s}:3:2")],
                [InlineKeyboardButton("😓 Muy cansado",    callback_data=f"sesion:{sem}:{dia_s}:2:4")],
            ])
            try:
                await edit(msg_wow + "\n\n<b>¿Cómo estuvo?</b>", kb_feed)
            except Exception:
                await context.bot.send_message(chat_id=chat_id,
                    text=msg_wow + "\n\n<b>¿Cómo estuvo?</b>",
                    reply_markup=kb_feed, parse_mode="HTML")
            return

        if data.startswith("sesion:"):
            parts  = data.split(":")
            sem, dia_s, rir, fatiga = int(parts[1]), parts[2], int(parts[3]), int(parts[4])
            db.save_progreso_sesion(uid, sem, dia_s, rir=rir, fatiga=fatiga)
            nueva_sem, nuevo_dia = db.avanzar_dia(uid, sem, dia_s)
            db.upsert_estado(uid, nueva_sem, nuevo_dia)
            racha = gam.get_racha(uid)
            kb_fin = InlineKeyboardMarkup([
                [InlineKeyboardButton("💪 Siguiente sesión", callback_data="menu:hoy")],
                [InlineKeyboardButton("🌐 Ver progreso →",   url=ren.WEB_URL)],
                [InlineKeyboardButton("🏠 Menú",            callback_data="menu:main")],
            ])
            fin_txt = f"💾 Guardado.{'  🔥 ' + str(racha) + ' días de racha' if racha >= 3 else ''}"
            try:
                await edit(fin_txt, kb_fin)
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text=fin_txt, reply_markup=kb_fin)
            return

        if data.startswith("sueño:"):
            _, sem_s, dia_s, horas_s = data.split(":")
            horas = float(horas_s)
            if horas > 0:
                db.upsert_perfil(uid, sueño_horas=horas)
            aviso = ""
            if horas and horas < 6:
                aviso = "\n\n⚠️ Menos de 6h afecta tu recuperación. Prioriza dormir hoy."
            racha = gam.get_racha(uid)
            try:
                await edit(
                    f"✅ Registrado.{aviso}\n\n"
                    f"{'🔥 ' + str(racha) + ' días — ' if racha >= 3 else ''}"
                    "El análisis llega esta noche 🧠",
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton("💪 Siguiente", callback_data="menu:hoy")],
                        [InlineKeyboardButton("🏠 Menú",      callback_data="menu:main")],
                    ])
                )
            except Exception:
                pass
            return

        # ── SWAP ─────────────────────────────────────────────────────────────
        if data.startswith("swp_ask:"):
            parts  = data.split(":")
            eid, sem_s, dia_s = parts[1], parts[2], parts[3]
            pagina = int(parts[4]) if len(parts) > 4 else 0
            perfil = db.get_perfil(uid)
            ej_row = db.fetchone("SELECT grupo, rol FROM rutinas WHERE user_id=? AND ejercicio_id=?", (uid, eid))
            if not ej_row:
                return
            alts = [
                {"id": e.id, "nombre": e.nombre, "emg_score": e.emg_score}
                for e in cat.CATALOG
                if e.grupo == ej_row["grupo"] and e.rol == ej_row["rol"]
                and e.id != eid and perfil.get("ambiente_preferido","gym") in e.ambiente
            ]
            txt, kb = ren.render_swap(eid, int(sem_s), dia_s, alts, pagina)
            await edit(txt, kb)
            return

        if data.startswith("swp_do:"):
            _, id_orig, id_nuevo, sem_s, dia_s = data.split(":")
            ej_new  = cat.BY_ID.get(id_nuevo)
            ej_orig = cat.BY_ID.get(id_orig)
            if ej_new and ej_orig:
                with db.get_db() as conn:
                    conn.execute(
                        "UPDATE rutinas SET ejercicio_id=?, ejercicio=?, patron=? WHERE user_id=? AND ejercicio_id=?",
                        (id_nuevo, ej_new.nombre, ej_new.patron, uid, id_orig)
                    )
                db.save_swap(uid, id_orig, id_nuevo, ej_orig.grupo, ej_orig.rol)
                sesion = db.get_sesion_activa(uid)
                if sesion:
                    txt, kb = ren.render_ejercicio(uid, int(sem_s), dia_s, sesion["ej_idx"])
                else:
                    txt, kb = ren.rutina_preview(uid, int(sem_s), dia_s)
                await edit(f"✅ {ej_new.nombre} reemplaza a {ej_orig.nombre}\n\n{txt}", kb)
            return

        if data.startswith("swp_cancel:"):
            _, sem_s, dia_s = data.split(":")
            sesion = db.get_sesion_activa(uid)
            if sesion:
                txt, kb = ren.render_ejercicio(uid, int(sem_s), dia_s, sesion["ej_idx"])
            else:
                txt, kb = ren.rutina_preview(uid, int(sem_s), dia_s)
            await edit(txt, kb)
            return

        # ── SKIP DAY ──────────────────────────────────────────────────────────
        if data.startswith("skip_day:"):
            _, sem_s, dia_s = data.split(":")
            db.clear_sesion_activa(uid)
            nueva_sem, nuevo_dia = db.avanzar_dia(uid, int(sem_s), dia_s)
            db.upsert_estado(uid, nueva_sem, nuevo_dia)
            texto_m = await _menu_texto(uid, nombre)
            await edit(f"Día saltado 👍\n\n{texto_m}", ren.MENU_PRINCIPAL)
            return

        # ── AYUDA ─────────────────────────────────────────────────────────────
        if data == "ver_ayuda":
            await edit(
                "❓ <b>¿Qué necesitas?</b>\n\n"
                "<code>/start</code> — Menú principal\n"
                "<code>/login</code> — Entrar a la web\n"
                "<code>/sethorario</code> — Cambiar recordatorio\n"
                "<code>/reset_plan</code> — Cambiar rutina o dieta",
                ren.AYUDA_KB
            )
            return

        if data == "ayuda:horario":
            await edit("⏰ ¿A qué hora quieres el recordatorio?", _kb_horario(back_cb="ver_ayuda"))
            return

        if data == "ayuda:login":
            token = db.create_login_token(uid)
            url   = f"{ren.WEB_URL}/auth?token={token}"
            await edit(
                "Toca para entrar 👇\n<i>Válido 5 minutos.</i>",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌐 Entrar", url=url)],
                    [InlineKeyboardButton("← Atrás",   callback_data="ver_ayuda")],
                ])
            )
            return

        if data == "ayuda:pausa":
            await edit(
                "✈️ <b>Pausa</b>\n\n¿Cuántos días?",
                InlineKeyboardMarkup([
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
            fecha = (datetime.now() + timedelta(days=dias)).strftime("%d/%m/%Y")
            db.execute("UPDATE usuarios SET hora_recordatorio=? WHERE user_id=?",
                       (f"PAUSA:{fecha}", uid))
            await edit(f"✈️ Pausa {dias} días — hasta {fecha}.\n/sethorario para reactivar.", ren.BTN_MENU)
            return

        if data.startswith("horario:"):
            parts = data.split(":")
            hora  = None if parts[1] == "none" else f"{parts[1]}:{parts[2]}" if len(parts) > 2 else parts[1]
            db.upsert_perfil(uid, hora_recordatorio=hora)
            msg = f"⏰ Recordatorio: <b>{hora}</b> ✅" if hora else "❌ Recordatorio desactivado"
            try:
                await edit(msg, ren.BTN_MENU)
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
            return

        logger.debug("Callback no manejado: %s", data)

    except Exception as e:
        err = str(e)
        if "Message is not modified" in err:
            return  # silencioso — contenido ya correcto
        logger.error("callback error [%s] uid=%s: %s", data, uid, e, exc_info=True)
        try:
            await context.bot.send_message(
                chat_id = chat_id,
                text    = f"❌ Error. Escribe /start para continuar.\n<code>{err[:100]}</code>",
                parse_mode = "HTML",
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRO
# ══════════════════════════════════════════════════════════════════════════════

def register(app: Application) -> None:
    allowed = db.get_allowed_users()
    logger.info("Usuarios permitidos: %s", allowed)
    logger.info("handlers.py version: 2026-06-05-v9")

    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("login",      cmd_login))
    app.add_handler(CommandHandler("sethorario", cmd_sethorario))
    app.add_handler(CommandHandler("reset_plan", cmd_reset_plan))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("adduser",    cmd_adduser))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler_texto))
