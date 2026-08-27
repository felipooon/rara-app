from .carrito import Carrito
from .models import ConfiguracionSitio

def carrito_global(request):
    """Procesador de contexto global para el Carrito de Compras"""
    return {
        'carrito': Carrito(request)
    }

def configuracion_sitio(request):
    """Procesador de contexto global para tener acceso a config_sitio en todas las plantillas HTML"""
    try:
        config = ConfiguracionSitio.get_solo()
    except Exception:
        config = None
    return {
        'config_sitio': config
    }