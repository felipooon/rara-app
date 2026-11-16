"""
Módulo de Coberturas, Puntos y Tarifario Blue Express para Rara Tienda.
Contiene las 16 Regiones de Chile y sus 346 Comunas oficiales,
con tarifas zonales según el tarifario Blue Express Pyme (origen tienda: Puerto Montt).
"""

import json
import math
import os
import re
import urllib.request
from datetime import datetime
from django.conf import settings

ORIGEN_TIENDA_COMUNA = "Puerto Montt"
ORIGEN_TIENDA_REGION = "Región de Los Lagos"

MONTO_MINIMO_ENTREGA_PRESENCIAL_GRATIS = 25000
COSTO_ENTREGA_PRESENCIAL_REDUCIDO = 1500

BLUE_API_URL = "https://pudom.api.blue.cl/pdoohd/agencies-external/v3/filters?country_id=75&status=1"
BLUE_API_HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": "uGo31Lp5eja66Ftj1juRe9oSiinzqhKi6p39mYok",
    "Channel": "Mapa-pickup",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

REGIONES_Y_COMUNAS = {
    "Región Metropolitana de Santiago": [
        "Cerrillos", "Cerro Navia", "Conchalí", "El Bosque", "Estación Central",
        "Huechuraba", "Independencia", "La Cisterna", "La Florida", "La Granja",
        "La Pintana", "La Reina", "Las Condes", "Lo Barnechea", "Lo Espejo",
        "Lo Prado", "Macul", "Maipú", "Ñuñoa", "Pedro Aguirre Cerda",
        "Peñalolén", "Providencia", "Pudahuel", "Quilicura", "Quinta Normal",
        "Recoleta", "Renca", "San Joaquín", "San Miguel", "San Ramón",
        "Santiago", "Vitacura", "Puente Alto", "Pirque", "San José de Maipo",
        "San Bernardo", "Buin", "Calera de Tango", "Paine", "Colina",
        "Lampa", "Tiltil", "Melipilla", "Alhué", "Curacaví",
        "María Pinto", "San Pedro", "Talagante", "El Monte", "Isla de Maipo",
        "Padre Hurtado", "Peñaflor"
    ],
    "Región de Valparaíso": [
        "Valparaíso", "Casablanca", "Concón", "Juan Fernández", "Puchuncaví",
        "Quintero", "Viña del Mar", "Isla de Pascua", "Los Andes", "Calle Larga",
        "Rinconada", "San Esteban", "La Ligua", "Cabildo", "Papudo",
        "Petorca", "Zapallar", "Quillota", "Calera", "Hijuelas",
        "La Cruz", "Nogales", "San Antonio", "Algarrobo", "Cartagena",
        "El Quisco", "El Tabo", "Santo Domingo", "San Felipe", "Catemu",
        "Llaillay", "Panquehue", "Putaendo", "Santa María", "Quilpué",
        "Limache", "Olmué", "Villa Alemana"
    ],
    "Región del Libertador Gral. Bernardo O'Higgins": [
        "Rancagua", "Codegua", "Coinco", "Coltauco", "Doñihue",
        "Graneros", "Las Cabras", "Machalí", "Malloa", "Mostazal",
        "Olivar", "Peumo", "Pichidegua", "Quinta de Tilcoco", "Rengo",
        "Requínoa", "San Vicente", "Pichilemu", "La Estrella", "Litueche",
        "Marchihue", "Navidad", "Paredones", "San Fernando", "Chépica",
        "Chimbarongo", "Lolol", "Nancagua", "Palmilla", "Peralillo",
        "Placilla", "Pumanque", "Santa Cruz"
    ],
    "Región de Coquimbo": [
        "La Serena", "Coquimbo", "Andacollo", "La Higuera", "Paiguano",
        "Vicuña", "Illapel", "Canela", "Los Vilos", "Salamanca",
        "Ovalle", "Combarbalá", "Monte Patria", "Punitaqui", "Río Hurtado"
    ],
    "Región del Maule": [
        "Talca", "Constitución", "Curepto", "Empedrado", "Maule",
        "Pelarco", "Pencahue", "Río Claro", "San Clemente", "San Rafael",
        "Cauquenes", "Chanco", "Pelluhue", "Curicó", "Hualañé",
        "Licantén", "Molina", "Rauco", "Romeral", "Sagrada Familia",
        "Teno", "Vichuquén", "Linares", "Colbún", "Longaví",
        "Parral", "Retiro", "San Javier", "Villa Alegre", "Yerbas Buenas"
    ],
    "Región de Ñuble": [
        "Chillán", "Bulnes", "Cobquecura", "Coelemu", "Coihueco",
        "Chillán Viejo", "El Carmen", "Ninhue", "Ñiquén", "Pemuco",
        "Pinto", "Portezuelo", "Quillón", "Quirihue", "Ránquil",
        "San Carlos", "San Fabián", "San Ignacio", "San Nicolás", "Treguaco",
        "Yungay"
    ],
    "Región del Biobío": [
        "Concepción", "Coronel", "Chiguayante", "Florida", "Hualqui",
        "Lota", "Penco", "San Pedro de la Paz", "Santa Juana", "Talcahuano",
        "Tomé", "Hualpén", "Lebu", "Arauco", "Cañete",
        "Contulmo", "Curanilahue", "Los Álamos", "Tirúa", "Los Ángeles",
        "Antuco", "Cabrero", "Laja", "Mulchén", "Nacimiento",
        "Negrete", "Quilaco", "Quilleco", "San Rosendo", "Santa Bárbara",
        "Tucapel", "Yumbel", "Alto Biobío"
    ],
    "Región de La Araucanía": [
        "Temuco", "Carahue", "Cunco", "Curarrehue", "Freire",
        "Galvarino", "Gorbea", "Lautaro", "Loncoche", "Melipeuco",
        "Nueva Imperial", "Padre Las Casas", "Perquenco", "Pitrufquén", "Pucón",
        "Saavedra", "Teodoro Schmidt", "Toltén", "Vilcún", "Villarrica",
        "Cholchol", "Angol", "Collipulli", "Curacautín", "Ercilla",
        "Lonquimay", "Los Sauces", "Lumaco", "Purén", "Renaico",
        "Traiguén", "Victoria"
    ],
    "Región de Los Ríos": [
        "Valdivia", "Corral", "Lanco", "Los Lagos", "Máfil",
        "Mariquina", "Paillaco", "Panguipulli", "La Unión", "Futrono",
        "Lago Ranco", "Río Bueno"
    ],
    "Región de Los Lagos": [
        "Puerto Montt", "Calbuco", "Cochamó", "Fresia", "Frutillar",
        "Los Muermos", "Llanquihue", "Maullín", "Puerto Varas", "Castro",
        "Ancud", "Chonchi", "Curaco de Vélez", "Dalcahue", "Puqueldón",
        "Queilén", "Quellón", "Quemchi", "Quinchao", "Osorno",
        "Puerto Octay", "Purranque", "Puyehue", "Río Negro", "San Juan de la Costa",
        "San Pablo", "Chaitén", "Futaleufú", "Hualaihué", "Palena"
    ],
    "Región de Atacama": [
        "Copiapó", "Caldera", "Tierra Amarilla", "Chañaral", "Diego de Almagro",
        "Vallenar", "Alto del Carmen", "Freirina", "Huasco"
    ],
    "Región de Antofagasta": [
        "Antofagasta", "Mejillones", "Sierra Gorda", "Taltal", "Calama",
        "Ollagüe", "San Pedro de Atacama", "Tocopilla", "María Elena"
    ],
    "Región de Tarapacá": [
        "Iquique", "Alto Hospicio", "Pozo Almonte", "Camiña", "Colchane",
        "Huara", "Pica"
    ],
    "Región de Arica y Parinacota": [
        "Arica", "Camarones", "Putre", "General Lagos"
    ],
    "Región de Aysén del Gral. Carlos Ibáñez del Campo": [
        "Coyhaique", "Lago Verde", "Aysén", "Cisnes", "Guaitecas",
        "Cochrane", "O'Higgins", "Tortel", "Chile Chico", "Río Ibáñez"
    ],
    "Región de Magallanes y de la Antártica Chilena": [
        "Punta Arenas", "Laguna Blanca", "Río Verde", "San Gregorio", "Cabo de Hornos",
        "Antártica", "Porvenir", "Primavera", "Timaukel", "Natales",
        "Torres del Paine"
    ]
}

