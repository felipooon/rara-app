from decimal import Decimal
from django.conf import settings
from .models import Producto

class Carrito:
    PACK_CALCETINES_CANTIDAD = 3
    PACK_CALCETINES_PRECIO = 15990

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
        self._productos_cache = None
        self._pack_info_cache = None

    def agregar(self, producto, cantidad=1):
        id = str(producto.id)
        cantidad = int(cantidad)
        precio_a_cobrar = str(producto.precio_actual)
        precio_original = str(producto.precio)
        en_oferta = producto.tiene_descuento
        descuento_porcentaje = producto.porcentaje_descuento

        if id not in self.carrito:
            # El producto no está en el carrito, evaluamos si pide más del stock
            if cantidad > producto.stock:
                self.carrito[id] = {
                    "producto_id": producto.id,
                    "nombre": producto.nombre,
                    "precio": precio_a_cobrar,
                    "precio_original": precio_original,
                    "en_oferta": en_oferta,
                    "descuento_porcentaje": descuento_porcentaje,
                    "cantidad": producto.stock, # Lo limitamos al stock máximo
                    "imagen": producto.imagen.url if producto.imagen else ""
                }
                self.guardar()
                return False # Retornamos False para indicar que se limitó por stock
            else:
                self.carrito[id] = {
                    "producto_id": producto.id,
                    "nombre": producto.nombre,
                    "precio": precio_a_cobrar,
                    "precio_original": precio_original,
                    "en_oferta": en_oferta,
                    "descuento_porcentaje": descuento_porcentaje,
                    "cantidad": cantidad,
                    "imagen": producto.imagen.url if producto.imagen else ""
                }
                self.guardar()
                return True
        else:
            # El producto ya está en el carrito, evaluamos la suma y actualizamos precio vigente
            self.carrito[id]["precio"] = precio_a_cobrar
            self.carrito[id]["precio_original"] = precio_original
            self.carrito[id]["en_oferta"] = en_oferta
            self.carrito[id]["descuento_porcentaje"] = descuento_porcentaje
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

    def _invalidar_cache(self):
        self._productos_cache = None
        self._pack_info_cache = None

    def _get_productos_map(self):
        """Obtiene y cachea en memoria por petición los Producto del carrito."""
        if self._productos_cache is None:
            producto_ids = list(self.carrito.keys())
            if not producto_ids:
                self._productos_cache = {}
            else:
                self._productos_cache = {
                    str(p.id): p
                    for p in Producto.objects.select_related('categoria').filter(id__in=producto_ids)
                }
        return self._productos_cache

    def guardar(self):
        """
        Le avisa a Django que la sesión fue modificada y debe guardarse.
        """
        self._invalidar_cache()
        self.session.modified = True

    def get_total_bruto(self):
        """Calcula el precio bruto total (sin descuento de pack) de todos los items en el carrito."""
        return sum(int(item['precio']) * item['cantidad'] for item in self.carrito.values())

    def get_info_pack_calcetines(self):
        """
        Calcula si hay packs completos de calcetines (3 pares por $15.990) en el carrito.
        Retorna un dict con cantidad_calcetines, packs_completos, faltan_para_pack y descuento_pack.
        """
        if self._pack_info_cache is not None:
            return self._pack_info_cache

        if not self.carrito:
            self._pack_info_cache = {
                'cantidad_calcetines': 0,
                'packs_completos': 0,
                'faltan_para_pack': self.PACK_CALCETINES_CANTIDAD,
                'descuento_pack': 0,
                'precio_pack': self.PACK_CALCETINES_PRECIO,
                'cantidad_pack': self.PACK_CALCETINES_CANTIDAD,
            }
            return self._pack_info_cache

        productos_map = self._get_productos_map()

        precios_calcetines = []
        for pid, data in self.carrito.items():
            cant = max(0, int(data.get('cantidad', 0)))
            if cant <= 0:
                continue
            prod = productos_map.get(str(pid))
            if prod and prod.categoria:
                slug_cat = (prod.categoria.slug or '').lower()
                nom_cat = (prod.categoria.nombre or '').lower()
                if 'calcetin' in slug_cat or 'calcet' in nom_cat:
                    precio_unit = int(prod.precio_actual)
                    precios_calcetines.extend([precio_unit] * cant)

        total_calcetines = len(precios_calcetines)
        packs_completos = total_calcetines // self.PACK_CALCETINES_CANTIDAD
        descuento_pack = 0

        if packs_completos > 0:
            precios_calcetines.sort(reverse=True)
            unidades_en_pack = packs_completos * self.PACK_CALCETINES_CANTIDAD
            costo_normal_packs = sum(precios_calcetines[:unidades_en_pack])
            descuento_pack = max(0, costo_normal_packs - (packs_completos * self.PACK_CALCETINES_PRECIO))

        resto = total_calcetines % self.PACK_CALCETINES_CANTIDAD
        faltan_para_pack = (self.PACK_CALCETINES_CANTIDAD - resto) if resto > 0 else self.PACK_CALCETINES_CANTIDAD

        self._pack_info_cache = {
            'cantidad_calcetines': total_calcetines,
            'packs_completos': packs_completos,
            'faltan_para_pack': faltan_para_pack,
            'descuento_pack': descuento_pack,
            'precio_pack': self.PACK_CALCETINES_PRECIO,
            'cantidad_pack': self.PACK_CALCETINES_CANTIDAD,
        }
        return self._pack_info_cache

    @property
    def info_pack_calcetines(self):
        return self.get_info_pack_calcetines()

    def get_descuento_pack(self):
        return self.get_info_pack_calcetines()['descuento_pack']

    def get_total(self):
        """
        Calcula el precio total de todos los items en el carrito aplicando el pack de calcetines.
        """
        return max(0, self.get_total_bruto() - self.get_descuento_pack())

    def __len__(self):
        """
        Retorna la cantidad total de unidades en el carrito.
        """
        return sum(item['cantidad'] for item in self.carrito.values())

    @property
    def total_items(self):
        """
        Retorna la cantidad total de unidades en el carrito.
        """
        return sum(item['cantidad'] for item in self.carrito.values())

    @property
    def minimo_entrega_gratis(self):
        """Monto mínimo para Entrega Presencial Gratis en Puerto Montt o Puerto Varas."""
        return 25000

    @property
    def costo_entrega_reducido(self):
        """Costo reducido de Entrega Presencial bajo el monto mínimo."""
        return 1500

    @property
    def falta_para_entrega_gratis(self):
        """Cuánto falta en CLP para alcanzar Entrega Presencial Gratis."""
        return max(0, self.minimo_entrega_gratis - self.get_total())

    @property
    def porcentaje_entrega_gratis(self):
        """Porcentaje de avance (0 a 100) hacia Entrega Presencial Gratis."""
        total = self.get_total()
        if total <= 0:
            return 0
        return min(100, int(round((total / self.minimo_entrega_gratis) * 100)))

    @property
    def tiene_entrega_gratis(self):
        """Retorna True si el carrito ya alcanzó el mínimo para Entrega Presencial Gratis."""
        return self.get_total() >= self.minimo_entrega_gratis

    def get_puntos_caja(self):
        """
        Calcula los puntos totales de capacidad de empaque del carrito (Caja XS = 12 pts):
        - Los artículos MINI (pins, stickers) aprovechan los huecos libres de la caja:
          si hay otros productos en la caja, hasta 2.5 pts (5 pins/stickers) no suman volumen extra.
        """
        if not self.carrito:
            return 0.0

        productos_map = self._get_productos_map()

        puntos_no_mini = 0.0
        puntos_mini = 0.0

        for pid, data in self.carrito.items():
            cant = max(0, int(data.get('cantidad', 0)))
            if cant <= 0:
                continue
            prod = productos_map.get(str(pid))
            if prod:
                tam = prod.tamano_envio_efectivo
                pts_unit = prod.puntos_caja_unidad
            else:
                tam = 'ESTANDAR'
                pts_unit = 4.0

            if tam == 'MINI':
                puntos_mini += cant * pts_unit
            else:
                puntos_no_mini += cant * pts_unit

        if puntos_no_mini > 0:
            # Hasta 6 llaveros/pines/stickers (3.0 pts) caben en los espacios libres junto a 3 pares de calcetines u otros productos
            puntos_mini_extra = max(0.0, puntos_mini - 3.0)
            return round(puntos_no_mini + puntos_mini_extra, 1)

        return round(puntos_mini, 1)

    def get_talla_envio(self):
        """
        Determina la Talla Blue Express (XS, S, M, L) según los puntos de capacidad:
        - Hasta 12 pts -> Talla XS (1 caja XS estándar: 3 calcetines + pins, 4 guías, 2 arneses, etc.)
        - 12.1 a 36 pts -> Talla S (hasta 3 cajas XS o 1-2 libros grandes)
        - 36.1 a 72 pts -> Talla M (1 casa de pájaros o pedidos medianos)
        - Más de 72 pts -> Talla L (2+ casas de pájaros o pedidos grandes)
        """
        pts = self.get_puntos_caja()
        if pts <= 12.0:
            return 'XS'
        elif pts <= 36.0:
            return 'S'
        elif pts <= 72.0:
            return 'M'
        return 'L'

    @property
    def puntos_caja(self):
        return self.get_puntos_caja()

    @property
    def talla_envio(self):
        return self.get_talla_envio()

    def __iter__(self):
        """
        Permite iterar sobre los items del carrito en los templates HTML y 
        trae los objetos Producto reales de la base de datos para validaciones de stock.
        Crea una copia independiente de cada item para no contaminar la sesión de Django con objetos no serializables.
        """
        productos = self._get_productos_map().values()
        
        # Hacemos una copia independiente de los diccionarios internos del carrito
        carrito_copia = {key: value.copy() for key, value in self.carrito.items()}

        for producto in productos:
            key = str(producto.id)
            if key in carrito_copia:
                carrito_copia[key]['producto_real'] = producto
                carrito_copia[key]['precio'] = str(producto.precio_actual)
                carrito_copia[key]['precio_original'] = str(producto.precio)
                carrito_copia[key]['en_oferta'] = producto.tiene_descuento
                carrito_copia[key]['descuento_porcentaje'] = producto.porcentaje_descuento
                if producto.imagen:
                    carrito_copia[key]['imagen'] = producto.get_imagen_url_300 or producto.imagen.url

        for item in carrito_copia.values():
            item['precio_total'] = int(item['precio']) * item['cantidad']
            yield item