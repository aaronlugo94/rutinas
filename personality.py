"""
personality.py — El alma del bot.

Voz: mexicano con chispa, sin groserías, personalidad real.
Sistema: mensajes adaptativos por género, racha, fatiga, progresión y objetivo.
"""
from __future__ import annotations
import random
from dataclasses import dataclass


# ══════════════════════════════════════════════════════════════════════════════
# ONBOARDING — primera impresión
# ══════════════════════════════════════════════════════════════════════════════

BIENVENIDA = """🏆 <b>GymCoach — Tu entrenador personal con ciencia real</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

¿Sabes cuántos planes de gym se abandonan en la primera semana?
<b>El 92%.</b>

Los que sobreviven tienen algo en común: un plan que <i>realmente funciona</i>, progresión visible, y alguien que los entiende.

Eso soy yo. 🤝

✔ Rutinas basadas en EMG real (no YouTube, no broscience)
✔ Me adapto a ti cada semana según cómo te fue
✔ Modo gym y modo casa — sin pretextos
✔ Cardio que quema grasa sin destruir músculo

<i>5 preguntas · tu plan listo en 60 segundos</i>

<b>¿Empezamos?</b> 👇"""


def bienvenida_objetivo(objetivo: str, genero: str) -> str:
    configs = {
        ("gluteo", "mujer"): (
            "🍑", "Glúteo y pierna prioritarios",
            "Vamos por ese glúteo que hace voltear. Periodización ondulatoria, "
            "orden por activación EMG, cardio zona 2 que quema grasa sin tocar músculo.",
            "Contreras (2015) prueba que el hip thrust activa el glúteo al 200% del máximo voluntario. "
            "Eso es lo que vas a hacer."
        ),
        ("gluteo", "hombre"): (
            "💪", "Glúteo y pierna potentes",
            "Pierna fuerte es atleta fuerte. Sentadilla, RDL, prensa alta — lo que da resultados de verdad.",
            "El glúteo es el músculo más grande del cuerpo. Entrenarlo bien mejora TODO lo demás."
        ),
        ("peso", "mujer"): (
            "🔥", "Pérdida de grasa con músculo",
            "Déficit calórico + músculo preservado = cuerpo que envídian. No dieta de hambre, entrenamiento inteligente.",
            "Schoenfeld (2017): más músculo = mayor metabolismo basal 24/7. Así se quema grasa de verdad."
        ),
        ("peso", "hombre"): (
            "🔥", "Recomposición corporal",
            "Quemar grasa mientras mantienes (o ganas) músculo. El santo grial. Es posible con el plan correcto.",
            "Déficit moderado + proteína alta + entrenamiento de fuerza = la fórmula real."
        ),
        ("general", "mujer"): (
            "⚡", "Cuerpo tonificado y fuerte",
            "Fuerza funcional, tono muscular, energía todo el día. Nada de rutinas de 'musculitos'.",
            "Las mujeres que levantan pesado no se ponen grandes — se ponen fuertes y definidas."
        ),
        ("general", "hombre"): (
            "⚡", "Fuerza y estética completa",
            "Pecho, espalda, hombros, brazos, piernas. Un físico completo y equilibrado.",
            "Frecuencia 2× por músculo (Schoenfeld 2016) = el doble de resultados en el mismo tiempo."
        ),
    }
    key    = (objetivo, genero)
    emoji, titulo, desc, ciencia = configs.get(key, configs[("general", "hombre")])
    return (
        f"{emoji} <b>{titulo}</b>\n\n"
        f"{desc}\n\n"
        f"<i>🔬 {ciencia}</i>"
    )


# ══════════════════════════════════════════════════════════════════════════════
# MENSAJES DE INICIO DE SESIÓN
# Personalizados por racha, hora, historial reciente
# ══════════════════════════════════════════════════════════════════════════════

