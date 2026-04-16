from django.contrib import admin
from .models import Categoria, Producto, Pedido, ItemPedido

# --- Configuración de Categorías ---
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)} 

# --- Configuración de Productos ---
@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    # Columnas que verás en la lista
    list_display = ('nombre', 'categoria', 'precio', 'stock', 'disponible')
    # Te permite cambiar el stock y disponibilidad directo desde la tabla general
    list_editable = ('stock', 'disponible') 
    list_filter = ('categoria', 'disponible')
    search_fields = ('nombre',)

# --- Configuración para agregar items directo en el pedido ---
class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 1 # Muestra una fila vacía por defecto para agregar un producto

# --- Configuración de Pedidos ---
@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre_completo', 'rut', 'ciudad', 'creado', 'pagado')
    list_filter = ('pagado', 'creado', 'ciudad')
    search_fields = ('nombre_completo', 'email', 'rut')
    
    # Aquí incrustamos los productos dentro de la vista del pedido
    inlines = [ItemPedidoInline]