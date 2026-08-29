from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_GET
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import models

from ..models import Categoria, Producto, BlogPost, ResenaProducto, Pedido, MetricaProducto
from ..forms import ResenaForm


def aplicar_ordenamiento(queryset, orden):
    if orden == 'precio_asc':
        return queryset.order_by('precio')
    elif orden == 'precio_desc':
        return queryset.order_by('-precio')
    elif orden == 'nombre':
        return queryset.order_by('nombre')
    elif orden == 'recientes':
        return queryset.order_by('-id')
    return queryset


def index(request):
    categorias = Categoria.objects.all()
    orden = request.GET.get('orden', '')
    productos = Producto.objects.filter(disponible=True)
    productos = aplicar_ordenamiento(productos, orden)
    productos_destacados = Producto.objects.filter(disponible=True).order_by('?')[:8]
    resenas = ResenaProducto.objects.filter(aprobado=True).select_related('producto')[:8]
    ultimas_entradas_blog = BlogPost.objects.filter(publicado=True).order_by('-fecha_creacion')[:3]

    return render(request, "index.html", {
        "categorias": categorias,
        "productos": productos,
        "productos_destacados": productos_destacados,
        "resenas": resenas,
        "ultimas_entradas_blog": ultimas_entradas_blog,
        "orden_actual": orden
    })


def terminos_condiciones(request):
    return render(request, "terminos.html")


def categoria_detail(request, slug):
    categoria = get_object_or_404(Categoria, slug=slug)
    orden = request.GET.get('orden', '')

    productos = Producto.objects.filter(
        categoria=categoria,
        disponible=True
    )
    productos = aplicar_ordenamiento(productos, orden)

    return render(request, "categoria.html", {
        "categoria": categoria,
        "productos": productos,
        "orden_actual": orden
    })


@require_GET
def api_buscar_productos(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'productos': []})
    
    productos = Producto.objects.filter(
        models.Q(nombre__icontains=q) | models.Q(descripcion__icontains=q),
        disponible=True
    )[:6]
    
    data = []
    for p in productos:
        data.append({
            'id': p.id,
            'nombre': p.nombre,
            'precio': f"${p.precio:,}".replace(',', '.'),
            'url': p.get_absolute_url(),
            'imagen': p.imagen.url if p.imagen else ''
        })
    return JsonResponse({'productos': data})


def producto_detail(request, slug=None, id=None):
    if slug:
        if slug.isdigit():
            producto = Producto.objects.filter(id=int(slug)).first()
            if producto:
                if producto.slug and producto.slug != slug:
                    return redirect(producto.get_absolute_url(), permanent=True)
                return render(request, "producto_detail.html", {"producto": producto})
        producto = get_object_or_404(Producto, slug=slug)
    elif id:
        producto = get_object_or_404(Producto, id=id)
        if producto.slug:
            return redirect(producto.get_absolute_url(), permanent=True)
    else:
        return redirect('index')

    resenas = producto.resenas.filter(aprobado=True)
    resena_form = ResenaForm()

    from django.utils import timezone
    hoy = timezone.localdate()
    metrica_prod, created = MetricaProducto.objects.get_or_create(producto=producto, fecha=hoy)
    MetricaProducto.objects.filter(id=metrica_prod.id).update(vistas=models.F('vistas') + 1)

    return render(request, "producto_detail.html", {
        "producto": producto,
        "resenas": resenas,
        "resena_form": resena_form,
    })


def producto_detail_by_id(request, id):
    producto = get_object_or_404(Producto, id=id)
    if producto.slug:
        return redirect(producto.get_absolute_url(), permanent=True)
        
    from django.utils import timezone
    hoy = timezone.localdate()
    metrica_prod, created = MetricaProducto.objects.get_or_create(producto=producto, fecha=hoy)
    MetricaProducto.objects.filter(id=metrica_prod.id).update(vistas=models.F('vistas') + 1)

    return render(request, "producto_detail.html", {
        "producto": producto
    })


