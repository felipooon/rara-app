import os
import json
import random
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from ..models import PuntajeJuego, ConfiguracionSitio

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def menu_juegos(request):
    return render(request, "juegos/menu_juegos.html")


def menu_pajarea(request):
    return render(request, "pajarea/menu_pajarea.html")


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
    modo = request.GET.get('modo', '').strip().lower()
    if modo == 'juegos':
        juegos_path = os.path.join(settings.BASE_DIR, 'tienda', 'species_juegos.json')
        file_path = juegos_path if os.path.exists(juegos_path) else os.path.join(settings.BASE_DIR, 'tienda', 'species.json')
    else:
        file_path = os.path.join(settings.BASE_DIR, 'tienda', 'species.json')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        response = JsonResponse(data, safe=False)
        response["Access-Control-Allow-Origin"] = "*"
        return response
    except FileNotFoundError:
        return JsonResponse({"error": "Archivo no encontrado"}, status=404)


def _rango_mes_actual_y_anterior():
    ahora = timezone.localtime(timezone.now())
    inicio_mes_actual = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if ahora.month == 12:
        inicio_mes_siguiente = inicio_mes_actual.replace(year=ahora.year + 1, month=1)
    else:
        inicio_mes_siguiente = inicio_mes_actual.replace(month=ahora.month + 1)

    if ahora.month == 1:
        prev_year, prev_month = ahora.year - 1, 12
    else:
        prev_year, prev_month = ahora.year, ahora.month - 1
    inicio_mes_anterior = inicio_mes_actual.replace(year=prev_year, month=prev_month)

    return {
        "mes_actual_nombre": MESES_ES.get(ahora.month, ""),
        "mes_anterior_nombre": MESES_ES.get(prev_month, ""),
        "inicio_mes_actual": inicio_mes_actual,
        "inicio_mes_siguiente": inicio_mes_siguiente,
        "inicio_mes_anterior": inicio_mes_anterior,
    }


def _serializar_ranking(juego_slug, inicio_mes, fin_mes, limite=10):
    qs = (
        PuntajeJuego.objects.filter(
            juego=juego_slug,
            fecha_registro__gte=inicio_mes,
            fecha_registro__lt=fin_mes,
        )
        .order_by('-puntaje', 'fecha_registro')[:limite]
    )
    return [
        {
            "pos": idx,
            "id": p.id,
            "nombre": p.nombre,
            "puntaje": p.puntaje,
            "detalle": p.detalle,
            "fecha": timezone.localtime(p.fecha_registro).strftime("%d/%m/%Y"),
        }
        for idx, p in enumerate(qs, 1)
    ]


def _obtener_campeon_anterior(juego_slug, inicio_mes_anterior, inicio_mes_actual, mes_anterior_nombre):
    campeon = (
        PuntajeJuego.objects.filter(
            juego=juego_slug,
            fecha_registro__gte=inicio_mes_anterior,
            fecha_registro__lt=inicio_mes_actual,
        )
        .order_by('-puntaje', 'fecha_registro')
        .first()
    )
    if not campeon:
        return None
    return {
        "nombre": campeon.nombre,
        "puntaje": campeon.puntaje,
        "detalle": campeon.detalle,
        "mes": mes_anterior_nombre,
    }


@require_GET
def api_ranking_juego(request):
    juego_slug = (request.GET.get('juego') or '').strip()
    validos = dict(PuntajeJuego.JUEGO_CHOICES)
    if juego_slug not in validos:
        return JsonResponse({"ok": False, "error": "Juego no válido"}, status=400)

    rango = _rango_mes_actual_y_anterior()
    ranking = _serializar_ranking(juego_slug, rango["inicio_mes_actual"], rango["inicio_mes_siguiente"], limite=10)
    total = PuntajeJuego.objects.filter(
        juego=juego_slug,
        fecha_registro__gte=rango["inicio_mes_actual"],
        fecha_registro__lt=rango["inicio_mes_siguiente"],
    ).count()
    campeon_anterior = _obtener_campeon_anterior(
        juego_slug,
        rango["inicio_mes_anterior"],
        rango["inicio_mes_actual"],
        rango["mes_anterior_nombre"],
    )

    config = ConfiguracionSitio.get_solo()
    es_juego_premio = (config.juego_premio_mes == juego_slug)

    return JsonResponse({
        "ok": True,
        "juego": juego_slug,
        "mes_actual": rango["mes_actual_nombre"],
        "total_registros": total,
        "ranking": ranking,
        "campeon_anterior": campeon_anterior,
        "es_juego_premio": es_juego_premio,
        "texto_premio": config.texto_premio_mes if es_juego_premio else "",
    })


@csrf_exempt
@require_POST
def api_guardar_puntaje_juego(request):
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    juego_slug = (payload.get('juego') or '').strip()
    nombre = (payload.get('nombre') or '').strip()[:80]
    email = (payload.get('email') or '').strip().lower()[:150]
    detalle = (payload.get('detalle') or '').strip()[:120]

    validos = dict(PuntajeJuego.JUEGO_CHOICES)
    if juego_slug not in validos:
        return JsonResponse({"ok": False, "error": "Juego no válido"}, status=400)
    if len(nombre) < 2:
        return JsonResponse({"ok": False, "error": "Ingresa tu nombre o apodo (mínimo 2 caracteres)."}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "error": "Ingresa un correo electrónico válido."}, status=400)

    try:
        puntaje = max(0, int(payload.get('puntaje', 0)))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Puntaje inválido."}, status=400)

    rango = _rango_mes_actual_y_anterior()
    qs_mes = PuntajeJuego.objects.filter(
        juego=juego_slug,
        fecha_registro__gte=rango["inicio_mes_actual"],
        fecha_registro__lt=rango["inicio_mes_siguiente"],
    )

    existente = qs_mes.filter(email__iexact=email).first()
    supero_record = True
    if existente:
        if puntaje > existente.puntaje:
            existente.nombre = nombre
            existente.puntaje = puntaje
            existente.detalle = detalle
            existente.fecha_registro = timezone.now()
            existente.save()
            registro = existente
        else:
            registro = existente
            supero_record = False
    else:
        registro = PuntajeJuego.objects.create(
            juego=juego_slug,
            nombre=nombre,
            email=email,
            puntaje=puntaje,
            detalle=detalle,
        )

    mejores_antes = qs_mes.filter(puntaje__gt=registro.puntaje).count()
    empatados_antes = qs_mes.filter(
        puntaje=registro.puntaje,
        fecha_registro__lt=registro.fecha_registro,
    ).count()
    posicion = mejores_antes + empatados_antes + 1

    return JsonResponse({
        "ok": True,
        "id": registro.id,
        "posicion": posicion,
        "supero_record": supero_record,
        "mejor_puntaje": registro.puntaje,
        "mes_actual": rango["mes_actual_nombre"],
        "ranking": _serializar_ranking(juego_slug, rango["inicio_mes_actual"], rango["inicio_mes_siguiente"], limite=10),
        "total_registros": qs_mes.count(),
    })
