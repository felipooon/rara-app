from .carrito import Carrito
from .models import ConfiguracionSitio, Categoria

def carrito_global(request):
    """Procesador de contexto global para el Carrito de Compras"""
    return {
        'carrito': Carrito(request)
    }

def configuracion_sitio(request):
    """Procesador de contexto global para tener acceso a config_sitio y categorías en todas las plantillas HTML"""
    try:
        config = ConfiguracionSitio.get_solo()
    except Exception:
        config = None
    try:
        categorias_nav = list(Categoria.objects.filter(producto__disponible=True).distinct().order_by('nombre'))
    except Exception:
        categorias_nav = []
    return {
        'config_sitio': config,
        'categorias_nav': categorias_nav,
    }