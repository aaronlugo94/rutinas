"""
personality.py — Voz del coach.

Tono: coach profesional mexicano. Directo, específico, sin drama.
Reglas:
  - Nunca frases de póster motivacional ("tú puedes", "sigue adelante")
  - Siempre concreto — si hay un dato, úsalo
  - Máximo 1 emoji por mensaje, a veces ninguno
  - Habla como si conocieras a la persona, no como anuncio
  - El humor viene de la honestidad, no de exclamaciones
"""
from __future__ import annotations
import random


# ══════════════════════════════════════════════════════════════════════════════
# ONBOARDING
# ══════════════════════════════════════════════════════════════════════════════

BIENVENIDA = """<b>GymCoach</b>

Rutinas basadas en ciencia, no en YouTube.

El plan se genera según tu objetivo, nivel y dónde entrenas. Se ajusta cada semana según cómo te fue la anterior — si progresaste, sube; si estás agotado/a, baja.

Cinco preguntas y listo."""


def bienvenida_objetivo(objetivo: str, genero: str = "") -> str:
    configs = {
        "mamado": (
            "Objetivo: hipertrofia máxima.\n\n"
            "PPL — Push/Pull/Legs. Frecuencia 2x por músculo por semana (Schoenfeld 2016). "
            "Volumen dentro del MAV de Israetel. Barras libres primero: press barra, "
            "dominadas con lastre, sentadilla libre, peso muerto.\n\n"
            "Cardio mínimo — 15 min zona 2. El exceso de cardio interfiere con la síntesis proteica."
        ),
        "gluteo": (
            "Objetivo: glúteo.\n\n"
            "El plan usa periodización ondulatoria — tres tipos de sesión que rotan "
            "(fuerza, hipertrofia, metabólico). El hip thrust va primero en cada sesión. "
            "Contreras (2015): activa el glúteo al 200% del máximo voluntario."
        ),
        "peso": (
            "Objetivo: pérdida de grasa.\n\n"
            "Fuerza + cardio zona 2. La zona 2 oxida grasa sin elevar cortisol — "
            "al contrario del HIIT intenso post-fuerza, que cataboliza músculo."
        ),
        "general": (
            "Objetivo: fuerza y estética.\n\n"
            "Pecho, espalda, hombros, piernas. Frecuencia 2x por músculo por semana "
            "(Schoenfeld 2016) — más efectivo que el bro split clásico."
        ),
    }
    return configs.get(objetivo, configs["general"])


# ══════════════════════════════════════════════════════════════════════════════
# SALUDOS DE INICIO DE SESIÓN
# ══════════════════════════════════════════════════════════════════════════════

def saludo_inicio(nombre: str, racha: int, genero: str,
                  grupo_hoy: str, rutinas_totales: int) -> str:
    n = nombre.split()[0] if nombre else ""

    if rutinas_totales == 0:
        return f"Primera sesión{', ' + n if n else ''}. Empieza con técnica, no con peso."

    grupo_msgs = {
        "gluteo": [
            "Hip thrust primero. Pausa 1 segundo arriba.",
            "Día de glúteo. Orden por activación — los compuestos antes que el aislamiento.",
            "Glúteo hoy. Si el peso se siente ligero, no lo es — reduce el RIR.",
        ],
        "pierna": [
            "Pierna hoy. Calienta bien las rodillas antes de cargar.",
            "Sentadilla o prensa primero, mientras tienes energía para la técnica.",
            "Día de pierna. El más exigente del plan — vale la pena hacerlo bien.",
        ],
        "empuje": [
            "Empuje hoy. Escápulas fijas durante todo el press.",
            "Pecho y hombros. Codos a 45° del cuerpo en el press — no perpendiculares.",
            "Empuje. Si el hombro molesta, avísame y ajusto.",
        ],
        "tiron": [
            "Tirón hoy. Piensa en jalar con los codos, no con las manos.",
            "Espalda y bíceps. Retracción escapular al final de cada rep.",
            "Día de tirón. El dorsal es el músculo que más cambia la silueta.",
        ],
        "core": [
            "Core hoy. Calidad sobre cantidad — 10 reps perfectas valen más que 30 rápidas.",
            "Core. La plancha que duele en el primer segundo no está bien hecha.",
        ],
        "cardio": [
            "Cardio hoy. Zona 2 significa que puedes hablar con normalidad.",
            "Si tienes que respirar por la boca para mantener el ritmo, baja la intensidad.",
        ],
    }

    racha_msgs = {
        range(3, 7):   f"{racha} días seguidos.",
        range(7, 14):  f"Semana completa de racha.",
        range(14, 30): f"{racha} días. Ya es hábito.",
        range(30, 999):f"{racha} días de racha.",
    }

    racha_str = ""
    for r, msg in racha_msgs.items():
        if racha in r:
            racha_str = f" {msg}"
            break

    base = random.choice(grupo_msgs.get(grupo_hoy, ["A trabajar."]))
    return f"{base}{racha_str}"


