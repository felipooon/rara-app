from django.contrib import admin
from .models import Categoria, Producto, Pedido, ItemPedido, Cupon

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