def saludo_inicio(nombre: str, racha: int, genero: str, grupo_hoy: str,
                  rutinas_totales: int) -> str:
    nombre_s = nombre.split()[0] if nombre else ""

    # Primera vez
    if rutinas_totales == 0:
        msgs = [
            f"{'¡Hola' if not nombre_s else f'¡Hola, {nombre_s}'}! Hoy empieza todo. "
            "El día 1 siempre es el más importante — es el que decide si habrá un día 2. 💚",
            f"Primera sesión. Esto es lo único que importa hoy: terminarla. "
            "No importa el peso, no importa si fue perfecta. Solo terminarla. 🌱",
        ]
        return random.choice(msgs)

    # Racha alta
    if racha >= 30:
        return (
            f"{'🏅 ' + nombre_s + ' — ' if nombre_s else '🏅 '}30+ días de racha. "
            "Eso no es motivación, eso es identidad. Ya eres alguien que entrena. 🔥"
        )
    if racha >= 14:
        return (
            f"{'💎 ' + nombre_s + ' — ' if nombre_s else '💎 '}{racha} días seguidos. "
            "2 semanas de consistencia. La mayoría ya abandonó. Tú no. 💪"
        )
    if racha >= 7:
        return (
            f"{'⚡ ' + nombre_s if nombre_s else '⚡'} — Semana completa de racha. "
            "Así se construyen los hábitos reales. ¿Vamos por la segunda? 🎯"
        )
    if racha >= 3:
        return (
            f"{'🌟 ' + nombre_s if nombre_s else '🌟'} — {racha} días seguidos. "
            "El momentum está contigo. No lo rompas hoy. 💚"
        )

    # Mensajes por grupo del día
    grupo_msgs = {
        "gluteo": [
            f"{'¡' + nombre_s + ', a' if nombre_s else 'A'} trabajar ese glúteo! 🍑 "
            "Hip thrust primero — es el rey del glúteo con razón.",
            "Día de glúteo. El ejercicio que más va a cambiar tu físico. Hazlo con intención. 🎯",
            f"{'¡Hoy toca glúteo' + (', ' + nombre_s) + '!' if nombre_s else '¡Hoy toca glúteo!'} "
            "Recuerda: pausa 1 segundo arriba en cada hip thrust. Eso es lo que hace la diferencia. 🍑",
        ],
        "pierna": [
            "Día de pierna. El más difícil. El que más vale. 🦵",
            f"{'¡Piernas, ' + nombre_s + '!' if nombre_s else '¡Día de piernas!'} "
            "El músculo más grande = el que más grasa quema. Vale la pena el dolor.",
            "Nadie que entrena piernas bien se arrepiente. Nadie que la salta tampoco — pero se nota. 🦵",
        ],
        "empuje": [
            f"{'¡' + nombre_s + ', h' if nombre_s else 'H'}oy empuje! Pecho, hombros y tríceps. "
            "Codos a 45° — no los abras, te lo juro que es la diferencia. 💪",
            "Día de empuje. Escápulas fijas, excéntrico lento. Así es como se construye músculo real. 💪",
        ],
        "tiron": [
            f"{'¡' + nombre_s + ', t' if nombre_s else 'T'}irón hoy! Espalda y bíceps. "
            "Piensa en jalar con los codos, no con las manos. Cambia todo. 🏋️",
            "Día de tirón. La espalda es lo primero que la gente nota — aunque no te digan nada. 🏋️",
        ],
    }
    msgs_grupo = grupo_msgs.get(grupo_hoy, [
        f"{'¡Vamos, ' + nombre_s + '!' if nombre_s else '¡Vamos!'} Hoy es día de sudar. 💪",
        "Otro día, otra oportunidad de superar a quien eras ayer. 🎯",
    ])
    return random.choice(msgs_grupo)


# ══════════════════════════════════════════════════════════════════════════════
# CELEBRACIONES AL TERMINAR RUTINA
# El momento más importante para retención
# ══════════════════════════════════════════════════════════════════════════════