# ══════════════════════════════════════════════════════════════════════════════
# CELEBRACIONES AL TERMINAR
# ══════════════════════════════════════════════════════════════════════════════

def celebracion_rutina(rutinas_totales: int, racha: int, grupo: str,
                       progreso: str, genero: str, nombre: str = "") -> str:

    # Milestones específicos — solo cuando hay algo real que decir
    milestones = {
        1:   "Listo. Primera sesión registrada.\nMañana va a doler un poco — es normal. Significa que el músculo respondió.",
        10:  f"10 sesiones completadas.\nYa tienes datos suficientes para ver patrones — revisa tu volumen semanal.",
        25:  f"25 sesiones. Un mes de trabajo real.\nEn este punto el plan ya sabe cómo responde tu cuerpo.",
        50:  f"50 sesiones.\nPocos llegan aquí. La mayoría abandona antes del primer mes.",
        100: f"100 sesiones registradas.\nEso es más de lo que la mayoría hace en toda su vida de gym.",
    }

    if rutinas_totales in milestones:
        return milestones[rutinas_totales]

    # Progresión — el dato concreto importa más que el aplauso
    if progreso == "si":
        progreso_msgs = {
            "gluteo": [
                "Progresaste en glúteo. Ese es el único indicador que importa semana a semana.",
                "Más peso o más reps en glúteo. El estímulo mecánico aumentó — eso es crecimiento.",
            ],
            "pierna": [
                "Progresaste en pierna. La sentadilla o la prensa más cargada es fuerza real.",
                "Más carga en pierna esta semana. El músculo más grande del cuerpo está respondiendo.",
            ],
        }
        msgs = progreso_msgs.get(grupo, [
            "Progresaste. El peso o las reps subieron — eso es el objetivo.",
            "Más carga esta semana. La progresión compuesta funciona así.",
        ])
        return random.choice(msgs)

    # Racha notable
    if racha in (7, 14, 21, 30):
        return f"{racha} días seguidos. El plan está funcionando."

    # Default — simple y directo
    defaults = [
        "Sesión registrada.",
        "Listo. Descansa bien hoy — el músculo crece en recuperación, no en el gym.",
        "Hecho. La proteína post-entreno en los próximos 45 minutos.",
        "Completado. El EPOC va a mantener el metabolismo elevado las próximas horas.",
    ]
    return random.choice(defaults)


# ══════════════════════════════════════════════════════════════════════════════
# RESUMEN SEMANAL
# ══════════════════════════════════════════════════════════════════════════════

def resumen_semanal(semana: int, rutinas_completadas: int, rutinas_programadas: int,
                    racha: int, progresiones: int, grupo_principal: str,
                    genero: str, nombre: str = "", fatiga_promedio: float = 2.5) -> str:

    n   = nombre.split()[0] if nombre else ""
    pct = round(rutinas_completadas / max(rutinas_programadas, 1) * 100)

    # Evaluación honesta sin drama
    if pct == 100:
        eval_str = f"Semana {semana} completa — {rutinas_completadas}/{rutinas_programadas} sesiones."
    elif pct >= 75:
        eval_str = f"Semana {semana} — {rutinas_completadas}/{rutinas_programadas} sesiones."
    elif pct >= 50:
        eval_str = (
            f"Semana {semana} — {rutinas_completadas}/{rutinas_programadas} sesiones. "
            f"La mitad. Funciona, pero el plan está diseñado para {rutinas_programadas}."
        )
    else:
        faltaron = rutinas_programadas - rutinas_completadas
        eval_str = (
            f"Semana {semana} — {rutinas_completadas}/{rutinas_programadas} sesiones. "
            f"Faltaron {faltaron}. ¿Qué pasó? Si fue por tiempo o energía, puedo ajustar el plan."
        )

    # Progresiones
    if progresiones >= 3:
        prog_str = f"{progresiones} ejercicios con más carga que la semana anterior."
    elif progresiones == 1:
        prog_str = "1 ejercicio con progresión."
    elif progresiones == 0:
        prog_str = "Sin progresiones esta semana — la siguiente es la oportunidad."
    else:
        prog_str = f"{progresiones} progresiones registradas."

    # Fatiga
    if fatiga_promedio <= 2.0:
        fatiga_str = "Fatiga baja — puedes subir intensidad la siguiente semana."
    elif fatiga_promedio <= 3.0:
        fatiga_str = "Fatiga dentro del rango normal."
    elif fatiga_promedio <= 4.0:
        fatiga_str = "Fatiga alta — prioriza sueño y proteína este fin de semana."
    else:
        fatiga_str = "Fatiga crítica — la semana que viene baja el peso un 20% en todos los ejercicios."

    # Proyección específica por grupo
    proyecciones = {
        "gluteo": (
            f"Glúteo a semana {semana}: con esta frecuencia y progresión, "
            f"los cambios visibles suelen aparecer entre semana 6 y 8."
        ),
        "pierna": (
            f"La fuerza en pierna mejora rápido — en 4 semanas lo que hoy es tu peso de trabajo "
            f"va a ser tu calentamiento."
        ),
    }
    proy_str = proyecciones.get(grupo_principal, "")

    partes = [eval_str, prog_str, fatiga_str]
    if proy_str:
        partes.append(proy_str)

    return "\n".join(partes)


