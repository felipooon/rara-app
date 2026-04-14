from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from .models import Categoria, Producto
from .forms import CategoriaForm, ProductoForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView

#PAGINA PUBLICA

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

#PANEL DE ADMINISTRACION

@login_required
def panel_productos(request):
    productos = Producto.objects.all()

    categoria_id = request.GET.get("categoria")
    estado = request.GET.get("estado")

    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)

    if estado == "disponible":
        productos = productos.filter(disponible=True)

    elif estado == "agotado":
        productos = productos.filter(disponible=False)

    categorias = Categoria.objects.all()

    return render(request, "panel/productos.html", {
        "productos": productos,
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