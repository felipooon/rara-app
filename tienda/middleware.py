from django.utils import timezone
from django.db.models import F
from crawlerdetect import CrawlerDetect
from .models import MetricaDiaria

crawler_detector = CrawlerDetect()

class AnaliticasMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Solo registrar rutas públicas (ignorar admin, estáticos, media, panel)
        if request.path.startswith('/admin/') or request.path.startswith('/static/') or request.path.startswith('/media/') or request.path.startswith('/panel/'):
            return response
            
        # Si no es una respuesta exitosa, no contamos
        if response.status_code not in (200, 301, 302):
            return response

        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # 1. Detección avanzada de bots con base de datos amplia de User-Agents
        es_bot = crawler_detector.isCrawler(user_agent)
        
        hoy = timezone.localdate()
        metrica, created = MetricaDiaria.objects.get_or_create(fecha=hoy)
        
        if es_bot:
            MetricaDiaria.objects.filter(id=metrica.id).update(visitas_bots=F('visitas_bots') + 1)
        else:
            # 2. Visitantes humanos únicos por día mediante cookie
            cookie_key = f'v_h_{hoy.strftime("%Y%m%d")}'
            if not request.COOKIES.get(cookie_key):
                MetricaDiaria.objects.filter(id=metrica.id).update(visitas_humanos=F('visitas_humanos') + 1)
                response.set_cookie(cookie_key, '1', max_age=86400, httponly=True, samesite='Lax')
            
        return response