RM_PERIFERICAS = {
    "colina", "lampa", "tiltil", "pirque", "san jose de maipo", "san josé de maipo",
    "buin", "calera de tango", "paine", "melipilla", "alhue", "alhué",
    "curacavi", "curacaví", "maria pinto", "maría pinto", "san pedro",
    "talagante", "el monte", "isla de maipo", "padre hurtado", "penaflor", "peñaflor"
}


def normalizar_texto(texto):
    """Limpia acentos y minúsculas para comparaciones seguras."""
    if not texto:
        return ""
    texto = str(texto).strip().lower()
    reemplazos = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n', 'ü': 'u'
    }
    for orig, rep in reemplazos.items():
        texto = texto.replace(orig, rep)
    return texto


# Asegurar que las comunas de cada región se presenten ordenadas alfabéticamente
for _reg in REGIONES_Y_COMUNAS:
    REGIONES_Y_COMUNAS[_reg] = sorted(REGIONES_Y_COMUNAS[_reg], key=lambda c: normalizar_texto(c))


def obtener_region_de_comuna(comuna_nombre):
    """Encuentra la región oficial dada una comuna."""
    comuna_norm = normalizar_texto(comuna_nombre)
    for region, comunas in REGIONES_Y_COMUNAS.items():
        for c in comunas:
            if normalizar_texto(c) == comuna_norm:
                return region
    return ORIGEN_TIENDA_REGION