def celebracion_rutina(
    rutinas_totales: int,
    racha: int,
    grupo: str,
    progreso: str,
    genero: str,
    nombre: str = "",
) -> str:
    nombre_s = nombre.split()[0] if nombre else ""

    # Milestones numéricos especiales
    if rutinas_totales == 1:
        return (
            "🌱 <b>¡PRIMERA RUTINA TERMINADA!</b>\n\n"
            "Este momento importa más de lo que crees.\n"
            "La mayoría nunca llega aquí.\n\n"
            "Tú sí llegaste. 💚\n\n"
            "<i>Mañana va a doler. Eso es el músculo creciendo. Es buena señal.</i>"
        )
    if rutinas_totales == 5:
        return (
            "🔥 <b>¡5 RUTINAS!</b>\n\n"
            "Una semana completa de trabajo real.\n"
            "Tu cuerpo ya está cambiando — aunque el espejo todavía no lo muestre.\n\n"
            "Los cambios internos (fuerza, metabolismo, densidad ósea) van primero. "
            "El espejo viene después. Confía en el proceso. 💪"
        )
    if rutinas_totales == 10:
        return (
            "💎 <b>¡10 RUTINAS COMPLETADAS!</b>\n\n"
            "Dos semanas de consistencia. Eso pone en el top 20% de la gente "
            "que alguna vez pagó un gym. En serio.\n\n"
            "Ya no eres 'alguien que quiere entrenar'.\n"
            "<b>Eres alguien que entrena.</b> 🏆"
        )
    if rutinas_totales == 25:
        return (
            "🏅 <b>¡25 RUTINAS!</b>\n\n"
            "Un mes de trabajo. Esto ya es un hábito real, no motivación.\n\n"
            "La motivación sube y baja. Los hábitos se quedan.\n"
            "Tú ya cruzaste esa línea. 🌟\n\n"
            "<i>¿Ya notas la diferencia en cómo te ves? ¿Cómo te mueves? "
            "¿Cómo duermes? Eso es real. Eso lo hiciste tú.</i>"
        )
    if rutinas_totales == 50:
        return (
            "👑 <b>¡50 RUTINAS!</b>\n\n"
            "Cincuenta veces elegiste entrenar sobre no hacerlo.\n"
            "Cincuenta veces ganaste.\n\n"
            "Eso no es suerte. Eso no es talento.\n"
            "<b>Eso es carácter.</b> 🏆💪🔥"
        )
    if rutinas_totales == 100:
        return (
            "🌟👑🏆 <b>¡100 RUTINAS!</b> 👑🌟🏆\n\n"
            "Cien. Uno-cero-cero.\n\n"
            "Eres oficialmente alguien diferente a quien empezó esto.\n"
            "Literalmente — tu cuerpo tiene más músculo, tu cerebro tiene "
            "nuevas conexiones neuronales, tu identidad cambió.\n\n"
            "Eso no lo hace casi nadie. Tú sí lo hiciste. 🔥"
        )

    # Celebraciones de racha
    if racha % 7 == 0 and racha > 0:
        semanas = racha // 7
        return (
            f"🎯 <b>¡{racha} DÍAS DE RACHA!</b> ({semanas} {'semana' if semanas == 1 else 'semanas'})\n\n"
            f"{'¡' + nombre_s + ', e' if nombre_s else 'E'}so es consistencia de élite.\n"
            "La mayoría rompe la racha en el día 3. Tú llevas {racha}. 💚\n\n"
            "<i>No rompas el eslabón mañana.</i> 🔗"
        )

    # Celebraciones por progreso
    if progreso == "si":
        msgs_progreso = {
            "gluteo": [
                "📈 <b>¡PROGRESASTE HOY!</b> 🍑\n\n"
                "Más peso en el hip thrust = más glúteo. Simple. Brutal. Efectivo.\n\n"
                "Cada kilo que subes es músculo nuevo que tu cuerpo está construyendo. "
                "Así funciona. 💚",
                "📈 <b>¡PROGRESIÓN CONFIRMADA!</b>\n\n"
                "El glúteo responde diferente al peso que a las reps.\n"
                "Hoy subiste la carga — eso es exactamente lo que prescribe Contreras. 🔬",
            ],
            "pierna": [
                "📈 <b>¡PROGRESASTE HOY!</b> 🦵\n\n"
                "Pierna más fuerte = cuerpo más fuerte. No hay atajos.\n"
                "Lo que hiciste hoy va a recompensar en todo lo demás. 💪",
            ],
        }
        msgs = msgs_progreso.get(grupo, [
            "📈 <b>¡PROGRESASTE HOY!</b>\n\n"
            f"{'¡' + nombre_s + ', s' if nombre_s else 'S'}ubiste peso o reps. "
            "Eso se llama progresión de carga — la base de todo cambio físico real.\n\n"
            "El músculo solo crece cuando le das un motivo. Hoy se lo diste. 💪",
            "📈 <b>¡MÁS FUERTE QUE LA SEMANA PASADA!</b>\n\n"
            "La progresión compuesta es magia. Sube 1kg por semana = "
            "+52kg al año. Eso es lo que está pasando. 🚀",
        ])
        return random.choice(msgs)

    # Celebración genérica (pero con personalidad)
    msgs_genericas = [
        f"✅ {'¡' + nombre_s + ', r' if nombre_s else 'R'}utina completada!\n\n"
        "Mientras tú entrenabas, alguien más estaba pensando en empezar mañana.\n"
        "Tú ya ganaste el día. 💚",

        f"✅ {'¡Bien hecho, ' + nombre_s + '!' if nombre_s else '¡Rutina completada!'}\n\n"
        "El cuerpo que quieres se construye con días como hoy — "
        "los que no tienes ganas pero lo haces de todos modos. 🎯",

        f"✅ <b>¡Listo!</b>\n\n"
        "Otra sesión en el banco. Otro ladrillo en el edificio.\n"
        "No se ve todavía — pero está ahí. Confía en el proceso. 🏗",

        "✅ <b>¡Sesión completada!</b> 💪\n\n"
        "Dato: tu cuerpo sigue quemando calorías extra las próximas 24-48h "
        "después de entrenar fuerza. Se llama EPOC.\n"
        "Literalmente ganas durmiendo hoy. 🔥",
    ]
    return random.choice(msgs_genericas)


