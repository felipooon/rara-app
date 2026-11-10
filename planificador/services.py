import os
import re
import math
import time
import json
import logging
from datetime import datetime, timedelta
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

EBIRD_API_BASE = 'https://api.ebird.org/v2'
OPEN_METEO_BASE = 'https://api.open-meteo.com/v1/forecast'

# Simple in-memory cache to prevent hitting eBird rate limits (500 req/hr)
CACHE = {}
CACHE_TTL = 900  # 15 minutes

def get_cached(key):
    entry = CACHE.get(key)
    if entry and time.time() - entry['timestamp'] < CACHE_TTL:
        return entry['data']
    return None

def set_cached(key, data):
    CACHE[key] = {
        'timestamp': time.time(),
        'data': data
    }

def get_api_key(request=None):
    if request:
        token = request.headers.get('X-eBirdApiToken') or request.GET.get('key')
        if token:
            return token
    return getattr(settings, 'EBIRD_API_KEY', '') or os.environ.get('EBIRD_API_KEY', '')

# Reference hubs in Región de Los Lagos (kept for backwards compatibility)
LOS_LAGOS_HUBS = {
    'puerto_varas': {'name': 'Puerto Varas (Base Lago Llanquihue)', 'lat': -41.3195, 'lng': -72.9854},
    'puerto_montt': {'name': 'Puerto Montt (Capital Regional & Seno)', 'lat': -41.4693, 'lng': -72.9424},
    'castro': {'name': 'Castro (Isla Grande de Chiloé Central)', 'lat': -42.4721, 'lng': -73.7732},
    'ancud': {'name': 'Ancud (Norte de Chiloé & Golfos)', 'lat': -41.8687, 'lng': -73.8277},
    'maullin': {'name': 'Maullín (Humedales & Santuario de la Naturaleza)', 'lat': -41.6158, 'lng': -73.6019},
    'osorno': {'name': 'Osorno (Valle Central & Acceso PN Puyehue)', 'lat': -40.5739, 'lng': -73.1335},
    'frutillar': {'name': 'Frutillar (Ribera Llanquihue)', 'lat': -41.1275, 'lng': -73.0583},
    'cochamo': {'name': 'Cochamó (Estuario del Reloncaví)', 'lat': -41.4939, 'lng': -72.3083}
}