def validar_comuna_existe(comuna_nombre):
    """Retorna el nombre canónico de la comuna si existe en el catálogo oficial, o None."""
    comuna_norm = normalizar_texto(comuna_nombre)
    if not comuna_norm:
        return None
    for region, comunas in REGIONES_Y_COMUNAS.items():
        for c in comunas:
            if normalizar_texto(c) == comuna_norm:
                return c
    return None


REGIONES_EXACTAS_BLUE_EXPRESS = [
    "Región Metropolitana de Santiago",
    "Región de Aysén del Gral. Carlos Ibañez del Campo",
    "Región de Antofagasta",
    "Región de Arica y Parinacota",
    "Región de Atacama",
    "Región de Coquimbo",
    "Región de Magallanes y de la Antártica Chilena",
    "Región de Tarapacá",
    "Región de Valparaíso",
    "Región de la Araucanía",
    "Región de los Lagos",
    "Región de los Ríos",
    "Región de Ñuble",
    "Región del Biobío",
    "Región del Libertador Gral. Bernardo O'Higgins",
    "Región del Maule"
]


def normalizar_region_blue_express(region_nombre):
    """Retorna el nombre exacto de región esperado por la plantilla de Blue Express."""
    if not region_nombre:
        return "Región de los Lagos"
    norm = normalizar_texto(region_nombre)
    for reg in REGIONES_EXACTAS_BLUE_EXPRESS:
        if normalizar_texto(reg) == norm:
            return reg
    if 'metropolitana' in norm or 'santiago' in norm:
        return "Región Metropolitana de Santiago"
    if 'araucania' in norm:
        return "Región de la Araucanía"
    if 'lagos' in norm:
        return "Región de los Lagos"
    if 'rios' in norm:
        return "Región de los Ríos"
    if 'aysen' in norm or 'ibanez' in norm:
        return "Región de Aysén del Gral. Carlos Ibañez del Campo"
    if 'magallanes' in norm or 'antartica' in norm:
        return "Región de Magallanes y de la Antártica Chilena"
    if 'ohiggins' in norm or "o'higgins" in norm:
        return "Región del Libertador Gral. Bernardo O'Higgins"
    return "Región de los Lagos"


def normalizar_comuna_blue_express(comuna_nombre):
    """Ajusta nombres de comuna con particularidades en el catálogo de Blue Express."""
    if not comuna_nombre:
        return ORIGEN_TIENDA_COMUNA
    norm = normalizar_texto(comuna_nombre)
    if norm in ('santiago', 'santiago centro'):
        return "Santiago Centro"
    if 'ohiggins' in norm or "o'higgins" in norm:
        return "O’higgins"
    return comuna_nombre.strip()


def parsear_direccion_chilena(direccion):
    """
    Separa una dirección en calle, número de domicilio, departamento/oficina y ayuda.
    Cumple con el formato de Carga Masiva de Blue Express.
    """
    if not direccion:
        return ("", "S/N", "", "")
    dir_str = direccion.strip()
    depto = ""
    depto_patterns = [
        r'(?:depto|dpto|departamento|oficina|of|of\.|block|piso)\s*[:#]?\s*([a-zA-Z0-9\-]+)',
        r'#\s*([a-zA-Z0-9\-]+)'
    ]
    for pattern in depto_patterns:
        match = re.search(pattern, dir_str, re.IGNORECASE)
        if match:
            depto = match.group(1).strip()
            dir_str = (dir_str[:match.start()] + dir_str[match.end():]).strip().rstrip(',').strip()
            break

    num_match = re.search(r'\b(\d+[a-zA-Z]?)\b(?=[^\d]*$)', dir_str)
    if num_match:
        numero = num_match.group(1)
        calle = dir_str[:num_match.start()].strip().rstrip(',').strip()
        resto = dir_str[num_match.end():].strip().lstrip(',').strip()
        if resto and not depto:
            depto = resto
    else:
        calle = dir_str
        numero = "S/N"

    if not calle:
        calle = direccion
        numero = "S/N"

    return (calle, numero, depto, "")


