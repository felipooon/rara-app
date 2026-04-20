from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from .models import Categoria, Producto, Pedido, ItemPedido
from .forms import CategoriaForm, ProductoForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from .carrito import Carrito
from django.contrib import messages

#----------------
#PAGINA PUBLICA
#----------------

def index(request):
    categorias = Categoria.objects.all()
    productos = Producto.objects.all()

    return render(request, "index.html", {
        "categorias": categorias,
        "productos": productos
    })


def categoria_detail(request, slug):
    categoria = Categoria.objects.get(slug=slug)

    productos = Producto.objects.filter(
        categoria=categoria,
        disponible=True
    )

    return render(request, "categoria.html", {
        "categoria": categoria,
        "productos": productos
    })

def producto_detail(request, id):
    producto = get_object_or_404(Producto, id=id)

    return render(request, "producto_detail.html", {
        "producto": producto
    })

# CARRITO

def agregar_al_carrito(request, producto_id):
    # 1. Inicializamos clase
    carrito = Carrito(request)
    producto = get_object_or_404(Producto, id=producto_id)
    
    # 2. Usamos método personalizado para validar el stock
    if producto.hay_stock():
        carrito.agregar(producto)
        messages.success(request, f'¡{producto.nombre} agregado a tu nido! 🪹')
    else:
        messages.error(request, f'Lo sentimos, {producto.nombre} está agotado por ahora.')
        
    # Redirigimos al catálogo o donde estaba el usuario
    #return redirect('ver_carrito')
    url_anterior = request.META.get('HTTP_REFERER', '/')
    if '?' in url_anterior:
        return redirect(url_anterior + '&cart=open')
    else:
        return redirect(url_anterior + '?cart=open')


def ver_carrito(request):
    # Simplemente iniciamos el carro y se lo mandamos al HTML
    carrito = Carrito(request)
    return render(request, 'carrito.html', {'carrito': carrito})


def procesar_pedido(request):
    carrito = Carrito(request)
    
    # Seguridad: Si el carro está vacío, no los dejamos pasar
    if len(carrito.carrito) == 0:
        messages.warning(request, "Tu carrito está vacío. ¡Ve a pajarear al catálogo!")
        return redirect('index')

    if request.method == 'POST':
        # 1. Capturamos los datos del cliente desde el formulario
        pedido = Pedido.objects.create(
            nombre_completo=request.POST.get('nombre_completo'),
            rut=request.POST.get('rut'),
            email=request.POST.get('email'),
            telefono=request.POST.get('telefono'),
            direccion=request.POST.get('direccion'),
            ciudad=request.POST.get('ciudad', 'Puerto Montt') # Tu valor por defecto
        )
        
        # 2. método __iter__ en el carrito hace que esto sea súper fácil
        for item in carrito:
            ItemPedido.objects.create(
                pedido=pedido,
                producto=item['producto_real'], # ¡Gracias al iterador, ya tenemos el objeto de la BD!
                precio=item['precio'],
                cantidad=item['cantidad']
            )
        
        # 3. ¡Venta lista! Limpiamos la sesión usando el método
        carrito.limpiar()
        
        # Opcional: Aquí podrías llamar a una función para enviar un correo de confirmación
        
        #return redirect('index')
        return redirect('pedido_confirmado', pedido_id=pedido.id)

    return render(request, 'checkout.html', {'carrito': carrito})


# views.py

def restar_del_carrito(request, producto_id):
    carrito = Carrito(request)
    producto = get_object_or_404(Producto, id=producto_id)
    carrito.restar(producto)
    #return redirect('ver_carrito')
    url_anterior = request.META.get('HTTP_REFERER', '/')
    if '?' in url_anterior:
        return redirect(url_anterior + '&cart=open')
    else:
        return redirect(url_anterior + '?cart=open')

def quitar_del_carrito(request, producto_id):
    carrito = Carrito(request)
    producto = get_object_or_404(Producto, id=producto_id)
    carrito.eliminar(producto)
    #return redirect('ver_carrito')
    url_anterior = request.META.get('HTTP_REFERER', '/')
    if '?' in url_anterior:
        return redirect(url_anterior + '&cart=open')
    else:
        return redirect(url_anterior + '?cart=open')