# ══════════════════════════════════════════════════════════════════════════════
# RESUMEN SEMANAL — el momento WOW
# ══════════════════════════════════════════════════════════════════════════════

def resumen_semanal(
    semana: int,
    rutinas_completadas: int,
    rutinas_programadas: int,
    racha: int,
    progresiones: int,
    grupo_principal: str,
    genero: str,
    nombre: str = "",
    fatiga_promedio: float = 2.5,
) -> str:
    nombre_s   = nombre.split()[0] if nombre else ""
    pct        = round(rutinas_completadas / max(rutinas_programadas, 1) * 100)
    estrella   = "⭐" * min(5, max(1, rutinas_completadas))

    # Rating de la semana
    if pct == 100:
        rating = "💯 SEMANA PERFECTA"
        rating_msg = "Completaste TODO. Eso no es normal — eso es excepcional."
    elif pct >= 75:
        rating = "🔥 SEMANA SÓLIDA"
        rating_msg = f"3 de 4 rutinas. El músculo creció. La semana valió."
    elif pct >= 50:
        rating = "📊 SEMANA REGULAR"
        rating_msg = "La mitad. Funciona. Pero sabes que puedes más."
    else:
        rating = "⚠️ SEMANA DIFÍCIL"
        rating_msg = "Pasa. Lo que importa es la siguiente. No la perfecta — la constante."

    # Análisis de fatiga
    if fatiga_promedio <= 2:
        fatiga_msg = "Energía muy buena — puedes considerar subir intensidad la próxima semana."
    elif fatiga_promedio <= 3:
        fatiga_msg = "Fatiga óptima — el plan está calibrado perfecto para ti."
    elif fatiga_promedio <= 4:
        fatiga_msg = "Fatiga alta — descansa bien este fin de semana antes de la siguiente semana."
    else:
        fatiga_msg = "⚠️ Fatiga crítica detectada — semana que viene con carga reducida."

    # Mensaje de progresiones
    if progresiones >= 3:
        prog_msg = f"🚀 <b>{progresiones} ejercicios</b> con peso nuevo. Semana de crecimiento real."
    elif progresiones >= 1:
        prog_msg = f"📈 <b>{progresiones} progresión{'es' if progresiones > 1 else ''}</b> esta semana."
    else:
        prog_msg = "➡️ Sin progresiones esta semana — la siguiente es la oportunidad."

    # Proyección motivacional
    if grupo_principal == "gluteo":
        proyeccion = (
            "🍑 <b>Glúteo:</b> Con 3 sesiones/semana y progresión consistente, "
            "los cambios visibles llegan entre semana 4 y semana 8. "
            f"Vas en semana <b>{semana}</b>. Sigue."
        )
    elif grupo_principal == "pierna":
        proyeccion = (
            "🦵 <b>Pierna:</b> La fuerza en sentadilla y prensa mejora rápido. "
            "En 4 semanas vas a notar que lo que antes era pesado ahora es tu calentamiento."
        )
    else:
        proyeccion = (
            "💪 La consistencia semanal es lo único que predice resultados a largo plazo. "
            f"Vas {semana} semanas. El cambio ya está pasando — aunque no lo veas todavía."
        )

    return (
        f"📊 <b>RESUMEN SEMANA {semana}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{rating}\n"
        f"<i>{rating_msg}</i>\n\n"
        f"{'🏃 ' + nombre_s if nombre_s else '🏃'} "
        f"<b>{rutinas_completadas}/{rutinas_programadas}</b> rutinas completadas {estrella}\n"
        f"🔗 Racha actual: <b>{racha} días</b>\n"
        f"{prog_msg}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>Estado físico:</b> {fatiga_msg}\n\n"
        f"{proyeccion}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Próxima semana: mismo plan, más peso. Así funciona.</i> 🎯"
    )