# =========================================================================
# TARIFARIO OFICIAL BLUE EXPRESS PYME (CON IVA)
# =========================================================================

TARIFAS_BLUE_EXPRESS = {
    'XS': {'RM': 3100, 'CENTRO': 4300, 'EXTREMO': 5200},
    'S':  {'RM': 4200, 'CENTRO': 5600, 'EXTREMO': 9500},
    'M':  {'RM': 4800, 'CENTRO': 7300, 'EXTREMO': 14500},
    'L':  {'RM': 5400, 'CENTRO': 9200, 'EXTREMO': 17000},
}

TARIFAS_BLUE_EXPRESS_PUNTO = {
    'XS': {'RM': 2600, 'CENTRO': 3800, 'EXTREMO': 4700},
    'S':  {'RM': 3700, 'CENTRO': 5100, 'EXTREMO': 9000},
    'M':  {'RM': 4300, 'CENTRO': 6800, 'EXTREMO': 14000},
    'L':  {'RM': 4900, 'CENTRO': 8700, 'EXTREMO': 16500},
}

REGIONES_EXTREMO = {
    "Región de Arica y Parinacota",
    "Región de Tarapacá",
    "Región de Antofagasta",
    "Región de Aysén del Gral. Carlos Ibáñez del Campo",
    "Región de Magallanes y de la Antártica Chilena"
}


def _get_data_paths():
    data_dir = os.path.join(settings.BASE_DIR, 'tienda', 'data')
    puntos_path = os.path.join(data_dir, 'puntos_blue_express.json')
    tarifas_path = os.path.join(data_dir, 'tarifas_blue_express.json')
    return data_dir, puntos_path, tarifas_path


def cargar_tarifas():
    _, _, tarifas_path = _get_data_paths()
    if os.path.exists(tarifas_path):
        try:
            with open(tarifas_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "origen": ORIGEN_TIENDA_COMUNA,
        "moneda": "CLP",
        "incluye_iva": True,
        "tallas_peso_kg": {
            "XS": {"max_kg": 0.5},
            "S": {"max_kg": 3.0},
            "M": {"max_kg": 6.0},
            "L": {"max_kg": 20.0},
        },
        "regiones_extremo": list(REGIONES_EXTREMO),
        "tarifas_domicilio": TARIFAS_BLUE_EXPRESS,
        "tarifas_punto_blue": TARIFAS_BLUE_EXPRESS_PUNTO,
    }


def determinar_talla_peso(peso_kg):
    try:
        p = float(peso_kg)
    except (ValueError, TypeError):
        p = 0.40

    if p <= 0.5:
        return 'XS'
    elif p <= 3.0:
        return 'S'
    elif p <= 6.0:
        return 'M'
    else:
        return 'L'


def determinar_talla_por_tarifas(peso_kg, tarifas=None):
    if not tarifas:
        return determinar_talla_peso(peso_kg)
    try:
        p = float(peso_kg)
    except (ValueError, TypeError):
        p = 0.4
    tallas = tarifas.get("tallas_peso_kg", {})
    for talla in ("XS", "S", "M", "L"):
        max_kg = tallas.get(talla, {}).get("max_kg")
        if max_kg is not None and p <= float(max_kg):
            return talla
    return "L"


def determinar_zona(origen_region, destino_region, tarifas=None):
    """
    Determina la zona tarifaria entre región de origen y destino:
    - Misma región (origen == destino): 'RM' ('Misma región / zona local')
    - Alguna en zona extrema: 'EXTREMO' ('Zona Extrema')
    - Resto del país: 'CENTRO' ('Zona Centro')
    """
    regiones_extremo = set(tarifas.get("regiones_extremo", REGIONES_EXTREMO)) if tarifas else REGIONES_EXTREMO
    if normalizar_texto(origen_region) == normalizar_texto(destino_region):
        return "RM", "Misma región / zona local"
    if destino_region in regiones_extremo or origen_region in regiones_extremo:
        return "EXTREMO", "Zona Extrema"
    return "CENTRO", "Zona Centro"


def haversine_km(lat1, lng1, lat2, lng2):
    try:
        lat1, lng1, lat2, lng2 = float(lat1), float(lng1), float(lat2), float(lng2)
    except (TypeError, ValueError):
        return None
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)


def obtener_zona_blue_express(region_destino, region_origen=ORIGEN_TIENDA_REGION):
    zona, _ = determinar_zona(region_origen, region_destino)
    return zona


