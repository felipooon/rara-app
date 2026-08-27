from django.contrib import admin
from .models import Categoria, Producto, Pedido, ItemPedido, Cupon, BlogPost, ResenaProducto, ConfiguracionSitio, LogProducto, LogPedido

# --- Configuración de Categorías ---
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)} 

# --- Configuración de Productos ---
@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio', 'stock', 'disponible')
    list_editable = ('stock', 'disponible') 
    list_filter = ('categoria', 'disponible')
    search_fields = ('nombre',)

# --- Configuración de Cupones ---
@admin.register(Cupon)
class CuponAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descuento_porcentaje', 'descuento_monto', 'activo', 'usos_actuales', 'usos_maximos', 'fecha_expiracion')
    list_editable = ('activo',)
    search_fields = ('codigo',)

# --- Configuración para agregar items directo en el pedido ---
class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 1

# --- Configuración de Pedidos ---
@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre_completo', 'rut', 'ciudad', 'estado', 'empresa_transporte', 'numero_seguimiento', 'creado', 'pagado')
    list_filter = ('estado', 'pagado', 'creado', 'ciudad')
    list_editable = ('estado',)
    search_fields = ('nombre_completo', 'email', 'rut', 'numero_seguimiento')
    
    inlines = [ItemPedidoInline]

# --- Configuración de Blog ---
@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'autor', 'fecha_creacion', 'publicado')
    list_filter = ('publicado', 'fecha_creacion')
    search_fields = ('titulo', 'autor', 'contenido')
    prepopulated_fields = {'slug': ('titulo',)}

# --- Configuración de Reseñas ---
@admin.register(ResenaProducto)
class ResenaProductoAdmin(admin.ModelAdmin):
    list_display = ('producto', 'nombre_cliente', 'calificacion', 'comprador_verificado', 'aprobado', 'fecha')
    list_filter = ('aprobado', 'comprador_verificado', 'calificacion', 'fecha')
    list_editable = ('aprobado',)
    search_fields = ('nombre_cliente', 'comentario', 'producto__nombre')

# --- Configuración del Sitio ---
@admin.register(ConfiguracionSitio)
class ConfiguracionSitioAdmin(admin.ModelAdmin):
    list_display = ('mostrar_blog', 'mostrar_resenas')

# --- Configuración de Logs de Productos ---
@admin.register(LogProducto)
class LogProductoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'accion', 'nombre_producto', 'producto_id', 'usuario', 'detalles')
    list_filter = ('accion', 'fecha', 'usuario')
    search_fields = ('nombre_producto', 'detalles', 'usuario__username')
    readonly_fields = ('fecha', 'accion', 'nombre_producto', 'producto_id', 'usuario', 'detalles')

    def has_add_permission(self, request):
        return False

# --- Configuración de Logs de Pedidos ---
@admin.register(LogPedido)
class LogPedidoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'accion', 'codigo_orden', 'cliente_nombre', 'cliente_email', 'usuario', 'detalles')
    list_filter = ('accion', 'fecha', 'usuario')
    search_fields = ('codigo_orden', 'cliente_nombre', 'cliente_email', 'detalles')
    readonly_fields = ('fecha', 'accion', 'codigo_orden', 'cliente_nombre', 'cliente_email', 'pedido_id', 'usuario', 'detalles')

    def has_add_permission(self, request):
        return False