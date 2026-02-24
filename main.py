import os
import json
import html
import gspread
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Pon aquí tu ID de Telegram y el de ella. (Puedes hablarle a @userinfobot para saber sus IDs)
ALLOWED_USERS = {123456789, 987654321} 

def safe(text: str) -> str:
    """Escapa caracteres HTML para evitar que Telegram rompa el mensaje."""
    return html.escape(str(text), quote=True)

# --- CAPA DE DATOS (GOOGLE SHEETS) ---
def get_rutinas_desde_sheets(dia_solicitado: str) -> str:
    """Se conecta a Google Sheets, lee la rutina del día y genera el HTML."""
    try:
        creds_str = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        sheet_id = os.environ.get('SPREADSHEET_ID')
        
        if not creds_str or not sheet_id:
            return "❌ Error: Faltan variables de entorno de Google."

        creds_dict = json.loads(creds_str)
        scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly', 'https://www.googleapis.com/auth/drive.readonly']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
        client = gspread.authorize(creds)
        
        # Abrimos la hoja y traemos todos los datos como diccionarios
        sheet = client.open_by_key(sheet_id).sheet1
        datos = sheet.get_all_records()
        
        # Filtramos por día
        ejercicios_del_dia = [fila for fila in datos if str(fila.get('Día', '')).strip().lower() == dia_solicitado.lower()]
        
        if not ejercicios_del_dia:
            return f"Hoy ({dia_solicitado}) es día de descanso 🛋️ o no encontré la rutina."

        # Ordenamos por la columna 'Orden'
        ejercicios_del_dia.sort(key=lambda x: int(x.get('Orden', 99)))
        
        grupo_muscular = safe(ejercicios_del_dia[0].get('Grupo_Muscular', 'Entrenamiento'))
        
        # Construimos el HTML
        lineas = [f"🔥 <b>¡A darle con todo! Hoy toca {grupo_muscular}</b>\n"]
        
        for ex in ejercicios_del_dia:
            nombre = safe(ex.get('Ejercicio', 'Ejercicio'))
            url = ex.get('URL_Video', '').strip()
            series = safe(ex.get('Series_Reps', ''))
            notas = safe(ex.get('Notas', ''))
            
            if url:
                lineas.append(f"• <a href='{url}'>{nombre}</a> - {series}")
            else:
                lineas.append(f"• <b>{nombre}</b> - {series}")
                
            if notas:
                lineas.append(f"   <i>💡 {notas}</i>")
                
        lineas.append("\n💪 <i>¡Toca el nombre del ejercicio para ver el video!</i>")
        return "\n".join(lineas)
        
    except Exception as e:
        return f"❌ Error al leer la rutina: {e}"

# --- CAPA DE TELEGRAM (HANDLERS) ---
async def check_auth(update: Update) -> bool:
    """Valida que solo ustedes dos puedan usar el bot."""
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        if update.message:
            await update.message.reply_text("⛔ Lo siento, este bot es privado.")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update): return
    
    keyboard = [
        [InlineKeyboardButton("💪 Lunes", callback_data='lunes'), InlineKeyboardButton("🔥 Martes", callback_data='martes')],
        [InlineKeyboardButton("🍑 Miércoles", callback_data='miercoles'), InlineKeyboardButton("🏋️‍♀️ Jueves", callback_data='jueves')],
        [InlineKeyboardButton("🏃‍♀️ Viernes", callback_data='viernes')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "¡Hola mi amor! ❤️ ¿Lista para entrenar? Elige el día de hoy:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.from_user.id not in ALLOWED_USERS:
        await query.answer("No autorizado ⛔", show_alert=True)
        return
        
    await query.answer() # Evita que el botón se quede cargando
    
    dia_elegido = query.data
    rutina_html = get_rutinas_desde_sheets(dia_elegido)
    
    # Usamos edit_message_text para UX limpia (reemplaza el menú)
    await query.edit_message_text(
        text=rutina_html,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def gemini_coach_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja el texto libre usando a Gemini como coach."""
    if not await check_auth(update): return
    
    texto_usuario = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
        modelo = genai.GenerativeModel(
            'gemini-1.5-flash',
            system_instruction=(
                "Eres un entrenador personal virtual empático y directo. "
                "Tu objetivo es dar soporte rápido sobre dolores, fatiga o motivación en el gimnasio. "
                "REGLAS: "
                "1. Respuestas de máximo 3 oraciones. "
                "2. Si reporta dolor agudo, dile que pare. "
                "3. NO inventes rutinas. Si pide rutina, dile que use el comando /start y toque los botones."
            )
        )
        respuesta = modelo.generate_content(texto_usuario)
        await update.message.reply_text(respuesta.text)
    except Exception as e:
        await update.message.reply_text("Uf, estoy un poco cansado para pensar. Usa los botones por ahora ❤️")

# --- ARRANQUE DEL BOT ---
def main() -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("Error: No se encontró TELEGRAM_TOKEN")
        return

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    # Atrapa cualquier texto que no sea comando para mandarlo a Gemini
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gemini_coach_handler))

    print("Bot iniciando...")
    application.run_polling()

if __name__ == '__main__':
    main()
