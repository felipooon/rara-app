import json
import time
import logging
import requests
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .services import (
    LOS_LAGOS_HUBS,
    CHILE_REGIONS_CONFIG,
    REGIONAL_PROBABLE_SPECIES,
    EBIRD_API_BASE,
    get_api_key,
    fetch_ebird_hotspots,
    fetch_recent_observations,
    fetch_notable_observations,
    fetch_weather_forecast,
    get_tide_events_los_lagos,
    get_tide_at_hour,
    run_optimize_route,
)

logger = logging.getLogger(__name__)

def index(request):
    """Render the main birdplan UI."""
    response = render(request, 'planificador/index.html', {
        'regions_config_json': json.dumps(CHILE_REGIONS_CONFIG, ensure_ascii=False)
    })
    response['Referrer-Policy'] = 'origin-when-cross-origin'
    return response

def api_species_probable(request):
    return JsonResponse(REGIONAL_PROBABLE_SPECIES, safe=False)

def api_hubs(request):
    region = request.GET.get('region', 'CL-LL')
    cfg = CHILE_REGIONS_CONFIG.get(region, CHILE_REGIONS_CONFIG['CL-LL'])
    return JsonResponse(cfg['hubs'])

def api_regions(request):
    return JsonResponse(CHILE_REGIONS_CONFIG)

@csrf_exempt
def api_ebird_proxy(request):
    endpoint = request.GET.get('endpoint', '').strip('/')
    if not endpoint:
        return JsonResponse({'error': 'Missing endpoint parameter'}, status=400)

    api_key = get_api_key(request)
    url = f"{EBIRD_API_BASE}/{endpoint}"

    params = {k: v for k, v in request.GET.items() if k not in ['endpoint', 'key']}
    headers = {
        'X-eBirdApiToken': api_key,
        'User-Agent': 'RaraTienda-Planificador/1.0'
    }

    start_time = time.time()
    try:
        if request.method == 'POST':
            payload = json.loads(request.body.decode('utf-8')) if request.body else None
            res = requests.post(url, headers=headers, params=params, json=payload, timeout=20)
        else:
            res = requests.get(url, headers=headers, params=params, timeout=20)

        elapsed_ms = round((time.time() - start_time) * 1000)

        try:
            data = res.json()
        except Exception:
            data = res.text

        response = JsonResponse({
            'status': res.status_code,
            'elapsed_ms': elapsed_ms,
            'endpoint': endpoint,
            'data': data
        })
        response.status_code = res.status_code
        return response
    except Exception as e:
        logger.error(f"Proxy error for endpoint {endpoint}: {e}")
        return JsonResponse({
            'error': str(e),
            'endpoint': endpoint,
            'status': 500
        }, status=500)

def api_hotspots(request):
    region = request.GET.get('region', 'CL-LL')
    min_species = int(request.GET.get('min_species', 15))
    exclude_cities = request.GET.get('exclude_cities', 'true').lower() == 'true'
    api_key = get_api_key(request)

    all_hotspots = fetch_ebird_hotspots(region, api_key)
    filtered = [
        h for h in all_hotspots
        if h.get('numSpeciesAllTime', 0) >= min_species
        and (not exclude_cities or not h.get('is_city_centroid', False))
    ]
    return JsonResponse(filtered, safe=False)

def api_recent_observations(request):
    region = request.GET.get('region', 'CL-LL')
    back = int(request.GET.get('back', 14))
    api_key = get_api_key(request)
    obs = fetch_recent_observations(region, back, api_key)
    return JsonResponse(obs, safe=False)

def api_notable_observations(request):
    region = request.GET.get('region', 'CL-LL')
    back = int(request.GET.get('back', 14))
    api_key = get_api_key(request)
    obs = fetch_notable_observations(region, back, api_key)
    return JsonResponse(obs, safe=False)

def api_weather(request):
    lat = float(request.GET.get('lat', -41.3195))
    lng = float(request.GET.get('lng', -72.9854))
    target_date = request.GET.get('date')
    data = fetch_weather_forecast(lat, lng, target_date)
    return JsonResponse(data or {})

@csrf_exempt
def api_optimize_route(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        payload = {}

    api_key = get_api_key(request)
    result = run_optimize_route(payload, api_key)
    return JsonResponse(result)

def api_tides(request):
    target_date = request.GET.get('date')
    tide_data = get_tide_events_los_lagos(target_date)
    hourly = []
    for h in range(5, 23):
        t_info = get_tide_at_hour(float(h), target_date)
        hourly.append({
            'time': f"{h:02d}:00",
            'height_m': t_info['height_m'],
            'state': t_info['state'],
            'status_label': t_info['status_label'],
            'note': t_info['note']
        })
    tide_data['hourly'] = hourly
    return JsonResponse(tide_data)


_TILE_SESSION = requests.Session()
_TILE_SESSION.headers.update({
    'User-Agent': 'RaraTienda-Planificador/1.0 (https://raratienda.cl; contacto@raratienda.cl)',
    'Referer': 'https://raratienda.cl/'
})


def api_osm_tile_proxy(request, z, x, y):
    """Proxy OpenStreetMap tiles with compliant User-Agent & Referer so localhost/strict browsers never get 403."""
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    try:
        res = _TILE_SESSION.get(url, timeout=8)
        if res.status_code == 200:
            response = HttpResponse(res.content, content_type=res.headers.get('Content-Type', 'image/png'))
            response['Cache-Control'] = 'public, max-age=604800'
            return response
    except Exception as e:
        logger.warning(f"Tile proxy error for {z}/{x}/{y}: {e}")
    return HttpResponse(status=404)