# ══════════════════════════════════════════════════════════════════════════════
# MENSAJES DE FATIGA ALTA
# ══════════════════════════════════════════════════════════════════════════════

FATIGA_MSGS = {
    1: [
        "😊 Fresco como lechuga. Perfecto — así debería ser la mayoría de los días.",
        "💚 Energía al 100%. El cuerpo te lo agradece.",
    ],
    2: [
        "🙂 Cansancio leve. Eso es normal — significa que trabajaste.",
        "💚 Fatiga controlada. El plan está funcionando exactamente como debe.",
    ],
    3: [
        "😐 Fatiga moderada. Monitoreo activado — si se repite dos veces seguidas, ajusto la carga.",
        "⚡ Moderado. Descansa bien hoy — el músculo crece mientras duermes, no en el gym.",
    ],
    4: [
        "😓 Fatiga alta. Eso me dice que tu cuerpo necesita recuperación real.\n"
        "Prioridades: 8h de sueño, proteína, hidratación. La siguiente sesión la calibro.",
        "⚠️ Fatiga alta detectada. Reduzco el volumen de tu próxima sesión.\n"
        "No es retroceder — es inteligencia deportiva. Los mejores atletas descansan mejor, no más.",
    ],
    5: [
        "💀 Fatiga crítica. Esto es importante: el sobreentrenamiento destruye músculo.\n\n"
        "Próxima sesión al 60% de carga. Sin negociar. Tu cuerpo está gritando que necesita recuperarse.\n"
        "<i>Los mejores atletas del mundo priorizan el descanso tanto como el entrenamiento.</i>",
    ],
}


def msg_fatiga(nivel: int, nombre: str = "") -> str:
    nombre_s = nombre.split()[0] if nombre else ""
    msgs = FATIGA_MSGS.get(nivel, FATIGA_MSGS[3])
    msg  = random.choice(msgs)
    if nombre_s and nivel >= 4:
        msg = f"{'¡' + nombre_s + '! — ' if nombre_s else ''}{msg}"
    return msg


# ══════════════════════════════════════════════════════════════════════════════
# GAMIFICACIÓN — BADGES Y RACHAS
# ══════════════════════════════════════════════════════════════════════════════