# ══════════════════════════════════════════════════════════════════════════════
# FATIGA
# ══════════════════════════════════════════════════════════════════════════════

FATIGA_MSGS = {
    1: "Fresco. Puedes subir la carga la siguiente sesión.",
    2: "Cansancio normal.",
    3: "Fatiga moderada. Si se repite dos veces seguidas ajusto el volumen.",
    4: (
        "Fatiga alta. Reduzco el volumen de tu próxima sesión.\n"
        "Duerme bien hoy — sin recuperación no hay adaptación."
    ),
    5: (
        "Fatiga crítica. Próxima sesión al 60% de carga.\n"
        "El sobreentrenamiento destruye músculo. No tiene sentido forzar."
    ),
}

def msg_fatiga(nivel: int, nombre: str = "") -> str:
    return FATIGA_MSGS.get(nivel, FATIGA_MSGS[3])


# ══════════════════════════════════════════════════════════════════════════════
# RIR
# ══════════════════════════════════════════════════════════════════════════════

RIR_MSGS = {
    0: "Sin reserva. Asegúrate de descansar bien hoy.",
    1: "RIR 1 — intensidad óptima para hipertrofia.",
    2: "RIR 2 — zona correcta. El músculo tuvo estímulo sin destruir el sistema nervioso.",
    3: "RIR 3 o más — el peso estaba ligero. Sube 5-10% la próxima vez.",
}

def msg_rir(rir: int) -> str:
    return RIR_MSGS.get(rir, RIR_MSGS[2])


# ══════════════════════════════════════════════════════════════════════════════
# TIPS CIENTÍFICOS — uno por ejercicio, sin exageración
# ══════════════════════════════════════════════════════════════════════════════

TIPS_POR_PATRON = {
    "puente_cadera": [
        "Pausa 1 segundo arriba con el glúteo contraído. Sin esa pausa pierdes parte del estímulo isométrico.",
        "Pies cerca del glúteo, no lejos. Cambia el ángulo de activación.",
        "Empuja con los talones. Si sientes más el cuádriceps, algo está mal con la posición.",
    ],
    "bisagra_cadera": [
        "La bisagra sale de la cadera — si duele la espalda baja, es técnica, no peso.",
        "Barra pegada al cuerpo durante todo el recorrido. Si se aleja, pierdes mecánica.",
        "Excéntrico 3 segundos bajando. La fase negativa es donde ocurre el mayor daño muscular útil.",
    ],
    "sentadilla": [
        "Rodillas que siguen la línea de los pies. Si colapsan hacia adentro, hay debilidad de glúteo medio.",
        "Profundidad mínima: muslos paralelos al suelo. Arriba de eso reduce el rango de activación.",
        "Pecho arriba. Si miras al suelo, la espalda se redondea bajo carga.",
    ],
    "desplante_unilateral": [
        "Torso adelante 15° activa más glúteo. Torso recto activa más cuádriceps. No es accidental.",
        "Rodilla delantera sobre el tobillo — si pasa de ahí, aumenta la carga en la articulación.",
        "Empuja con el talón de la pierna delantera al subir.",
    ],
    "press_horizontal": [
        "Codos a 45° del cuerpo, no perpendiculares. Así protege el manguito rotador bajo carga.",
        "Escápulas retraídas y fijas en el banco durante todo el movimiento.",
        "Excéntrico 3 segundos bajando — el músculo crece más en la fase negativa.",
    ],
    "jalon_vertical": [
        "El codo jala hacia el bolsillo, no la mano hacia abajo. Cambia qué músculo trabaja.",
        "El pecho va a buscar la barra. Si el torso no se mueve, el dorsal no termina el recorrido.",
    ],
    "remo_horizontal": [
        "Escápulas juntas al final de cada rep. Sin eso el dorsal no termina el movimiento.",
        "Isométrico 1 segundo cuando las escápulas están juntas.",
    ],
    "abduccion": [
        "Movimiento lento y controlado. La inercia le quita trabajo al glúteo medio.",
        "Si sientes el TFL (lateral del muslo) más que el glúteo, ajusta el ángulo del pie.",
    ],
    "patada": [
        "Rodilla semiflexionada activa más el glúteo que la pierna recta.",
        "No rotar la cadera hacia arriba — eso es compensación lumbar, no activación glútea.",
    ],
}