# Comprehensive configuration for all 16 Chilean Regions (eBird CL-*)
CHILE_REGIONS_CONFIG = {
    'CL-AP': {
        'code': 'CL-AP',
        'name': 'Arica y Parinacota (XV)',
        'short_name': 'Arica y Parinacota',
        'macrozone': 'Norte Grande',
        'center': [-18.4783, -69.85],
        'zoom': 8,
        'default_hub': 'arica',
        'hubs': {
            'arica': {'name': 'Arica (Costa & Desembocadura Río Lluta)', 'lat': -18.4783, 'lng': -70.3126},
            'putre': {'name': 'Putre (Precordillera & Acceso Lauca)', 'lat': -18.1964, 'lng': -69.5592},
            'azapa': {'name': 'Valle de Azapa & Chaca (Oasis y Picaflores)', 'lat': -18.5186, 'lng': -70.1783},
            'parinacota': {'name': 'Parinacota / Lago Chungará (Altiplano)', 'lat': -18.2031, 'lng': -69.2683},
            'codpa': {'name': 'Valle de Codpa & Camarones', 'lat': -18.8331, 'lng': -69.7444}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región de Arica y Parinacota (Máximo Rango)'},
            {'id': 'costa_valles', 'name': 'Humedal Río Lluta, Costa de Arica & Valles (Azapa/Chaca)', 'lng_max': -69.85},
            {'id': 'precordillera', 'name': 'Precordillera de Putre, Socoroma & Quebradas Andinas', 'lng_min': -69.85, 'lng_max': -69.40},
            {'id': 'altiplano', 'name': 'Parque Nacional Lauca, Lago Chungará & Surire', 'lng_min': -69.45}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Valles, Costa y Altiplano)'},
            {'id': 'forest', 'name': 'Oasis, Valles Costeros y Queñoales (Picaflor de Arica, Comesebo)'},
            {'id': 'wetland', 'name': 'Humedal Río Lluta, Bofedales y Salares (Tagua gigante, Flamencos)'}
        ],
        'bio_strategy': 'El algoritmo programa valles agrícolas y quebradas al amanecer (actividad de picaflores endémicos como el Picaflor de Arica y el de Cora) y prioriza el Humedal del Río Lluta o bofedales altoandinos hacia media mañana.',
        'iconic_species': [
            {'comName': 'Picaflor de Arica', 'sciName': 'Eulidia yarrellii', 'habitat': 'valdivian_forest', 'rarity': 'En Peligro Crítico'},
            {'comName': 'Picaflor de Cora', 'sciName': 'Thaumastura cora', 'habitat': 'mixed_countryside', 'rarity': 'Especialista Valles'},
            {'comName': 'Tagua gigante', 'sciName': 'Fulica gigantea', 'habitat': 'lake_inland', 'rarity': 'Altiplano'},
            {'comName': 'Flamenco andino', 'sciName': 'Phoenicoparrus andinus', 'habitat': 'wetland_estuary', 'rarity': 'Bofedal / Salar'},
            {'comName': 'Gaviotín elegante', 'sciName': 'Thalasseus elegans', 'habitat': 'marine_coast', 'rarity': 'Humedal Lluta'}
        ]
    },
    'CL-TA': {
        'code': 'CL-TA',
        'name': 'Tarapacá (I)',
        'short_name': 'Tarapacá',
        'macrozone': 'Norte Grande',
        'center': [-20.25, -69.65],
        'zoom': 8,
        'default_hub': 'iquique',
        'hubs': {
            'iquique': {'name': 'Iquique (Borde Costero & Península Cavancha)', 'lat': -20.2307, 'lng': -70.1357},
            'pica': {'name': 'Oasis de Pica & Matilla (Desierto y Tamarugal)', 'lat': -20.4897, 'lng': -69.3292},
            'pozo_almonte': {'name': 'Reserva Nacional Pampa del Tamarugal', 'lat': -20.2597, 'lng': -69.7861},
            'colchane': {'name': 'Colchane & PN Volcán Isluga (Altiplano)', 'lat': -19.2756, 'lng': -68.6386},
            'patache': {'name': 'Punta Patache & Desembocadura Río Loa', 'lat': -20.8069, 'lng': -70.1939}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región de Tarapacá (Máximo Rango)'},
            {'id': 'costa', 'name': 'Costa de Iquique, Punta Patache & Río Loa', 'lng_max': -69.95},
            {'id': 'pampa_oasis', 'name': 'Pampa del Tamarugal & Oasis de Pica / Mamiña', 'lng_min': -69.95, 'lng_max': -69.10},
            {'id': 'altiplano', 'name': 'Altiplano de Isluga, Salar del Huasco & Colchane', 'lng_min': -69.10}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Corriente de Humboldt a Altiplano)'},
            {'id': 'forest', 'name': 'Bosque de Tamarugos y Oasis (Comesebo de los tamarugos)'},
            {'id': 'wetland', 'name': 'Costa Rocosa, Río Loa y Salar del Huasco (Gaviotín chico, Flamencos)'}
        ],
        'bio_strategy': 'Prioriza la Reserva Pampa del Tamarugal y los oasis de Pica al amanecer para detectar al endémico Comesebo de los tamarugos, desplazándose luego hacia roqueríos costeros o lagunas altoandinas.',
        'iconic_species': [
            {'comName': 'Comesebo de los tamarugos', 'sciName': 'Conirostrum tamarugense', 'habitat': 'valdivian_forest', 'rarity': 'Endémica Tamarugal'},
            {'comName': 'Gaviotín chico', 'sciName': 'Sternula lorata', 'habitat': 'marine_coast', 'rarity': 'En Peligro'},
            {'comName': 'Suri / Ñandú de la puna', 'sciName': 'Pterocnemia tarapacensis', 'habitat': 'mixed_countryside', 'rarity': 'Altiplano'},
            {'comName': 'Flamenco de James', 'sciName': 'Phoenicoparrus jamesi', 'habitat': 'wetland_estuary', 'rarity': 'Salar altoandino'}
        ]
    },
    'CL-AN': {
        'code': 'CL-AN',
        'name': 'Antofagasta (II)',
        'short_name': 'Antofagasta',
        'macrozone': 'Norte Grande',
        'center': [-23.35, -69.15],
        'zoom': 7,
        'default_hub': 'san_pedro',
        'hubs': {
            'san_pedro': {'name': 'San Pedro de Atacama (Salar & Ayllus)', 'lat': -22.9087, 'lng': -68.1997},
            'antofagasta': {'name': 'Antofagasta (La Chimba & Península Mejillones)', 'lat': -23.6509, 'lng': -70.3975},
            'calama': {'name': 'Calama (Oasis del Río Loa & Chiu-Chiu)', 'lat': -22.4544, 'lng': -68.9292},
            'mejillones': {'name': 'Mejillones & Isla Santa María', 'lat': -23.1000, 'lng': -70.4500},
            'taltal': {'name': 'Taltal & Quebrada Paposo (Oasis de Niebla)', 'lat': -25.4058, 'lng': -70.4839}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región de Antofagasta (Máximo Rango)'},
            {'id': 'atacama_salar', 'name': 'Cuenca de San Pedro de Atacama, Lagunas Altiplánicas & El Tatio', 'lng_min': -68.70},
            {'id': 'loa', 'name': 'Corredor Río Loa, Calama & Quillagua', 'lng_min': -69.70, 'lng_max': -68.60},
            {'id': 'costa_paposo', 'name': 'Costa de Antofagasta, Mejillones & Lomajes de Paposo', 'lng_max': -69.70}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Salar, Oasis y Costa de Humboldt)'},
            {'id': 'forest', 'name': 'Ayllus, Quebradas y Oasis de Niebla (Chercán, Mineros, Canasteros)'},
            {'id': 'wetland', 'name': 'Lagunas Altiplánicas y Costa Marina (3 especies de Flamencos, Chorlos)'}
        ],
        'bio_strategy': 'Combina los ayllus arbolados y quebradas al amanecer con las lagunas salobres del Salar de Atacama o surgencias marinas de Mejillones antes de que aumente el viento térmico de la tarde.',
        'iconic_species': [
            {'comName': 'Flamenco andino', 'sciName': 'Phoenicoparrus andinus', 'habitat': 'wetland_estuary', 'rarity': 'Salar de Atacama'},
            {'comName': 'Chorlo de la puna', 'sciName': 'Anarhynchus alticola', 'habitat': 'lake_inland', 'rarity': 'Altoandina'},
            {'comName': 'Caití', 'sciName': 'Recurvirostra andina', 'habitat': 'wetland_estuary', 'rarity': 'Lagunas salobres'},
            {'comName': 'Piquero peruano', 'sciName': 'Sula variegata', 'habitat': 'marine_coast', 'rarity': 'Corriente Humboldt'}
        ]
    },
    'CL-AT': {
        'code': 'CL-AT',
        'name': 'Atacama (III)',
        'short_name': 'Atacama',
        'macrozone': 'Norte Chico',
        'center': [-27.36, -70.33],
        'zoom': 8,
        'default_hub': 'caldera',
        'hubs': {
            'caldera': {'name': 'Caldera & Bahía Inglesa (Humedal Río Copiapó)', 'lat': -27.0672, 'lng': -70.8178},
            'copiapo': {'name': 'Copiapó (Valle & Ruta al Nevado Tres Cruces)', 'lat': -27.3668, 'lng': -70.3322},
            'huasco': {'name': 'Huasco & PN Llanos de Challe (Humedal Costero)', 'lat': -28.4664, 'lng': -71.2189},
            'chanaral': {'name': 'Chañaral & Parque Nacional Pan de Azúcar', 'lat': -26.3478, 'lng': -70.6225},
            'vallenar': {'name': 'Vallenar & Valle del Huasco', 'lat': -28.5761, 'lng': -70.7586}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región de Atacama (Máximo Rango)'},
            {'id': 'costa_humedales', 'name': 'Humedales Río Copiapó, Río Huasco & Llanos de Challe', 'lng_max': -70.50},
            {'id': 'pan_de_azucar', 'name': 'PN Pan de Azúcar & Costa Norte de Atacama', 'lat_min': -26.80},
            {'id': 'cordillera', 'name': 'PN Nevado Tres Cruces, Laguna Santa Rosa & Maricunga', 'lng_min': -69.80}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Desierto Florido, Humedales y Puna)'},
            {'id': 'forest', 'name': 'Matorral Desértico y Quebradas (Turca, Tapaculo, Bandurrilla)'},
            {'id': 'wetland', 'name': 'Desembocaduras de Copiapó/Huasco y Lagunas Andinas'}
        ],
        'bio_strategy': 'Aprovecha la mañana sin viento en el matorral costero (Llanos de Challe y Pan de Azúcar) para endemismos como la Turca, y visita estuarios como Huasco y Copiapó con la marea media.',
        'iconic_species': [
            {'comName': 'Turca', 'sciName': 'Pteroptochos megapodius', 'habitat': 'mixed_countryside', 'rarity': 'Endémica de Chile'},
            {'comName': 'Pingüino de Humboldt', 'sciName': 'Spheniscus humboldti', 'habitat': 'marine_coast', 'rarity': 'Vulnerable'},
            {'comName': 'Siete-colores', 'sciName': 'Tachuris rubrigastra', 'habitat': 'wetland_estuary', 'rarity': 'Totoral costero'},
            {'comName': 'Gaviota andina', 'sciName': 'Chroicocephalus serranus', 'habitat': 'lake_inland', 'rarity': 'Maricunga'}
        ]
    },
    'CL-CO': {
        'code': 'CL-CO',
        'name': 'Coquimbo (IV)',
        'short_name': 'Coquimbo',
        'macrozone': 'Norte Chico',
        'center': [-30.15, -71.15],
        'zoom': 8,
        'default_hub': 'la_serena',
        'hubs': {
            'la_serena': {'name': 'La Serena (Desembocadura Río Elqui & Punta Teatinos)', 'lat': -29.9027, 'lng': -71.2519},
            'coquimbo': {'name': 'Coquimbo & Humedal El Culebrón / Tongoy', 'lat': -29.9533, 'lng': -71.3436},
            'ovalle': {'name': 'Ovalle & Parque Nacional Bosque Fray Jorge', 'lat': -30.6011, 'lng': -71.1992},
            'vicuna': {'name': 'Vicuña & Valle de Elqui', 'lat': -30.0319, 'lng': -70.7081},
            'los_vilos': {'name': 'Los Vilos & Laguna Conchalí (Sitio Ramsar)', 'lat': -31.9083, 'lng': -71.5128}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región de Coquimbo (Máximo Rango)'},
            {'id': 'bahias_humedales', 'name': 'Red de Humedales Costeros: Punta Teatinos, Elqui, Culebrón y Tongoy', 'lat_min': -30.40, 'lng_max': -71.10},
            {'id': 'fray_jorge_limari', 'name': 'PN Bosque Fray Jorge, Desembocadura Limarí & Ovalle', 'lat_min': -31.00, 'lat_max': -30.30},
            {'id': 'choapa_conchali', 'name': 'Laguna Conchalí, Los Vilos & Valle del Choapa', 'lat_max': -31.00}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Humedales Costeros y Bosque Relicto)'},
            {'id': 'forest', 'name': 'Bosque Relicto Fray Jorge y Matorral (Tapaculo, Tenca, Rayadito)'},
            {'id': 'wetland', 'name': 'Humedales de Coquimbo, Tongoy y Conchalí (Playeras y Acuáticas)'}
        ],
        'bio_strategy': 'Inicia al amanecer en quebradas costeras o en el bosque valdiviano relicto de Fray Jorge, y encadena durante el día la red de humedales costeros entre Punta Teatinos, El Culebrón y Tongoy.',
        'iconic_species': [
            {'comName': 'Tapaculo', 'sciName': 'Scelorchilus albicollis', 'habitat': 'mixed_countryside', 'rarity': 'Endémica de Chile'},
            {'comName': 'Tenca', 'sciName': 'Mimus thenca', 'habitat': 'mixed_countryside', 'rarity': 'Endémica'},
            {'comName': 'Yunco', 'sciName': 'Pelecanoides garnotii', 'habitat': 'marine_coast', 'rarity': 'En Peligro'},
            {'comName': 'Pidén común', 'sciName': 'Pardirallus sanguinolentus', 'habitat': 'wetland_estuary', 'rarity': 'Humedales'}
        ]
    },
    'CL-VS': {
        'code': 'CL-VS',
        'name': 'Valparaíso (V)',
        'short_name': 'Valparaíso',
        'macrozone': 'Zona Central',
        'center': [-33.05, -71.40],
        'zoom': 9,
        'default_hub': 'santo_domingo',
        'hubs': {
            'santo_domingo': {'name': 'Santo Domingo / San Antonio (Humedal Río Maipo)', 'lat': -33.6358, 'lng': -71.6281},
            'concon': {'name': 'Concón & Mantagua (Desembocadura Río Aconcagua)', 'lat': -32.9189, 'lng': -71.5097},
            'olmué': {'name': 'Olmué (Parque Nacional La Campana)', 'lat': -32.9961, 'lng': -71.1856},
            'valparaiso': {'name': 'Valparaíso & Viña del Mar (Costa y Laguna Verde)', 'lat': -33.0472, 'lng': -71.6127},
            'algarrobo': {'name': 'Algarrobo, El Yali & Tunquén (Litoral Central)', 'lat': -33.3683, 'lng': -71.6689},
            'los_andes': {'name': 'Los Andes & Portillo (Cordillera Aconcagua)', 'lat': -32.8337, 'lng': -70.5982}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región de Valparaíso (Máximo Rango)'},
            {'id': 'litoral_sur', 'name': 'Humedal Río Maipo, Reserva El Yali, Cartagena & Algarrobo', 'lat_max': -33.25},
            {'id': 'aconcagua_mantagua', 'name': 'Humedal de Mantagua, Río Aconcagua, Quintero & Maitencillo', 'lat_min': -33.05, 'lng_max': -71.30},
            {'id': 'la_campana_interior', 'name': 'PN La Campana, Valle de Aconcagua & Cordillera', 'lng_min': -71.35}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Hotspots Top de Chile Central)'},
            {'id': 'forest', 'name': 'Bosque Esclerófilo y Palmas (Turca, Chiricoca, Carpinterito)'},
            {'id': 'wetland', 'name': 'Humedales Río Maipo, Mantagua y El Yali (+180 especies)'}
        ],
        'bio_strategy': 'La Región de Valparaíso concentra algunos de los mayores récords de Big Day en Chile: combina bosque esclerófilo (La Campana o quebradas costeras) al alba con los humedales de Mantagua, Aconcagua o Río Maipo.',
        'iconic_species': [
            {'comName': 'Chiricoca', 'sciName': 'Ochetorhynchus melanurus', 'habitat': 'mixed_countryside', 'rarity': 'Endémica de Chile'},
            {'comName': 'Turca', 'sciName': 'Pteroptochos megapodius', 'habitat': 'valdivian_forest', 'rarity': 'Endémica de Chile'},
            {'comName': 'Gaviotín elegante', 'sciName': 'Thalasseus elegans', 'habitat': 'wetland_estuary', 'rarity': 'Río Maipo / Aconcagua'},
            {'comName': 'Churrete costero', 'sciName': 'Cinclodes nigrofumosus', 'habitat': 'marine_coast', 'rarity': 'Endémica Litoral'}
        ]
    },
    'CL-RM': {
        'code': 'CL-RM',
        'name': 'Metropolitana de Santiago (RM)',
        'short_name': 'Metropolitana',
        'macrozone': 'Zona Central',
        'center': [-33.50, -70.55],
        'zoom': 9,
        'default_hub': 'santiago',
        'hubs': {
            'santiago': {'name': 'Santiago Oriente (Acceso Farellones & Parques)', 'lat': -33.4167, 'lng': -70.5667},
            'san_jose_maipo': {'name': 'San José de Maipo (Cajón del Maipo & El Yeso)', 'lat': -33.6408, 'lng': -70.3528},
            'lampa_batuco': {'name': 'Lampa & Humedal de Batuco (Santuario Acuático)', 'lat': -33.2261, 'lng': -70.8081},
            'pirque': {'name': 'Pirque & Reserva Nacional Río Clarillo', 'lat': -33.7269, 'lng': -70.4872},
            'paine': {'name': 'Paine, Laguna de Aculeo & Altos de Cantillana', 'lat': -33.8167, 'lng': -70.7500}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región Metropolitana (Máximo Rango)'},
            {'id': 'cajon_maipo', 'name': 'Cajón del Maipo, Embalse El Yeso & Valle El Arenas', 'lng_min': -70.48, 'lat_max': -33.48},
            {'id': 'farellones_andes', 'name': 'Ruta Farellones, Valle Nevado & Yerba Loca', 'lng_min': -70.48, 'lat_min': -33.48},
            {'id': 'batuco_valle', 'name': 'Humedal de Batuco, Lampa, Maipo Medio & Río Clarillo', 'lng_max': -70.48}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Humedal, Esclerófilo y Alta Cordillera)'},
            {'id': 'forest', 'name': 'Bosque Esclerófilo y Quebradas Andinas (Turca, Chiricoca, Cóndor)'},
            {'id': 'wetland', 'name': 'Humedal de Batuco y Vegas Altoandinas (Chorlo de diadema, Piuquén)'}
        ],
        'bio_strategy': 'Combina quebradas de bosque esclerófilo (Río Clarillo o Camino a Farellones) a primera hora para detectar Turca y Chiricoca, subiendo a vegas cordilleranas (El Yeso) o bajando al Humedal de Batuco.',
        'iconic_species': [
            {'comName': 'Chorlito cordillerano', 'sciName': 'Phegornis mitchellii', 'habitat': 'wetland_estuary', 'rarity': 'Joya Altoandina'},
            {'comName': 'Cóndor andino', 'sciName': 'Vultur gryphus', 'habitat': 'mixed_countryside', 'rarity': 'Cajón del Maipo'},
            {'comName': 'Chiricoca', 'sciName': 'Ochetorhynchus melanurus', 'habitat': 'valdivian_forest', 'rarity': 'Endémica de Chile'},
            {'comName': 'Siete-colores', 'sciName': 'Tachuris rubrigastra', 'habitat': 'lake_inland', 'rarity': 'Humedal de Batuco'}
        ]
    },
    'CL-LI': {
        'code': 'CL-LI',
        'name': "O'Higgins (VI)",
        'short_name': "O'Higgins",
        'macrozone': 'Zona Central',
        'center': [-34.40, -71.20],
        'zoom': 8,
        'default_hub': 'pichilemu',
        'hubs': {
            'pichilemu': {'name': 'Pichilemu & Cáhuil (Salinas y Humedal Petrel)', 'lat': -34.3872, 'lng': -72.0053},
            'rancagua': {'name': 'Rancagua & Reserva Nacional Río de los Cipreses', 'lat': -34.1708, 'lng': -70.7444},
            'san_fernando': {'name': 'San Fernando & Sierras de Bellavista', 'lat': -34.5839, 'lng': -70.9892},
            'rapel': {'name': 'Lago Rapel & Navidad (Desembocadura Río Rapel)', 'lat': -34.1422, 'lng': -71.5036},
            'bucalemu': {'name': 'Bucalemu & Laguna Boyeruca', 'lat': -34.6419, 'lng': -72.0431}
        },
        'subzones': [
            {'id': 'all', 'name': "Toda la Región de O'Higgins (Máximo Rango)"},
            {'id': 'costa_cahuil', 'name': 'Humedales de Cáhuil, Petrel, Bucalemu & Navidad', 'lng_max': -71.50},
            {'id': 'cordillera_cipreses', 'name': 'RN Río de los Cipreses & Sierras de Bellavista (Loros Tricahue)', 'lng_min': -70.95}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Cordillera a Salinas Costeras)'},
            {'id': 'forest', 'name': 'Bosque Esclerófilo y Precordillera (Tricahue, Hued-hued castaño)'},
            {'id': 'wetland', 'name': 'Salinas de Cáhuil, Laguna Petrel y Bucalemu (Cisnes, Flamencos)'}
        ],
        'bio_strategy': 'En la precordillera (Río de los Cipreses / Bellavista) las bandadas de Loro Tricahue y el Hued-hued castaño son muy vocales por la mañana; en la costa, las salinas de Cáhuil y Petrel brillan al mediodía.',
        'iconic_species': [
            {'comName': 'Tricahue', 'sciName': 'Cyanoliseus patagonus', 'habitat': 'valdivian_forest', 'rarity': 'Río Los Cipreses'},
            {'comName': 'Hued-hued castaño', 'sciName': 'Pteroptochos castaneus', 'habitat': 'valdivian_forest', 'rarity': 'Precordillera'},
            {'comName': 'Cisne coscoroba', 'sciName': 'Coscoroba coscoroba', 'habitat': 'wetland_estuary', 'rarity': 'Cáhuil / Petrel'}
        ]
    },
    'CL-ML': {
        'code': 'CL-ML',
        'name': 'Maule (VII)',
        'short_name': 'Maule',
        'macrozone': 'Zona Central',
        'center': [-35.45, -71.55],
        'zoom': 8,
        'default_hub': 'talca',
        'hubs': {
            'talca': {'name': 'Talca & Acceso RN Altos de Lircay', 'lat': -35.4264, 'lng': -71.6554},
            'vilches': {'name': 'Vilches & RN Altos de Lircay (Bosque Maulino)', 'lat': -35.5969, 'lng': -71.1636},
            'constitucion': {'name': 'Constitución & Humedales de Putú - Huenchullamí', 'lat': -35.3333, 'lng': -72.4167},
            'iloca': {'name': 'Iloca, Vichuquén & Laguna Torca', 'lat': -34.9333, 'lng': -72.1833},
            'colbun': {'name': 'Colbún & Laguna del Maule (Alta Cordillera)', 'lat': -35.6989, 'lng': -71.4083}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región del Maule (Máximo Rango)'},
            {'id': 'lircay_andes', 'name': 'RN Altos de Lircay, Radal Siete Tazas & Laguna del Maule', 'lng_min': -71.40},
            {'id': 'costa_putu', 'name': 'Humedales de Putú, Laguna Torca, Vichuquén & Reloca', 'lng_max': -71.90}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Bosque Maulino y Humedales Costeros)'},
            {'id': 'forest', 'name': 'Bosque de Roble-Hualo en Altos de Lircay (Carpintero negro, Hued-hued)'},
            {'id': 'wetland', 'name': 'Humedales de Putú, Laguna Torca y Laguna del Maule'}
        ],
        'bio_strategy': 'Programa temprano los bosques de Nothofagus en Altos de Lircay o Siete Tazas (límite norte del Carpintero negro y Cachaña) y continúa hacia los extensos humedales costeros de Putú y Laguna Torca.',
        'iconic_species': [
            {'comName': 'Hued-hued castaño', 'sciName': 'Pteroptochos castaneus', 'habitat': 'valdivian_forest', 'rarity': 'Especialista Maulino'},
            {'comName': 'Carpintero negro', 'sciName': 'Campephilus magellanicus', 'habitat': 'valdivian_forest', 'rarity': 'Altos de Lircay'},
            {'comName': 'Cuervo de pantano', 'sciName': 'Plegadis chihi', 'habitat': 'wetland_estuary', 'rarity': 'Humedales de Putú'}
        ]
    },
    'CL-NB': {
        'code': 'CL-NB',
        'name': 'Ñuble (XVI)',
        'short_name': 'Ñuble',
        'macrozone': 'Zona Sur',
        'center': [-36.62, -72.10],
        'zoom': 8,
        'default_hub': 'chillan',
        'hubs': {
            'chillan': {'name': 'Chillán (Valle Central & Acceso Cordillera)', 'lat': -36.6063, 'lng': -72.1034},
            'las_trancas': {'name': 'Valle Las Trancas & RN Ñuble / Huemules de Niblinto', 'lat': -36.9114, 'lng': -71.4797},
            'cobquecura': {'name': 'Cobquecura, Buchupureo & Desembocadura Río Itata', 'lat': -36.1328, 'lng': -72.7931},
            'san_fabian': {'name': 'San Fabián de Alico (Cajón del Río Ñuble)', 'lat': -36.5567, 'lng': -71.5494}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región de Ñuble (Máximo Rango)'},
            {'id': 'cordillera_trancas', 'name': 'Valle Las Trancas, Shangri-La & Reserva Nacional Ñuble', 'lng_min': -71.80},
            {'id': 'costa_itata', 'name': 'Humedal Desembocadura Río Itata, Cobquecura & Vegas de Itata', 'lng_max': -72.40}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Andes de Ñuble a Desembocadura del Itata)'},
            {'id': 'forest', 'name': 'Bosque Caducifolio y Nothofagus (Hued-hued castaño, Carpintero negro)'},
            {'id': 'wetland', 'name': 'Desembocadura del Río Itata y Lobería de Cobquecura'}
        ],
        'bio_strategy': 'Al amanecer los bosques de Las Trancas y Niblinto ofrecen alta detectabilidad vocal de Hued-hued castaño y Carpintero negro; hacia el mediodía, la desembocadura del Río Itata reúne miles de aves costeras.',
        'iconic_species': [
            {'comName': 'Hued-hued castaño', 'sciName': 'Pteroptochos castaneus', 'habitat': 'valdivian_forest', 'rarity': 'Endémica Centro-Sur'},
            {'comName': 'Pato cortacorrientes', 'sciName': 'Merganetta armata', 'habitat': 'lake_inland', 'rarity': 'Ríos Andinos'},
            {'comName': 'Gaviotín elegante', 'sciName': 'Thalasseus elegans', 'habitat': 'wetland_estuary', 'rarity': 'Río Itata'}
        ]
    },
    'CL-BI': {
        'code': 'CL-BI',
        'name': 'Biobío (VIII)',
        'short_name': 'Biobío',
        'macrozone': 'Zona Sur',
        'center': [-37.15, -72.90],
        'zoom': 8,
        'default_hub': 'concepcion',
        'hubs': {
            'concepcion': {'name': 'Concepción & Talcahuano (Humedal Rocuant-Andalién)', 'lat': -36.8201, 'lng': -73.0444},
            'peninsula_hualpen': {'name': 'Península de Hualpén, Chome & Desembocadura Biobío', 'lat': -36.7833, 'lng': -73.1667},
            'arauco_tubul': {'name': 'Arauco & Humedal Tubul-Raqui (Golfo de Arauco)', 'lat': -37.2456, 'lng': -73.3175},
            'canete_lanalhue': {'name': 'Cañete, Lago Lanalhue & Cordillera de Nahuelbuta', 'lat': -37.8014, 'lng': -73.3961},
            'los_angeles': {'name': 'Los Ángeles & Parque Nacional Laguna del Laja', 'lat': -37.4697, 'lng': -72.3537}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región del Biobío (Máximo Rango)'},
            {'id': 'gran_concepcion', 'name': 'Humedal Rocuant-Andalién, Península de Hualpén &PN Nonguén', 'lat_min': -37.05, 'lng_max': -72.85},
            {'id': 'arauco_nahuelbuta', 'name': 'Humedal Tubul-Raqui, Golfo de Arauco & Nahuelbuta', 'lat_max': -37.05, 'lng_max': -72.90},
            {'id': 'alto_biobio_laja', 'name': 'PN Laguna del Laja, Antuco & Alto Biobío', 'lng_min': -72.60}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (PN Nonguén, Rocuant y Golfo de Arauco)'},
            {'id': 'forest', 'name': 'Bosque de Nonguén y Nahuelbuta (Chucao, Hued-hued castaño, Concón)'},
            {'id': 'wetland', 'name': 'Megahumedales Rocuant-Andalién y Tubul-Raqui (Playeras y Acuáticas)'}
        ],
        'bio_strategy': 'El Biobío es zona de contacto biogeográfico: inicia al amanecer en el Parque Nacional Nonguén o Nahuelbuta (donde conviven Hued-hued castaño y Chucao) y visita Rocuant-Andalién o Tubul-Raqui con la marea.',
        'iconic_species': [
            {'comName': 'Hued-hued castaño', 'sciName': 'Pteroptochos castaneus', 'habitat': 'valdivian_forest', 'rarity': 'Límite Sur'},
            {'comName': 'Chucao', 'sciName': 'Scelorchilus rubecula', 'habitat': 'valdivian_forest', 'rarity': 'Bosque Nonguén'},
            {'comName': 'Zarapito de pico recto', 'sciName': 'Limosa haemastica', 'habitat': 'wetland_estuary', 'rarity': 'Rocuant / Tubul'}
        ]
    },
    'CL-AR': {
        'code': 'CL-AR',
        'name': 'La Araucanía (IX)',
        'short_name': 'La Araucanía',
        'macrozone': 'Zona Sur',
        'center': [-38.90, -72.30],
        'zoom': 8,
        'default_hub': 'pucon',
        'hubs': {
            'pucon': {'name': 'Pucón & Villarrica (PN Huerquehue y Volcán Villarrica)', 'lat': -39.2822, 'lng': -71.9542},
            'temuco': {'name': 'Temuco & Monumento Natural Cerro Ñielol', 'lat': -38.7359, 'lng': -72.5904},
            'curacautin': {'name': 'Curacautín, Malalcahuello & PN Conguillío', 'lat': -38.4369, 'lng': -71.8883},
            'angol': {'name': 'Angol & Parque Nacional Nahuelbuta', 'lat': -37.7989, 'lng': -72.7086},
            'saavedra': {'name': 'Puerto Saavedra, Lago Budi & Queule (Humedales Costeros)', 'lat': -38.7833, 'lng': -73.4000}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región de La Araucanía (Máximo Rango)'},
            {'id': 'andina_conguillio', 'name': 'Corredor Araucarias: PN Conguillío, Huerquehue & Villarrica', 'lng_min': -72.25},
            {'id': 'nahuelbuta_valle', 'name': 'PN Nahuelbuta, MN Cerro Ñielol & Valle Central', 'lng_min': -73.05, 'lng_max': -72.25},
            {'id': 'costa_budi', 'name': 'Lago Budi, Río Imperial, Toltén & Humedal de Queule', 'lng_max': -73.05}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Bosque de Araucarias a Lago Budi)'},
            {'id': 'forest', 'name': 'Bosques de Araucaria y Nothofagus (Carpintero negro, Choroy, Chucao)'},
            {'id': 'wetland', 'name': 'Lago Budi, Humedal de Queule y Lagunas Andinas (Cisnes, Pato anteojillo)'}
        ],
        'bio_strategy': 'Programa bosques antiguos de Araucaria y Coigüe (Conguillío, Huerquehue, Nahuelbuta o Ñielol) temprano al amanecer para Carpintero negro y tapaculos, y humedales como el Lago Budi o lagos precordilleranos por la tarde.',
        'iconic_species': [
            {'comName': 'Carpintero negro', 'sciName': 'Campephilus magellanicus', 'habitat': 'valdivian_forest', 'rarity': 'Bosque Araucarias'},
            {'comName': 'Choroy', 'sciName': 'Enicognathus leptorhynchus', 'habitat': 'valdivian_forest', 'rarity': 'Endémica Sur'},
            {'comName': 'Cisne coscoroba', 'sciName': 'Coscoroba coscoroba', 'habitat': 'wetland_estuary', 'rarity': 'Lago Budi'},
            {'comName': 'Pato anteojillo', 'sciName': 'Speculanas specularis', 'habitat': 'lake_inland', 'rarity': 'Ríos y Lagos Andinos'}
        ]
    },
    'CL-LR': {
        'code': 'CL-LR',
        'name': 'Los Ríos (XIV)',
        'short_name': 'Los Ríos',
        'macrozone': 'Zona Sur',
        'center': [-39.85, -72.95],
        'zoom': 9,
        'default_hub': 'valdivia',
        'hubs': {
            'valdivia': {'name': 'Valdivia (Santuario Río Cruces & Humedales Urbanos)', 'lat': -39.8142, 'lng': -73.2459},
            'niebla_corral': {'name': 'Niebla, Corral & Parque Oncol / PN Alerce Costero', 'lat': -39.8667, 'lng': -73.3958},
            'panguipulli': {'name': 'Panguipulli, Siete Lagos & Reserva Huilo-Huilo', 'lat': -39.6422, 'lng': -72.3328},
            'lago_ranco': {'name': 'Lago Ranco, Futrono & Cuenca del Ranco', 'lat': -40.3208, 'lng': -72.4789},
            'mehuin': {'name': 'Mehuín & Humedal Río Lingue (Costa Valdiviana)', 'lat': -39.4333, 'lng': -73.2167}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región de Los Ríos (Máximo Rango)'},
            {'id': 'valdivia_cruces', 'name': 'Santuario Río Cruces, Humedales de Valdivia, Oncol & Costa', 'lng_max': -72.90},
            {'id': 'siete_lagos', 'name': 'Panguipulli, Huilo-Huilo & Cuenca del Lago Ranco', 'lng_min': -72.90}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Selva Valdiviana y Santuario Río Cruces)'},
            {'id': 'forest', 'name': 'Selva Valdiviana en Oncol, Llancahue y Huilo-Huilo (Chucao, Huet-huet)'},
            {'id': 'wetland', 'name': 'Santuario Río Cruces, Catrico y Estuario de Corral (Cisnes, Garzas)'}
        ],
        'bio_strategy': 'En Los Ríos la selva valdiviana costera (Parque Oncol, Llancahue, Alerce Costero) ofrece un coro matutino extraordinario de tapaculos; desde media mañana la ruta recorre el Santuario del Río Cruces y humedales de Valdivia.',
        'iconic_species': [
            {'comName': 'Cisne de cuello negro', 'sciName': 'Cygnus melancoryphus', 'habitat': 'wetland_estuary', 'rarity': 'Santuario Río Cruces'},
            {'comName': 'Chucao', 'sciName': 'Scelorchilus rubecula', 'habitat': 'valdivian_forest', 'rarity': 'Selva Valdiviana'},
            {'comName': 'Huet-huet común', 'sciName': 'Pteroptochos tarnii', 'habitat': 'valdivian_forest', 'rarity': 'Especialista'},
            {'comName': 'Garza cuca', 'sciName': 'Ardea cocoi', 'habitat': 'wetland_estuary', 'rarity': 'Humedales Valdivia'}
        ]
    },
    'CL-LL': {
        'code': 'CL-LL',
        'name': 'Los Lagos (X)',
        'short_name': 'Los Lagos',
        'macrozone': 'Zona Sur',
        'center': [-41.35, -73.05],
        'zoom': 9,
        'default_hub': 'puerto_varas',
        'hubs': LOS_LAGOS_HUBS,
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región de Los Lagos (Máximo Rango)'},
            {'id': 'llanquihue', 'name': 'Cuenca Lago Llanquihue & PN Vicente Pérez Rosales', 'lng_min': -74.0, 'lng_max': -72.1, 'lat_min': -41.75},
            {'id': 'chiloe', 'name': 'Archipiélago de Chiloé (Humedales & Costa Pacífica)', 'lat_max': -41.80},
            {'id': 'maullin', 'name': 'Santuario Humedales de Maullín & Desembocadura', 'lat_min': -41.80, 'lat_max': -41.45, 'lng_min': -73.9, 'lng_max': -73.4, 'keywords': ['maullín', 'carelmapu']},
            {'id': 'osorno_puyehue', 'name': 'Parque Nacional Puyehue & Bosque Valdiviano', 'lat_min': -41.0}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Todas las Familias)'},
            {'id': 'forest', 'name': 'Especialistas de Bosque Templado (Chucao, Huet-huet, Carpintero)'},
            {'id': 'wetland', 'name': 'Humedales y Aves Playeras (Cisnes, Zarapitos, Flamencos)'}
        ],
        'bio_strategy': 'El algoritmo programa bosques templados al amanecer (máxima detección de tapaculos como Chucao y Churrín por canto) y traslada la ruta a estuarios y humedales hacia el mediodía y la tarde cuando las aves acuáticas se alimentan con la marea.',
        'iconic_species': list(ICONIC_LOS_LAGOS_SPECIES.values()) if 'ICONIC_LOS_LAGOS_SPECIES' in globals() else []
    },
    'CL-AI': {
        'code': 'CL-AI',
        'name': 'Aysén (XI)',
        'short_name': 'Aysén',
        'macrozone': 'Zona Austral',
        'center': [-45.57, -72.06],
        'zoom': 7,
        'default_hub': 'coyhaique',
        'hubs': {
            'coyhaique': {'name': 'Coyhaique (Reserva Coyhaique & Valle Simpson)', 'lat': -45.5712, 'lng': -72.0685},
            'puerto_aysen': {'name': 'Puerto Aysén & Puerto Chacabuco (Fiordos)', 'lat': -45.4033, 'lng': -72.6917},
            'chile_chico': {'name': 'Chile Chico & PN Patagonia (Lago General Carrera)', 'lat': -46.5411, 'lng': -71.7244},
            'puyuhuapi': {'name': 'Puyuhuapi & Parque Nacional Queulat', 'lat': -44.3256, 'lng': -72.5564},
            'cochrane': {'name': 'Cochrane & Valle Chacabuco (Estepa y Bosque)', 'lat': -47.2553, 'lng': -72.5733}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región de Aysén (Máximo Rango)'},
            {'id': 'coyhaique_simpson', 'name': 'Coyhaique, Balmaceda, Ñirehuao & Puerto Aysén', 'lat_min': -46.10, 'lat_max': -45.00},
            {'id': 'queulat_norte', 'name': 'Carretera Austral Norte: PN Queulat, Puyuhuapi & La Junta', 'lat_min': -45.00},
            {'id': 'carrera_patagonia', 'name': 'Lago General Carrera, PN Patagonia & Cochrane', 'lat_max': -46.10}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (BosqueSiempreverde a Estepa Patagónica)'},
            {'id': 'forest', 'name': 'Bosque de Lenga y Siempreverde (Carpintero negro, Cachaña, Chucao)'},
            {'id': 'wetland', 'name': 'Lagunas de Estepa (Ñirehuao/Chacabuco) y Fiordos (Pimpollo tobiano)'}
        ],
        'bio_strategy': 'Combina bosques de lenga y ñirre a primera hora (Reserva Coyhaique o Queulat) con las lagunas esteparias de Balmaceda, Ñirehuao o Valle Chacabuco donde nidifican aves acuáticas patagónicas.',
        'iconic_species': [
            {'comName': 'Carpintero negro', 'sciName': 'Campephilus magellanicus', 'habitat': 'valdivian_forest', 'rarity': 'Bosque de Lenga'},
            {'comName': 'Pimpollo tobiano', 'sciName': 'Podiceps gallardoi', 'habitat': 'lake_inland', 'rarity': 'En Peligro Crítico'},
            {'comName': 'Canquén común', 'sciName': 'Chloephaga poliocephala', 'habitat': 'wetland_estuary', 'rarity': 'Patagonia'},
            {'comName': 'Choique / Ñandú', 'sciName': 'Rhea pennata', 'habitat': 'mixed_countryside', 'rarity': 'Estepa Patagónica'}
        ]
    },
    'CL-MA': {
        'code': 'CL-MA',
        'name': 'Magallanes y la Antártica Chilena (XII)',
        'short_name': 'Magallanes',
        'macrozone': 'Zona Austral',
        'center': [-52.60, -71.20],
        'zoom': 7,
        'default_hub': 'punta_arenas',
        'hubs': {
            'punta_arenas': {'name': 'Punta Arenas (Humedal Tres Puentes & Reserva Magallanes)', 'lat': -53.1638, 'lng': -70.9171},
            'puerto_natales': {'name': 'Puerto Natales & Seno Última Esperanza', 'lat': -51.7236, 'lng': -72.4875},
            'torres_del_paine': {'name': 'Parque Nacional Torres del Paine', 'lat': -51.0950, 'lng': -72.9800},
            'porvenir': {'name': 'Porvenir & Bahía Lomas (Tierra del Fuego)', 'lat': -53.2956, 'lng': -70.3686},
            'puerto_williams': {'name': 'Puerto Williams & Isla Navarino (Cabo de Hornos)', 'lat': -54.9333, 'lng': -67.6167}
        },
        'subzones': [
            {'id': 'all', 'name': 'Toda la Región de Magallanes (Máximo Rango)'},
            {'id': 'estrecho_punta_arenas', 'name': 'Punta Arenas, Humedal Tres Puentes, Fuerte Bulnes & Pali Aike', 'lat_max': -52.20, 'lng_max': -70.50},
            {'id': 'ultima_esperanza_paine', 'name': 'Puerto Natales, Sierra Baguales & PN Torres del Paine', 'lat_min': -52.20},
            {'id': 'tierra_del_fuego', 'name': 'Tierra del Fuego: Porvenir, Bahía Lomas & Parque Pingüino Rey', 'lng_min': -70.50}
        ],
        'focus_options': [
            {'id': 'all', 'name': 'Máxima Biodiversidad (Estepa, Bosque Magallánico y Estrecho)'},
            {'id': 'forest', 'name': 'Bosque Magallánico y Estepa (Carpintero negro, Chorlo de Magallanes)'},
            {'id': 'wetland', 'name': 'Humedal Tres Puentes, Bahía Lomas y Costas del Estrecho'}
        ],
        'bio_strategy': 'Prioriza la Reserva Magallanes o bosques subantárticos temprano cuando el viento austral es más moderado, y luego recorre el Humedal Tres Puentes, la costa del Estrecho de Magallanes y lagunas esteparias.',
        'iconic_species': [
            {'comName': 'Chorlo de Magallanes', 'sciName': 'Pluvianellus socialis', 'habitat': 'wetland_estuary', 'rarity': 'Joya Patagónica'},
            {'comName': 'Canquén colorado', 'sciName': 'Chloephaga rubidiceps', 'habitat': 'mixed_countryside', 'rarity': 'En Peligro Crítico'},
            {'comName': 'Pingüino rey', 'sciName': 'Aptenodytes patagonicus', 'habitat': 'marine_coast', 'rarity': 'Tierra del Fuego'},
            {'comName': 'Carpintero negro', 'sciName': 'Campephilus magellanicus', 'habitat': 'valdivian_forest', 'rarity': 'Bosque Magallánico'}
        ]
    }
}