BADGES = {
    "primera_rutina":   ("🌱", "Primera rutina",    "El inicio de todo"),
    "racha_3":          ("🔗", "3 días de racha",    "El hábito empieza aquí"),
    "racha_7":          ("⚡", "Semana completa",    "7 días seguidos"),
    "racha_14":         ("💎", "Dos semanas",        "Consistencia real"),
    "racha_30":         ("🏅", "Mes completo",       "Eres élite"),
    "rutinas_10":       ("🔥", "10 rutinas",         "Ya eres alguien que entrena"),
    "rutinas_25":       ("🌟", "25 rutinas",         "Un mes de trabajo"),
    "rutinas_50":       ("🏆", "50 rutinas",         "Mitad de año de disciplina"),
    "rutinas_100":      ("👑", "100 rutinas",        "Leyenda"),
    "progresion_5":     ("📈", "5 progresiones",     "El músculo está creciendo"),
    "sin_deload":       ("🔩", "4 semanas sin deload","Recuperación perfecta"),
    "gluteo_specialist":("🍑", "Glúteo Specialist",  "12 sesiones de glúteo completadas"),
    "perfeccionista":   ("💯", "Semana perfecta",    "100% de rutinas en una semana"),
}


def badge_html(key: str) -> str:
    if key not in BADGES:
        return ""
    emoji, nombre, desc = BADGES[key]
    return f"{emoji} <b>{nombre}</b>\n   <i>{desc}</i>"


def calcular_badges_nuevos(
    rutinas_totales: int,
    racha: int,
    progresiones_totales: int,
    semanas_sin_deload: int,
    sesiones_gluteo: int,
    semana_perfecta: bool,
) -> list[str]:
    """Retorna lista de badge keys que se deben otorgar ahora."""
    earned = []
    checks = [
        ("primera_rutina",    rutinas_totales >= 1),
        ("racha_3",           racha >= 3),
        ("racha_7",           racha >= 7),
        ("racha_14",          racha >= 14),
        ("racha_30",          racha >= 30),
        ("rutinas_10",        rutinas_totales >= 10),
        ("rutinas_25",        rutinas_totales >= 25),
        ("rutinas_50",        rutinas_totales >= 50),
        ("rutinas_100",       rutinas_totales >= 100),
        ("progresion_5",      progresiones_totales >= 5),
        ("sin_deload",        semanas_sin_deload >= 4),
        ("gluteo_specialist", sesiones_gluteo >= 12),
        ("perfeccionista",    semana_perfecta),
    ]
    for key, cond in checks:
        if cond:
            earned.append(key)
    return earned


# ══════════════════════════════════════════════════════════════════════════════
# BARRA DE PROGRESO VISUAL
# ══════════════════════════════════════════════════════════════════════════════

def barra_progreso(completados: int, total: int, ancho: int = 10) -> str:
    """Barra visual tipo [████████░░] con porcentaje."""
    pct    = completados / max(total, 1)
    llenos = round(pct * ancho)
    return f"[{'█' * llenos}{'░' * (ancho - llenos)}] {completados}/{total}"


def barra_racha(racha: int) -> str:
    """Visualización de racha con fuego."""
    if racha == 0:
        return "─── Sin racha aún"
    fuegos  = min(racha, 10)
    restante = max(0, 10 - fuegos)
    pct = min(racha, 10) * 10
    return f"{'🔥' * fuegos}{'·' * restante} {racha} días"


def semaforo_volumen(series: int, opt_low: int, opt_high: int) -> str:
    """🟢🟡🔴 para el volumen semanal."""
    if series == 0:               return "⚫"
    if series < opt_low:          return "🔴"
    if series <= opt_high:        return "🟢"
    if series <= opt_high * 1.3:  return "🟡"
    return "🔴"


# ══════════════════════════════════════════════════════════════════════════════
# COACH TIPS — consejos cortos entre ejercicios
# ══════════════════════════════════════════════════════════════════════════════

