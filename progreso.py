"""
progreso.py — Visualización de progreso de pesos.

Genera los mensajes de progresión por ejercicio y resumen global.
Sin gráficas externas — todo en texto ASCII dentro de Telegram.
"""
from __future__ import annotations
import html
import catalog as cat
import database as db


def safe(t: str) -> str:
    return html.escape(str(t))


# ══════════════════════════════════════════════════════════════════════════════
# BARRA ASCII — progresión visual sin librerías externas
# ══════════════════════════════════════════════════════════════════════════════

def _barra_ascii(valores: list[float], ancho: int = 12) -> list[str]:
    """
    Genera barras ASCII proporcionales al valor máximo.
    Retorna lista de strings, uno por valor.
    """
    if not valores:
        return []
    max_v = max(valores)
    if max_v == 0:
        return ["░" * ancho for _ in valores]
    barras = []
    for v in valores:
        filled = round((v / max_v) * ancho)
        barras.append("█" * filled + "░" * (ancho - filled))
    return barras


def _tendencia(valores: list[float]) -> str:
    """↑ sube · → igual · ↓ baja"""
    if len(valores) < 2:
        return ""
    diff = valores[-1] - valores[0]
    if diff > 0:
        return f"↑ +{diff:g} lbs"
    elif diff < 0:
        return f"↓ {diff:g} lbs"
    return "→ sin cambio"


# ══════════════════════════════════════════════════════════════════════════════
# PROGRESIÓN POR EJERCICIO
# ══════════════════════════════════════════════════════════════════════════════

def msg_progresion_ejercicio(user_id: int, ejercicio_id: str) -> str:
    """Mensaje con historial semana a semana de un ejercicio."""
    ej      = cat.BY_ID.get(ejercicio_id)
    nombre  = ej.nombre if ej else ejercicio_id
    hist    = db.get_progresion_ejercicio(user_id, ejercicio_id)

    if not hist:
        return f"<b>{safe(nombre)}</b>\n\n<i>Sin registros aún.</i>"

    pesos   = [float(r["mejor_peso"]) for r in hist]
    barras  = _barra_ascii(pesos, ancho=10)
    tendencia = _tendencia(pesos)

    lineas = [f"<b>{safe(nombre)}</b>", ""]
    for i, (row, barra) in enumerate(zip(hist, barras)):
        peso_str = f"{row['mejor_peso']:g} lbs"
        marker   = " ←" if i == len(hist) - 1 else ""
        lineas.append(f"S{row['semana']}  <code>{barra}</code>  {peso_str}{marker}")

    lineas += ["", f"<i>{tendencia}</i>"]

    # Sugerencia próxima sesión
    sug = db.get_peso_sugerido(user_id, ejercicio_id)
    if sug:
        lineas.append(f"Próxima sesión: <b>{sug} lbs</b>")

    return "\n".join(lineas)


# ══════════════════════════════════════════════════════════════════════════════
# LISTA DE EJERCICIOS CON HISTORIAL
# ══════════════════════════════════════════════════════════════════════════════

GRUPO_ICON = {
    "gluteo": "🍑", "pierna": "🦵", "empuje": "💪",
    "tiron": "🏋️", "core": "🎯", "cardio": "🏃",
}

def msg_lista_ejercicios(user_id: int) -> tuple[str, list[dict]]:
    """
    Lista todos los ejercicios con historial.
    Retorna (texto, lista_ejercicios) para construir los botones.
    """
    ejercicios = db.get_ejercicios_con_historial(user_id)

    if not ejercicios:
        return (
            "<b>Progreso de pesos</b>\n\n"
            "<i>Aún no hay registros.\n"
            "Completa tu primera sesión y registra los pesos.</i>",
            []
        )

    # Agrupar por grupo muscular
    grupos: dict[str, list[dict]] = {}
    for e in ejercicios:
        grupos.setdefault(e["grupo"], []).append(e)

    lineas = ["<b>Progreso de pesos</b>\n", "Toca un ejercicio para ver su historial:\n"]

    for grupo, ejs in grupos.items():
        icon = GRUPO_ICON.get(grupo, "💪")
        lineas.append(f"\n{icon} <b>{grupo.upper()}</b>")
        for e in ejs:
            n_sem    = e["semanas_registradas"]
            max_lbs  = f"{e['peso_maximo']:g}"
            resumen  = db.get_resumen_progresion(user_id)
            prog_ej  = resumen.get(e["ejercicio_id"])
            if prog_ej:
                diff = prog_ej["ultimo_peso"] - prog_ej["primer_peso"]
                flecha = f"  ↑+{diff:g}" if diff > 0 else ""
            else:
                flecha = ""
            lineas.append(
                f"  · {safe(e['ejercicio'][:28])}"
                f"  {max_lbs} lbs{flecha}"
                f"  <i>({n_sem} sem)</i>"
            )

    return "\n".join(lineas), ejercicios


# ══════════════════════════════════════════════════════════════════════════════
# RESUMEN GLOBAL — el "dashboard" en texto
# ══════════════════════════════════════════════════════════════════════════════

def msg_resumen_global(user_id: int) -> str:
    """
    Vista resumen: top progresiones, total de peso levantado, etc.
    """
    resumen   = db.get_resumen_progresion(user_id)
    ejercicios = db.get_ejercicios_con_historial(user_id)

    if not resumen and not ejercicios:
        return (
            "<b>Resumen de fuerza</b>\n\n"
            "<i>Registra pesos en al menos 2 semanas para ver tu progresión.</i>"
        )

    lineas = ["<b>Resumen de fuerza</b>\n"]

    # Top 5 progresiones absolutas
    if resumen:
        lineas.append("<b>Mayor progresión (lbs ganadas):</b>")
        top = sorted(resumen.values(),
                     key=lambda x: x["ultimo_peso"] - x["primer_peso"],
                     reverse=True)[:5]
        for r in top:
            ej     = cat.BY_ID.get(r["ejercicio_id"])
            nombre = ej.nombre[:28] if ej else r["ejercicio_id"]
            diff   = r["ultimo_peso"] - r["primer_peso"]
            lineas.append(
                f"  ↑ {safe(nombre)}"
                f"  {r['primer_peso']:g} → {r['ultimo_peso']:g} lbs"
                f"  <b>(+{diff:g})</b>"
            )

    # Pesos máximos actuales por grupo
    lineas.append("\n<b>Máximos actuales:</b>")
    por_grupo: dict[str, dict] = {}
    for e in ejercicios:
        grupo = e["grupo"]
        if grupo not in por_grupo or e["peso_maximo"] > por_grupo[grupo]["peso_maximo"]:
            por_grupo[grupo] = e
    for grupo, e in sorted(por_grupo.items()):
        icon   = GRUPO_ICON.get(grupo, "💪")
        nombre = e["ejercicio"][:24]
        lineas.append(f"  {icon} {safe(nombre)}: <b>{e['peso_maximo']:g} lbs</b>")

    # Total sesiones con pesos registrados
    total_registros = len(ejercicios)
    lineas.append(f"\n<i>{total_registros} ejercicios con historial</i>")

    return "\n".join(lineas)