def limpiar_carrito(request):
    carrito = Carrito(request)
    carrito.limpiar()
    return redirect('ver_carrito')


def pedido_confirmado(request, pedido_id):
    # Buscamos el pedido recién creado para mostrarle sus datos
    pedido = get_object_or_404(Pedido, id=pedido_id)
    return render(request, 'pedido_confirmado.html', {'pedido': pedido})

#-----------------------
#PANEL DE ADMINISTRACION
#-----------------------

@login_required
def panel_productos(request):
    productos = Producto.objects.all().order_by('-id')

    categoria_id = request.GET.get("categoria")
    estado = request.GET.get("estado")

    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)

    if estado == "disponible":
        productos = productos.filter(disponible=True)

    elif estado == "agotado":
        productos = productos.filter(disponible=False)

    categorias = Categoria.objects.all()

    paginator = Paginator(productos, 10) # <-- Cambia el 10 si quieres más o menos filas
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "panel/productos.html", {
      #  "productos": productos,
        "page_obj": page_obj,
        "categorias": categorias
    })


@login_required
def crear_producto(request):
    form = ProductoForm(request.POST or None, request.FILES or None)

    if form.is_valid():
        form.save()
        return redirect("panel_productos")

    return render(request, "panel/producto_form.html", {
        "form": form
    })


@login_required
def crear_categoria(request):
    form = CategoriaForm(request.POST or None, request.FILES or None)

    if form.is_valid():
        form.save()
        return redirect("panel_home")

    return render(request, "panel/categoria_form.html", {
        "form": form
    })


def toggle_producto(request, id):
    producto = get_object_or_404(Producto, id=id)
    producto.disponible = not producto.disponible
    producto.save()
    return redirect("panel_productos")


from .models import Producto, Categoria


@login_required
def panel_home(request):
    total_productos = Producto.objects.count()
    total_categorias = Categoria.objects.count()
    productos_disponibles = Producto.objects.filter(disponible=True).count()
    productos_agotados = Producto.objects.filter(disponible=False).count()
    ultimos_productos = Producto.objects.order_by('-id')[:5]

    return render(request, 'panel/dashboard.html', {
        'total_productos': total_productos,
        'total_categorias': total_categorias,
        'productos_disponibles': productos_disponibles,
        'productos_agotados': productos_agotados,
        'ultimos_productos': ultimos_productos,
    })

class CustomLoginView(LoginView):
    template_name = "login.html"


@login_required
def editar_producto(request, id):
    # 1. Buscamos el producto específico
    producto = get_object_or_404(Producto, id=id)
    
    # 2. Reutilizamos tu formulario, pero le pasamos la "instance" (los datos actuales)
    form = ProductoForm(request.POST or None, request.FILES or None, instance=producto)
    
    if form.is_valid():
        form.save()
        return redirect('panel_productos')
        
    # 3. Usamos el mismo HTML que usaste para crear, ¡así te ahorras hacer otra vista!
    return render(request, "panel/producto_form.html", {
        "form": form,
        "editando": True # Le pasamos esto por si quieres cambiar el título a "Editar Producto"
    })

@login_required
def eliminar_producto(request, id):
    # Buscamos y destruimos
    producto = get_object_or_404(Producto, id=id)
    producto.delete()
    return redirect('panel_productos')

@login_required
def panel_pedidos(request):
    # Traemos todos los pedidos, los más nuevos primero
    pedidos = Pedido.objects.all().order_by('-id')
    return render(request, 'panel/pedidos.html', {'pedidos': pedidos})

@login_required
def detalle_pedido(request, id):
    # Buscamos el pedido y sus items relacionados
    pedido = get_object_or_404(Pedido, id=id)
    # Gracias al related_name='items' que pusiste en el modelo, 
    # podemos acceder a los productos así: pedido.items.all()
    return render(request, 'panel/detalle_pedido.html', {'pedido': pedido})