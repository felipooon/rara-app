from django.test import TestCase, RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from .models import Categoria, Producto, Pedido, ItemPedido
from .carrito import Carrito

class ProductoModelTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Aves")
        
    def test_producto_sin_stock_se_agota_automaticamente(self):
        """Si se guarda un producto con stock 0, debe quedar como no disponible."""
        producto = Producto.objects.create(
            categoria=self.categoria,
            nombre="Binoculares",
            precio=50000,
            stock=0,
            disponible=True
        )
        # La lógica del método save() debería cambiar disponible a False
        self.assertFalse(producto.disponible)

    def test_producto_con_stock_sigue_disponible(self):
        """Un producto con stock se mantiene disponible si así se creó."""
        producto = Producto.objects.create(
            categoria=self.categoria,
            nombre="Guía de campo",
            precio=25000,
            stock=10,
            disponible=True
        )
        self.assertTrue(producto.disponible)


class CarritoTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.categoria = Categoria.objects.create(nombre="Aves")
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre="Cámara",
            precio=100000,
            stock=3,
            disponible=True
        )

    def _get_request_con_sesion(self):
        request = self.factory.get('/')
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def test_agregar_producto_nuevo(self):
        """Agregar un producto válido lo pone en el carrito."""
        request = self._get_request_con_sesion()
        carrito = Carrito(request)
        resultado = carrito.agregar(self.producto, 1)
        
        self.assertTrue(resultado)
        self.assertEqual(len(carrito.carrito), 1)
        self.assertEqual(carrito.carrito[str(self.producto.id)]['cantidad'], 1)

    def test_agregar_mas_del_stock_permitido(self):
        """Si intentan agregar más del stock, el carrito bloquea la acción."""
        request = self._get_request_con_sesion()
        carrito = Carrito(request)
        
        # Intentamos agregar 5 (el stock es 3)
        resultado = carrito.agregar(self.producto, 5)
        
        self.assertFalse(resultado) # Devuelve False por exceder límite
        self.assertEqual(carrito.carrito[str(self.producto.id)]['cantidad'], 3) # Se capa en 3

    def test_calculo_total_correcto(self):
        """El total del carrito debe multiplicar cantidad por precio."""
        request = self._get_request_con_sesion()
        carrito = Carrito(request)
        
        producto2 = Producto.objects.create(
            categoria=self.categoria, nombre="Lápiz", precio=2000, stock=10, disponible=True
        )
        
        carrito.agregar(self.producto, 2) # 2 x 100000 = 200000
        carrito.agregar(producto2, 3)     # 3 x 2000 = 6000
        
        self.assertEqual(carrito.get_total(), 206000)

    def test_iter_no_contamina_sesion_json(self):
        """La iteración del carrito no debe inyectar objetos Producto en la sesión original."""
        request = self._get_request_con_sesion()
        carrito = Carrito(request)
        carrito.agregar(self.producto, 1)
        
        # Iteramos sobre el carrito para forzar __iter__
        list(iter(carrito))
        
        # Guardar la sesión no debe lanzar TypeError
        try:
            request.session.save()
            sesion_valida = True
        except TypeError:
            sesion_valida = False
            
        self.assertTrue(sesion_valida)

class PedidoModelTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Aves")
        self.producto = Producto.objects.create(
            categoria=self.categoria,
            nombre="Peluche Rara",
            precio=15000,
            stock=5,
            disponible=True
        )
        self.pedido = Pedido.objects.create(
            nombre_completo="Juan Pérez",
            rut="12345678-9",
            email="juan@ejemplo.com",
            telefono="987654321",
            direccion="Calle Falsa 123",
            ciudad="Santiago"
        )
        ItemPedido.objects.create(
            pedido=self.pedido,
            producto=self.producto,
            precio=15000,
            cantidad=2
        )

    def test_confirmar_pago_descuenta_stock(self):
        """Al confirmar el pago, se debe restar el inventario."""
        self.pedido.confirmar_pago()
        
        # Actualizamos el producto desde la base de datos
        self.producto.refresh_from_db()
        
        # Habían 5, compraron 2, deberían quedar 3
        self.assertEqual(self.producto.stock, 3)
        self.assertTrue(self.producto.disponible)
        self.assertTrue(self.pedido.pagado)

    def test_confirmar_pago_agota_stock(self):
        """Si la compra consume todo el stock, el producto debe marcarse agotado."""
        # Modificamos el item existente para que consuma todo el stock (5)
        item = self.pedido.items.first()
        item.cantidad = 5
        item.save()
        
        self.pedido.confirmar_pago()
        
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 0)
        self.assertFalse(self.producto.disponible)
