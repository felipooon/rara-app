# tienda/context_processors.py
from .carrito import Carrito

def carrito_global(request):
    # Esto inyecta la variable 'carrito' en TODOS tus archivos HTML
    return {'carrito': Carrito(request)}