# Habitat classifications for birding hotspots across Chile
HABITAT_KEYWORDS = {
    'valdivian_forest': [
        'parque nacional', 'reserva nacional', 'alerce', 'puyehue', 'vicente pérez', 'bosque', 'sendero',
        'volcán', 'cascadas', 'pumallín', 'lahuen ñadi', 'quebrada', 'oasis', 'tamarugal', 'fray jorge',
        'la campana', 'clarillo', 'cipreses', 'lircay', 'siete tazas', 'trancas', 'nonguén', 'nahuelbuta',
        'conguillío', 'huerquehue', 'ñielol', 'oncol', 'huilo', 'queulat', 'paine', 'magallanes', 'cajón'
    ],
    'wetland_estuary': [
        'humedal', 'estuario', 'río', 'maullín', 'caulín', 'pullao', 'curaco', 'putemún', 'santuario',
        'laguna', 'totoral', 'desembocadura', 'salar', 'bofedal', 'vega', 'batuco', 'mantagua', 'yali',
        'cáhuil', 'petrel', 'putú', 'rocuant', 'tubul', 'budi', 'cruces', 'tres puentes', 'lluta'
    ],
    'marine_coast': [
        'playa', 'bahía', 'caleta', 'punta', 'seno', 'costanera', 'puerto', 'roquerío', 'isla',
        'canal', 'lacustre', 'muelle', 'península', 'estrecho', 'fiordo', 'faro', 'litoral', 'costa'
    ],
    'lake_inland': [
        'lago', 'llanquihue', 'todos los santos', 'rupanco', 'ranco', 'embalse', 'chungará', 'cotacotani',
        'miscanti', 'acabón', 'yeso', 'aculeo', 'rapel', 'colbún', 'laja', 'villarrica', 'general carrera'
    ]
}

