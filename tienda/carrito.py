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
        id = str(producto.id)
        cantidad = int(cantidad)

        if id not in self.carrito:
            # El producto no está en el carrito, evaluamos si pide más del stock
            if cantidad > producto.stock:
                self.carrito[id] = {
                    "producto_id": producto.id,
                    "nombre": producto.nombre,
                    "precio": str(producto.precio),
                    "cantidad": producto.stock, # Lo limitamos al stock máximo
                    "imagen": producto.imagen.url if producto.imagen else ""
                }
                self.guardar()
                return False # Retornamos False para indicar que se limitó por stock
            else:
                self.carrito[id] = {
                    "producto_id": producto.id,
                    "nombre": producto.nombre,
                    "precio": str(producto.precio),
                    "cantidad": cantidad,
                    "imagen": producto.imagen.url if producto.imagen else ""
                }
                self.guardar()
                return True
        else:
            # El producto ya está en el carrito, evaluamos la suma
            cantidad_actual = self.carrito[id]["cantidad"]
            cantidad_total_deseada = cantidad_actual + cantidad

            if cantidad_total_deseada > producto.stock:
                # Si la suma supera el stock, lo topamos al máximo
                self.carrito[id]["cantidad"] = producto.stock
                self.guardar()
                return False # Retornamos False para indicar límite
            else:
                self.carrito[id]["cantidad"] += cantidad
                self.guardar()
                return True

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