def obtener_tarifa_blue_express(comuna_nombre, peso_kg=0.40, origen_comuna=ORIGEN_TIENDA_COMUNA, talla=None):
    origen_reg = obtener_region_de_comuna(origen_comuna)
    destino_reg = obtener_region_de_comuna(comuna_nombre)
    zona, _ = determinar_zona(origen_reg, destino_reg)
    talla_usar = talla if talla in ('XS', 'S', 'M', 'L') else determinar_talla_peso(peso_kg)
    return TARIFAS_BLUE_EXPRESS.get(talla_usar, TARIFAS_BLUE_EXPRESS['XS'])[zona]


def obtener_tarifa_blue_express_punto(comuna_nombre, peso_kg=0.40, origen_comuna=ORIGEN_TIENDA_COMUNA, talla=None):
    """Tarifa reducida para entrega fuera de casa en Punto Blue Express / Copec."""
    origen_reg = obtener_region_de_comuna(origen_comuna)
    destino_reg = obtener_region_de_comuna(comuna_nombre)
    zona, _ = determinar_zona(origen_reg, destino_reg)
    talla_usar = talla if talla in ('XS', 'S', 'M', 'L') else determinar_talla_peso(peso_kg)
    return TARIFAS_BLUE_EXPRESS_PUNTO.get(talla_usar, TARIFAS_BLUE_EXPRESS_PUNTO['XS'])[zona]


def calcular_costo_envio(comuna_nombre, total_carrito=0, peso_kg=0.40, tipo_entrega='PUNTO_BLUE', origen_comuna=ORIGEN_TIENDA_COMUNA, talla='XS'):
    """
    Calcula el costo final de envío desde Puerto Montt (por defecto Talla XS):
    1. RETIRO (Entrega Presencial en Puerto Montt o Puerto Varas):
       - Gratis ($0) en compras >= $15.000
       - Costo reducido ($1.500) en compras < $15.000
    2. PUNTO_BLUE: Tarifa reducida oficial Punto Blue Express / Copec.
    3. DOMICILIO / ENVIO: Tarifa oficial entrega a domicilio Blue Express.
    """
    if tipo_entrega == 'RETIRO':
        try:
            subtotal = int(total_carrito or 0)
        except (TypeError, ValueError):
            subtotal = 0
        return 0 if subtotal >= MONTO_MINIMO_ENTREGA_PRESENCIAL_GRATIS else COSTO_ENTREGA_PRESENCIAL_REDUCIDO
    if tipo_entrega == 'PUNTO_BLUE':
        return obtener_tarifa_blue_express_punto(comuna_nombre, peso_kg=peso_kg, origen_comuna=origen_comuna, talla=talla)
    return obtener_tarifa_blue_express(comuna_nombre, peso_kg=peso_kg, origen_comuna=origen_comuna, talla=talla)


# =========================================================================
# CACHÉ Y GESTIÓN DE PUNTOS BLUE EXPRESS
# =========================================================================

_CACHE_PUNTOS_LISTA = None
_CACHE_PUNTOS_POR_COMUNA = None
_CACHE_PUNTOS_POR_ID = None


def invalidar_cache_puntos_blue():
    """Limpia el caché en memoria para forzar la recarga del archivo JSON."""
    global _CACHE_PUNTOS_LISTA, _CACHE_PUNTOS_POR_COMUNA, _CACHE_PUNTOS_POR_ID
    _CACHE_PUNTOS_LISTA = None
    _CACHE_PUNTOS_POR_COMUNA = None
    _CACHE_PUNTOS_POR_ID = None


def obtener_fecha_puntos():
    _, puntos_path, _ = _get_data_paths()
    if not os.path.exists(puntos_path):
        return None
    mtime = os.path.getmtime(puntos_path)
    return datetime.fromtimestamp(mtime).strftime("%d-%m-%Y %H:%M")


def cargar_puntos_lista():
    """Retorna la lista completa de puntos Blue Express desde JSON (con caché en memoria)."""
    global _CACHE_PUNTOS_LISTA
    if _CACHE_PUNTOS_LISTA is not None:
        return _CACHE_PUNTOS_LISTA

    _, puntos_path, _ = _get_data_paths()
    if not os.path.exists(puntos_path):
        _CACHE_PUNTOS_LISTA = []
        return _CACHE_PUNTOS_LISTA

    try:
        with open(puntos_path, 'r', encoding='utf-8') as f:
            _CACHE_PUNTOS_LISTA = json.load(f)
    except Exception:
        _CACHE_PUNTOS_LISTA = []

    return _CACHE_PUNTOS_LISTA