# Top iconic bird species in Los Lagos to track for specific target lists
ICONIC_LOS_LAGOS_SPECIES = {
    'chucao': {'comName': 'Chucao', 'sciName': 'Scelorchilus rubecula', 'habitat': 'valdivian_forest', 'rarity': 'Endémica de bosque', 'activity': 'dawn'},
    'huethuet': {'comName': 'Huet-huet común', 'sciName': 'Pteroptochos tarnii', 'habitat': 'valdivian_forest', 'rarity': 'Especialista', 'activity': 'dawn'},
    'carpintero_negro': {'comName': 'Carpintero negro', 'sciName': 'Campephilus magellanicus', 'habitat': 'valdivian_forest', 'rarity': 'Emblemática', 'activity': 'morning'},
    'rayadito': {'comName': 'Rayadito', 'sciName': 'Aphrastura spinicauda', 'habitat': 'valdivian_forest', 'rarity': 'Frecuente en bosque', 'activity': 'morning'},
    'comesebo': {'comName': 'Comesebo grande', 'sciName': 'Pygarrhichas albogularis', 'habitat': 'valdivian_forest', 'rarity': 'Especialista', 'activity': 'morning'},
    'churrin': {'comName': 'Churrín de la mocha', 'sciName': 'Eugralla paradoxa', 'habitat': 'valdivian_forest', 'rarity': 'Difícil / Tapaculo', 'activity': 'dawn'},
    'cisne_cuello_negro': {'comName': 'Cisne de cuello negro', 'sciName': 'Cygnus melancoryphus', 'habitat': 'wetland_estuary', 'rarity': 'Humedales', 'activity': 'all_day'},
    'zarapito_recto': {'comName': 'Zarapito de pico recto', 'sciName': 'Limosa haemastica', 'habitat': 'wetland_estuary', 'rarity': 'Migratoria Neártica', 'activity': 'tides'},
    'flamenco_chileno': {'comName': 'Flamenco chileno', 'sciName': 'Phoenicopterus chilensis', 'habitat': 'wetland_estuary', 'rarity': 'Humedales Chiloé', 'activity': 'midday'},
    'martin_pescador': {'comName': 'Martín pescador', 'sciName': 'Megaceryle torquata', 'habitat': 'lake_inland', 'rarity': 'Acuática', 'activity': 'morning'},
    'quetru_no_volador': {'comName': 'Quetru no volador', 'sciName': 'Tachyeres pteneres', 'habitat': 'marine_coast', 'rarity': 'Costa marina', 'activity': 'all_day'},
    'pilpilen_negro': {'comName': 'Pilpilén negro', 'sciName': 'Haematopus ater', 'habitat': 'marine_coast', 'rarity': 'Costera rocosa', 'activity': 'tides'}
}

