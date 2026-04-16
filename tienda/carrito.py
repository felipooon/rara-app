from decimal import Decimal
from django.conf import settings
from .models import Producto

class Carrito:
    def __init__(self, request):
        """
        Inicializa el carrito pidiéndole a Django la sesión actual del usuario.
        """
        self.session = request.session
        carrito = self.session.get('carrito')
        
        # Si el usuario no tiene un carrito en esta sesión, le creamos uno vacío
        if not carrito:
            carrito = self.session['carrito'] = {}
            
        self.carrito = carrito

    def agregar(self, producto, cantidad=1):
        """
        Agrega un producto al carrito o actualiza su cantidad.
        """
        # Las claves en las sesiones de Django deben ser strings
        producto_id = str(producto.id)

        if producto_id not in self.carrito:
            self.carrito[producto_id] = {
                'producto_id': producto.id,
                'nombre': producto.nombre,
                'precio': producto.precio, # Recuerda que en tu modelo es un IntegerField
                'cantidad': 0,
                # Guardamos la URL de la imagen para mostrarla en el resumen del carrito
                'imagen': producto.imagen.url if producto.imagen else '' 
            }
        
        self.carrito[producto_id]['cantidad'] += cantidad
        self.guardar()

    def restar(self, producto):
        """
        Resta la cantidad de un producto. Si llega a 0, lo elimina.
        """
        producto_id = str(producto.id)
        if producto_id in self.carrito:
            self.carrito[producto_id]['cantidad'] -= 1
            if self.carrito[producto_id]['cantidad'] <= 0:
                self.eliminar(producto)
            self.guardar()

    def eliminar(self, producto):
        """
        Elimina un producto del carrito por completo.
        """
        producto_id = str(producto.id)
        if producto_id in self.carrito:
            del self.carrito[producto_id]
            self.guardar()

    def limpiar(self):
        """
        Vacía el carrito completo (ideal para después de un pago exitoso).
        """
        self.session['carrito'] = {}
        self.guardar()

    def guardar(self):
        """
        Le avisa a Django que la sesión fue modificada y debe guardarse.
        """
        self.session.modified = True

    def get_total(self):
        """
        Calcula el precio total de todos los items en el carrito.
        """
        return sum(int(item['precio']) * item['cantidad'] for item in self.carrito.values())

    def __iter__(self):
        """
        Permite iterar sobre los items del carrito en los templates HTML y 
        trae los objetos Producto reales de la base de datos para validaciones de stock.
        """
        producto_ids = self.carrito.keys()
        # Obtenemos los productos reales de la base de datos
        productos = Producto.objects.filter(id__in=producto_ids)
        
        # Hacemos una copia del carrito para iterar de forma segura
        carrito_copia = self.carrito.copy()

        for producto in productos:
            carrito_copia[str(producto.id)]['producto_real'] = producto

        for item in carrito_copia.values():
            item['precio_total'] = int(item['precio']) * item['cantidad']
            yield item