TIPS_GENERALES = [
    "Exhala en el esfuerzo, inhala al bajar. No aguantes la respiración bajo carga.",
    "El músculo crece en recuperación, no durante el entrenamiento. Sueño y proteína.",
    "Progresión doble: cuando llegas al máximo de reps del rango, sube el peso 2.5-5 kg.",
    "La técnica correcta con poco peso siempre vale más que técnica rota con mucho.",
]

def tip_para_patron(patron: str) -> str:
    msgs = TIPS_POR_PATRON.get(patron, TIPS_GENERALES)
    return random.choice(msgs)


# ══════════════════════════════════════════════════════════════════════════════
# GAMIFICACIÓN — sin fanfarria, datos concretos
# ══════════════════════════════════════════════════════════════════════════════

BADGES = {
    "primera_rutina":    ("", "Primera sesión",     ""),
    "racha_7":           ("", "7 días seguidos",    ""),
    "racha_14":          ("", "14 días seguidos",   ""),
    "racha_30":          ("", "30 días seguidos",   ""),
    "rutinas_10":        ("", "10 sesiones",        ""),
    "rutinas_25":        ("", "25 sesiones",        ""),
    "rutinas_50":        ("", "50 sesiones",        ""),
    "rutinas_100":       ("", "100 sesiones",       ""),
    "progresion_5":      ("", "5 progresiones",     ""),
    "gluteo_specialist": ("", "12 sesiones de glúteo", ""),
    "perfeccionista":    ("", "Semana completa",    ""),
}

def badge_html(key: str) -> str:
    if key not in BADGES:
        return ""
    _, nombre, _ = BADGES[key]
    return f"· {nombre}"

def calcular_badges_nuevos(rutinas_totales: int, racha: int, progresiones_totales: int,
                           semanas_sin_deload: int, sesiones_gluteo: int,
                           semana_perfecta: bool) -> list[str]:
    earned = []
    checks = [
        ("primera_rutina",    rutinas_totales >= 1),
        ("racha_7",           racha >= 7),
        ("racha_14",          racha >= 14),
        ("racha_30",          racha >= 30),
        ("rutinas_10",        rutinas_totales >= 10),
        ("rutinas_25",        rutinas_totales >= 25),
        ("rutinas_50",        rutinas_totales >= 50),
        ("rutinas_100",       rutinas_totales >= 100),
        ("progresion_5",      progresiones_totales >= 5),
        ("gluteo_specialist", sesiones_gluteo >= 12),
        ("perfeccionista",    semana_perfecta),
    ]
    for key, cond in checks:
        if cond:
            earned.append(key)
    return earned


# ══════════════════════════════════════════════════════════════════════════════
# VISUALES — mínimos y funcionales
# ══════════════════════════════════════════════════════════════════════════════

def barra_progreso(completados: int, total: int, ancho: int = 10) -> str:
    pct    = completados / max(total, 1)
    llenos = round(pct * ancho)
    return f"{'█' * llenos}{'░' * (ancho - llenos)} {completados}/{total}"

def barra_racha(racha: int) -> str:
    if racha == 0:
        return "sin racha"
    return f"{racha} días"

def semaforo_volumen(series: int, opt_low: int, opt_high: int) -> str:
    if series == 0:              return "○"
    if series < opt_low:         return "↓"
    if series <= opt_high:       return "✓"
    if series <= opt_high * 1.3: return "↑"
    return "↑↑"

DELOAD_MSG = (
    "Semana de recuperación.\n\n"
    "Mismos ejercicios, 60% de la carga habitual. "
    "La súper-compensación — el fenómeno que produce el crecimiento real — "
    "ocurre durante el descanso. Esta semana es parte del plan, no una pausa."
)