CHILE_REGIONS_CONFIG['CL-LL']['iconic_species'] = list(ICONIC_LOS_LAGOS_SPECIES.values())

# Master Reference Checklist of Probable Bird Species in Región de Los Lagos (CL-LL)
REGIONAL_PROBABLE_SPECIES = [
    # Bosque Templado y Sotobosque
    {'speciesCode': 'chucao1', 'comName': 'Chucao', 'sciName': 'Scelorchilus rubecula', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'bkhhuet1', 'comName': 'Huet-huet común', 'sciName': 'Pteroptochos tarnii', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'magwoo1', 'comName': 'Carpintero negro', 'sciName': 'Campephilus magellanicus', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Media'},
    {'speciesCode': 'stbwoo1', 'comName': 'Carpinterito', 'sciName': 'Veniliornis lignarius', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Media'},
    {'speciesCode': 'thbray1', 'comName': 'Rayadito', 'sciName': 'Aphrastura spinicauda', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'whtwhi1', 'comName': 'Comesebo grande', 'sciName': 'Pygarrhichas albogularis', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'octtap1', 'comName': 'Churrín de la mocha', 'sciName': 'Eugralla paradoxa', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Media'},
    {'speciesCode': 'magtap1', 'comName': 'Churrín del sur', 'sciName': 'Scytalopus magellanicus', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'destai1', 'comName': 'Colilarga', 'sciName': 'Sylviorthorhynchus desmursii', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'whcwae1', 'comName': 'Fío-fío', 'sciName': 'Elaenia albiceps', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'pattyr1', 'comName': 'Viudita', 'sciName': 'Colorhamphus parvirostris', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'rufpla1', 'comName': 'Rara', 'sciName': 'Phytotoma rara', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Alta'},
    {'speciesCode': 'grecro1', 'comName': 'Picaflor chico', 'sciName': 'Sephanoides sephaniodes', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'clpige2', 'comName': 'Torcaza', 'sciName': 'Patagioenas araucana', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'slbpar1', 'comName': 'Choroy', 'sciName': 'Enicognathus leptorhynchus', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Alta'},
    {'speciesCode': 'auspar1', 'comName': 'Cachaña', 'sciName': 'Enicognathus ferrugineus', 'group': 'forest', 'groupName': '🌲 Bosque Templado y Sotobosque', 'habitats': ['valdivian_forest'], 'base_prob': 'Alta'},

    # Humedales, Anátidas y Cisnes
    {'speciesCode': 'blnswa1', 'comName': 'Cisne de cuello negro', 'sciName': 'Cygnus melancoryphus', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'cosswa1', 'comName': 'Cisne coscoroba', 'sciName': 'Coscoroba coscoroba', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary'], 'base_prob': 'Media'},
    {'speciesCode': 'chifla1', 'comName': 'Flamenco chileno', 'sciName': 'Phoenicopterus chilensis', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'broduc1', 'comName': 'Pato anteojillo', 'sciName': 'Speculanas specularis', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['valdivian_forest', 'lake_inland'], 'base_prob': 'Media'},
    {'speciesCode': 'yebduc1', 'comName': 'Pato jergón grande', 'sciName': 'Anas georgica', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'yebtea1', 'comName': 'Pato jergón chico', 'sciName': 'Anas flavirostris', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'chiwig1', 'comName': 'Pato real', 'sciName': 'Mareca sibilatrix', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Alta'},
    {'speciesCode': 'siltea1', 'comName': 'Pato capuchino', 'sciName': 'Spatula versicolor', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary'], 'base_prob': 'Media'},
    {'speciesCode': 'redcoo1', 'comName': 'Tagua común', 'sciName': 'Fulica armillata', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'reffro1', 'comName': 'Tagua de frente roja', 'sciName': 'Fulica rufifrons', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Alta'},
    {'speciesCode': 'spmgre1', 'comName': 'Picurio', 'sciName': 'Podilymbus podiceps', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Alta'},
    {'speciesCode': 'greti1', 'comName': 'Huala', 'sciName': 'Podiceps major', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['lake_inland', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'whfrgr1', 'comName': 'Pimpollo', 'sciName': 'Rollandia rolland', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'lake_inland'], 'base_prob': 'Alta'},
    {'speciesCode': 'cocor1', 'comName': 'Garza cuca', 'sciName': 'Ardea cocoi', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'greteg', 'comName': 'Garza grande', 'sciName': 'Ardea alba', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'snoegr', 'comName': 'Garza chica', 'sciName': 'Egretta thula', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'bcnher', 'comName': 'Huairavo', 'sciName': 'Nycticorax nycticorax', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'marcor1', 'comName': 'Siete-colores', 'sciName': 'Tachuris rubrigastra', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'wrkrus1', 'comName': 'Trabajador', 'sciName': 'Phleocryptes melanops', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'riwkin1', 'comName': 'Martín pescador', 'sciName': 'Megaceryle torquata', 'group': 'wetland', 'groupName': '🦢 Humedales, Anátidas y Acuáticas', 'habitats': ['lake_inland', 'wetland_estuary'], 'base_prob': 'Alta'},

    # Aves Playeras y Marinas
    {'speciesCode': 'hudgod', 'comName': 'Zarapito de pico recto', 'sciName': 'Limosa haemastica', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'whimbr', 'comName': 'Zarapito común', 'sciName': 'Numenius phaeopus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast', 'wetland_estuary'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'amtoys1', 'comName': 'Pilpilén común', 'sciName': 'Haematopus palliatus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'blaoys1', 'comName': 'Pilpilén negro', 'sciName': 'Haematopus ater', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'fstduc1', 'comName': 'Quetru no volador', 'sciName': 'Tachyeres pteneres', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'fstdul1', 'comName': 'Quetru volador', 'sciName': 'Tachyeres patachonicus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['lake_inland', 'marine_coast'], 'base_prob': 'Media'},
    {'speciesCode': 'twochi1', 'comName': 'Chorlo de doble collar', 'sciName': 'Charadrius falklandicus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast', 'wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'sander', 'comName': 'Playero blanco', 'sciName': 'Calidris alba', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'baisan', 'comName': 'Playero de Baird', 'sciName': 'Calidris bairdii', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'gretel', 'comName': 'Pitotoy grande', 'sciName': 'Tringa melanoleuca', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'lestel', 'comName': 'Pitotoy chico', 'sciName': 'Tringa flavipes', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'kelgul', 'comName': 'Gaviota dominicana', 'sciName': 'Larus dominicanus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast', 'wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'bkhgul2', 'comName': 'Gaviota cáhuil', 'sciName': 'Chroicocephalus maculipennis', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast', 'wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'fragul', 'comName': 'Gaviota de Franklin', 'sciName': 'Leucophaeus pipixcan', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast', 'wetland_estuary'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'sutern1', 'comName': 'Gaviotín sudamericano', 'sciName': 'Sterna hirundinacea', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'impcor1', 'comName': 'Cormorán imperial', 'sciName': 'Leucocarbo atriceps', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'magsha1', 'comName': 'Cormorán de las rocas', 'sciName': 'Poikilocarbo magellanicus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Alta'},
    {'speciesCode': 'neocor', 'comName': 'Yeco', 'sciName': 'Phalacrocorax brasilianus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast', 'wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'perpel1', 'comName': 'Pelícano peruano', 'sciName': 'Pelecanus thagus', 'group': 'shorebird', 'groupName': '🌊 Aves Playeras y Marinas', 'habitats': ['marine_coast'], 'base_prob': 'Alta'},

    # Rapaces y Búhos
    {'speciesCode': 'rufowl1', 'comName': 'Concón', 'sciName': 'Strix rufipes', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['valdivian_forest'], 'base_prob': 'Media'},
    {'speciesCode': 'auspig1', 'comName': 'Chuncho', 'sciName': 'Glaucidium nana', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Alta'},
    {'speciesCode': 'bkbmer1', 'comName': 'Águila mora', 'sciName': 'Geranoaetus melanoleucus', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['valdivian_forest', 'marine_coast', 'mixed_countryside'], 'base_prob': 'Alta'},
    {'speciesCode': 'varhaw1', 'comName': 'Aguilucho común', 'sciName': 'Geranoaetus polyosoma', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['mixed_countryside', 'valdivian_forest'], 'base_prob': 'Alta'},
    {'speciesCode': 'chihaw1', 'comName': 'Peuquito', 'sciName': 'Accipiter chilensis', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['valdivian_forest'], 'base_prob': 'Media'},
    {'speciesCode': 'whthaw1', 'comName': 'Bailarín', 'sciName': 'Elanus leucurus', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['mixed_countryside'], 'base_prob': 'Alta'},
    {'speciesCode': 'amkes1', 'comName': 'Cernícalo', 'sciName': 'Falco sparverius', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'chimca1', 'comName': 'Tiuque', 'sciName': 'Milvago chimango', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['mixed_countryside', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'crecar1', 'comName': 'Traro / Carancho', 'sciName': 'Caracara plancus', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'blkvul', 'comName': 'Jote de cabeza negra', 'sciName': 'Coragyps atratus', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['mixed_countryside', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'turvul', 'comName': 'Jote de cabeza colorada', 'sciName': 'Cathartes aura', 'group': 'raptor', 'groupName': '🦅 Rapaces y Búhos', 'habitats': ['marine_coast', 'mixed_countryside'], 'base_prob': 'Alta'},

    # Paseriformes de Matorral, Pradera y Campo
    {'speciesCode': 'blfibi1', 'comName': 'Bandurria común', 'sciName': 'Theristicus melanopis', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'wetland_estuary'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'soulap1', 'comName': 'Queltehue común', 'sciName': 'Vanellus chilensis', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'wetland_estuary'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'ausruf1', 'comName': 'Zorzal patagónico', 'sciName': 'Turdus falcklandii', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'valdivian_forest'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'houwre1', 'comName': 'Chercán común', 'sciName': 'Troglodytes musculus', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'valdivian_forest'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'fiepee1', 'comName': 'Diucón', 'sciName': 'Pyrope pyrope', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'tuttyr1', 'comName': 'Cachudito común', 'sciName': 'Anairetes parulus', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'aneneg1', 'comName': 'Colegial común', 'sciName': 'Lessonia rufa', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['wetland_estuary', 'marine_coast'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'spmcin1', 'comName': 'Churrete patagónico', 'sciName': 'Cinclodes patagonicus', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['marine_coast', 'wetland_estuary', 'lake_inland'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'pipit1', 'comName': 'Bailarín chico común', 'sciName': 'Anthus correndera', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'wetland_estuary'], 'base_prob': 'Alta'},
    {'speciesCode': 'lonmea1', 'comName': 'Loica común', 'sciName': 'Leistes loyca', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'ausbla1', 'comName': 'Tordo común', 'sciName': 'Curaeus curaeus', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'valdivian_forest'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'rufcol1', 'comName': 'Chincol', 'sciName': 'Zonotrichia capensis', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'comdiu1', 'comName': 'Diuca común', 'sciName': 'Diuca diuca', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'blcsis1', 'comName': 'Jilguero común', 'sciName': 'Spinus barbatus', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['valdivian_forest', 'mixed_countryside'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'patfyn1', 'comName': 'Cometocino patagónico', 'sciName': 'Phrygilus patagonicus', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['valdivian_forest'], 'base_prob': 'Muy Alta'},
    {'speciesCode': 'chiswa1', 'comName': 'Golondrina chilena', 'sciName': 'Tachycineta leucopyga', 'group': 'passerine', 'groupName': '🌾 Pradera, Matorral y Paseriformes', 'habitats': ['mixed_countryside', 'lake_inland', 'marine_coast'], 'base_prob': 'Muy Alta'}
]

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def estimate_drive_minutes(dist_km, lat1, lon1, lat2, lon2):
    is_chacao_crossing = False
    if (lat1 > -41.75 and lat2 < -41.82) or (lat1 < -41.82 and lat2 > -41.75):
        if -73.9 < lon1 < -73.4 and -73.9 < lon2 < -73.4:
            is_chacao_crossing = True

    drive_hours = dist_km / 55.0
    minutes = drive_hours * 60.0

    if is_chacao_crossing:
        minutes += 45

    return max(15, round(minutes))

CITIES_LOS_LAGOS = {
    'puerto varas', 'puerto montt', 'osorno', 'castro', 'ancud', 'llanquihue',
    'frutillar', 'calbuco', 'maullín', 'maullin', 'fresia', 'purranque',
    'achao', 'quellón', 'quellon', 'chonchi', 'dalcahue', 'queilén', 'queilen',
    'puqueldón', 'puqueldon', 'curaco de vélez', 'curaco de velez', 'cochamó',
    'cochamo', 'hualaihué', 'hualaihue', 'chaitén', 'chaiten', 'futaleufú',
    'futaleufu', 'palena', 'los muermos', 'san pablo', 'río negro', 'rio negro',
    'puerto octay', 'quemchi', 'quinchao', 'carelmapu', 'pargua', 'correntoso',
    'alessandri', 'ensenada',
    'arica', 'iquique', 'alto hospicio', 'antofagasta', 'calama', 'copiapó', 'copiapo',
    'vallenar', 'la serena', 'coquimbo', 'ovalle', 'valparaíso', 'valparaiso',
    'viña del mar', 'vina del mar', 'quilpué', 'villa alemana', 'san antonio',
    'santiago', 'providencia', 'las condes', 'maipú', 'puente alto', 'rancagua',
    'san fernando', 'curicó', 'curico', 'talca', 'linares', 'chillán', 'chillan',
    'concepción', 'concepcion', 'talcahuano', 'los ángeles', 'los angeles',
    'angol', 'temuco', 'villarrica', 'pucón', 'pucon', 'valdivia', 'la unión',
    'coyhaique', 'puerto aysén', 'punta arenas', 'puerto natales'
}

DISQUALIFY_PATTERNS = [
    r'usar localidades',
    r'localidades espec[ií]ficas',
    r'use specific',
    r'no usar',
    r'do not use',
    r'comuna de\b',
    r'ciudad de\b',
    r'radio urbano',
    r'zona urbana',
    r'centro urbano'
]

def is_generic_city_centroid(loc_name):
    if not loc_name:
        return True
    raw = loc_name.strip()
    low = raw.lower()

    for pat in DISQUALIFY_PATTERNS:
        if re.search(pat, low):
            return True

    clean = re.sub(r'\[.*?\]', '', low).strip()
    clean = re.sub(r'\(.*?\)', '', clean).strip()

    if clean in CITIES_LOS_LAGOS:
        return True

    for c in CITIES_LOS_LAGOS:
        if clean == c:
            return True
        if clean.startswith(c + ' - ') or clean.startswith(c + ' -- '):
            suffix = clean.split('-', 1)[1].strip('- ')
            if suffix in ['centro', 'ciudad', 'comuna', 'urbano', 'sur', 'norte', 'oriente', 'poniente']:
                return True

    return False

def classify_habitat(loc_name):
    name_lower = loc_name.lower()
    for habitat, keywords in HABITAT_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return habitat
    return 'mixed_countryside'

def fetch_ebird_hotspots(region_code='CL-LL', api_key=None):
    if not api_key:
        api_key = get_api_key()
    cache_key = f'hotspots_{region_code}'
    cached = get_cached(cache_key)
    if cached:
        return cached

    url = f"{EBIRD_API_BASE}/ref/hotspot/{region_code}?fmt=json"
    headers = {'X-eBirdApiToken': api_key}
    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            for h in data:
                h['habitat'] = classify_habitat(h.get('locName', ''))
                h['is_city_centroid'] = is_generic_city_centroid(h.get('locName', ''))
            set_cached(cache_key, data)
            return data
    except Exception as e:
        logger.error(f"Error fetching hotspots: {e}")
    return []

def fetch_recent_observations(region_code='CL-LL', days=14, api_key=None):
    if not api_key:
        api_key = get_api_key()
    cache_key = f'recent_obs_{region_code}_{days}'
    cached = get_cached(cache_key)
    if cached:
        return cached

    url = f"{EBIRD_API_BASE}/data/obs/{region_code}/recent?back={days}&sppLocale=es_CL"
    headers = {'X-eBirdApiToken': api_key}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            set_cached(cache_key, data)
            return data
    except Exception as e:
        logger.error(f"Error fetching observations: {e}")
    return []

def fetch_notable_observations(region_code='CL-LL', days=14, api_key=None):
    if not api_key:
        api_key = get_api_key()
    cache_key = f'notable_obs_{region_code}_{days}'
    cached = get_cached(cache_key)
    if cached:
        return cached

    url = f"{EBIRD_API_BASE}/data/obs/{region_code}/recent/notable?back={days}&detail=full&sppLocale=es_CL"
    headers = {'X-eBirdApiToken': api_key}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            set_cached(cache_key, data)
            return data
    except Exception as e:
        logger.error(f"Error fetching notable observations: {e}")
    return []

def fetch_weather_forecast(lat, lng, target_date=None):
    if not target_date:
        target_date = datetime.now().strftime('%Y-%m-%d')
    cache_key = f"weather_{round(lat, 2)}_{round(lng, 2)}_{target_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    url = (
        f"{OPEN_METEO_BASE}?latitude={lat}&longitude={lng}"
        f"&start_date={target_date}&end_date={target_date}"
        "&hourly=temperature_2m,precipitation_probability,precipitation,wind_speed_10m,cloud_cover,weather_code"
        "&daily=sunrise,sunset,precipitation_sum,wind_speed_10m_max,temperature_2m_max,temperature_2m_min"
        "&timezone=America/Santiago"
    )
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            set_cached(cache_key, data)
            return data
    except Exception as e:
        logger.error(f"Error fetching weather from Open-Meteo for date {target_date}: {e}")

    fallback_url = (
        f"{OPEN_METEO_BASE}?latitude={lat}&longitude={lng}"
        "&hourly=temperature_2m,precipitation_probability,precipitation,wind_speed_10m,cloud_cover,weather_code"
        "&daily=sunrise,sunset,precipitation_sum,wind_speed_10m_max,temperature_2m_max,temperature_2m_min"
        "&timezone=America/Santiago"
    )
    try:
        res = requests.get(fallback_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            set_cached(cache_key, data)
            return data
    except Exception:
        pass
    return None

def _compute_daily_tide_model(target_date=None):
    """Calculate semidiurnal tide events and lunar phase for Seno de Reloncaví / Chiloé based on target_date."""
    if not target_date:
        target_date = datetime.now().strftime('%Y-%m-%d')
    try:
        dt = datetime.strptime(target_date, '%Y-%m-%d').date()
    except Exception:
        dt = datetime.now().date()
        target_date = dt.strftime('%Y-%m-%d')

    # Reference anchor: 2026-10-10 (New Moon / Sicigia in Reloncaví & Chiloé)
    ref_date = datetime(2026, 10, 10).date()
    days_diff = (dt - ref_date).days

    # Lunar synodic period = 29.53059 days; semidiurnal spring-neap cycle = 14.7653 days
    synodic_age = (days_diff % 29.53059)
    # Daily lunar retardation ~ 50.47 minutes (0.8412 hours/day) modulo 12.4206h M2 period
    shift_hours = (days_diff * 0.8412) % 12.4206

    # Spring-neap modulation factor: +1 at syzygy (new/full moon), -1 at quadrature (quarters)
    syzygy_factor = math.cos(2 * math.pi * days_diff / 14.7653)

    if syzygy_factor > 0.45:
        lunar_phase = 'Mareas Vivas (Sicigia)'
        short_phase = 'Marea Sicigia'
    elif syzygy_factor < -0.45:
        lunar_phase = 'Mareas Muertas (Cuadratura)'
        short_phase = 'Marea Cuadratura'
    else:
        lunar_phase = 'Marea Intermedia'
        short_phase = 'Ciclo de Marea'

    mean_level = 3.55
    semi_amp = 2.45 + 0.50 * syzygy_factor  # ranges ~1.95m (neap) to ~2.95m (spring)
    high_h = round(mean_level + semi_amp, 1)
    low_h = round(max(0.3, mean_level - semi_amp), 1)
    tidal_range = round(high_h - low_h, 1)

    # Base events on reference day (hours decimal): High 1.75 (01:45), Low 7.917 (07:55)
    first_high = (1.75 + shift_hours) % 12.4206
    half_period = 6.2103

    raw_Node_hours = [
        (first_high - half_period, low_h, 'Bajamar'),
        (first_high, high_h, 'Pleamar'),
        (first_high + half_period, low_h, 'Bajamar'),
        (first_high + 2 * half_period, round(min(7.0, high_h + 0.15), 1), 'Pleamar'),
        (first_high + 3 * half_period, round(max(0.2, low_h - 0.1), 1), 'Bajamar'),
        (first_high + 4 * half_period, high_h, 'Pleamar'),
    ]

    day_events = []
    for h_dec, height_val, t_type in raw_Node_hours:
        if 0.0 <= h_dec < 24.0:
            hh = int(h_dec)
            mm = int(round((h_dec - hh) * 60))
            if mm == 60:
                hh = (hh + 1) % 24
                mm = 0
            day_events.append({
                'hour_dec': h_dec,
                'time': f"{hh:02d}:{mm:02d}",
                'height_m': height_val,
                'type': t_type,
                'label': 'Pleamar (Marea Alta)' if t_type == 'Pleamar' else 'Bajamar (Marea Baja)'
            })

    return {
        'target_date': target_date,
        'lunar_phase': lunar_phase,
        'short_phase': short_phase,
        'tidal_range_m': tidal_range,
        'raw_nodes': raw_Node_hours,
        'day_events': day_events
    }

def get_tide_events_los_lagos(target_date=None):
    model = _compute_daily_tide_model(target_date)
    events = [
        {
            'time': ev['time'],
            'height_m': ev['height_m'],
            'type': ev['type'],
            'label': ev['label']
        }
        for ev in model['day_events']
    ]
    lows = [e for e in events if e['type'] == 'Bajamar']
    highs = [e for e in events if e['type'] == 'Pleamar']
    b_str = f"{lows[0]['time']} ({lows[0]['height_m']}m)" if lows else "07:55 (0.7m)"
    p_str = f"{highs[-1]['time']} ({highs[-1]['height_m']}m)" if highs else "14:15 (6.5m)"

    return {
        'date': model['target_date'],
        'reference_zone': 'Seno de Reloncaví & Chiloé (Promedio Regional Los Lagos)',
        'lunar_phase': model['lunar_phase'],
        'short_phase': model['short_phase'],
        'tidal_range_m': model['tidal_range_m'],
        'summary_text': f"{model['lunar_phase']} con bajamar a las {b_str} y pleamar a las {p_str}.",
        'events': events
    }

def get_tide_at_hour(hour_decimal, target_date=None):
    model = _compute_daily_tide_model(target_date)
    events = model['raw_nodes']
    t = hour_decimal % 24

    t_prev, h_prev, type_prev = events[0]
    t_next, h_next, type_next = events[-1]
    for i in range(len(events) - 1):
        if events[i][0] <= t <= events[i + 1][0]:
            t_prev, h_prev, type_prev = events[i]
            t_next, h_next, type_next = events[i + 1]
            break

    span = max(0.1, t_next - t_prev)
    phase = (t - t_prev) / span * math.pi
    height = h_next + (h_prev - h_next) * (1 + math.cos(phase)) / 2.0
    height = round(height, 2)

    is_rising = (type_next == 'Pleamar')
    if abs(t - t_prev) < 0.75:
        state = 'Pleamar' if type_prev == 'Pleamar' else 'Bajamar'
        status_label = 'Pleamar (Marea Alta)' if type_prev == 'Pleamar' else 'Bajamar (Marea Baja)'
        note = 'Dormideros de pleamar; aves buceadoras cerca de la orilla' if type_prev == 'Pleamar' else 'Bancos de lodo expuestos; máxima alimentación de playeras'
    elif abs(t - t_next) < 0.75:
        state = 'Pleamar' if type_next == 'Pleamar' else 'Bajamar'
        status_label = 'Pleamar (Marea Alta)' if type_next == 'Pleamar' else 'Bajamar (Marea Baja)'
        note = 'Dormideros de pleamar; aves buceadoras cerca de la orilla' if type_next == 'Pleamar' else 'Bancos de lodo expuestos; máxima alimentación de playeras'
    elif is_rising:
        state = 'Subiendo'
        status_label = 'Marea Subiendo (Flujo)'
        note = 'Marea entrante empuja a playeros y zarapitos hacia la orilla'
    else:
        state = 'Bajando'
        status_label = 'Marea Bajando (Reflujo)'
        note = 'Agua retrocede descubriendo invertebrados frescos en el fango'

    low_nodes = [ev[0] for ev in events if ev[2] == 'Bajamar']
    high_nodes = [ev[0] for ev in events if ev[2] == 'Pleamar']

    return {
        'height_m': height,
        'state': state,
        'status_label': status_label,
        'note': note,
        'is_rising': is_rising,
        'is_low_tide': any(abs(t - ln) < 1.25 for ln in low_nodes),
        'is_high_tide': any(abs(t - hn) < 1.25 for hn in high_nodes)
    }

def calculate_bird_activity_score(hour, habitat, weather_hourly, hour_idx, tide_info=None):
    if 6.0 <= hour < 9.5:
        base_score = 1.9 if habitat == 'valdivian_forest' else 1.6
    elif 9.5 <= hour < 12.0:
        base_score = 1.4
    elif 12.0 <= hour < 15.5:
        base_score = 1.6 if habitat in ('wetland_estuary', 'marine_coast') else 1.1
    elif 15.5 <= hour < 19.5:
        base_score = 1.5 if habitat in ('wetland_estuary', 'marine_coast') else 1.3
    else:
        base_score = 0.6

    if habitat in ('wetland_estuary', 'marine_coast') and tide_info:
        if tide_info.get('is_low_tide'):
            base_score += 0.35
        elif tide_info.get('is_rising'):
            base_score += 0.25

    weather_multiplier = 1.0
    rain_prob = 0
    wind_kmh = 10
    temp_c = 14
    w_code = 0

    if weather_hourly and hour_idx is not None and hour_idx < len(weather_hourly.get('temperature_2m', [])):
        temp_c = weather_hourly.get('temperature_2m', [14])[hour_idx]
        precip = weather_hourly.get('precipitation', [0])[hour_idx]
        rain_prob = weather_hourly.get('precipitation_probability', [10])[hour_idx]
        wind_kmh = weather_hourly.get('wind_speed_10m', [10])[hour_idx]
        w_code = weather_hourly.get('weather_code', [0])[hour_idx]

        if precip > 2.0 or rain_prob > 75:
            weather_multiplier *= 0.55
        elif precip > 0.5 or rain_prob > 50:
            weather_multiplier *= 0.80

        if wind_kmh > 35:
            weather_multiplier *= 0.60
        elif wind_kmh > 22:
            weather_multiplier *= 0.85

        if temp_c < 2:
            weather_multiplier *= 0.85

    final_score = round(base_score * weather_multiplier, 2)
    return {
        'activity_multiplier': final_score,
        'temp_c': temp_c,
        'rain_prob': rain_prob,
        'wind_kmh': wind_kmh,
        'weather_code': w_code,
        'is_peak_window': base_score >= 1.5
    }

def _classify_species_group(com_name, sci_name, default_habitat=None):
    txt = f"{com_name} {sci_name}".lower()
    if any(w in txt for w in ['águila', 'aguilucho', 'halcón', 'cernícalo', 'tiuque', 'traro', 'carancho', 'jote', 'cóndor', 'peuco', 'peuquito', 'bailarín', 'vari', 'concón', 'chuncho', 'tucúquere', 'lechuza', 'nuco']):
        return ('raptor', 'Rapaces y Nocturnas')
    if any(w in txt for w in ['zarapito', 'playero', 'chorlo', 'chorlito', 'pilpilén', 'gaviota', 'gaviotín', 'cormorán', 'yeco', 'pelícano', 'piquero', 'pingüino', 'quetru', 'fardela', 'petrel', 'albatros', 'rayador', 'salteador', 'yunco']):
        return ('shorebird', 'Costa, Playeras y Marinas')
    if any(w in txt for w in ['cisne', 'flamenco', 'pato', 'tagua', 'tagüita', 'pimpollo', 'huala', 'picurio', 'garza', 'huairavo', 'cuervo de pantano', 'bandurria', 'siete-colores', 'trabajador', 'martín pescador', 'pidén', 'canquén', 'piuquén', 'caití', 'blanquillo']):
        return ('wetland', 'Humedales, Lagunas y Ríos')
    if any(w in txt for w in ['chucao', 'huet', 'hued', 'carpintero', 'carpinterito', 'rayadito', 'comesebo', 'churrín', 'colilarga', 'fío-fío', 'viudita', 'rara', 'picaflor', 'torcaza', 'choroy', 'cachaña', 'tricahue', 'turca', 'tapaculo', 'chiricoca', 'tenca', 'tijeral', 'canastero', 'minero', 'bandurrilla']):
        return ('forest', 'Bosques, Quebradas y Especialistas')
    if default_habitat == 'valdivian_forest':
        return ('forest', 'Bosques, Quebradas y Especialistas')
    if default_habitat in ('wetland_estuary', 'lake_inland'):
        return ('wetland', 'Humedales, Lagunas y Ríos')
    if default_habitat == 'marine_coast':
        return ('shorebird', 'Costa, Playeras y Marinas')
    return ('passerine', 'Valles, Praderas y Paseriformes')


def compile_probable_species(selected_stops, recent_obs, region_code='CL-LL'):
    habitats_visited = {s['habitat'] for s in selected_stops} if selected_stops else set()
    stop_by_loc_id = {s['locId']: s for s in selected_stops}
    habitat_stops = {}
    for s in selected_stops:
        h = s['habitat']
        if h not in habitat_stops:
            habitat_stops[h] = s

    compiled = []
    seen_species = set()

    # 1. Species directly highlighted in the selected route stops
    for s in selected_stops:
        for sp in s.get('target_species', []):
            com = sp.get('comName', '').strip()
            if not com or com.lower() in seen_species:
                continue
            seen_species.add(com.lower())
            sci = sp.get('sciName', '')
            grp_id, grp_label = _classify_species_group(com, sci, s.get('habitat'))
            code = sp.get('speciesCode') or re.sub(r'[^a-z0-9]', '', (sci or com).lower())[:10]
            compiled.append({
                'speciesCode': code,
                'comName': com,
                'sciName': sci,
                'group': grp_id,
                'groupName': grp_label,
                'probability': 'Muy Alta (Clave en Parada)',
                'is_habitat_matched': True,
                'best_stop_name': s['locName'],
                'best_stop_number': s['stop_number']
            })

    # 2. Recent eBird observations recorded directly at the route's stops
    for obs in recent_obs:
        loc_id = obs.get('locId')
        if loc_id not in stop_by_loc_id:
            continue
        com = (obs.get('comName') or '').strip()
        if not com or com.lower() in seen_species:
            continue
        seen_species.add(com.lower())
        s = stop_by_loc_id[loc_id]
        sci = obs.get('sciName', '')
        grp_id, grp_label = _classify_species_group(com, sci, s.get('habitat'))
        compiled.append({
            'speciesCode': obs.get('speciesCode') or re.sub(r'[^a-z0-9]', '', (sci or com).lower())[:10],
            'comName': com,
            'sciName': sci,
            'group': grp_id,
            'groupName': grp_label,
            'probability': 'Alta (Reciente en Hotspot)',
            'is_habitat_matched': True,
            'best_stop_name': s['locName'],
            'best_stop_number': s['stop_number']
        })

    # 3. For Southern regions, include habitat-matched species from REGIONAL_PROBABLE_SPECIES
    if region_code in ('CL-BI', 'CL-AR', 'CL-LR', 'CL-LL', 'CL-AI', 'CL-MA'):
        for sp in REGIONAL_PROBABLE_SPECIES:
            com = sp['comName']
            if com.lower() in seen_species:
                continue
            matches_visited = any(hab in habitats_visited for hab in sp['habitats']) if habitats_visited else True
            if not matches_visited:
                continue
            seen_species.add(com.lower())
            best_stop = None
            for hab in sp['habitats']:
                if hab in habitat_stops:
                    best_stop = habitat_stops[hab]
                    break
            if not best_stop and selected_stops:
                best_stop = selected_stops[0]
            grp_id, grp_label = _classify_species_group(com, sp['sciName'])
            compiled.append({
                'speciesCode': sp['speciesCode'],
                'comName': com,
                'sciName': sp['sciName'],
                'group': grp_id,
                'groupName': grp_label,
                'probability': sp.get('base_prob', 'Alta'),
                'is_habitat_matched': True,
                'best_stop_name': best_stop['locName'] if best_stop else 'En ruta',
                'best_stop_number': best_stop['stop_number'] if best_stop else 1
            })

    # 4. Fill up with recent regional eBird observations matching the route's habitats (up to ~65 species total for a clean field list)
    for obs in recent_obs:
        if len(compiled) >= 65:
            break
        com = (obs.get('comName') or '').strip()
        if not com or com.lower() in seen_species:
            continue
        sci = obs.get('sciName', '')
        obs_hab = classify_habitat(obs.get('locName', ''))
        best_stop = habitat_stops.get(obs_hab) or (selected_stops[0] if selected_stops else None)
        seen_species.add(com.lower())
        grp_id, grp_label = _classify_species_group(com, sci, obs_hab)
        compiled.append({
            'speciesCode': obs.get('speciesCode') or re.sub(r'[^a-z0-9]', '', (sci or com).lower())[:10],
            'comName': com,
            'sciName': sci,
            'group': grp_id,
            'groupName': grp_label,
            'probability': 'Media (Frecuente en Zona)',
            'is_habitat_matched': True,
            'best_stop_name': best_stop['locName'] if best_stop else obs.get('locName', 'En ruta'),
            'best_stop_number': best_stop['stop_number'] if best_stop else 1
        })

    group_order = {'forest': 1, 'wetland': 2, 'shorebird': 3, 'raptor': 4, 'passerine': 5}
    compiled.sort(key=lambda x: (group_order.get(x['group'], 9), x['best_stop_number'], x['comName']))
    return compiled

def format_habitat_label(habitat, region_code='CL-LL'):
    is_north_or_central = region_code in ('CL-AP', 'CL-TA', 'CL-AN', 'CL-AT', 'CL-CO', 'CL-VS', 'CL-RM', 'CL-LI')
    labels = {
        'valdivian_forest': (
            'Bosque Nativo / Quebrada y Oasis (Especialistas Terrestres)'
            if is_north_or_central
            else 'Bosque Templado / Nativo (Tapaculos y Pájaros Carpinteros)'
        ),
        'wetland_estuary': 'Humedal / Estuario / Salar (Aves Acuáticas & Migratorias)',
        'marine_coast': 'Costa Marina / Roqueríos (Playeras, Gaviotas, Cormoranes)',
        'lake_inland': 'Borde Lacustre / Laguna (Patos, Taguas, Acuáticas)',
        'mixed_countryside': 'Pradera / Matorral, Estepa y Borde de Valle'
    }
    return labels.get(habitat, 'Hábitat Mixto')

def _matches_subzone_filter(cand_lat, cand_lng, loc_name, subzone_id, region_cfg):
    if not subzone_id or subzone_id == 'all':
        return True
    subzones = region_cfg.get('subzones', [])
    sub_def = next((s for s in subzones if s['id'] == subzone_id), None)
    if not sub_def:
        return True

    in_bounds = True
    if 'lat_min' in sub_def and cand_lat < sub_def['lat_min']:
        in_bounds = False
    if 'lat_max' in sub_def and cand_lat > sub_def['lat_max']:
        in_bounds = False
    if 'lng_min' in sub_def and cand_lng < sub_def['lng_min']:
        in_bounds = False
    if 'lng_max' in sub_def and cand_lng > sub_def['lng_max']:
        in_bounds = False

    if in_bounds:
        return True

    keywords = sub_def.get('keywords', [])
    if keywords:
        low_name = (loc_name or '').lower()
        if any(kw in low_name for kw in keywords):
            return True

    return False

def run_optimize_route(payload, api_key=None):
    if not api_key:
        api_key = get_api_key()

    today_str = datetime.now().strftime('%Y-%m-%d')
    target_date = payload.get('date') or today_str
    region_code = payload.get('region', 'CL-LL')
    if region_code not in CHILE_REGIONS_CONFIG:
        region_code = 'CL-LL'
    region_cfg = CHILE_REGIONS_CONFIG[region_code]
    region_hubs = region_cfg['hubs']
    default_hub_id = region_cfg['default_hub']

    hub_id = payload.get('hub', default_hub_id)
    custom_lat = payload.get('start_lat')
    custom_lng = payload.get('start_lng')

    if custom_lat is not None and custom_lng is not None:
        start_pt = {'name': 'Ubicación personalizada', 'lat': float(custom_lat), 'lng': float(custom_lng)}
    else:
        hub_data = region_hubs.get(hub_id) or region_hubs.get(default_hub_id) or list(region_hubs.values())[0]
        start_pt = {'name': hub_data['name'], 'lat': hub_data['lat'], 'lng': hub_data['lng']}

    subzone = payload.get('subzone', 'all')
    target_focus = payload.get('focus', 'all')
    duration_hours = float(payload.get('duration_hours', 12.0))
    max_stops = int(payload.get('max_stops', 8))
    start_time_str = payload.get('start_time', '06:00')

    pace_mode = payload.get('pace', 'blitz' if max_stops >= 7 else 'tactical')
    pace_minutes_map = {
        'blitz': 35,
        'tactical': 45,
        'standard': 65,
        'relaxed': 85
    }
    birding_minutes_per_stop = pace_minutes_map.get(pace_mode, 40)
    is_big_day = payload.get('is_big_day', False) or pace_mode == 'blitz' or max_stops >= 7

    all_hotspots = fetch_ebird_hotspots(region_code, api_key)
    recent_obs = fetch_recent_observations(region_code, 14, api_key)

    hotspot_recent_species = {}
    for obs in recent_obs:
        loc_id = obs.get('locId')
        if loc_id:
            if loc_id not in hotspot_recent_species:
                hotspot_recent_species[loc_id] = []
            hotspot_recent_species[loc_id].append(obs)

    min_species_req = 10 if is_big_day else 16
    candidates = []
    for h in all_hotspots:
        if is_generic_city_centroid(h.get('locName', '')):
            continue

        num_sp = h.get('numSpeciesAllTime', 0)
        if num_sp < min_species_req:
            continue

        lat = h['lat']
        lng = h['lng']
        habitat = h.get('habitat', 'mixed_countryside')

        if not _matches_subzone_filter(lat, lng, h.get('locName', ''), subzone, region_cfg):
            continue

        if target_focus == 'forest' and habitat not in ('valdivian_forest', 'mixed_countryside'):
            continue
        elif target_focus == 'wetland' and habitat not in ('wetland_estuary', 'lake_inland', 'marine_coast'):
            continue

        dist_from_start = haversine_km(start_pt['lat'], start_pt['lng'], lat, lng)
        max_dist_start = 220 if is_big_day else 170
        if dist_from_start > max_dist_start:
            continue

        recent_list = hotspot_recent_species.get(h['locId'], [])
        candidates.append({
            'locId': h['locId'],
            'locName': h['locName'],
            'lat': lat,
            'lng': lng,
            'numSpeciesAllTime': num_sp,
            'recentSpeciesCount': len(recent_list),
            'recentSpecies': recent_list[:10],
            'habitat': habitat,
            'dist_from_start': dist_from_start
        })

    candidates.sort(key=lambda x: (x['recentSpeciesCount'] * 2.5 + x['numSpeciesAllTime']), reverse=True)
    candidate_pool_size = 90 if is_big_day else 45
    top_candidates = candidates[:candidate_pool_size]

    if not top_candidates:
        top_candidates = sorted(
            [h for h in all_hotspots if h.get('numSpeciesAllTime', 0) >= 8 and not is_generic_city_centroid(h.get('locName', ''))],
            key=lambda x: haversine_km(start_pt['lat'], start_pt['lng'], x['lat'], x['lng'])
        )[:35]
        for h in top_candidates:
            h['habitat'] = classify_habitat(h.get('locName', ''))
            h['dist_from_start'] = haversine_km(start_pt['lat'], start_pt['lng'], h['lat'], h['lng'])
            h['recentSpeciesCount'] = len(hotspot_recent_species.get(h['locId'], []))
            h['recentSpecies'] = hotspot_recent_species.get(h['locId'], [])[:10]

    weather_data = fetch_weather_forecast(start_pt['lat'], start_pt['lng'], target_date)
    daily_w = weather_data.get('daily', {}) if weather_data else {}
    hourly_w = weather_data.get('hourly', {}) if weather_data else {}

    sunrise_iso = daily_w.get('sunrise', [None])[0] or '07:15'
    sunset_iso = daily_w.get('sunset', [None])[0] or '19:45'

    sunrise_time = sunrise_iso.split('T')[1][:5] if 'T' in sunrise_iso else sunrise_iso
    sunset_time = sunset_iso.split('T')[1][:5] if 'T' in sunset_iso else sunset_iso

    current_lat = start_pt['lat']
    current_lng = start_pt['lng']

    sh, sm = map(int, start_time_str.split(':'))
    current_time_minutes = sh * 60 + sm
    max_total_minutes = int(duration_hours * 60)

    selected_stops = []
    visited_loc_ids = set()
    total_km = 0
    total_drive_minutes = 0
    accumulated_unique_species = set()

    for stop_idx in range(max_stops):
        best_candidate = None
        best_score = -999999
        best_drive_time = 0
        best_dist = 0

        current_hour_decimal = (current_time_minutes / 60.0) % 24
        hour_index = min(23, max(0, int(current_hour_decimal)))

        for cand in top_candidates:
            if cand['locId'] in visited_loc_ids:
                continue

            dist = haversine_km(current_lat, current_lng, cand['lat'], cand['lng'])
            drive_time = estimate_drive_minutes(dist, current_lat, current_lng, cand['lat'], cand['lng'])

            birding_time = birding_minutes_per_stop
            arrival_minutes = current_time_minutes + drive_time
            arrival_hour = (arrival_minutes / 60.0) % 24
            arr_hour_idx = min(23, max(0, int(arrival_hour)))

            return_dist = haversine_km(cand['lat'], cand['lng'], start_pt['lat'], start_pt['lng'])
            return_time = estimate_drive_minutes(return_dist, cand['lat'], cand['lng'], start_pt['lat'], start_pt['lng'])

            if (arrival_minutes + birding_time + return_time) > (sh * 60 + sm + max_total_minutes):
                continue

            act_info = calculate_bird_activity_score(arrival_hour, cand['habitat'], hourly_w, arr_hour_idx)
            act_mult = act_info['activity_multiplier']

            species_richness = cand['numSpeciesAllTime'] * 0.4 + cand['recentSpeciesCount'] * 3.0

            synergy_bonus = 0
            if arrival_hour < 10.5 and cand['habitat'] == 'valdivian_forest':
                synergy_bonus += 35
            elif 11.0 <= arrival_hour <= 16.0 and cand['habitat'] in ('wetland_estuary', 'marine_coast'):
                synergy_bonus += 35
            elif cand['habitat'] != 'valdivian_forest' and any(s['habitat'] == 'valdivian_forest' for s in selected_stops):
                synergy_bonus += 15

            if dist < 20:
                distance_penalty = dist * 0.35
            else:
                distance_penalty = dist * 0.85

            score = (species_richness * act_mult) + synergy_bonus - distance_penalty

            if score > best_score:
                best_score = score
                best_candidate = cand
                best_drive_time = drive_time
                best_dist = dist

        if not best_candidate:
            break

        visited_loc_ids.add(best_candidate['locId'])
        arrival_minutes = current_time_minutes + best_drive_time
        birding_minutes = birding_minutes_per_stop
        departure_minutes = arrival_minutes + birding_minutes

        arr_h = int(arrival_minutes // 60)
        arr_m = int(arrival_minutes % 60)
        dep_h = int(departure_minutes // 60)
        dep_m = int(departure_minutes % 60)

        arr_hour_decimal = (arrival_minutes / 60.0) % 24
        arr_hour_idx = min(23, max(0, int(arr_hour_decimal)))

        is_coastal = best_candidate['habitat'] in ('wetland_estuary', 'marine_coast') or any(k in best_candidate['locName'].lower() for k in ['humedal', 'estuario', 'bahía', 'caulín', 'maullín', 'pullao', 'putemún', 'mar', 'seno', 'costa'])
        tide_info = get_tide_at_hour(arr_hour_decimal, target_date) if is_coastal else None

        act_info = calculate_bird_activity_score(arr_hour_decimal, best_candidate['habitat'], hourly_w, arr_hour_idx, tide_info)

        stop_species = []
        for o in best_candidate['recentSpecies']:
            s_name = o.get('comName', '')
            if s_name and s_name not in accumulated_unique_species:
                accumulated_unique_species.add(s_name)
                stop_species.append({
                    'comName': s_name,
                    'sciName': o.get('sciName', ''),
                    'howMany': o.get('howMany', 1),
                    'obsDt': o.get('obsDt', '')
                })

        region_iconic_list = region_cfg.get('iconic_species') or list(ICONIC_LOS_LAGOS_SPECIES.values())
        for sp_meta in region_iconic_list:
            if sp_meta['habitat'] == best_candidate['habitat'] and sp_meta['comName'] not in accumulated_unique_species:
                accumulated_unique_species.add(sp_meta['comName'])
                stop_species.append({
                    'comName': sp_meta['comName'],
                    'sciName': sp_meta['sciName'],
                    'howMany': 'Frecuente',
                    'isTarget': True,
                    'rarity': sp_meta['rarity']
                })
                if len(stop_species) >= 7:
                    break

        if arr_hour_decimal < 11.25:
            day_block = 'morning'
            day_block_label = 'Bloque Mañana (Amanecer – 11:00 hrs)'
            day_block_short = 'Mañana'
        elif arr_hour_decimal < 15.5:
            day_block = 'midday'
            day_block_label = 'Bloque Mediodía (11:00 – 15:30 hrs)'
            day_block_short = 'Mediodía'
        else:
            day_block = 'afternoon'
            day_block_label = 'Bloque Tarde (15:30 hrs – Ocaso)'
            day_block_short = 'Tarde'

        selected_stops.append({
            'stop_number': stop_idx + 1,
            'locId': best_candidate['locId'],
            'locName': best_candidate['locName'],
            'lat': best_candidate['lat'],
            'lng': best_candidate['lng'],
            'habitat': best_candidate['habitat'],
            'habitat_label': format_habitat_label(best_candidate['habitat'], region_code),
            'numSpeciesAllTime': best_candidate['numSpeciesAllTime'],
            'distance_from_prev_km': round(best_dist, 1),
            'drive_time_from_prev_min': best_drive_time,
            'arrival_time': f"{arr_h:02d}:{arr_m:02d}",
            'departure_time': f"{dep_h:02d}:{dep_m:02d}",
            'day_block': day_block,
            'day_block_label': day_block_label,
            'day_block_short': day_block_short,
            'birding_minutes': birding_minutes,
            'activity': act_info,
            'tide': tide_info,
            'target_species': stop_species,
            'expected_new_species': len(stop_species)
        })

        total_km += best_dist
        total_drive_minutes += best_drive_time
        current_lat = best_candidate['lat']
        current_lng = best_candidate['lng']
        current_time_minutes = departure_minutes

    return_dist = haversine_km(current_lat, current_lng, start_pt['lat'], start_pt['lng'])
    return_time = estimate_drive_minutes(return_dist, current_lat, current_lng, start_pt['lat'], start_pt['lng'])
    end_minutes = current_time_minutes + return_time
    total_km += return_dist
    total_drive_minutes += return_time

    end_h = int(end_minutes // 60)
    end_m = int(end_minutes % 60)

    total_birding_minutes = sum(s['birding_minutes'] for s in selected_stops)
    all_probable_species = compile_probable_species(selected_stops, recent_obs, region_code)
    tides_data = get_tide_events_los_lagos(target_date)

    return {
        'origin': start_pt,
        'summary': {
            'region_code': region_code,
            'region_name': region_cfg['name'],
            'region_short_name': region_cfg['short_name'],
            'target_date': target_date,
            'date_label': target_date,
            'is_big_day': is_big_day,
            'pace_mode': pace_mode,
            'birding_minutes_per_stop': birding_minutes_per_stop,
            'start_time': start_time_str,
            'finish_time': f"{end_h:02d}:{end_m:02d}",
            'total_duration_hours': round((end_minutes - (sh * 60 + sm)) / 60.0, 1),
            'total_km': round(total_km, 1),
            'total_drive_minutes': total_drive_minutes,
            'total_birding_minutes': total_birding_minutes,
            'num_stops': len(selected_stops),
            'estimated_total_species': max(len(accumulated_unique_species), round(len(selected_stops) * 9.5 + 26)),
            'total_probable_species_count': len(all_probable_species),
            'sunrise': sunrise_time,
            'sunset': sunset_time,
            'tides': tides_data
        },
        'stops': selected_stops,
        'all_probable_species': all_probable_species,
        'weather_overview': {
            'target_date': target_date,
            'date_label': target_date,
            'sunrise': sunrise_time,
            'sunset': sunset_time,
            'max_temp': daily_w.get('temperature_2m_max', [15.0])[0] if daily_w else 15.0,
            'min_temp': daily_w.get('temperature_2m_min', [10.4])[0] if daily_w else 10.4,
            'precip_sum': daily_w.get('precipitation_sum', [0.8])[0] if daily_w else 0.8,
            'wind_max': daily_w.get('wind_speed_10m_max', [16.2])[0] if daily_w else 16.2
        },
        'tides': tides_data
    }

