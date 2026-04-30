from django.db import models
from django.utils.text import slugify

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    imagen = models.ImageField(upload_to='categorias/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    precio = models.IntegerField()
    imagen = models.ImageField(upload_to='productos/')

    # Nuevo campo para el control de inventario
    stock = models.PositiveIntegerField(default=0, help_text="Cantidad disponible en inventario")
    disponible = models.BooleanField(default=True) 

    def __str__(self):
        return self.nombre
    
    # Opcional: un método rápido para saber si hay stock
    def hay_stock(self):
        return self.stock > 0 and self.disponible

    # --- LÓGICA DE AUTOMATIZACIÓN AL GUARDAR ---
    def save(self, *args, **kwargs):
        # 1. Si el stock es 0, forzamos 'disponible' a False (Agotado)
        if self.stock == 0:
            self.disponible = False
        
        # 2. Si el stock es mayor a 0 y estaba marcado como agotado (False),
        # lo volvemos a poner como disponible (True) automáticamente.
        elif self.stock > 0 and self.disponible == False:
            self.disponible = True
            
        # Llamamos al método save original para que guarde en la BD
        super().save(*args, **kwargs)
    

    
    # =========================
    #   PEDIDOS (aun sin uso)
    # ========================= 

class Pedido(models.Model):
    # 1. Datos del cliente (Compra como invitado)
    nombre_completo = models.CharField(max_length=200)
    rut = models.CharField(max_length=12, help_text="Formato: 12.345.678-9")
    email = models.EmailField()
    telefono = models.CharField(max_length=20)
    direccion = models.CharField(max_length=250)
    ciudad = models.CharField(max_length=100, default="Puerto Montt")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    @property
    def codigo_orden(self):
        """
        Suma 1100 al ID real. Si el ID en base de datos es 7, 
        para el cliente será el pedido 1107.
        """        
        return str(self.id + 1100)
    
    # 2. Datos de la transacción
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    pagado = models.BooleanField(default=False)
    id_transaccion = models.CharField(max_length=100, blank=True, null=True, help_text="ID de MercadoPago o Webpay")

    class Meta:
        ordering = ['-creado'] # Los pedidos más nuevos saldrán primero en tu panel
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'

    def __str__(self):
        return f"Pedido #{self.id} - {self.nombre_completo}"

    def get_total_cost(self):
        # Calcula el total sumando el costo de cada item
        return sum(item.get_costo() for item in self.items.all())
    
    def confirmar_pago(self):
        # 1. Marcamos el pedido como pagado
        self.pagado = True
        self.save()

        # 2. Recorremos cada item comprado en este pedido
        for item in self.items.all():
            producto = item.producto
            
            # Restamos la cantidad comprada al stock del producto
            if producto.stock >= item.cantidad:
                producto.stock -= item.cantidad
            else:
                producto.stock = 0 # Evitamos números negativos por seguridad
            
            # 3. Si el stock llega a 0, lo bajamos de la tienda automáticamente
            if producto.stock == 0:
                producto.disponible = False
                
            # Guardamos los cambios en el producto
            producto.save()


class ItemPedido(models.Model):
    # Relaciona el producto específico con el pedido general
    pedido = models.ForeignKey(Pedido, related_name='items', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, related_name='items_pedido', on_delete=models.CASCADE)
    precio = models.IntegerField(help_text="Precio al momento de la compra") 
    cantidad = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre}"

    def get_costo(self):
        return self.precio * self.cantidad