def blog_list(request):
    posts_list = BlogPost.objects.filter(publicado=True)
    paginator = Paginator(posts_list, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, "blog/blog_list.html", {"page_obj": page_obj})


def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, publicado=True)
    otros_posts = BlogPost.objects.filter(publicado=True).exclude(id=post.id)[:3]
    productos_destacados = Producto.objects.filter(disponible=True).order_by('?')[:4]
    return render(request, "blog/blog_detail.html", {
        "post": post,
        "otros_posts": otros_posts,
        "productos_destacados": productos_destacados,
    })


def evaluar_compra(request, token):
    pedido = get_object_or_404(Pedido, token_resena=token)
    items = pedido.items.select_related('producto').all()
    
    if request.method == 'POST':
        resenas_creadas = 0
        for item in items:
            prod_id = item.producto.id
            calif_key = f"calificacion_{prod_id}"
            coment_key = f"comentario_{prod_id}"
            
            if calif_key in request.POST:
                try:
                    calificacion = int(request.POST.get(calif_key, 5))
                except ValueError:
                    calificacion = 5
                comentario = request.POST.get(coment_key, '').strip()
                
                if comentario:
                    ResenaProducto.objects.create(
                        producto=item.producto,
                        pedido=pedido,
                        nombre_cliente=pedido.nombre_completo,
                        email_cliente=pedido.email,
                        calificacion=calificacion,
                        comentario=comentario,
                        comprador_verificado=True,
                        aprobado=True
                    )
                    resenas_creadas += 1

        if resenas_creadas > 0:
            return render(request, "evaluaciones/evaluar_exito.html", {"pedido": pedido, "resenas_creadas": resenas_creadas})
        else:
            messages.warning(request, "Por favor escribe al menos un comentario en tu calificación.")

    return render(request, "evaluaciones/evaluar_compra.html", {"pedido": pedido, "items": items})


def evaluar_producto_directo(request, id):
    producto = get_object_or_404(Producto, id=id)
    
    if request.method == 'POST':
        nombre_cliente = request.POST.get('nombre_cliente', '').strip()
        email_cliente = request.POST.get('email_cliente', '').strip()
        try:
            calificacion = int(request.POST.get('calificacion', 5))
        except ValueError:
            calificacion = 5
        comentario = request.POST.get('comentario', '').strip()
        
        if nombre_cliente and comentario:
            ResenaProducto.objects.create(
                producto=producto,
                nombre_cliente=nombre_cliente,
                email_cliente=email_cliente,
                calificacion=calificacion,
                comentario=comentario,
                comprador_verificado=True,
                aprobado=True
            )
            return render(request, "evaluaciones/evaluar_producto_exito.html", {"producto": producto, "nombre_cliente": nombre_cliente})
        else:
            messages.warning(request, "Por favor completa tu nombre y comentario.")

    return render(request, "evaluaciones/evaluar_producto_directo.html", {"producto": producto})


def agregar_resena(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        form = ResenaForm(request.POST)
        if form.is_valid():
            resena = form.save(commit=False)
            resena.producto = producto
            resena.save()
            messages.success(request, "¡Gracias por tu reseña! Ha sido publicada.")
        else:
            messages.error(request, "Por favor revisa los campos ingresados en tu reseña.")
    return redirect(producto.get_absolute_url())


@require_GET
def api_destacados_random(request):
    import random
    badges_pool = ['✨ Recomendado', '🔥 Tendencia', '🌟 Selección Rara', '🌿 Favorito', '🎨 Arte Local', '🦉 Novedad Rara', '💖 Destacado', '⭐ Recomendación']
    random.shuffle(badges_pool)
    productos = Producto.objects.filter(disponible=True).order_by('?')[:8]
    
    data = []
    for idx, p in enumerate(productos):
        data.append({
            'id': p.id,
            'nombre': p.nombre,
            'precio': f"{p.precio:,}".replace(',', '.'),
            'url': p.get_absolute_url(),
            'imagen': p.get_imagen_url_absoluta,
            'badge': badges_pool[idx % len(badges_pool)]
        })
    return JsonResponse({'productos': data})