def cargar_puntos_blue_express():
    """Carga y agrupa por comuna normalizada los puntos de retiro Blue Express."""
    global _CACHE_PUNTOS_POR_COMUNA, _CACHE_PUNTOS_POR_ID
    if _CACHE_PUNTOS_POR_COMUNA is not None:
        return _CACHE_PUNTOS_POR_COMUNA

    lista = cargar_puntos_lista()
    agrupados = {}
    por_id = {}
    for p in lista:
        c_norm = normalizar_texto(p.get('comuna', ''))
        if c_norm not in agrupados:
            agrupados[c_norm] = []
        agrupados[c_norm].append(p)
        if p.get('id') is not None:
            por_id[int(p['id'])] = p

    _CACHE_PUNTOS_POR_COMUNA = agrupados
    _CACHE_PUNTOS_POR_ID = por_id
    return _CACHE_PUNTOS_POR_COMUNA


def obtener_puntos_blue_por_comuna(comuna_nombre):
    """Retorna la lista de Puntos Blue Express habilitados para la comuna indicada."""
    if not comuna_nombre:
        return []
    puntos_map = cargar_puntos_blue_express()
    c_norm = normalizar_texto(comuna_nombre)
    return puntos_map.get(c_norm, [])


def obtener_punto_blue_por_id(punto_id):
    """Retorna el diccionario de un Punto Blue Express dado su ID numérico."""
    if not punto_id:
        return None
    try:
        pid = int(punto_id)
    except (ValueError, TypeError):
        return None
    cargar_puntos_blue_express()
    if _CACHE_PUNTOS_POR_ID:
        return _CACHE_PUNTOS_POR_ID.get(pid)
    return None


def calcular_envio_detalle(
    origen_comuna=ORIGEN_TIENDA_COMUNA,
    destino_comuna=ORIGEN_TIENDA_COMUNA,
    origen_region=None,
    destino_region=None,
    peso_kg=0.4,
    talla=None,
    tipo_entrega="PUNTO_BLUE",
    punto_origen_id=None,
    punto_destino_id=None,
    total_carrito=0,
):
    tarifas = cargar_tarifas()
    origen_comuna_clean = validar_comuna_existe(origen_comuna) or origen_comuna or ORIGEN_TIENDA_COMUNA
    destino_comuna_clean = validar_comuna_existe(destino_comuna) or destino_comuna or ORIGEN_TIENDA_COMUNA

    orig_reg = origen_region or obtener_region_de_comuna(origen_comuna_clean)
    dest_reg = destino_region or obtener_region_de_comuna(destino_comuna_clean)

    if talla not in ("XS", "S", "M", "L"):
        talla = determinar_talla_por_tarifas(peso_kg, tarifas)

    zona, zona_desc = determinar_zona(orig_reg, dest_reg, tarifas)
    precio_domicilio = tarifas["tarifas_domicilio"][talla][zona]
    precio_punto = tarifas["tarifas_punto_blue"][talla][zona]
    try:
        subtotal_num = int(total_carrito or 0)
    except (TypeError, ValueError):
        subtotal_num = 0
    precio_retiro = 0 if subtotal_num >= MONTO_MINIMO_ENTREGA_PRESENCIAL_GRATIS else COSTO_ENTREGA_PRESENCIAL_REDUCIDO

    if tipo_entrega == "PUNTO_BLUE":
        precio_seleccionado = precio_punto
    elif tipo_entrega == "RETIRO":
        precio_seleccionado = precio_retiro
    else:
        precio_seleccionado = precio_domicilio

    p_orig = obtener_punto_blue_por_id(punto_origen_id)
    p_dest = obtener_punto_blue_por_id(punto_destino_id)
    distancia_km = None
    if p_orig and p_dest:
        distancia_km = haversine_km(
            p_orig.get("lat"), p_orig.get("lng"), p_dest.get("lat"), p_dest.get("lng")
        )

    return {
        "ok": True,
        "origen_comuna": origen_comuna_clean,
        "origen_region": orig_reg,
        "destino_comuna": destino_comuna_clean,
        "destino_region": dest_reg,
        "zona": zona,
        "zona_desc": zona_desc,
        "talla": talla,
        "precio_domicilio": precio_domicilio,
        "precio_punto": precio_punto,
        "precio_retiro": precio_retiro,
        "minimo_retiro_gratis": MONTO_MINIMO_ENTREGA_PRESENCIAL_GRATIS,
        "costo_retiro_reducido": COSTO_ENTREGA_PRESENCIAL_REDUCIDO,
        "precio_seleccionado": precio_seleccionado,
        "ahorro_punto": precio_domicilio - precio_punto,
        "distancia_km": distancia_km,
        "incluye_iva": tarifas.get("incluye_iva", True),
    }