TIPS_POR_PATRON = {
    "puente_cadera": [
        "💡 Pies cerca del glúteo, no lejos. Entre más cerca, más activación.",
        "💡 Pausa 1s arriba con el glúteo apretado al máximo. Sin esa pausa, pierdes el 40% del estímulo.",
        "💡 Empuja con los talones, no con los dedos. Sientes la diferencia inmediatamente.",
    ],
    "bisagra_cadera": [
        "💡 La bisagra sale de la cadera, no de la espalda. Si duele la espalda, es técnica.",
        "💡 Barra (o mancuernas) pegadas al cuerpo todo el tiempo. Si se alejan, pierdes fuerza y arriesgas espalda.",
        "💡 Excéntrico 3 segundos bajando. Eso es donde ocurre el 60% del crecimiento muscular.",
    ],
    "sentadilla": [
        "💡 Rodillas siguen la línea de los pies. Si colapsan hacia adentro, glúteo débil — trabájalo.",
        "💡 Profundidad mínima: muslos paralelos al suelo. Arriba de eso es un cuarto de sentadilla.",
        "💡 Pecho arriba, mirada al frente. Si miras al suelo, la espalda se redondea.",
    ],
    "desplante_unilateral": [
        "💡 Torso adelante 15° = más glúteo. Torso recto = más cuádriceps. Elige.",
        "💡 Rodilla delantera sobre el tobillo. Si pasa el tobillo, estrés en la rodilla.",
        "💡 Empuja con el talón de la pierna delantera para subir. Así activa el glúteo.",
    ],
    "press_horizontal": [
        "💡 Codos a 45° del cuerpo — no perpendiculares. Así proteges el manguito rotador.",
        "💡 Escápulas retraídas y fijas en el banco durante todo el movimiento.",
        "💡 Excéntrico 3 segundos bajando. El músculo crece más en la fase negativa.",
    ],
    "jalon_vertical": [
        "💡 Piensa en jalar los codos hacia los bolsillos — no en jalar la barra.",
        "💡 El pecho va a buscar la barra, no al revés.",
        "💡 No balancees el torso. Si lo haces, estás usando inercia, no músculo.",
    ],
    "remo_horizontal": [
        "💡 Junta escápulas al final. Si no las juntas, el dorsal no termina el movimiento.",
        "💡 Codo pegado al cuerpo — no afuera. Cambiar de remo a trapecio.",
        "💡 Isométrico 1s cuando las escápulas están juntas. Eso marca la diferencia.",
    ],
}

TIPS_GENERALES = [
    "💡 Respira: exhala en el esfuerzo, inhala al bajar. No aguantes la respiración.",
    "💡 El músculo crece entre sesiones, no durante. Sueño + proteína = resultados.",
    "💡 RIR 2 significa 2 reps de reserva. Si puedes hacer 10 más, no estás trabajando.",
    "💡 La técnica perfecta con poco peso > técnica rota con mucho peso. Siempre.",
    "💡 Progresión doble: cuando llegues al máximo de reps, sube el peso 2.5-5kg.",
    "💡 El calentamiento no es opcional. Reduce lesiones y mejora el rendimiento real.",
]


def tip_para_patron(patron: str) -> str:
    msgs = TIPS_POR_PATRON.get(patron, TIPS_GENERALES)
    return random.choice(msgs)


# ══════════════════════════════════════════════════════════════════════════════
# RIR — mensajes contextuales
# ══════════════════════════════════════════════════════════════════════════════

RIR_CONTEXTO = {
    0: "🔥 Sin reserva — dejaste todo. Asegúrate de recuperarte bien hoy.",
    1: "💪 RIR 1 — intensidad óptima para hipertrofia. Exactamente donde debes estar.",
    2: "✅ RIR 2 — la zona dorada. Estimulas el músculo sin destruir el sistema nervioso.",
    3: "😌 RIR 3+ — demasiado fácil. La próxima vez sube el peso un 5-10%. El músculo necesita motivo para crecer.",
}


def msg_rir(rir: int) -> str:
    return RIR_CONTEXTO.get(rir, RIR_CONTEXTO[2])


# ══════════════════════════════════════════════════════════════════════════════
# DELOAD — mensaje de recuperación
# ══════════════════════════════════════════════════════════════════════════════

DELOAD_MSG = (
    "🔄 <b>SEMANA DE RECUPERACIÓN ACTIVA</b>\n\n"
    "Esto no es retroceder — es parte del plan.\n\n"
    "La súper-compensación (el fenómeno que te hace crecer) "
    "ocurre <i>durante</i> el descanso, no durante el entrenamiento.\n\n"
    "Esta semana: <b>mismos ejercicios, 60% de la carga</b>.\n"
    "Enfócate en técnica perfecta. Tu cuerpo va a agradecer esto "
    "con más fuerza la semana siguiente. Garantizado. 🔬"
)
