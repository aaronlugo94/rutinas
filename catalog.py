"""
catalog.py — Catálogo científico completo.

Fuentes EMG y ciencia:
  - Contreras (2015): EMG glúteo — hip thrust 200% MVIC, sentadilla 130%
  - Schoenfeld (2010, 2017): hipertrofia, volumen óptimo, frecuencia
  - Nippard (2023): glute science, periodización ondulatoria
  - Bryanton (2012): activación glúteo vs profundidad sentadilla
  - ACSM (2021): prescripción ejercicio, zona 2 cardio

Tres ambientes:
  gym  — máquinas, barras, poleas, mancuernas
  home — peso corporal (sin equipo o equipo mínimo)
  band — banda elástica (subconjunto de home)

EMG score: activación relativa del músculo objetivo (% MVIC)
  5 = >150% MVIC  (elite — hip thrust con barra, RDL)
  4 = 100-150%    (alto — sentadilla profunda, búlgara)
  3 = 60-100%     (medio — desplante, puente con peso)
  2 = 30-60%      (bajo — aislamiento, abducción)
  1 = <30%        (mínimo — estabilización)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

Ambiente = Literal["gym", "home", "band"]
Grupo    = Literal["gluteo", "pierna", "empuje", "tiron", "core", "cardio"]
Rol      = Literal["principal", "secundario", "aislamiento",
                   "core_estabilidad", "core_dinamico", "cardio"]
Nivel    = Literal["principiante", "intermedio", "avanzado"]
Fatiga   = Literal["alta", "media", "baja"]


@dataclass(frozen=True)
class Ejercicio:
    id:          str
    nombre:      str
    grupo:       Grupo
    rol:         Rol
    patron:      str
    ambiente:    tuple[str, ...]
    emg_score:   int
    fatiga:      Fatiga = "baja"
    cue:         str    = ""
    nivel_min:   Nivel  = "principiante"
    musculo_sec: tuple[str, ...] = field(default_factory=tuple)
    equipo:      str    = ""

    def es_cardio(self)    -> bool: return self.grupo == "cardio"
    def es_gym(self)       -> bool: return "gym" in self.ambiente
    def es_home(self)      -> bool: return "home" in self.ambiente or "band" in self.ambiente
    def es_principal(self) -> bool: return self.rol == "principal"


_RAW: list[dict] = [

    # ═══════════════════════════════════════════════
    # GLÚTEO — GYM
    # EMG fuente: Contreras (2015), Nippard (2023)
    # ═══════════════════════════════════════════════
    dict(id="GLU_G01", nombre="Hip thrust con barra",
         grupo="gluteo", rol="principal", patron="puente_cadera",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="intermedio",
         cue="pausa 1s arriba, caderas neutras, no hiperlordosis",
         musculo_sec=("isquiotibial", "core"), equipo=""),

    dict(id="GLU_G02", nombre="Hip thrust en máquina",
         grupo="gluteo", rol="principal", patron="puente_cadera",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="principiante",
         cue="pies en plataforma alta, rodillas 90°, pausa 1s",
         musculo_sec=("isquiotibial",), equipo=""),

    dict(id="GLU_G03", nombre="Hip thrust con mancuerna en banco",
         grupo="gluteo", rol="principal", patron="puente_cadera",
         ambiente=("gym",), emg_score=4, fatiga="media", nivel_min="principiante",
         cue="mancuerna en cadera con toalla, espalda alta en banco",
         musculo_sec=("isquiotibial",), equipo=""),

    dict(id="GLU_G04", nombre="Peso muerto rumano con barra",
         grupo="gluteo", rol="principal", patron="bisagra_cadera",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="intermedio",
         cue="barra cerca del cuerpo, bisagra pura, rodillas suaves",
         musculo_sec=("isquiotibial", "lumbar"), equipo=""),

    dict(id="GLU_G05", nombre="Peso muerto rumano con mancuernas",
         grupo="gluteo", rol="principal", patron="bisagra_cadera",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="principiante",
         cue="mancuernas cerca del cuerpo, excéntrico 3s lento",
         musculo_sec=("isquiotibial",), equipo=""),

    dict(id="GLU_G06", nombre="Sentadilla búlgara con mancuernas",
         grupo="gluteo", rol="principal", patron="desplante_unilateral",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="avanzado",
         cue="torso inclinado 15° adelante = más glúteo, menos cuádríceps",
         musculo_sec=("cuadriceps", "core"), equipo=""),

    dict(id="GLU_G07", nombre="Prensa pierna pies altos y anchos",
         grupo="gluteo", rol="secundario", patron="prensa",
         ambiente=("gym",), emg_score=4, fatiga="media", nivel_min="principiante",
         cue="pies altos en plataforma, rango completo, rodillas afuera",
         musculo_sec=("isquiotibial",), equipo=""),

    dict(id="GLU_G08", nombre="Extensión de cadera en polea baja",
         grupo="gluteo", rol="aislamiento", patron="patada",
         ambiente=("gym",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="tobillera ajustada, contracción isométrica 1s al tope",
         musculo_sec=(), equipo=""),

    dict(id="GLU_G09", nombre="Abducción en máquina sentada",
         grupo="gluteo", rol="aislamiento", patron="abduccion",
         ambiente=("gym",), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="espalda recta, contracción sostenida, no rebotar",
         musculo_sec=("gluteo_medio",), equipo=""),

    dict(id="GLU_G10", nombre="Abducción en polea de pie",
         grupo="gluteo", rol="aislamiento", patron="abduccion",
         ambiente=("gym",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="pierna de apoyo suave, movimiento controlado hacia afuera",
         musculo_sec=("gluteo_medio",), equipo=""),

    dict(id="GLU_G11", nombre="Hip thrust a una pierna en banco",
         grupo="gluteo", rol="principal", patron="puente_cadera_unilateral",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="intermedio",
         cue="cadera sin rotación, contracción máxima arriba, pausa 1s",
         musculo_sec=("isquiotibial", "core"), equipo=""),

    dict(id="GLU_G12", nombre="Good morning con barra",
         grupo="gluteo", rol="secundario", patron="bisagra_cadera",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="avanzado",
         cue="barra alta en trapecios, bisagra de cadera pura, no squat",
         musculo_sec=("isquiotibial", "lumbar"), equipo=""),

    dict(id="GLU_G13", nombre="Curl femoral tumbada en máquina",
         grupo="gluteo", rol="aislamiento", patron="curl_femoral",
         ambiente=("gym",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="excéntrico 3s, no balancear caderas",
         musculo_sec=("isquiotibial",), equipo=""),

    dict(id="GLU_G14", nombre="Step-up en cajón alto",
         grupo="gluteo", rol="secundario", patron="desplante_unilateral",
         ambiente=("gym",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="cajón alto rodilla >90°, empujar con talón, glúteo activo",
         musculo_sec=("cuadriceps",), equipo=""),

    dict(id="GLU_G15", nombre="Sentadilla sumo con mancuerna",
         grupo="gluteo", rol="secundario", patron="sentadilla",
         ambiente=("gym",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="pies 45° afuera, profundidad máxima, rodillas siguen pies",
         musculo_sec=("cuadriceps", "aductores"), equipo=""),

    # ═══════════════════════════════════════════════
    # GLÚTEO — HOME (peso corporal)
    # ═══════════════════════════════════════════════
    dict(id="GLU_H01", nombre="Puente de glúteo en suelo",
         grupo="gluteo", rol="principal", patron="puente_cadera",
         ambiente=("home", "band"), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="pausa 2s arriba, apretar glúteo al máximo, talones cerca de glúteos",
         musculo_sec=("isquiotibial",), equipo="ninguno"),

    dict(id="GLU_H02", nombre="Puente de glúteo a una pierna",
         grupo="gluteo", rol="principal", patron="puente_cadera_unilateral",
         ambiente=("home", "band"), emg_score=4, fatiga="media", nivel_min="principiante",
         cue="cadera al nivel, pierna libre extendida, pausa 1s contracción",
         musculo_sec=("isquiotibial", "core"), equipo="ninguno"),

    dict(id="GLU_H03", nombre="Hip thrust con silla o sofá",
         grupo="gluteo", rol="principal", patron="puente_cadera",
         ambiente=("home",), emg_score=4, fatiga="media", nivel_min="principiante",
         cue="espalda alta en mueble, mochila con libros en cadera como lastre",
         musculo_sec=("isquiotibial",), equipo="silla o sofá"),

    dict(id="GLU_H04", nombre="Buenos días peso corporal",
         grupo="gluteo", rol="secundario", patron="bisagra_cadera",
         ambiente=("home", "band"), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="manos en nuca, bisagra de cadera, espalda neutra siempre",
         musculo_sec=("isquiotibial", "lumbar"), equipo="ninguno"),

    dict(id="GLU_H05", nombre="Peso muerto a una pierna sin peso",
         grupo="gluteo", rol="principal", patron="bisagra_cadera",
         ambiente=("home", "band"), emg_score=4, fatiga="media", nivel_min="intermedio",
         cue="cadera cuadrada, pierna trasera recta, foco en elongación glúteo",
         musculo_sec=("isquiotibial", "core"), equipo="ninguno"),

    dict(id="GLU_H06", nombre="Sentadilla búlgara peso corporal",
         grupo="gluteo", rol="principal", patron="desplante_unilateral",
         ambiente=("home",), emg_score=4, fatiga="alta", nivel_min="intermedio",
         cue="torso 15° adelante = glúteo, torso recto = cuádriceps. Elige.",
         musculo_sec=("cuadriceps",), equipo="silla o sofá"),

    dict(id="GLU_H07", nombre="Patada de glúteo en cuadrupedia",
         grupo="gluteo", rol="aislamiento", patron="patada",
         ambiente=("home", "band"), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="no rotar cadera, contracción 1s al tope, rodilla 90°",
         musculo_sec=(), equipo="ninguno"),

    dict(id="GLU_H08", nombre="Fire hydrant en cuadrupedia",
         grupo="gluteo", rol="aislamiento", patron="abduccion",
         ambiente=("home", "band"), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="rodilla 90°, rotar solo cadera, no compensar con lumbar",
         musculo_sec=("gluteo_medio",), equipo="ninguno"),

    dict(id="GLU_H09", nombre="Desplante reverso peso corporal",
         grupo="gluteo", rol="secundario", patron="desplante_unilateral",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="rodilla delantera sobre tobillo, torso recto, rodilla al suelo",
         musculo_sec=("cuadriceps",), equipo="ninguno"),

    dict(id="GLU_H10", nombre="Sentadilla sumo peso corporal",
         grupo="gluteo", rol="secundario", patron="sentadilla",
         ambiente=("home",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="pies 45°, profundidad máxima, rodillas siguen línea de pies",
         musculo_sec=("cuadriceps", "aductores"), equipo="ninguno"),

    # ═══════════════════════════════════════════════
    # GLÚTEO — BANDA ELÁSTICA
    # ═══════════════════════════════════════════════
    dict(id="GLU_B01", nombre="Puente de glúteo con banda en rodillas",
         grupo="gluteo", rol="principal", patron="puente_cadera",
         ambiente=("band",), emg_score=4, fatiga="media", nivel_min="principiante",
         cue="banda activa glúteo medio, rodillas empujan afuera durante todo el mov",
         musculo_sec=("gluteo_medio",), equipo="banda elástica"),

    dict(id="GLU_B02", nombre="Caminata lateral con banda",
         grupo="gluteo", rol="aislamiento", patron="abduccion",
         ambiente=("band",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="pasos laterales controlados, rodillas no colapsan hacia adentro",
         musculo_sec=("gluteo_medio",), equipo="banda elástica"),

    dict(id="GLU_B03", nombre="Abducción de cadera con banda de pie",
         grupo="gluteo", rol="aislamiento", patron="abduccion",
         ambiente=("band",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="banda en tobillos, pierna de apoyo suave, movimiento lateral lento",
         musculo_sec=("gluteo_medio",), equipo="banda elástica"),

    dict(id="GLU_B04", nombre="Clamshell con banda",
         grupo="gluteo", rol="aislamiento", patron="abduccion",
         ambiente=("band",), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="cadera estable, solo rota rodilla hacia arriba, pausa en tope",
         musculo_sec=("gluteo_medio", "rotadores_externos"), equipo="banda elástica"),

    dict(id="GLU_B05", nombre="Sentadilla con banda en rodillas",
         grupo="gluteo", rol="secundario", patron="sentadilla",
         ambiente=("band",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="la banda obliga a empujar rodillas afuera = recluta glúteo medio",
         musculo_sec=("cuadriceps", "gluteo_medio"), equipo="banda elástica"),

    dict(id="GLU_B06", nombre="Patada de glúteo con banda en cuadrupedia",
         grupo="gluteo", rol="aislamiento", patron="patada",
         ambiente=("band",), emg_score=4, fatiga="baja", nivel_min="principiante",
         cue="banda en pies, resistencia en toda la fase concéntrica",
         musculo_sec=(), equipo="banda elástica"),

    dict(id="GLU_B07", nombre="Hip thrust con banda anclada",
         grupo="gluteo", rol="principal", patron="puente_cadera",
         ambiente=("band",), emg_score=4, fatiga="media", nivel_min="principiante",
         cue="banda sobre cadera anclada en punto fijo, misma técnica que barra",
         musculo_sec=("isquiotibial",), equipo="banda elástica + anclaje"),


    # ═══════════════════════════════════════════════
    # GLÚTEO — HOME ADICIONAL (sin equipo absoluto)
    # Completa la cobertura sin ningún implemento
    # ═══════════════════════════════════════════════
    dict(id="GLU_H11", nombre="Sentadilla isométrica en pared glúteo",
         grupo="gluteo", rol="secundario", patron="sentadilla",
         ambiente=("home",), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="rodillas 90°, pausa 45s, glúteo apretado contra la pared",
         musculo_sec=("cuadriceps",), equipo="ninguno"),

    dict(id="GLU_H12", nombre="Puente de glúteo con pausa larga",
         grupo="gluteo", rol="principal", patron="puente_cadera",
         ambiente=("home",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="pausa 5s arriba, 15 reps lentas = más TUT que 30 reps rápidas",
         musculo_sec=("isquiotibial",), equipo="ninguno"),

    dict(id="GLU_H13", nombre="Sentadilla sumo con pausa abajo",
         grupo="gluteo", rol="secundario", patron="sentadilla",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="pausa 2s en el punto más bajo, talones empujan el suelo al subir",
         musculo_sec=("cuadriceps", "aductores"), equipo="ninguno"),

    dict(id="GLU_H14", nombre="Patada trasera de pie junto a pared",
         grupo="gluteo", rol="aislamiento", patron="patada",
         ambiente=("home",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="mano en pared para balance, rodilla semiflexionada, empuja talón atrás",
         musculo_sec=(), equipo="pared"),

    dict(id="GLU_H15", nombre="Abducción de cadera de pie junto a pared",
         grupo="gluteo", rol="aislamiento", patron="abduccion",
         ambiente=("home",), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="pierna de apoyo suave, empuja lateral sin inclinar el torso",
         musculo_sec=("gluteo_medio",), equipo="pared"),

    # ═══════════════════════════════════════════════
    # PIERNA — HOME ADICIONAL (sin equipo)
    # ═══════════════════════════════════════════════
    dict(id="PIE_H08", nombre="Sentadilla pistola asistida",
         grupo="pierna", rol="principal", patron="sentadilla",
         ambiente=("home",), emg_score=4, fatiga="alta", nivel_min="avanzado",
         cue="mano en pared para asistir, pierna libre extendida, profundidad máxima",
         musculo_sec=("gluteo",), equipo="pared"),

    dict(id="PIE_H09", nombre="Desplante lateral (curtsy lunge)",
         grupo="pierna", rol="secundario", patron="desplante_unilateral",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="intermedio",
         cue="pie cruza detrás, rodilla delantera sobre tobillo, glúteo activo",
         musculo_sec=("gluteo", "aductores"), equipo="ninguno"),

    dict(id="PIE_H10", nombre="Sentadilla con salto",
         grupo="pierna", rol="principal", patron="sentadilla",
         ambiente=("home",), emg_score=3, fatiga="alta", nivel_min="intermedio",
         cue="profundidad completa, salto explosivo, aterrizaje suave con rodillas dobladas",
         musculo_sec=("gluteo",), equipo="ninguno"),

    dict(id="PIE_H11", nombre="Desplante con rodilla al pecho",
         grupo="pierna", rol="secundario", patron="desplante_unilateral",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="de fondo, sube la rodilla trasera al pecho antes de volver",
         musculo_sec=("core", "gluteo"), equipo="ninguno"),

    dict(id="PIE_H12", nombre="Elevación de talón a una pierna sin apoyo",
         grupo="pierna", rol="aislamiento", patron="pantorrilla",
         ambiente=("home",), emg_score=3, fatiga="baja", nivel_min="intermedio",
         cue="sin apoyo = más inestabilidad = más activación, excéntrico 3s",
         musculo_sec=(), equipo="ninguno"),

    # ═══════════════════════════════════════════════
    # EMPUJE — HOME ADICIONAL (sin equipo)
    # ═══════════════════════════════════════════════
    dict(id="EMP_H09", nombre="Flexiones diamante",
         grupo="empuje", rol="secundario", patron="triceps",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="intermedio",
         cue="manos formando diamante, codos juntos al cuerpo, máximo tríceps",
         musculo_sec=("triceps",), equipo="ninguno"),

    dict(id="EMP_H10", nombre="Flexiones arquero",
         grupo="empuje", rol="principal", patron="press_horizontal",
         ambiente=("home",), emg_score=3, fatiga="alta", nivel_min="avanzado",
         cue="brazo extendido a un lado, carga en el otro — unilateral sin equipo",
         musculo_sec=("triceps",), equipo="ninguno"),

    dict(id="EMP_H11", nombre="Flexiones con pausa en el pecho",
         grupo="empuje", rol="principal", patron="press_horizontal",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="pausa 2s con pecho en suelo — elimina inercia, más estímulo real",
         musculo_sec=("triceps",), equipo="ninguno"),

    dict(id="EMP_H12", nombre="Pike push-up (hombro en piso)",
         grupo="empuje", rol="principal", patron="press_vertical",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="intermedio",
         cue="caderas elevadas, cabeza hacia el suelo, activa deltoides",
         musculo_sec=("triceps",), equipo="ninguno"),

    dict(id="EMP_H13", nombre="Flexión con rotación (renegade push-up)",
         grupo="empuje", rol="secundario", patron="press_horizontal",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="intermedio",
         cue="al subir rota el torso y extiende un brazo — pecho + core + hombro",
         musculo_sec=("core", "hombro_anterior"), equipo="ninguno"),

    dict(id="EMP_H14", nombre="Extensión de tríceps en suelo",
         grupo="empuje", rol="aislamiento", patron="triceps",
         ambiente=("home",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="codos apuntando al techo, baja la cabeza hacia el suelo, extensión completa",
         musculo_sec=(), equipo="ninguno"),

    # ═══════════════════════════════════════════════
    # TIRÓN — HOME ADICIONAL (sin equipo o pared)
    # ═══════════════════════════════════════════════
    dict(id="TIR_H08", nombre="Remo isométrico con toalla en puerta",
         grupo="tiron", rol="principal", patron="remo_horizontal",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="toalla en manija de puerta, inclínate atrás, tira con los codos",
         musculo_sec=("biceps",), equipo="toalla + puerta"),

    dict(id="TIR_H09", nombre="Superman con pausa extendida",
         grupo="tiron", rol="secundario", patron="hombro_posterior",
         ambiente=("home",), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="pausa 3s arriba con brazos en Y — activa trapecio y lumbar",
         musculo_sec=("lumbar", "gluteo"), equipo="ninguno"),

    dict(id="TIR_H10", nombre="Curl de bíceps con mochila",
         grupo="tiron", rol="aislamiento", patron="biceps",
         ambiente=("home",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="mochila con libros colgando, codos fijos, supinación al subir",
         musculo_sec=(), equipo="mochila"),

    dict(id="TIR_H11", nombre="Retracción escapular en suelo",
         grupo="tiron", rol="aislamiento", patron="hombro_posterior",
         ambiente=("home",), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="boca abajo, brazos en W, junta escápulas sin despegar el cuerpo",
         musculo_sec=("romboides",), equipo="ninguno"),

    dict(id="TIR_H12", nombre="Remo con mochila a una mano",
         grupo="tiron", rol="principal", patron="remo_horizontal",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="rodilla y mano libre en silla, mochila como mancuerna, codo a cadera",
         musculo_sec=("biceps",), equipo="mochila + silla"),

    # ═══════════════════════════════════════════════
    # CORE — HOME ADICIONAL
    # ═══════════════════════════════════════════════
    dict(id="COR_11", nombre="Plank shoulder tap",
         grupo="core", rol="core_estabilidad", patron="core_estabilidad",
         ambiente=("gym", "home"), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="toca hombro alterno sin rotar las caderas, core súper activo",
         musculo_sec=("hombro",), equipo="ninguno"),

    dict(id="COR_12", nombre="Pallof press isométrico con banda",
         grupo="core", rol="core_estabilidad", patron="core_estabilidad",
         ambiente=("band",), emg_score=3, fatiga="baja", nivel_min="intermedio",
         cue="banda lateral, extiende brazos sin rotar el torso — anti-rotación pura",
         musculo_sec=("oblicuos",), equipo="banda elástica + anclaje"),

    dict(id="COR_13", nombre="Crunch bicicleta",
         grupo="core", rol="core_dinamico", patron="core_dinamico",
         ambiente=("gym", "home"), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="codo al rodilla opuesta, lumbar en suelo, lento y controlado",
         musculo_sec=("oblicuos",), equipo="ninguno"),

    dict(id="COR_14", nombre="Plancha en movimiento (plank walk)",
         grupo="core", rol="core_dinamico", patron="core_dinamico",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="intermedio",
         cue="de codos a manos alternando, caderas estables, 10 reps c/lado",
         musculo_sec=("hombro", "core"), equipo="ninguno"),

    dict(id="COR_15", nombre="Suitcase carry isométrico",
         grupo="core", rol="core_estabilidad", patron="core_estabilidad",
         ambiente=("home",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="mochila en un lado, camine 20 pasos sin inclinar — anti-lateral puro",
         musculo_sec=("oblicuos", "gluteo_medio"), equipo="mochila"),

    # ═══════════════════════════════════════════════
    # CARDIO — HOME ADICIONAL (sin equipo)
    # ═══════════════════════════════════════════════
    dict(id="CAR_H06", nombre="Burpees a ritmo zona 2",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("home",), emg_score=2, fatiga="media", nivel_min="intermedio",
         cue="ritmo lento y controlado, zona 2 — NO máxima intensidad",
         musculo_sec=(), equipo="ninguno"),

    dict(id="CAR_H07", nombre="Danza o zumba libre",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("home",), emg_score=1, fatiga="baja",
         cue="cualquier canción, 20 min de movimiento, FC zona 2, lo más adherente",
         musculo_sec=(), equipo="ninguno"),

    dict(id="CAR_H08", nombre="Sombra de boxeo zona 2",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("home",), emg_score=1, fatiga="baja",
         cue="golpes suaves al aire, 3 min rounds, 1 min descanso, FC zona 2",
         musculo_sec=(), equipo="ninguno"),


    # ═══════════════════════════════════════════════
    # EJERCICIOS CLAVE QUE FALTABAN
    # Para un programa serio de hipertrofia
    # ═══════════════════════════════════════════════
    dict(id="TIR_G10", nombre="Dominadas con lastre",
         grupo="tiron", rol="principal", patron="jalon_vertical",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="avanzado",
         cue="lastre en cinturón, rango completo, excéntrico 3s controlado",
         musculo_sec=("biceps", "romboides"), equipo="cinturón de lastre"),

    dict(id="TIR_G11", nombre="Dominadas peso corporal",
         grupo="tiron", rol="principal", patron="jalon_vertical",
         ambiente=("gym", "home"), emg_score=5, fatiga="alta", nivel_min="intermedio",
         cue="agarre supino o prono, pecho al bar, escápulas activas",
         musculo_sec=("biceps",), equipo="barra de dominadas"),

    dict(id="TIR_G12", nombre="Remo Pendlay con barra",
         grupo="tiron", rol="principal", patron="remo_horizontal",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="avanzado",
         cue="torso paralelo al suelo, barra arranca del suelo cada rep, explosivo",
         musculo_sec=("biceps", "lumbar"), equipo=""),

    dict(id="TIR_G13", nombre="Remo con barra supino",
         grupo="tiron", rol="principal", patron="remo_horizontal",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="intermedio",
         cue="agarre supino más recluta bíceps, codos pegados al cuerpo",
         musculo_sec=("biceps",), equipo=""),

    dict(id="EMP_G10", nombre="Fondos en paralelas con lastre",
         grupo="empuje", rol="principal", patron="press_horizontal",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="avanzado",
         cue="torso ligeramente adelante para pecho, rango completo",
         musculo_sec=("triceps", "hombro_anterior"), equipo="cinturón de lastre"),

    dict(id="EMP_G11", nombre="Fondos en paralelas peso corporal",
         grupo="empuje", rol="principal", patron="press_horizontal",
         ambiente=("gym", "home"), emg_score=4, fatiga="alta", nivel_min="intermedio",
         cue="torso inclinado 20° para pecho, codos afuera controlado",
         musculo_sec=("triceps",), equipo="paralelas"),

    dict(id="PIE_G11", nombre="Peso muerto convencional con barra",
         grupo="pierna", rol="principal", patron="bisagra_cadera",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="avanzado",
         cue="barra sobre el mediopié, espalda neutra, empuja el suelo",
         musculo_sec=("gluteo", "isquiotibial", "lumbar", "core"), equipo=""),

    dict(id="PIE_G12", nombre="Peso muerto rumano con barra",
         grupo="pierna", rol="principal", patron="bisagra_cadera",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="intermedio",
         cue="barra cerca del cuerpo, bisagra pura, siente el estiramiento isquio",
         musculo_sec=("gluteo", "isquiotibial", "lumbar"), equipo=""),

    dict(id="PIE_G13", nombre="Sentadilla búlgara con barra",
         grupo="pierna", rol="principal", patron="desplante_unilateral",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="avanzado",
         cue="barra alta en trapecios, torso 15° adelante, isquio y glúteo",
         musculo_sec=("gluteo", "core"), equipo=""),

    dict(id="PIE_G14", nombre="Leg press pies altos y anchos",
         grupo="pierna", rol="secundario", patron="prensa",
         ambiente=("gym",), emg_score=4, fatiga="media", nivel_min="principiante",
         cue="pies altos = más glúteo e isquio, rodillas no colapsan",
         musculo_sec=("gluteo", "isquiotibial"), equipo=""),

    dict(id="EMP_G12", nombre="Press de pecho con barra",
         grupo="empuje", rol="principal", patron="press_horizontal",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="avanzado",
         cue="agarre 1.5x ancho de hombros, excéntrico 3s, codos 45°",
         musculo_sec=("triceps", "hombro_anterior"), equipo=""),

    dict(id="EMP_G13", nombre="Press inclinado con barra",
         grupo="empuje", rol="principal", patron="press_inclinado",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="avanzado",
         cue="banco 30°, mismo patrón que plano, foco porción clavicular",
         musculo_sec=("triceps", "hombro_anterior"), equipo=""),

    dict(id="EMP_G14", nombre="Press militar con barra de pie",
         grupo="empuje", rol="principal", patron="press_vertical",
         ambiente=("gym",), emg_score=5, fatiga="alta", nivel_min="avanzado",
         cue="core activo, glúteo apretado, empuja sobre la cabeza sin arco lumbar",
         musculo_sec=("triceps", "trapecio", "core"), equipo=""),

    # ═══════════════════════════════════════════════
    # PIERNA — GYM
    # ═══════════════════════════════════════════════
    dict(id="PIE_G01", nombre="Sentadilla libre con barra",
         grupo="pierna", rol="principal", patron="sentadilla",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="avanzado",
         cue="rodillas siguen pies, profundidad paralela mínima, pecho arriba",
         musculo_sec=("gluteo", "core", "isquiotibial"), equipo=""),

    dict(id="PIE_G02", nombre="Sentadilla en máquina Smith",
         grupo="pierna", rol="principal", patron="sentadilla",
         ambiente=("gym",), emg_score=3, fatiga="alta", nivel_min="principiante",
         cue="pies ligeramente adelante de la barra, espalda neutra",
         musculo_sec=("gluteo",), equipo=""),

    dict(id="PIE_G03", nombre="Prensa de pierna convencional",
         grupo="pierna", rol="principal", patron="prensa",
         ambiente=("gym",), emg_score=3, fatiga="alta", nivel_min="principiante",
         cue="pies al centro, rango completo sin bloquear rodillas arriba",
         musculo_sec=("gluteo",), equipo=""),

    dict(id="PIE_G04", nombre="Extensión de cuádriceps en máquina",
         grupo="pierna", rol="aislamiento", patron="extension_quad",
         ambiente=("gym",), emg_score=4, fatiga="baja", nivel_min="principiante",
         cue="contracción isométrica 1s arriba, excéntrico lento 3s",
         musculo_sec=(), equipo=""),

    dict(id="PIE_G05", nombre="Curl femoral tumbada en máquina",
         grupo="pierna", rol="aislamiento", patron="curl_femoral",
         ambiente=("gym",), emg_score=4, fatiga="media", nivel_min="principiante",
         cue="excéntrico lento 3s, no despegar caderas de la máquina",
         musculo_sec=("isquiotibial",), equipo=""),

    dict(id="PIE_G06", nombre="Sentadilla hack en máquina",
         grupo="pierna", rol="principal", patron="sentadilla",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="principiante",
         cue="pies juntos y bajos = más cuádriceps, pies altos = más glúteo",
         musculo_sec=("gluteo",), equipo=""),

    dict(id="PIE_G07", nombre="Elevación de talones de pie",
         grupo="pierna", rol="aislamiento", patron="pantorrilla",
         ambiente=("gym",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="rango completo, pausa 1s arriba, excéntrico lento 3s",
         musculo_sec=(), equipo=""),

    dict(id="PIE_G08", nombre="Desplante caminando con mancuernas",
         grupo="pierna", rol="secundario", patron="desplante_unilateral",
         ambiente=("gym",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="rodilla delantera sobre tobillo, paso largo, torso recto",
         musculo_sec=("gluteo",), equipo=""),

    dict(id="PIE_G09", nombre="Sentadilla goblet con mancuerna",
         grupo="pierna", rol="secundario", patron="sentadilla",
         ambiente=("gym",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="mancuerna al pecho, profundidad máxima, codos adentro",
         musculo_sec=("gluteo", "core"), equipo=""),

    dict(id="PIE_G10", nombre="Curl femoral de pie en máquina",
         grupo="pierna", rol="aislamiento", patron="curl_femoral",
         ambiente=("gym",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="cadera pegada a la máquina, no balancear el cuerpo",
         musculo_sec=(), equipo=""),

    # ═══════════════════════════════════════════════
    # PIERNA — HOME
    # ═══════════════════════════════════════════════
    dict(id="PIE_H01", nombre="Sentadilla peso corporal",
         grupo="pierna", rol="principal", patron="sentadilla",
         ambiente=("home",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="profundidad máxima, rodillas siguen pies, pecho arriba",
         musculo_sec=("gluteo",), equipo="ninguno"),

    dict(id="PIE_H02", nombre="Sentadilla con mochila de lastre",
         grupo="pierna", rol="principal", patron="sentadilla",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="mochila al pecho como goblet, carga progresiva semana a semana",
         musculo_sec=("gluteo",), equipo="mochila con peso"),

    dict(id="PIE_H03", nombre="Desplante reverso peso corporal",
         grupo="pierna", rol="secundario", patron="desplante_unilateral",
         ambiente=("home",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="rodilla trasera al suelo, torso recto, rodilla sobre tobillo",
         musculo_sec=("gluteo",), equipo="ninguno"),

    dict(id="PIE_H04", nombre="Sentadilla búlgara peso corporal",
         grupo="pierna", rol="principal", patron="desplante_unilateral",
         ambiente=("home",), emg_score=4, fatiga="alta", nivel_min="intermedio",
         cue="pie trasero en silla, torso ligeramente adelante para glúteo",
         musculo_sec=("gluteo",), equipo="silla"),

    dict(id="PIE_H05", nombre="Step-up en escalón o silla",
         grupo="pierna", rol="secundario", patron="desplante_unilateral",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="empujar con talón, glúteo activo al subir, escalón alto",
         musculo_sec=("gluteo",), equipo="escalón o silla resistente"),

    dict(id="PIE_H06", nombre="Elevación de talones en escalón",
         grupo="pierna", rol="aislamiento", patron="pantorrilla",
         ambiente=("home",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="rango completo, una pierna para más resistencia progresiva",
         musculo_sec=(), equipo="escalón"),

    dict(id="PIE_H07", nombre="Sentadilla isométrica en pared",
         grupo="pierna", rol="secundario", patron="sentadilla",
         ambiente=("home",), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="rodillas 90°, 30-60s, activa cuádriceps sin carga articular",
         musculo_sec=(), equipo="pared"),

    # ═══════════════════════════════════════════════
    # EMPUJE — GYM
    # ═══════════════════════════════════════════════
    dict(id="EMP_G01", nombre="Press de pecho con mancuernas",
         grupo="empuje", rol="principal", patron="press_horizontal",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="principiante",
         cue="codos 45° del torso, excéntrico 3s, escápulas fijas en banco",
         musculo_sec=("triceps", "hombro_anterior"), equipo=""),

    dict(id="EMP_G02", nombre="Press inclinado con mancuernas",
         grupo="empuje", rol="principal", patron="press_inclinado",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="principiante",
         cue="banco 30-45°, foco porción superior pecho, codos a 45°",
         musculo_sec=("triceps", "hombro_anterior"), equipo=""),

    dict(id="EMP_G03", nombre="Press en máquina de pecho",
         grupo="empuje", rol="principal", patron="press_horizontal",
         ambiente=("gym",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="rango completo, no bloquear codos al extender arriba",
         musculo_sec=("triceps",), equipo=""),

    dict(id="EMP_G04", nombre="Aperturas en polea cruzada",
         grupo="empuje", rol="aislamiento", patron="aislamiento_pecho",
         ambiente=("gym",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="movimiento de arco, codos ligeramente flexionados siempre",
         musculo_sec=(), equipo=""),

    dict(id="EMP_G05", nombre="Press de hombro con mancuernas sentado",
         grupo="empuje", rol="principal", patron="press_vertical",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="principiante",
         cue="codos 90° al inicio, empujar hacia arriba sin encogerse",
         musculo_sec=("triceps", "trapecio"), equipo=""),

    dict(id="EMP_G06", nombre="Elevaciones laterales con mancuernas",
         grupo="empuje", rol="aislamiento", patron="hombro_lateral",
         ambiente=("gym",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="codo ligeramente flexionado, sin inercia, tope al nivel del hombro",
         musculo_sec=(), equipo=""),

    dict(id="EMP_G07", nombre="Jalón de tríceps en polea alta",
         grupo="empuje", rol="aislamiento", patron="triceps",
         ambiente=("gym",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="codos fijos junto al cuerpo, extensión completa abajo",
         musculo_sec=(), equipo=""),

    dict(id="EMP_G08", nombre="Press Arnold con mancuernas",
         grupo="empuje", rol="principal", patron="press_vertical",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="intermedio",
         cue="rotación supina a pronada activa los 3 haces del deltoides",
         musculo_sec=("triceps",), equipo=""),

    dict(id="EMP_G09", nombre="Elevaciones laterales en polea baja",
         grupo="empuje", rol="aislamiento", patron="hombro_lateral",
         ambiente=("gym",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="tensión constante a diferencia de mancuerna (sin punto muerto)",
         musculo_sec=(), equipo=""),

    # ═══════════════════════════════════════════════
    # EMPUJE — HOME
    # ═══════════════════════════════════════════════
    dict(id="EMP_H01", nombre="Flexiones estándar",
         grupo="empuje", rol="principal", patron="press_horizontal",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="intermedio",
         cue="cuerpo recto, codos 45°, pecho toca el suelo en cada rep",
         musculo_sec=("triceps", "core"), equipo="ninguno"),

    dict(id="EMP_H02", nombre="Flexiones en rodillas",
         grupo="empuje", rol="principal", patron="press_horizontal",
         ambiente=("home",), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="espalda recta, rango completo, codos a 45° del cuerpo",
         musculo_sec=("triceps",), equipo="ninguno"),

    dict(id="EMP_H03", nombre="Flexiones con pies elevados en silla",
         grupo="empuje", rol="principal", patron="press_inclinado",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="intermedio",
         cue="pies altos = más pecho superior, core activo todo el tiempo",
         musculo_sec=("triceps", "hombro_anterior"), equipo="silla"),

    dict(id="EMP_H04", nombre="Fondos en banco para tríceps",
         grupo="empuje", rol="secundario", patron="triceps",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="codos atrás, no abrir al bajar, rango completo al bajar",
         musculo_sec=("pecho_inferior",), equipo="silla o banco"),

    dict(id="EMP_H05", nombre="Press de hombro con botellas o mochila",
         grupo="empuje", rol="principal", patron="press_vertical",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="movimiento controlado, peso en botellas de agua llenas",
         musculo_sec=("triceps",), equipo="botellas o mochila"),

    dict(id="EMP_H06", nombre="Elevaciones laterales con botellas",
         grupo="empuje", rol="aislamiento", patron="hombro_lateral",
         ambiente=("home",), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="botellas de agua como mancuernas, mismo patrón que gym",
         musculo_sec=(), equipo="botellas de agua"),

    dict(id="EMP_H07", nombre="Extensión de tríceps con banda sobre cabeza",
         grupo="empuje", rol="aislamiento", patron="triceps",
         ambiente=("band",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="codos fijos junto a la cabeza, extensión completa abajo",
         musculo_sec=(), equipo="banda elástica"),

    dict(id="EMP_H08", nombre="Press de hombro con banda",
         grupo="empuje", rol="principal", patron="press_vertical",
         ambiente=("band",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="banda bajo los pies, misma técnica que con mancuernas",
         musculo_sec=("triceps",), equipo="banda elástica"),

    # ═══════════════════════════════════════════════
    # TIRÓN — GYM
    # ═══════════════════════════════════════════════
    dict(id="TIR_G01", nombre="Jalón al pecho agarre ancho",
         grupo="tiron", rol="principal", patron="jalon_vertical",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="principiante",
         cue="pecho hacia la barra, codos hacia los bolsillos",
         musculo_sec=("biceps", "romboides"), equipo=""),

    dict(id="TIR_G02", nombre="Remo en polea baja agarre neutro",
         grupo="tiron", rol="principal", patron="remo_horizontal",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="principiante",
         cue="escápulas juntas al final, isométrico 1s, no balancear torso",
         musculo_sec=("biceps", "romboides"), equipo=""),

    dict(id="TIR_G03", nombre="Remo con mancuerna a una mano",
         grupo="tiron", rol="principal", patron="remo_horizontal",
         ambiente=("gym",), emg_score=4, fatiga="alta", nivel_min="principiante",
         cue="codo hacia la cadera, no rotar torso, rango completo",
         musculo_sec=("biceps",), equipo=""),

    dict(id="TIR_G04", nombre="Jalón agarre estrecho neutro",
         grupo="tiron", rol="secundario", patron="jalon_vertical",
         ambiente=("gym",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="codos al cuerpo, dorsal activo en todo el recorrido",
         musculo_sec=("biceps",), equipo=""),

    dict(id="TIR_G05", nombre="Remo en máquina con apoyo en pecho",
         grupo="tiron", rol="principal", patron="remo_horizontal",
         ambiente=("gym",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="pecho en almohadilla, codos al cuerpo, retracción escapular",
         musculo_sec=("biceps",), equipo=""),

    dict(id="TIR_G06", nombre="Curl de bíceps con mancuernas alterno",
         grupo="tiron", rol="aislamiento", patron="biceps",
         ambiente=("gym",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="codos fijos, supinación al subir, excéntrico controlado",
         musculo_sec=(), equipo=""),

    dict(id="TIR_G07", nombre="Face pull en polea alta",
         grupo="tiron", rol="aislamiento", patron="hombro_posterior",
         ambiente=("gym",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="codos afuera y arriba, retracción y rotación externa al final",
         musculo_sec=("manguito_rotador",), equipo=""),

    dict(id="TIR_G08", nombre="Curl martillo con mancuernas",
         grupo="tiron", rol="aislamiento", patron="biceps",
         ambiente=("gym",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="agarre neutro, activa braquial y braquiorradial además del bíceps",
         musculo_sec=(), equipo=""),

    dict(id="TIR_G09", nombre="Pullover con mancuerna en banco",
         grupo="tiron", rol="secundario", patron="jalon_vertical",
         ambiente=("gym",), emg_score=3, fatiga="media", nivel_min="intermedio",
         cue="codos semiflexionados, arco amplio, estiramiento dorsal completo",
         musculo_sec=("pecho", "serrato"), equipo=""),

    # ═══════════════════════════════════════════════
    # TIRÓN — HOME
    # ═══════════════════════════════════════════════
    dict(id="TIR_H01", nombre="Remo invertido bajo mesa",
         grupo="tiron", rol="principal", patron="remo_horizontal",
         ambiente=("home",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="cuerpo recto, codos al cuerpo, pecho sube a tocar la mesa",
         musculo_sec=("biceps",), equipo="mesa resistente"),

    dict(id="TIR_H02", nombre="Remo con banda elástica sentado",
         grupo="tiron", rol="principal", patron="remo_horizontal",
         ambiente=("band",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="banda en pies, codos al cuerpo, retracción escapular al final",
         musculo_sec=("biceps",), equipo="banda elástica"),

    dict(id="TIR_H03", nombre="Jalón con banda desde punto alto",
         grupo="tiron", rol="principal", patron="jalon_vertical",
         ambiente=("band",), emg_score=3, fatiga="media", nivel_min="principiante",
         cue="banda anclada arriba, tirar codos hacia los bolsillos",
         musculo_sec=("biceps",), equipo="banda elástica + anclaje alto"),

    dict(id="TIR_H04", nombre="Curl de bíceps con banda",
         grupo="tiron", rol="aislamiento", patron="biceps",
         ambiente=("band",), emg_score=3, fatiga="baja", nivel_min="principiante",
         cue="banda bajo los pies, codos fijos, supinación al subir",
         musculo_sec=(), equipo="banda elástica"),

    dict(id="TIR_H05", nombre="Face pull con banda a altura de ojos",
         grupo="tiron", rol="aislamiento", patron="hombro_posterior",
         ambiente=("band",), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="banda anclada a ojos, codos arriba y afuera al jalar",
         musculo_sec=("manguito_rotador",), equipo="banda elástica + anclaje"),

    dict(id="TIR_H06", nombre="Curl con botellas de agua",
         grupo="tiron", rol="aislamiento", patron="biceps",
         ambiente=("home",), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="botellas llenas de agua o arena, misma técnica que mancuerna",
         musculo_sec=(), equipo="botellas de agua"),

    dict(id="TIR_H07", nombre="Superman en suelo",
         grupo="tiron", rol="aislamiento", patron="hombro_posterior",
         ambiente=("home",), emg_score=2, fatiga="baja", nivel_min="principiante",
         cue="pausa 2s arriba, activa lumbar y glúteo simultáneo",
         musculo_sec=("lumbar", "gluteo"), equipo="ninguno"),

    # ═══════════════════════════════════════════════
    # CORE — GYM + HOME
    # ═══════════════════════════════════════════════
    dict(id="COR_01", nombre="Plancha abdominal",
         grupo="core", rol="core_estabilidad", patron="core_estabilidad",
         ambiente=("gym", "home", "band"), emg_score=2, fatiga="baja",
         cue="cuerpo recto, glúteo apretado, lumbar neutra, 30-60s",
         musculo_sec=("hombro", "gluteo"), equipo="ninguno"),

    dict(id="COR_02", nombre="Plancha lateral",
         grupo="core", rol="core_estabilidad", patron="core_estabilidad",
         ambiente=("gym", "home", "band"), emg_score=2, fatiga="baja",
         cue="cadera arriba, oblicuo activo, 30s cada lado",
         musculo_sec=("oblicuos", "gluteo_medio"), equipo="ninguno"),

    dict(id="COR_03", nombre="Dead bug",
         grupo="core", rol="core_estabilidad", patron="core_estabilidad",
         ambiente=("gym", "home", "band"), emg_score=2, fatiga="baja",
         cue="lumbar pegada al suelo todo el tiempo, movimiento muy lento",
         musculo_sec=(), equipo="ninguno"),

    dict(id="COR_04", nombre="Bird dog",
         grupo="core", rol="core_estabilidad", patron="core_estabilidad",
         ambiente=("gym", "home", "band"), emg_score=2, fatiga="baja",
         cue="caderas cuadradas, extensión lenta, pausa 1s al extender",
         musculo_sec=("gluteo", "lumbar"), equipo="ninguno"),

    dict(id="COR_05", nombre="Crunch inverso",
         grupo="core", rol="core_dinamico", patron="core_dinamico",
         ambiente=("gym", "home"), emg_score=3, fatiga="baja",
         cue="lumbar se despega del suelo al final, control total bajando",
         musculo_sec=(), equipo="ninguno"),

    dict(id="COR_06", nombre="Elevación de piernas tumbada",
         grupo="core", rol="core_dinamico", patron="core_dinamico",
         ambiente=("gym", "home"), emg_score=3, fatiga="baja",
         cue="lumbar pegada, piernas rectas, no dejar caer al bajar",
         musculo_sec=(), equipo="ninguno"),

    dict(id="COR_07", nombre="Mountain climbers",
         grupo="core", rol="core_dinamico", patron="core_dinamico",
         ambiente=("gym", "home"), emg_score=3, fatiga="media",
         cue="caderas bajas, ritmo controlado, core siempre activo",
         musculo_sec=("cardio",), equipo="ninguno"),

    dict(id="COR_08", nombre="Hollow body hold",
         grupo="core", rol="core_estabilidad", patron="core_estabilidad",
         ambiente=("gym", "home"), emg_score=3, fatiga="baja", nivel_min="intermedio",
         cue="lumbar aplastada, brazos y piernas extendidos sin arco",
         musculo_sec=(), equipo="ninguno"),

    dict(id="COR_09", nombre="Rotación rusa con peso",
         grupo="core", rol="core_dinamico", patron="core_rotacion",
         ambiente=("gym", "home"), emg_score=3, fatiga="baja",
         cue="rotar desde el torso, no desde los brazos, pies ligeramente elevados",
         musculo_sec=("oblicuos",), equipo="mancuerna o botella"),

    dict(id="COR_10", nombre="Crunch en polea alta",
         grupo="core", rol="core_dinamico", patron="core_dinamico",
         ambiente=("gym",), emg_score=4, fatiga="baja", nivel_min="principiante",
         cue="redondear espalda hacia rodillas, no jalar solo con brazos",
         musculo_sec=(), equipo=""),

    # ═══════════════════════════════════════════════
    # CARDIO — GYM (zona 2 prioritaria)
    # Zona 2: 60-70% FCmax = oxidación grasa óptima (ACSM 2021)
    # NUNCA zona 4-5 post-fuerza (cortisol + catabolismo muscular)
    # ═══════════════════════════════════════════════
    dict(id="CAR_G01", nombre="Caminata inclinada en cinta",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("gym",), emg_score=2, fatiga="baja",
         cue="inclinación 8-12%, velocidad 3.5-4 km/h, FC zona 2 (120-135 bpm)",
         musculo_sec=("gluteo",), equipo=""),

    dict(id="CAR_G02", nombre="Bicicleta estática zona 2",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("gym",), emg_score=1, fatiga="baja",
         cue="resistencia moderada, cadencia 70-90 rpm, FC 120-135 bpm",
         musculo_sec=(), equipo=""),

    dict(id="CAR_G03", nombre="Elíptica ritmo constante zona 2",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("gym",), emg_score=1, fatiga="baja",
         cue="postura erguida, cadencia constante, FC zona 2",
         musculo_sec=(), equipo=""),

    dict(id="CAR_G04", nombre="Remo ergómetro zona 2",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("gym",), emg_score=2, fatiga="media",
         cue="empujar con piernas primero, luego espalda, luego brazos",
         musculo_sec=("espalda", "pierna"), equipo=""),

    dict(id="CAR_G05", nombre="Trote suave en cinta zona 2",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("gym",), emg_score=1, fatiga="baja", nivel_min="intermedio",
         cue="6-7 km/h, cadencia corta, respiración nasal = zona 2 confirmada",
         musculo_sec=(), equipo=""),

    # ═══════════════════════════════════════════════
    # CARDIO — HOME
    # ═══════════════════════════════════════════════
    dict(id="CAR_H01", nombre="Caminata al aire libre zona 2",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("home",), emg_score=1, fatiga="baja",
         cue="20-30 min, paso enérgico, FC zona 2, si puedes hablar estás bien",
         musculo_sec=(), equipo="ninguno"),

    dict(id="CAR_H02", nombre="Jumping jacks ritmo moderado",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("home",), emg_score=1, fatiga="baja",
         cue="60s activo + 30s descanso, FC zona 2, mantener 20 min total",
         musculo_sec=(), equipo="ninguno"),

    dict(id="CAR_H03", nombre="Marcha elevando rodillas en sitio",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("home",), emg_score=1, fatiga="baja",
         cue="rodillas al nivel de cadera, brazos activos, ritmo constante 20 min",
         musculo_sec=(), equipo="ninguno"),

    dict(id="CAR_H04", nombre="Saltar cuerda zona 2",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("home",), emg_score=1, fatiga="media", nivel_min="intermedio",
         cue="muñecas sueltas, salto pequeño, FC zona 2-3 máximo",
         musculo_sec=("pantorrilla",), equipo="cuerda"),

    dict(id="CAR_H05", nombre="Step aeróbico en escalón",
         grupo="cardio", rol="cardio", patron="cardio",
         ambiente=("home",), emg_score=2, fatiga="baja",
         cue="ritmo constante 20 min, activa glúteo en cada subida",
         musculo_sec=("gluteo",), equipo="escalón"),
]

# ─── ÍNDICES ──────────────────────────────────────────────────────────────────
CATALOG:     list[Ejercicio]             = [Ejercicio(**e) for e in _RAW]
BY_ID:       dict[str, Ejercicio]        = {e.id: e for e in CATALOG}
VALID_IDS:   frozenset[str]              = frozenset(e.id for e in CATALOG)
BY_GRUPO:    dict[str, list[Ejercicio]]  = {}
BY_PATRON:   dict[str, list[Ejercicio]]  = {}
BY_AMBIENTE: dict[str, list[Ejercicio]]  = {}

for _e in CATALOG:
    BY_GRUPO.setdefault(_e.grupo, []).append(_e)
    BY_PATRON.setdefault(_e.patron, []).append(_e)
    for _amb in _e.ambiente:
        BY_AMBIENTE.setdefault(_amb, []).append(_e)


def get(eid: str) -> Ejercicio | None:
    return BY_ID.get(eid)

def is_valid(eid: str) -> bool:
    return eid in VALID_IDS

def ids_por_grupo(grupo: str, ambiente: str = "gym") -> list[str]:
    return [e.id for e in BY_GRUPO.get(grupo, []) if ambiente in e.ambiente]

def por_ambiente(ambiente: str) -> list[Ejercicio]:
    return BY_AMBIENTE.get(ambiente, [])

def alternativas(eid: str, excluir: set[str], ambiente: str = "gym") -> list[Ejercicio]:
    ej = BY_ID.get(eid)
    if not ej:
        return []
    return sorted(
        [e for e in BY_GRUPO.get(ej.grupo, [])
         if e.id not in excluir and e.id != eid
         and e.rol == ej.rol and ambiente in e.ambiente],
        key=lambda x: x.emg_score, reverse=True
    )[:4]

def equivalente_casa(eid: str) -> Ejercicio | None:
    """Devuelve el mejor equivalente en casa para un ejercicio de gym."""
    ej = BY_ID.get(eid)
    if not ej or ej.es_home():
        return None
    candidatos = [
        e for e in BY_GRUPO.get(ej.grupo, [])
        if e.es_home() and e.rol == ej.rol and e.patron == ej.patron
    ]
    if not candidatos:
        candidatos = [
            e for e in BY_GRUPO.get(ej.grupo, [])
            if e.es_home() and e.rol == ej.rol
        ]
    return max(candidatos, key=lambda x: x.emg_score) if candidatos else None


# ─── REGLAS BIOMECÁNICAS ─────────────────────────────────────────────────────
MAX_POR_PATRON: dict[str, int] = {
    "puente_cadera":           2,
    "puente_cadera_unilateral":1,
    "sentadilla":              1,
    "desplante_unilateral":    2,
    "bisagra_cadera":          1,
    "press_horizontal":        2,
    "press_inclinado":         1,
    "press_vertical":          1,
    "jalon_vertical":          1,
    "remo_horizontal":         2,
    "curl_femoral":            1,
    "patada":                  2,
    "abduccion":               2,
    "biceps":                  2,
    "triceps":                 2,
    "core_estabilidad":        2,
    "core_dinamico":           2,
    "core_rotacion":           1,
    "prensa":                  1,
    "extension_quad":          1,
    "pantorrilla":             1,
    "hombro_lateral":          2,
    "hombro_posterior":        1,
    "aislamiento_pecho":       1,
    "cardio":                  1,
}
MAX_POR_PATRON_DEFAULT = 2

COMPUESTOS = frozenset({
    "sentadilla", "prensa", "bisagra_cadera", "press_horizontal",
    "press_inclinado", "press_vertical", "jalon_vertical",
    "remo_horizontal", "puente_cadera", "desplante_unilateral",
    "puente_cadera_unilateral",
})

# ─── PERIODIZACIÓN ONDULATORIA GLÚTEO (Contreras 2015 / Nippard 2023) ────────
# 3 tipos de sesión que se rotan para maximizar adaptación
SESION_GLUTEO = {
    "fuerza":      {"reps": "4-8",  "rir": 1, "desc": "Carga máxima, compuesto pesado primero"},
    "hipertrofia": {"reps": "8-12", "rir": 2, "desc": "Volumen óptimo, rango medio de carga"},
    "metabolico":  {"reps": "15-20","rir": 2, "desc": "Pump, aislamiento, banda, conexión mente-músculo"},
}

# Rotación por semana (S4 = deload mismo patrón que S1 a 60%)
ROTACION_ONDULATORIO: dict[int, dict[str, str]] = {
    1: {"g1": "fuerza",      "g2": "hipertrofia", "g3": "metabolico"},
    2: {"g1": "hipertrofia", "g2": "metabolico",  "g3": "fuerza"},
    3: {"g1": "fuerza",      "g2": "hipertrofia", "g3": "metabolico"},
    4: {"g1": "hipertrofia", "g2": "metabolico",  "g3": "fuerza"},
}

# ─── CALENTAMIENTOS POR GRUPO ─────────────────────────────────────────────────
# Calentamientos prácticos: 5 min, específicos al movimiento del día.
# Principio: activación específica > cardio genérico antes de fuerza.
# Fuente: Behm & Chaouachi (2011) — el estiramiento estático PRE-fuerza reduce rendimiento.
# Lo que sí funciona: activar el músculo que vas a trabajar con movimiento dinámico ligero.
CALENTAMIENTO: dict[str, list[tuple[str, str]]] = {
    "gluteo": [
        ("Caminata 3-5 min en cinta al 50% o en sitio",    "Eleva temperatura muscular sin fatiga"),
        ("Puente de glúteo sin peso — 2×15 con pausa 2s",  "Activa la conexión mente-músculo antes de cargar"),
        ("Hip thrust con barra vacía — 1×12",               "Practica el patrón con peso mínimo antes del trabajo real"),
    ],
    "pierna": [
        ("Caminata 3-5 min o bicicleta suave",              "Lubrica rodillas y caderas antes de cargar"),
        ("Sentadilla sin peso — 2×10 lentas",               "Activa el patrón motor, revisa rango de movimiento"),
        ("Peso muerto con barra vacía — 1×10",              "Calienta isquios y glúteo con el movimiento exacto"),
    ],
    "empuje": [
        ("Círculos de hombro hacia adelante y atrás — 2×10", "Lubrica la articulación glenohumeral"),
        ("Flexiones lentas sin peso — 2×8",                  "Activa el patrón del press, escápulas retraídas"),
        ("Press con barra vacía o mancuernas ligeras — 1×12","Practica el movimiento antes de la carga real"),
    ],
    "tiron": [
        ("Círculos de hombro y retracción escapular — 2×15", "Activa romboides y trapecio medio"),
        ("Jalón con banda o peso mínimo — 2×10",             "Pre-activa el dorsal con el patrón exacto"),
        ("Remo ligero — 1×12",                               "Calienta con el movimiento real, no uno diferente"),
    ],
    "core": [
        ("Caminata ligera 3 min",                            "Eleva temperatura antes del trabajo de core"),
        ("Dead bug lento — 2×8 c/lado",                     "Activa el transverso abdominal profundo"),
        ("Plancha 2×20s",                                    "Establece tensión de core antes de los ejercicios"),
    ],
    "cardio": [
        ("Primeros 3-5 min al 50% de la intensidad objetivo","El cardio se calienta a sí mismo — empieza suave"),
        ("Movilidad de cadera — 10 círculos c/dirección",    "Opcional si tienes caderas rígidas al despertar"),
    ],
}

NUTRICION: dict[str, dict[str, str]] = {
    "gluteo": {
        "pre":  "🥑 Pre: avena + plátano 60 min antes · carbos para el hip thrust pesado",
        "post": "🥩 Post: 25-35g proteína + carbos en 45 min · músculo en modo esponja",
    },
    "pierna": {
        "pre":  "🍌 Pre: carbo + cafeína 30-40 min antes · la sentadilla lo necesita",
        "post": "🥚 Post: proteína completa + carbos · pierna es el músculo más grande",
    },
    "empuje": {
        "pre":  "☕ Pre: cafeína 30 min antes · proteína si llevas +3h en ayunas",
        "post": "🍗 Post: proteína magra + algo de carbo · síntesis activa 24-48h",
    },
    "tiron": {
        "pre":  "🥜 Pre: proteína + algo de carbo · el dorsal necesita energía y aminoácidos",
        "post": "🐟 Post: proteína alta + carbo moderado · reconstrucción dorsal y bíceps",
    },
    "general": {
        "pre":  "🍌 Pre: carbo simple si tienes hambre · 500 ml agua antes",
        "post": "🥚 Post: proteína completa + algo de carbo para recuperación muscular",
    },
}

GRUPO_ICON = {
    "gluteo": "🍑", "pierna": "🦵", "empuje": "💪",
    "tiron": "🏋️", "core": "🎯", "cardio": "🏃", "general": "⚡",
}