def actualizar_puntos_desde_api():
    """
    Consulta la API oficial de Puntos Blue Express (Copec y Pick-up),
    actualiza el catálogo local en tienda/data/puntos_blue_express.json,
    invalida el caché y retorna estadísticas y diferencias (nuevos vs eliminados).
    """
    req = urllib.request.Request(BLUE_API_URL, headers=BLUE_API_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw_data = json.loads(resp.read().decode("utf-8"))

    mapa_comunas_canonica = {}
    for reg, comunas in REGIONES_Y_COMUNAS.items():
        for c in comunas:
            mapa_comunas_canonica[normalizar_texto(c)] = (c, reg)

    puntos_limpios = []
    for a in raw_data:
        if a.get("status") != "active":
            continue
        if not a.get("pickupAvailability"):
            continue

        addr = a.get("address", {})
        commune_data = addr.get("commune", {})
        state_data = addr.get("state", {})
        geo = addr.get("geolocation", {})
        type_agency = a.get("typeAgency", {})

        raw_commune = (
            commune_data.get("name", "")
            if isinstance(commune_data, dict)
            else str(commune_data or "")
        ).strip()
        raw_state = (
            state_data.get("name", "")
            if isinstance(state_data, dict)
            else str(state_data or "")
        ).strip()

        norm_c = normalizar_texto(raw_commune)
        if norm_c in mapa_comunas_canonica:
            comuna_canonica, region_canonica = mapa_comunas_canonica[norm_c]
        else:
            comuna_canonica = raw_commune.title()
            region_canonica = raw_state

        calle = addr.get("streetName", "").strip()
        numero = str(addr.get("streetNumber", "") or "").strip()
        if numero and numero.lower() not in ("none", "0", "s/n") and numero not in calle:
            direccion_completa = f"{calle} {numero}".strip()
        else:
            direccion_completa = calle

        sched = a.get("schedules", {})
        is_24_7 = sched.get("fullTime", False)
        if is_24_7:
            horario = "24/7 (Continuo)"
        else:
            attentions = sched.get("attentions", [])
            if attentions:
                d_inicio = attentions[0].get("day", "")[:3]
                d_fin = attentions[-1].get("day", "")[:3]
                h_inicio = attentions[0].get("startTime", "")
                h_fin = attentions[0].get("endTime", "")
                horario = f"{d_inicio} a {d_fin}: {h_inicio} - {h_fin}"
            else:
                horario = "Horario de comercio"

        puntos_limpios.append(
            {
                "id": a.get("agencyId"),
                "nombre": a.get("agencyName", "").strip(),
                "tipo": type_agency.get("name", "Punto Blue Express").strip(),
                "calle": calle,
                "numero": numero,
                "comuna": comuna_canonica,
                "region": region_canonica,
                "direccion_completa": direccion_completa,
                "horario": horario,
                "es_24_7": is_24_7,
                "lat": geo.get("latitude"),
                "lng": geo.get("longitude"),
            }
        )

    puntos_anteriores = cargar_puntos_lista()
    anteriores_por_id = {p.get("id"): p for p in puntos_anteriores if p.get("id") is not None}
    nuevos_por_id = {p.get("id"): p for p in puntos_limpios if p.get("id") is not None}

    ids_nuevos = [pid for pid in nuevos_por_id if pid not in anteriores_por_id]
    ids_eliminados = [pid for pid in anteriores_por_id if pid not in nuevos_por_id]

    puntos_nuevos = [nuevos_por_id[pid] for pid in ids_nuevos]
    puntos_eliminados = [anteriores_por_id[pid] for pid in ids_eliminados]

    data_dir, puntos_path, _ = _get_data_paths()
    os.makedirs(data_dir, exist_ok=True)
    with open(puntos_path, "w", encoding="utf-8") as f:
        json.dump(puntos_limpios, f, ensure_ascii=False, indent=2)

    # También sincronizar el archivo en la carpeta raíz 'calculadora bluexpress' si existe
    standalone_path = os.path.join(settings.BASE_DIR, "calculadora bluexpress", "puntos_blue_express.json")
    if os.path.isdir(os.path.dirname(standalone_path)):
        try:
            with open(standalone_path, "w", encoding="utf-8") as f:
                json.dump(puntos_limpios, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    invalidar_cache_puntos_blue()

    return {
        "ok": True,
        "total_recibidas_api": len(raw_data),
        "total_anterior": len(puntos_anteriores),
        "total_nuevo": len(puntos_limpios),
        "nuevos_count": len(puntos_nuevos),
        "eliminados_count": len(puntos_eliminados),
        "nuevos": puntos_nuevos,
        "eliminados": puntos_eliminados,
        "updated_at": obtener_fecha_puntos(),
        "puntos": puntos_limpios,
    }


def encontrar_punto_y_comuna_cercanos(lat, lng):
    """
    Dadas las coordenadas (lat, lng), busca el Punto Blue Express más cercano
    en el catálogo nacional y retorna (comuna, region, punto_dict, distancia_km).
    """
    try:
        lat_f, lng_f = float(lat), float(lng)
    except (TypeError, ValueError):
        return None, None, None, None

    puntos = cargar_puntos_lista()
    mejor_punto = None
    menor_dist = None

    for p in puntos:
        p_lat = p.get("lat")
        p_lng = p.get("lng")
        if p_lat is None or p_lng is None:
            continue
        dist = haversine_km(lat_f, lng_f, p_lat, p_lng)
        if dist is not None and (menor_dist is None or dist < menor_dist):
            menor_dist = dist
            mejor_punto = p

    if not mejor_punto:
        return None, None, None, None

    comuna_canonica = validar_comuna_existe(mejor_punto.get("comuna")) or mejor_punto.get("comuna")
    region_canonica = obtener_region_de_comuna(comuna_canonica)
    return comuna_canonica, region_canonica, mejor_punto, menor_dist


def detectar_comuna_por_ip_o_coords(ip=None, lat=None, lng=None, city_hint=None):
    """
    Detecta la comuna chilena y el Punto Blue Express más cercano usando:
    1. Coordenadas GPS (lat, lng) si se proporcionan.
    2. Geolocalización por IP pública (vía ip-api.com) como respaldo automático.
    """
    # 1. Si vienen coordenadas directas (ej. navegador GPS)
    if lat is not None and lng is not None:
        comuna, region, punto, dist = encontrar_punto_y_comuna_cercanos(lat, lng)
        if comuna:
            return {
                "ok": True,
                "metodo": "gps",
                "comuna": comuna,
                "region": region,
                "punto_cercano_id": punto.get("id") if punto else None,
                "punto_cercano_nombre": punto.get("nombre") if punto else None,
                "distancia_km": dist,
                "lat": float(lat),
                "lng": float(lng),
            }

    # 2. Si viene pista de ciudad directa
    if city_hint:
        comuna_directa = validar_comuna_existe(city_hint)
        if comuna_directa:
            pts = obtener_puntos_blue_por_comuna(comuna_directa)
            return {
                "ok": True,
                "metodo": "ip",
                "comuna": comuna_directa,
                "region": obtener_region_de_comuna(comuna_directa),
                "punto_cercano_id": pts[0]["id"] if pts else None,
                "punto_cercano_nombre": pts[0]["nombre"] if pts else None,
                "distancia_km": None,
            }

    # 3. Consulta por IP pública usando ip-api.com
    es_privada = (
        not ip
        or ip in ("127.0.0.1", "::1", "localhost")
        or ip.startswith("192.168.")
        or ip.startswith("10.")
        or ip.startswith("172.")
    )
    url = (
        "http://ip-api.com/json/?fields=status,countryCode,regionName,city,lat,lon"
        if es_privada
        else f"http://ip-api.com/json/{ip}?fields=status,countryCode,regionName,city,lat,lon"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RaraTienda/1.0"})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == "success" and data.get("countryCode") == "CL":
            city = data.get("city", "")
            ip_lat = data.get("lat")
            ip_lon = data.get("lon")

            comuna_por_nombre = validar_comuna_existe(city)
            comuna_coord, region_coord, punto_coord, dist_coord = encontrar_punto_y_comuna_cercanos(ip_lat, ip_lon)

            comuna_final = comuna_por_nombre or comuna_coord or ORIGEN_TIENDA_COMUNA
            region_final = obtener_region_de_comuna(comuna_final)

            # Si la comuna por nombre coincide con la del punto más cercano, usamos ese punto
            punto_id = None
            punto_nombre = None
            if punto_coord and normalizar_texto(punto_coord.get("comuna")) == normalizar_texto(comuna_final):
                punto_id = punto_coord.get("id")
                punto_nombre = punto_coord.get("nombre")
            else:
                pts_comuna = obtener_puntos_blue_por_comuna(comuna_final)
                if pts_comuna:
                    punto_id = pts_comuna[0].get("id")
                    punto_nombre = pts_comuna[0].get("nombre")

            return {
                "ok": True,
                "metodo": "ip",
                "comuna": comuna_final,
                "region": region_final,
                "punto_cercano_id": punto_id,
                "punto_cercano_nombre": punto_nombre,
                "distancia_km": dist_coord,
                "lat": ip_lat,
                "lng": ip_lon,
            }
    except Exception:
        pass

    return {
        "ok": False,
        "comuna": ORIGEN_TIENDA_COMUNA,
        "region": ORIGEN_TIENDA_REGION,
    }


