import os
import json
import random
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone


def menu_juegos(request):
    return render(request, "juegos/menu_juegos.html")


def quien_es_esta_ave(request):
    return render(request, "juegos/quien_es_esta_ave.html")


def memorice(request):
    return render(request, "juegos/memorice.html")


def letras_locas(request):
    return render(request, "juegos/letras_locas.html")


def minijuego(request):
    return render(request, "juegos/minijuego.html")


def rosco(request):
    return render(request, "juegos/rosco.html")


def aves_en_tu_zona(request):
    return render(request, "juegos/aves_en_tu_zona.html")


def radar_realtime(request):
    return render(request, "juegos/radar_realtime.html")


def generar_avistamientos_fallback(ebird_path):
    partes = ebird_path.split('/')
    region = 'CL-RM'
    for p in partes:
        if p.startswith('CL-'):
            region = p
            break
            
    regiones_map = {
        'CL-AP': (-18.4783, -70.3126, ['Desembocadura del Río Lluta', 'Valle de Azapa', 'Putre']),
        'CL-TA': (-20.2133, -70.1503, ['Salar de Huasco', 'Iquique Costanera', 'Pica']),
        'CL-AN': (-23.6509, -70.3975, ['La Portada', 'Humedal Aguada La Chimba', 'Mejillones']),
        'CL-AT': (-27.3668, -70.3323, ['Bahía Inglesa', 'Parque Nacional Pan de Azúcar', 'Huasco']),
        'CL-CO': (-29.9533, -71.3395, ['Humedal El Culebrón', 'Punta de Choros', 'Reserva Chinchillas']),
        'CL-VS': (-33.0472, -71.6127, ['Humedal El Peral', 'Concón Desembocadura', 'Laguna Verde']),
        'CL-RM': (-33.4489, -70.6693, ['Parque Bicentenario', 'Cajón del Maipo', 'Humedal Batuco', 'Cerro San Cristóbal']),
        'CL-LI': (-34.1701, -70.7407, ['Reserva Nacional Río de los Cipreses', 'Pichilemu', 'Rapel']),
        'CL-ML': (-35.4264, -71.6554, ['Reserva Altos de Lircay', 'Putú', 'Vilches']),
        'CL-NB': (-36.6066, -72.1034, ['Cobquecura', 'Nevados de Chillán', 'Quillón']),
        'CL-BI': (-36.8270, -73.0498, ['Desembocadura del Bío Bío', 'Dichato', 'Lenga']),
        'CL-AR': (-38.7359, -72.5904, ['Lago Villarrica', 'Parque Conguillío', 'Puerto Saavedra']),
        'CL-LR': (-39.8142, -73.2459, ['Santuario Carlos Anwandter', 'Niebla', 'Lago Ranco']),
        'CL-LL': (-41.4693, -72.9424, ['Seno de Reloncaví', 'Chiloé Castro', 'Frutillar', 'Alerce Andino']),
        'CL-AI': (-45.5752, -72.0662, ['Coyhaique Alto', 'Puerto Aysén', 'Lago General Carrera']),
        'CL-MA': (-53.1638, -70.9171, ['Estrecho de Magallanes', 'Torres del Paine', 'Puerto Natales']),
    }
    
    base_lat, base_lng, lugares = regiones_map.get(region, (-33.4489, -70.6693, ['Reserva Natural', 'Costanera', 'Parque Central']))
    
    especies_muestra = [
        ("austhr1", "Zorzal patagónico", "Turdus falcklandii"),
        ("rucspa1", "Chincol", "Zonotrichia capensis"),
        ("grbfir1", "Picaflor chico", "Sephanoides sephaniodes"),
        ("tuttyr1", "Cachudito común", "Anairetes parulus"),
        ("houwre4", "Chercán común", "Troglodytes musculus"),
        ("eardov1", "Tórtola", "Zenaida auriculata"),
        ("rocpig", "Paloma doméstica", "Columba livia"),
        ("ameoys", "Pilpilén común", "Haematopus palliatus"),
        ("lesrhe2", "Suri/Ñandú", "Rhea pennata"),
        ("bkbplo", "Chorlo ártico", "Pluvialis squatarola"),
        ("blhher1", "Garza cuca", "Ardea cocoi"),
        ("blnhea1", "Huairavo", "Nycticorax nycticorax"),
        ("chihaw1", "Peuco", "Parabuteo unicinctus"),
        ("bkycar1", "Tiuque", "Milvago chimango"),
    ]
    
    fallback_data = []
    ahora_str = timezone.now().strftime("%Y-%m-%d %H:%M")
    
    for idx, (code, com, sci) in enumerate(especies_muestra):
        num_obs = random.randint(1, 3)
        for o in range(num_obs):
            offset_lat = (random.random() - 0.5) * 0.15
            offset_lng = (random.random() - 0.5) * 0.15
            lugar = lugares[o % len(lugares)]
            
            fallback_data.append({
                "speciesCode": code,
                "comName": com,
                "sciName": sci,
                "locId": f"L{idx}{o}",
                "locName": lugar,
                "obsDt": ahora_str,
                "howMany": random.randint(1, 6),
                "lat": round(base_lat + offset_lat, 4),
                "lng": round(base_lng + offset_lng, 4),
                "obsValid": True,
                "obsReviewed": False,
                "locationPrivate": False,
                "subId": f"S{idx}{o}"
            })
            
    return fallback_data


@require_GET
def ebird_proxy(request, ebird_path):
    cache_key = f"ebird_{ebird_path}_{request.GET.urlencode()}"
    
    datos_cacheados = cache.get(cache_key)
    if datos_cacheados:
        return JsonResponse(datos_cacheados, safe=False)

    api_key = getattr(settings, 'EBIRD_API_KEY', None) or os.environ.get('EBIRD_API_KEY')
    
    if api_key:
        url = f"https://api.ebird.org/v2/{ebird_path}"
        headers = {"X-eBirdApiToken": api_key}
        params = request.GET.dict()
        
        try:
            response_ebird = requests.get(url, headers=headers, params=params)
            response_ebird.raise_for_status()
            
            datos_nuevos = response_ebird.json()
            cache.set(cache_key, datos_nuevos, 300)
            return JsonResponse(datos_nuevos, safe=False)
        except requests.RequestException as e:
            print(f"⚠️ Error al conectar con eBird API: {e}. Usando avistamientos de respaldo.")
    
    datos_fallback = generar_avistamientos_fallback(ebird_path)
    cache.set(cache_key, datos_fallback, 300)
    return JsonResponse(datos_fallback, safe=False)


def get_species_dict(request):
    file_path = os.path.join(settings.BASE_DIR, 'tienda', 'species.json')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        response = JsonResponse(data, safe=False)
        response["Access-Control-Allow-Origin"] = "*"
        return response
    except FileNotFoundError:
        return JsonResponse({"error": "Archivo no encontrado"}, status=404)
