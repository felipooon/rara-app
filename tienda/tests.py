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

    def test_producto_galeria_imagenes(self):
        """Un producto puede tener imágenes adicionales asociadas."""
        from .models import ImagenProducto
        producto = Producto.objects.create(
            categoria=self.categoria,
            nombre="Polera Ilustrada",
            precio=18000,
            stock=5,
            disponible=True
        )
        img_extra = ImagenProducto.objects.create(
            producto=producto,
            imagen="productos/galeria/test.jpg"
        )
        self.assertEqual(len(producto.todas_las_imagenes), 1)
        self.assertEqual(producto.todas_las_imagenes[0]['id'], img_extra.id)


class CloudinaryUrlTests(TestCase):
    def test_get_cloudinary_url_local(self):
        """Verifica que las URLs locales se formateen correctamente en entorno dev."""
        from .utils import get_cloudinary_url
        url = get_cloudinary_url("/media/productos/foto.png", width=600)
        self.assertEqual(url, "https://www.raratienda.cl/media/productos/foto.png")

    def test_get_cloudinary_url_transformations(self):
        """Verifica que se aplique f_auto, q_auto y w_{width} sin forzar extensión .jpg."""
        from .utils import get_cloudinary_url
        raw_url = "https://res.cloudinary.com/demo/image/upload/v12345/sample.png"
        url = get_cloudinary_url(raw_url, width=600)
        self.assertEqual(url, "https://res.cloudinary.com/demo/image/upload/f_auto,q_auto,w_600/v12345/sample.png")

    def test_get_cloudinary_url_reemplaza_f_jpg(self):
        """Verifica que reemplace f_jpg por f_auto y elimine transformaciones obsoletas."""
        from .utils import get_cloudinary_url
        old_url = "https://res.cloudinary.com/demo/image/upload/f_jpg,q_auto,w_600/v12345/sample.png"
        url = get_cloudinary_url(old_url, width=300)
        self.assertEqual(url, "https://res.cloudinary.com/demo/image/upload/f_auto,q_auto,w_300/v12345/sample.png")

    def test_templatetag_cloudinary_url(self):
        """Verifica el funcionamiento del template filter cloudinary_url."""
        from .templatetags.imagen_tags import cloudinary_url
        raw_url = "https://res.cloudinary.com/demo/image/upload/v12345/sample.png"
        res = cloudinary_url(raw_url, 1200)
        self.assertEqual(res, "https://res.cloudinary.com/demo/image/upload/f_auto,q_auto,w_1200/v12345/sample.png")

    def test_categoria_y_blog_image_properties(self):
        """Verifica que Categoria y BlogPost dispongan de get_imagen_url_600 y propiedades de tamaño."""
        cat = Categoria.objects.create(nombre="Aves Test", imagen="categorias/test.jpg")
        self.assertIsNotNone(cat.get_imagen_url_600)
        self.assertIsNotNone(cat.get_imagen_url_300)

        from .models import BlogPost
        post = BlogPost.objects.create(titulo="Blog Test", contenido="Test content", imagen="blog/test.jpg")
        self.assertIsNotNone(post.get_imagen_url_600)
        self.assertIsNotNone(post.get_imagen_url_1200)





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
        item = self.pedido.items.first()
        item.cantidad = 5
        item.save()
        
        self.pedido.confirmar_pago()
        
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 0)
        self.assertFalse(self.producto.disponible)

class CuponModelTests(TestCase):
    def test_validacion_cupon(self):
        """Un cupón activo debe calcular el descuento correctamente."""
        from tienda.models import Cupon
        cupon = Cupon.objects.create(
            codigo="RARA10",
            descuento_porcentaje=10,
            activo=True
        )
        valido, msg = cupon.es_valido()
        self.assertTrue(valido)
        self.assertEqual(cupon.calcular_descuento(10000), 1000)

class ApiBusquedaTests(TestCase):
    def test_api_buscar_productos(self):
        """La API de búsqueda debe retornar coincidencias en formato JSON."""
        categoria = Categoria.objects.create(nombre="Ropa")
        Producto.objects.create(categoria=categoria, nombre="Polera Chucao", precio=12000, stock=5, disponible=True)
        
        response = self.client.get('/api/buscar-productos/?q=Chucao')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['productos']), 1)
        self.assertIn("Polera Chucao", data['productos'][0]['nombre'])


class CategoriaIndexTests(TestCase):
    def test_index_oculta_categorias_sin_productos_disponibles(self):
        """La vista de inicio solo debe mostrar categorías con al menos un producto disponible."""
        cat_activa = Categoria.objects.create(nombre="Categoría Activa")
        cat_sin_stock = Categoria.objects.create(nombre="Categoría Sin Stock")
        cat_vacia = Categoria.objects.create(nombre="Categoría Vacía")

        Producto.objects.create(categoria=cat_activa, nombre="Producto Disponible", precio=1000, stock=5, disponible=True)
        Producto.objects.create(categoria=cat_sin_stock, nombre="Producto Agotado", precio=1000, stock=0, disponible=False)

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        categorias_en_contexto = list(response.context['categorias'])
        
        self.assertIn(cat_activa, categorias_en_contexto)
        self.assertNotIn(cat_sin_stock, categorias_en_contexto)
        self.assertNotIn(cat_vacia, categorias_en_contexto)


class OfertaProductoTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Aves")

    def test_producto_sin_oferta_tiene_precio_normal(self):
        prod = Producto.objects.create(
            categoria=self.categoria,
            nombre="Tazón Martín Pescador",
            precio=10000,
            stock=10,
            en_oferta=False
        )
        self.assertFalse(prod.tiene_descuento)
        self.assertEqual(prod.precio_actual, 10000)
        self.assertEqual(prod.porcentaje_descuento, 0)
        self.assertEqual(prod.monto_ahorro, 0)

    def test_producto_en_oferta_con_precio_fijo(self):
        prod = Producto.objects.create(
            categoria=self.categoria,
            nombre="Guía Ilustrada",
            precio=20000,
            precio_oferta=16000,
            en_oferta=True,
            stock=5
        )
        self.assertTrue(prod.tiene_descuento)
        self.assertEqual(prod.precio_actual, 16000)
        self.assertEqual(prod.porcentaje_descuento, 20)
        self.assertEqual(prod.monto_ahorro, 4000)

    def test_producto_en_oferta_con_porcentaje_calcula_precio_oferta(self):
        prod = Producto.objects.create(
            categoria=self.categoria,
            nombre="Polera Chucao",
            precio=20000,
            descuento_porcentaje=25,
            en_oferta=True,
            stock=5
        )
        self.assertTrue(prod.tiene_descuento)
        self.assertEqual(prod.precio_oferta, 15000)
        self.assertEqual(prod.precio_actual, 15000)
        self.assertEqual(prod.porcentaje_descuento, 25)
        self.assertEqual(prod.monto_ahorro, 5000)

    def test_carrito_cobra_precio_oferta(self):
        prod = Producto.objects.create(
            categoria=self.categoria,
            nombre="Gorra Rara",
            precio=15000,
            precio_oferta=12000,
            en_oferta=True,
            stock=5
        )
        request = RequestFactory().get('/')
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        carrito = Carrito(request)
        carrito.agregar(prod, cantidad=2)

        self.assertEqual(carrito.get_total(), 24000)
        items = list(carrito)
        self.assertEqual(items[0]['precio'], '12000')
        self.assertTrue(items[0]['en_oferta'])
        self.assertEqual(items[0]['descuento_porcentaje'], 20)

    def test_producto_form_validacion_oferta(self):
        from .forms import ProductoForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        # 1x1 transparent GIF valid bytes for Pillow
        gif_bytes = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        test_img = SimpleUploadedFile("test.gif", gif_bytes, content_type="image/gif")

        # Error si activa oferta sin precio ni porcentaje
        form = ProductoForm(
            data={
                'categoria': self.categoria.id,
                'nombre': 'Producto Test',
                'precio': '10.000',
                'stock': 5,
                'disponible': True,
                'en_oferta': True,
            },
            files={'imagen': test_img}
        )
        self.assertFalse(form.is_valid())
        self.assertIn('precio_oferta', form.errors)

        # Éxito ingresando solo porcentaje
        test_img2 = SimpleUploadedFile("test2.gif", gif_bytes, content_type="image/gif")
        form_pct = ProductoForm(
            data={
                'categoria': self.categoria.id,
                'nombre': 'Producto Test Pct',
                'precio': '20.000',
                'stock': 5,
                'disponible': True,
                'en_oferta': True,
                'descuento_porcentaje': 30,
            },
            files={'imagen': test_img2}
        )
        self.assertTrue(form_pct.is_valid(), form_pct.errors)
        prod = form_pct.save()
        self.assertEqual(prod.precio_oferta, 14000)
        self.assertEqual(prod.porcentaje_descuento, 30)

        # Error si precio oferta es mayor o igual al normal
        test_img3 = SimpleUploadedFile("test3.gif", gif_bytes, content_type="image/gif")
        form_invalido = ProductoForm(
            data={
                'categoria': self.categoria.id,
                'nombre': 'Producto Invalido',
                'precio': '10.000',
                'stock': 5,
                'disponible': True,
                'en_oferta': True,
                'precio_oferta': '12.000',
            },
            files={'imagen': test_img3}
        )
        self.assertFalse(form_invalido.is_valid())
        self.assertIn('precio_oferta', form_invalido.errors)

    def test_vista_detalle_muestra_oferta(self):
        prod = Producto.objects.create(
            categoria=self.categoria,
            nombre="Cuaderno Botánico",
            precio=8000,
            precio_oferta=6000,
            en_oferta=True,
            stock=10
        )
        response = self.client.get(prod.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$6.000")
        self.assertContains(response, "$8.000")
        self.assertContains(response, "25% OFF")

    def test_toggle_oferta_producto(self):
        from django.contrib.auth.models import User
        staff_user = User.objects.create_user(username='admin_test', password='password123', is_staff=True)
        self.client.login(username='admin_test', password='password123')

        prod = Producto.objects.create(
            categoria=self.categoria,
            nombre="Llavero Carpintero",
            precio=5000,
            precio_oferta=4000,
            en_oferta=False,
            stock=10
        )
        # Activar oferta vía toggle
        response = self.client.get(f'/panel/productos/{prod.id}/toggle-oferta/')
        self.assertEqual(response.status_code, 302)
        prod.refresh_from_db()
        self.assertTrue(prod.en_oferta)

        # Desactivar oferta vía toggle
        response = self.client.get(f'/panel/productos/{prod.id}/toggle-oferta/')
        self.assertEqual(response.status_code, 302)
        prod.refresh_from_db()
        self.assertFalse(prod.en_oferta)


