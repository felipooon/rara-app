import re
from django.utils import timezone
from django.db.models import F
from .models import MetricaDiaria

# Lista básica de cadenas en User-Agent comunes para bots
BOT_REGEX = re.compile(r'(bot|spider|crawl|slurp|google|bing|yandex|yahoo|baidu)', re.IGNORECASE)

class AnaliticasMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Solo registrar rutas públicas (ignorar admin, estáticos, media)
        if request.path.startswith('/admin/') or request.path.startswith('/static/') or request.path.startswith('/media/') or request.path.startswith('/panel/'):
            return response
            
        # Si no es una respuesta exitosa, no contamos
        if response.status_code not in (200, 301, 302):
            return response

        user_agent = request.META.get('HTTP_USER_AGENT', '')
        es_bot = bool(BOT_REGEX.search(user_agent))
        
        hoy = timezone.localdate()
        
        metrica, created = MetricaDiaria.objects.get_or_create(fecha=hoy)
        
        # Usamos update con F() para evitar condiciones de carrera (race conditions)
        if es_bot:
            MetricaDiaria.objects.filter(id=metrica.id).update(visitas_bots=F('visitas_bots') + 1)
        else:
            MetricaDiaria.objects.filter(id=metrica.id).update(visitas_humanos=F('visitas_humanos') + 1)
            
        return response
