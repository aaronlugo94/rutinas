"""
gamification.py — Sistema de gamificación completo.

Racha de días, badges, XP, resumen semanal automático.
Cada función es pura o lee/escribe DB de forma aislada.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import database as db
import personality as p

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# RACHA DE DÍAS CONSECUTIVOS
# ══════════════════════════════════════════════════════════════════════════════

def get_racha(user_id: int) -> int:
    """Lee la racha guardada en DB."""
    row = db.fetchone(
        "SELECT racha_actual FROM gamificacion WHERE user_id=?", (user_id,)
    )
    return int(row["racha_actual"]) if row else 0


def actualizar_racha(user_id: int) -> tuple[int, bool]:
    """
    Actualiza la racha del usuario al terminar una sesión.
    Retorna (racha_nueva, es_nueva_racha_maxima).
    """
    row = db.fetchone(
        "SELECT racha_actual, racha_maxima, ultima_sesion FROM gamificacion WHERE user_id=?",
        (user_id,)
    )
    hoy = date.today()

    if not row:
        db.execute(
            "INSERT INTO gamificacion (user_id, racha_actual, racha_maxima, ultima_sesion, xp_total) "
            "VALUES (?,1,1,?,0)",
            (user_id, hoy.isoformat()),
        )
        return 1, True

    ultima = date.fromisoformat(row["ultima_sesion"]) if row["ultima_sesion"] else None
    racha_actual = int(row["racha_actual"] or 0)
    racha_max    = int(row["racha_maxima"] or 0)

    if ultima == hoy:
        # Ya entrenó hoy — no sumar racha doble
        return racha_actual, False

    if ultima == hoy - timedelta(days=1):
        # Consecutivo
        nueva_racha = racha_actual + 1
    else:
        # Rompió la racha
        nueva_racha = 1

    nueva_max  = max(racha_max, nueva_racha)
    es_record  = nueva_racha > racha_max

    db.execute(
        "UPDATE gamificacion SET racha_actual=?, racha_maxima=?, ultima_sesion=? WHERE user_id=?",
        (nueva_racha, nueva_max, hoy.isoformat(), user_id),
    )
    return nueva_racha, es_record


# ══════════════════════════════════════════════════════════════════════════════
# XP — SISTEMA DE PUNTOS
# ══════════════════════════════════════════════════════════════════════════════

XP_EVENTOS = {
    "sesion_completa":  50,
    "progresion":       25,
    "racha_7":         100,
    "racha_14":        200,
    "racha_30":        500,
    "semana_perfecta": 150,
    "badge":            75,
}

NIVELES_XP = [
    (0,    "🌱 Principiante"),
    (200,  "⚡ En Forma"),
    (500,  "💪 Consistente"),
    (1000, "🔥 Dedicado"),
    (2000, "💎 Avanzado"),
    (4000, "🏅 Élite"),
    (8000, "👑 Leyenda"),
]


def get_nivel(xp: int) -> str:
    nivel = NIVELES_XP[0][1]
    for min_xp, nombre in NIVELES_XP:
        if xp >= min_xp:
            nivel = nombre
    return nivel


def get_siguiente_nivel(xp: int) -> tuple[str, int, int]:
    """Retorna (nombre_siguiente, xp_actual_en_nivel, xp_para_siguiente)."""
    for i, (min_xp, nombre) in enumerate(NIVELES_XP):
        if xp < min_xp:
            prev_xp  = NIVELES_XP[i - 1][0] if i > 0 else 0
            return nombre, xp - prev_xp, min_xp - prev_xp
    # Ya en nivel máximo
    ultimo_xp = NIVELES_XP[-1][0]
    return "👑 Leyenda", xp - ultimo_xp, xp - ultimo_xp


def sumar_xp(user_id: int, evento: str, cantidad: int | None = None) -> int:
    puntos = cantidad if cantidad is not None else XP_EVENTOS.get(evento, 0)
    if not puntos:
        return get_xp(user_id)
    db.execute(
        "UPDATE gamificacion SET xp_total = xp_total + ? WHERE user_id=?",
        (puntos, user_id),
    )
    row = db.fetchone("SELECT xp_total FROM gamificacion WHERE user_id=?", (user_id,))
    return int(row["xp_total"]) if row else 0


def get_xp(user_id: int) -> int:
    row = db.fetchone("SELECT xp_total FROM gamificacion WHERE user_id=?", (user_id,))
    return int(row["xp_total"]) if row else 0


# ══════════════════════════════════════════════════════════════════════════════
# BADGES
# ══════════════════════════════════════════════════════════════════════════════

def otorgar_badge_si_nuevo(user_id: int, key: str) -> bool:
    """Otorga el badge si no lo tiene. Retorna True si es nuevo."""
    row = db.fetchone(
        "SELECT 1 FROM badges WHERE user_id=? AND badge_key=?", (user_id, key)
    )
    if row:
        return False
    db.execute(
        "INSERT INTO badges (user_id, badge_key) VALUES (?,?)", (user_id, key)
    )
    sumar_xp(user_id, "badge")
    return True


def get_badges(user_id: int) -> list[str]:
    rows = db.fetchall(
        "SELECT badge_key FROM badges WHERE user_id=? ORDER BY fecha", (user_id,)
    )
    return [r["badge_key"] for r in rows]


def badges_html(user_id: int) -> str:
    keys = get_badges(user_id)
    if not keys:
        return "<i>Aún sin badges — completa tu primera rutina 💚</i>"
    lines = []
    for key in keys:
        if key in p.BADGES:
            lines.append(p.badge_html(key))
    return "\n".join(lines) if lines else "<i>Sin badges aún</i>"


# ══════════════════════════════════════════════════════════════════════════════
# PROCESAR FIN DE SESIÓN — orquesta todo
# ══════════════════════════════════════════════════════════════════════════════

def procesar_fin_sesion(
    user_id: int,
    semana: int,
    dia: str,
    progresion: str,
    grupo: str,
) -> dict:
    """
    Llama esto cuando el usuario termina y confirma una sesión.
    Retorna dict con todo lo que el handler necesita mostrar.
    """
    perfil    = db.get_perfil(user_id)
    stats     = db.get_stats(user_id)
    nombre    = perfil.get("nombre", "")
    genero    = perfil.get("genero", "mujer")
    objetivo  = perfil.get("objetivo", "general")

    rutinas_totales = stats["rutinas_completas"]
    racha, es_record = actualizar_racha(user_id)

    xp_ganado = XP_EVENTOS["sesion_completa"]
    if progresion == "si":
        xp_ganado += XP_EVENTOS["progresion"]

    xp_total = sumar_xp(user_id, "sesion_completa", xp_ganado)
    nivel    = get_nivel(xp_total)

    # Evaluar badges
    sesiones_gluteo = _contar_sesiones_gluteo(user_id)
    progresiones_totales = _contar_progresiones(user_id)
    semana_perfecta = db.semana_completa(user_id, semana)

    candidatos = p.calcular_badges_nuevos(
        rutinas_totales      = rutinas_totales,
        racha                = racha,
        progresiones_totales = progresiones_totales,
        semanas_sin_deload   = semana,  # aproximación
        sesiones_gluteo      = sesiones_gluteo,
        semana_perfecta      = semana_perfecta,
    )
    badges_nuevos = [k for k in candidatos if otorgar_badge_si_nuevo(user_id, k)]
    if badges_nuevos and "semana_perfecta" in badges_nuevos:
        sumar_xp(user_id, "semana_perfecta")
        xp_ganado += XP_EVENTOS["semana_perfecta"]
    if racha in (7, 14, 30):
        key = f"racha_{racha}"
        xp_racha = XP_EVENTOS.get(key, 0)
        if xp_racha:
            sumar_xp(user_id, key, xp_racha)
            xp_ganado += xp_racha

    celeb = p.celebracion_rutina(
        rutinas_totales = rutinas_totales,
        racha           = racha,
        grupo           = grupo,
        progreso        = progresion,
        genero          = genero,
        nombre          = nombre,
    )

    siguiente_nivel, xp_en_nivel, xp_para_nivel = get_siguiente_nivel(xp_total)
    barra_xp = p.barra_progreso(xp_en_nivel, xp_para_nivel, ancho=10)

    return {
        "celebracion":   celeb,
        "racha":         racha,
        "es_record":     es_record,
        "xp_ganado":     xp_ganado,
        "xp_total":      xp_total,
        "nivel":         nivel,
        "siguiente":     siguiente_nivel,
        "barra_xp":      barra_xp,
        "badges_nuevos": badges_nuevos,
        "semana_perfecta": semana_perfecta,
    }


def _contar_sesiones_gluteo(user_id: int) -> int:
    row = db.fetchone(
        "SELECT COUNT(DISTINCT semana || dia) as n FROM rutinas "
        "WHERE user_id=? AND grupo='gluteo' AND completado=1",
        (user_id,)
    )
    return int(row["n"]) if row else 0


def _contar_progresiones(user_id: int) -> int:
    row = db.fetchone(
        "SELECT COUNT(*) as n FROM progreso "
        "WHERE user_id=? AND progreso_reportado='si'",
        (user_id,)
    )
    return int(row["n"]) if row else 0


# ══════════════════════════════════════════════════════════════════════════════
# RESUMEN SEMANAL COMPLETO
# ══════════════════════════════════════════════════════════════════════════════

def generar_resumen_semanal(user_id: int, semana: int) -> str:
    perfil  = db.get_perfil(user_id)
    nombre  = perfil.get("nombre", "")
    genero  = perfil.get("genero", "mujer")
    objetivo = perfil.get("objetivo", "general")

    dias  = db.get_dias_semana(user_id, semana)
    completadas   = sum(1 for d in dias if db.rutina_completa(user_id, semana, d))
    programadas   = len(dias)
    racha         = get_racha(user_id)
    xp_total      = get_xp(user_id)
    nivel         = get_nivel(xp_total)
    stats         = db.get_stats(user_id)
    progresiones  = _contar_progresiones_semana(user_id, semana)
    badges_user   = get_badges(user_id)

    # Fatiga promedio de la semana
    rows_fatiga = db.fetchall(
        "SELECT fatiga_reportada FROM progreso WHERE user_id=? AND semana=? AND fatiga_reportada IS NOT NULL",
        (user_id, semana)
    )
    fatigas = [int(r["fatiga_reportada"]) for r in rows_fatiga]
    fatiga_prom = sum(fatigas) / len(fatigas) if fatigas else 2.5

    # Grupo principal de la semana
    row_grupo = db.fetchone(
        "SELECT grupo, COUNT(*) as n FROM rutinas WHERE user_id=? AND semana=? "
        "GROUP BY grupo ORDER BY n DESC LIMIT 1",
        (user_id, semana)
    )
    grupo_principal = row_grupo["grupo"] if row_grupo else objetivo

    msg_base = p.resumen_semanal(
        semana            = semana,
        rutinas_completadas = completadas,
        rutinas_programadas = programadas,
        racha             = racha,
        progresiones      = progresiones,
        grupo_principal   = grupo_principal,
        genero            = genero,
        nombre            = nombre,
        fatiga_promedio   = fatiga_prom,
    )

    # XP y nivel
    _, xp_en_nivel, xp_para_nivel = get_siguiente_nivel(xp_total)
    barra_xp = p.barra_progreso(xp_en_nivel, xp_para_nivel, ancho=10)

    xp_block = (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>{nivel}</b>\n"
        f"   {barra_xp}\n"
        f"   <i>{xp_total} XP totales</i>"
    )

    # Badges
    badge_block = ""
    if badges_user:
        last_badges = badges_user[-3:]
        badge_lines = [p.badge_html(k) for k in last_badges if k in p.BADGES]
        if badge_lines:
            badge_block = (
                f"\n\n🏅 <b>Tus últimos badges:</b>\n"
                + "\n".join(badge_lines)
            )

    return msg_base + xp_block + badge_block


def _contar_progresiones_semana(user_id: int, semana: int) -> int:
    row = db.fetchone(
        "SELECT COUNT(*) as n FROM progreso "
        "WHERE user_id=? AND semana=? AND progreso_reportado='si'",
        (user_id, semana)
    )
    return int(row["n"]) if row else 0


# ══════════════════════════════════════════════════════════════════════════════
# STATS COMPLETOS — para /stats
# ══════════════════════════════════════════════════════════════════════════════

def stats_completos_html(user_id: int) -> str:
    perfil   = db.get_perfil(user_id)
    nombre   = perfil.get("nombre", "")
    stats    = db.get_stats(user_id)
    racha    = get_racha(user_id)
    xp_total = get_xp(user_id)
    nivel    = get_nivel(xp_total)
    badges_u = get_badges(user_id)

    row_gam  = db.fetchone(
        "SELECT racha_maxima FROM gamificacion WHERE user_id=?", (user_id,)
    )
    racha_max = int(row_gam["racha_maxima"]) if row_gam else racha

    _, xp_en_nivel, xp_para_nivel = get_siguiente_nivel(xp_total)
    barra_xp  = p.barra_progreso(xp_en_nivel, xp_para_nivel, ancho=10)
    barra_r   = p.barra_racha(racha)

    nombre_s = nombre.split()[0] if nombre else "Tú"

    lineas = [
        f"📊 <b>ESTADÍSTICAS — {nombre_s.upper()}</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"⚡ <b>{nivel}</b>",
        f"   {barra_xp}",
        f"   <i>{xp_total} XP · siguiente: {xp_para_nivel - xp_en_nivel} XP</i>",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"💪 Rutinas completadas: <b>{stats['rutinas_completas']}</b>",
        f"🔥 Racha actual:        <b>{barra_r}</b>",
        f"🏆 Racha máxima:        <b>{racha_max} días</b>",
        f"📈 Progresiones totales: <b>{_contar_progresiones(user_id)}</b>",
        "",
    ]

    if badges_u:
        lineas += ["━━━━━━━━━━━━━━━━━━━━━━━━", f"🏅 <b>Badges ({len(badges_u)})</b>", ""]
        for key in badges_u:
            if key in p.BADGES:
                lineas.append(p.badge_html(key))

    return "\n".join(lineas)
