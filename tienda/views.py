import os
import json
import requests
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect
from .models import Categoria, Producto, Pedido, ItemPedido
from .forms import CategoriaForm, ProductoForm
from django.contrib.auth.views import LoginView
from .carrito import Carrito
from django.contrib import messages
from django.core.mail import send_mail
import mercadopago
from django.conf import settings
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.core.cache import cache
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
import re

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
    categoria = get_object_or_404(Categoria, slug=slug)

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

    try:
        cantidad = int(request.POST.get('cantidad', 1))
        if cantidad <= 0:
            messages.error(request, "La cantidad debe ser un número positivo.")
            return redirect(request.META.get('HTTP_REFERER', '/'))
    except ValueError:
        messages.error(request, "Cantidad no válida.")
        return redirect(request.META.get('HTTP_REFERER', '/'))
    
    # Opcional: si en el futuro agregas un input para elegir cantidad, lo lee aquí. Si no, usa 1.
    cantidad = int(request.POST.get('cantidad', 1) if request.method == 'POST' else 1)

    # 2. Verificamos si el producto tiene stock en absoluto (tu validación original)
    if producto.hay_stock():
        
        # 3. Intentamos agregar al carrito. Esto nos devolverá True (éxito) o False (pasó el límite)
        agregado_exitosamente = carrito.agregar(producto, cantidad)
        
        if agregado_exitosamente:
            messages.success(request, f'¡{producto.nombre} agregado a tu nido! 🪹')
        else:
            # Si devuelve False, es porque el cliente intentó agregar más de lo que tienes
            messages.warning(request, f'¡Límite alcanzado! Solo nos quedan {producto.stock} unidades de {producto.nombre} y ya están en tu nido. 🪹')
            
    else:
        # Si el stock en la base de datos es 0
        messages.error(request, f'Lo sentimos, {producto.nombre} está agotado por ahora.')
        
    # Redirigimos al catálogo o donde estaba el usuario y abrimos el carrito
    url_anterior = request.META.get('HTTP_REFERER', '/')
    if '?' in url_anterior:
        return redirect(url_anterior + '&cart=open')
    else:
        return redirect(url_anterior + '?cart=open')


def ver_carrito(request):
    
    return redirect('/?cart=open')


def procesar_pedido(request):
    carrito = Carrito(request)
    
    # Seguridad: Si el carro está vacío, no los dejamos pasar
    if len(carrito.carrito) == 0:
        messages.warning(request, "Tu nido está vacío. ¡Ve a pajarear al catálogo!")
        return redirect('index')
    
    # --- 🛡️ LA ADUANA FINAL (Pre-Checkout) 🛡️ ---
    
    for item_id, item_data in carrito.carrito.items():
        # Buscamos el producto real en la base de datos para ver su stock actual
        producto = Producto.objects.filter(id=item_data['producto_id']).first()
        cantidad_pedida = item_data['cantidad']
        
        # 1. Validar que el producto siga existiendo
        if not producto:
            messages.error(request, "Un producto de tu nido ya no está disponible.")
            return redirect('ver_carrito') # Cambia a la url de tu carrito
            
        # 2. Validar el hackeo de números negativos o cero
        if cantidad_pedida <= 0:
            messages.error(request, "Se detectó una cantidad inválida en tu nido. Por favor, revisa tus productos.")
            return redirect('ver_carrito')
            
        # 3. Validar el "Efecto Black Friday" (El stock bajó antes de que pagara)
        if cantidad_pedida > producto.stock:
            messages.warning(request, f"¡Atención! Mientras pensabas, el stock de '{producto.nombre}' bajó a {producto.stock} unidades. Por favor ajusta tu carrito.")
            return redirect('ver_carrito')

    if request.method == 'POST':
        rut_ingresado = request.POST.get('rut', '')

        if not validar_rut_chileno(rut_ingresado):
            context = {
                'carrito': carrito,
                'error_rut': "El RUT ingresado no es válido. Por favor, revísalo y escríbelo correctamente.",
                'datos_previos': request.POST
            }
            return render(request, 'checkout.html', context)


        # 1. Capturamos los datos del cliente desde el formulario
        pedido = Pedido.objects.create(
            nombre_completo=request.POST.get('nombre_completo'),
            rut=rut_ingresado,
            email=request.POST.get('email'),
            telefono=request.POST.get('telefono'),
            direccion=request.POST.get('direccion'),
            ciudad=request.POST.get('ciudad', 'Puerto Montt') # Tu valor por defecto
        )
        
        # 2. método __iter__ en el carrito hace que esto sea súper fácil
        for item in carrito:
            ItemPedido.objects.create(
                pedido=pedido,
                producto=item['producto_real'],
                precio=item['precio'],
                cantidad=item['cantidad']
            )

    # ========================================================
        # 🚀 INICIO INTEGRACIÓN MERCADO PAGO
        # ========================================================
        sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)

        # Armamos la lista de productos tal como los pide Mercado Pago
        items_mp = []
        for item in carrito:
            items_mp.append({
                "title": item['producto_real'].nombre,
                "quantity": int(item['cantidad']),
                "unit_price": int(item['precio']),
                "currency_id": "CLP"
            })

        # Construimos la URL completa para que Mercado Pago sepa a dónde devolver al cliente
        # request.build_absolute_uri crea algo como "https://raratienda.cl/pedido/confirmado/5/"
        # 🚨 FORZAMOS HTTPS: Los tokens de producción exigen URLs reales
        url_exito = f"https://raratienda.cl/pedido-confirmado/{pedido.id}/"
        url_fallo = "https://raratienda.cl/?cart=open"  # <--- Lo devuelve al home y le abre el carrito automáticamente
        
        url_webhook = "https://raratienda.cl/webhook/mercadopago/"

        preference_data = {
            "items": items_mp,
            "payer": {
                "name": pedido.nombre_completo,
                "email": pedido.email,
            },
            "back_urls": {
                "success": url_exito,
                "failure": url_fallo,
                "pending": url_exito,
            },
            "auto_return": "approved", # Si paga bien, lo devuelve automáticamente a tu tienda
            "external_reference": str(pedido.id), # 🔑 CLAVE: Guardamos el ID de tu pedido en MP
            "notification_url": url_webhook,
        }

        preference_response = sdk.preference().create(preference_data)

        print("\n=== RESPUESTA DE MERCADO PAGO ===")
        print(preference_response)
        print("=================================\n")

        # Verificamos si Mercado Pago nos dio el init_point
        if "init_point" not in preference_response.get("response", {}):
            # Si no está, devolvemos al cliente al carrito y le avisamos
            messages.error(request, "Hubo un problema al contactar a la pasarela de pago. Por favor intenta de nuevo.")
            return redirect('ver_carrito') # Asegúrate de que este sea el nombre correcto de tu url de carrito
        
        init_point = preference_response["response"]["init_point"] # ¡Este es el link de pago!
        # ========================================================
        # FIN INTEGRACIÓN MERCADO PAGO
        # ========================================================


        # ========================================================
        # BLOQUE DE CORREO: SÓLO ALERTA PARA ADMINISTRADORES
        # ========================================================
        try:
            asunto_admin = f"🚨 NUEVO PEDIDO RARATIENDA#{pedido.codigo_orden} - {pedido.nombre_completo}"
            mensaje_admin = f"""¡Atención! Acaba de entrar un nuevo pedido.

Cliente: {pedido.nombre_completo}
Ciudad: {pedido.ciudad}
Total a transferir: ${carrito.get_total()}
Teléfono: +56{pedido.telefono}

Revisa el panel de administración para ver el detalle completo y coordinar el pago.

www.raratienda.cl/panel
"""
            send_mail(
                asunto_admin,
                mensaje_admin,
                settings.DEFAULT_FROM_EMAIL,
                [settings.EMAIL_HOST_USER], # Se envía al correo de la tienda (el tuyo)
                fail_silently=False,
            )

        except Exception as e:
            # Si hay un problema temporal con Gmail, la venta no se cae
            print(f"Error silencioso al enviar alerta de pedido: {e}")
        # ========================================================
        
        # 3. ¡Venta lista! Limpiamos la sesión usando el método
        #carrito.limpiar()
        
        #return redirect('pedido_confirmado', pedido_id=pedido.id)
        return redirect(init_point)

    return render(request, 'checkout.html', {'carrito': carrito})



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
    carrito = Carrito(request)
    carrito.limpiar()
    return render(request, 'pedido_confirmado.html', {'pedido': pedido})


def validar_rut_chileno(rut):
    """Limpia y valida un RUT chileno usando el algoritmo de Módulo 11."""
    # 1. Quitar puntos, guiones y espacios, dejar en mayúscula
    rut_limpio = rut.replace(".", "").replace("-", "").replace(" ", "").upper()
    
    # 2. Validar que tenga el largo correcto y solo números + K
    if not re.match(r'^\d{7,8}[0-9K]$', rut_limpio):
        return False
        
    # 3. Separar cuerpo del dígito verificador
    cuerpo = rut_limpio[:-1]
    dv_ingresado = rut_limpio[-1]
    
    # 4. Cálculo matemático (Módulo 11)
    suma = 0
    multiplo = 2
    for c in reversed(cuerpo):
        suma += int(c) * multiplo
        multiplo += 1
        if multiplo == 8:
            multiplo = 2
            
    resto = suma % 11
    dv_esperado = 11 - resto
    
    if dv_esperado == 11:
        dv_esperado = "0"
    elif dv_esperado == 10:
        dv_esperado = "K"
    else:
        dv_esperado = str(dv_esperado)
        
    # 5. Comparar si el cálculo coincide con el del cliente
    return dv_ingresado == dv_esperado

#-----------------------
#PANEL DE ADMINISTRACION
#-----------------------

@staff_member_required
def panel_productos(request):
    productos_list = Producto.objects.all().order_by('-id')

    # Capturamos los filtros actuales
    categoria_id = request.GET.get("categoria", "")
    estado = request.GET.get("estado", "")
    per_page = request.GET.get('per_page', '10') # Nuevo: cantidad por página

    # Aplicamos filtros
    if categoria_id:
        productos_list = productos_list.filter(categoria_id=categoria_id)

    if estado == "disponible":
        productos_list = productos_list.filter(disponible=True)
    elif estado == "agotado":
        productos_list = productos_list.filter(disponible=False)

    categorias = Categoria.objects.all()

    # Paginación usando la variable dinámica per_page
    paginator = Paginator(productos_list, int(per_page))
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "panel/productos.html", {
        "page_obj": page_obj,
        "categorias": categorias,
        # Devolvemos estas variables para que el HTML sepa qué hay filtrado
        "categoria_actual": categoria_id,
        "estado_actual": estado,
        "per_page": per_page
    })


@staff_member_required
def crear_producto(request):
    # 1. Capturamos la URL de retorno
    next_url = request.GET.get('next') or request.POST.get('next') or 'panel_productos'
    
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto creado exitosamente.")
            # 2. Redirigimos al estado anterior
            return redirect(next_url)
    else:
        form = ProductoForm()

    return render(request, "panel/producto_form.html", {
        "form": form,
        "next": next_url  # 3. Lo mandamos al template
    })


@staff_member_required
def crear_categoria(request):

    next_url = request.GET.get('next') or request.POST.get('next') or 'panel_productos'
    
    if request.method == 'POST':
        form = CategoriaForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoria creada exitosamente.")
            return redirect(next_url)
    
    else:
        form = CategoriaForm()

    return render(request, "panel/categoria_form.html", {
        "form": form,
        "next": next_url
    })


@staff_member_required
def toggle_producto(request, id):
    producto = get_object_or_404(Producto, id=id)
    # Cambiamos el estado (si es True pasa a False, y viceversa)
    producto.disponible = not producto.disponible
    producto.save()
    
    # Buscamos si hay una dirección de retorno
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    else:
        return redirect('panel_productos')


@staff_member_required
def panel_home(request):
    context = {
        'pedidos_pendientes': Pedido.objects.filter(pagado=False).count(),
        'pedidos_pagados': Pedido.objects.filter(pagado=True).count(),
        'productos_agotados': Producto.objects.filter(stock=0).count(),
        'ultimos_pedidos': Pedido.objects.all().order_by('-fecha_creacion')[:5], # Los 5 más recientes
    }
    return render(request, 'panel/dashboard.html', context)

class CustomLoginView(LoginView):
    template_name = "login.html"


@staff_member_required
def editar_producto(request, id):
    # 1. Buscamos el producto específico
    producto = get_object_or_404(Producto, id=id)
    
    # 2. Capturamos la URL de retorno 
    # Lo buscamos en GET al entrar, o en POST al enviar el formulario.
    next_url = request.GET.get('next') or request.POST.get('next') or 'panel_productos'
    
    # 3. Reutilizamos tu formulario
    form = ProductoForm(request.POST or None, request.FILES or None, instance=producto)
    
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"Producto '{producto.nombre}' actualizado.")
        # Redirigimos a la URL completa guardada (con sus filtros y página)
        return redirect(next_url)
        
    # 4. Usamos el mismo HTML que usaste para crear
    return render(request, "panel/producto_form.html", {
        "form": form,
        "editando": True,
        "next": next_url # Mandamos la URL al template
    })

@staff_member_required
def eliminar_producto(request, id):
    # Buscamos y destruimos
    producto = get_object_or_404(Producto, id=id)
    producto.delete()
    return redirect('panel_productos')

@staff_member_required
def panel_pedidos(request):
    # Traemos todos los pedidos, los más nuevos primero
    pedidos = Pedido.objects.all().order_by('-id')
    return render(request, 'panel/pedidos.html', {'pedidos': pedidos})

@staff_member_required
def detalle_pedido(request, id):
    # Buscamos el pedido y sus items relacionados
    pedido = get_object_or_404(Pedido, id=id)
    # Gracias al related_name='items' que pusiste en el modelo, 
    # podemos acceder a los productos así: pedido.items.all()
    return render(request, 'panel/detalle_pedido.html', {'pedido': pedido})


@staff_member_required
def confirmar_pago_pedido(request, id):
    pedido = get_object_or_404(Pedido, id=id)
    if request.method == 'POST':
        with transaction.atomic():
            pedido = Pedido.objects.select_for_update().get(id=id)
            if pedido.pagado:
                messages.info(request, f'El pedido #{pedido.codigo_orden} ya estaba pagado.')
                return redirect('detalle_pedido', id=pedido.id)
            # 1. Ejecutamos tu método maestro que descuenta el stock
            pedido.confirmar_pago()
        
        # 2. Armamos el mensaje para el cliente
        asunto = f'¡Pago Confirmado! Pedido #{pedido.codigo_orden} en Rara Tienda 🦉'
        mensaje = f'''Hola {pedido.nombre_completo},

¡Tenemos excelentes noticias! Hemos confirmado el pago de tu pedido.

Tu nido de productos ya está siendo preparado con mucho cariño para ser enviado a {pedido.direccion}, {pedido.ciudad}. 

Te avisaremos por esta misma vía en cuanto el paquete inicie su vuelo.

¡Gracias por apoyar el arte y la naturaleza!
El equipo de Rara Tienda.
'''
        
        # 3. Disparamos el correo
        try:
            send_mail(
                asunto, 
                mensaje, 
                settings.EMAIL_HOST_USER, # Tu correo configurado en settings
                [pedido.email], # El correo del cliente
                fail_silently=False
            )
            messages.success(request, f'Pago confirmado, stock actualizado y correo enviado a {pedido.email}.')
        except Exception as e:
            # Si el correo falla (ej. problemas de red), igual confirmamos el pago en la BD
            messages.warning(request, f'Pago confirmado y stock descontado, pero no se pudo enviar el correo automático.')
            print(f"Error SMTP: {e}")
            
    return redirect('detalle_pedido', id=pedido.id)


@staff_member_required
def exportar_stock_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stock Rara Tienda"

    # --- 1. DEFINIR NUESTROS ESTILOS ---
    # Fondo naranja (el color de tu tienda) y letra blanca para el encabezado
    fill_header = PatternFill(start_color="FCA311", end_color="FCA311", fill_type="solid")
    font_header = Font(name='Calibri', size=12, bold=True, color="FFFFFF")
    align_center = Alignment(horizontal="center", vertical="center")
    
    # Bordes sutiles para todas las celdas
    thin_border = Border(left=Side(style='thin', color='DDDDDD'),
                         right=Side(style='thin', color='DDDDDD'),
                         top=Side(style='thin', color='DDDDDD'),
                         bottom=Side(style='thin', color='DDDDDD'))

    # Colores dinámicos para el estado
    font_agotado = Font(color="E74C3C", bold=True)  # Rojo alerta
    font_disponible = Font(color="27AE60", bold=True) # Verde éxito

    # --- 2. CREAR Y PINTAR EL ENCABEZADO ---
    headers = ['ID', 'Producto', 'Stock Actual', 'Precio', 'Estado']
    ws.append(headers)
    
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = fill_header
        cell.font = font_header
        cell.alignment = align_center
        cell.border = thin_border

    # --- 3. AJUSTAR ANCHOS DE COLUMNA (Para que no se corte el texto) ---
    ws.column_dimensions['A'].width = 10  # ID
    ws.column_dimensions['B'].width = 35  # Nombre del Producto
    ws.column_dimensions['C'].width = 15  # Stock
    ws.column_dimensions['D'].width = 15  # Precio
    ws.column_dimensions['E'].width = 18  # Estado

    # --- 4. POBLAR DATOS CON FORMATO INTELIGENTE ---
    productos = Producto.objects.all().order_by('nombre')
    
    # start=2 porque la fila 1 ya la ocupó el encabezado
    for row_num, p in enumerate(productos, start=2): 
        estado = "Disponible" if p.stock > 0 else "Agotado"
        
        # Insertar la fila de datos (agregamos el signo $ al precio para que se vea mejor)
        ws.append([p.id, p.nombre, p.stock, f"${p.precio}", estado])
        
        # Aplicar diseño a esta nueva fila
        for col_num in range(1, 6):
            cell = ws.cell(row=row_num, column=col_num)
            cell.border = thin_border
            
            # Centrar ID, Stock, Precio y Estado
            if col_num in [1, 3, 4, 5]: 
                cell.alignment = align_center
                
            # Pintar la palabra "Agotado" de rojo y "Disponible" de verde
            if col_num == 5:
                cell.font = font_agotado if estado == "Agotado" else font_disponible

    # --- 5. ENVIAR EL ARCHIVO HERMOSEADO ---
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Inventario_Rara_Tienda.xlsx"'
    wb.save(response)
    return response

#---------------------
# RADAR BIG DAY
#---------------------

@require_GET
def ebird_proxy(request, ebird_path):
    """Proxy para eBird que inyecta la API Key en secreto, bloquea robos de código y cachea respuestas"""
    


    # 2. LÓGICA DE CACHÉ: Crear una llave única para esta consulta
    # Esto asegura que si se piden datos distintos (ej. otra región), se guarden por separado
    cache_key = f"ebird_{ebird_path}_{request.GET.urlencode()}"
    
    # 3. Revisar si la respuesta ya está en memoria
    datos_cacheados = cache.get(cache_key)
    if datos_cacheados:
        # Si está en caché, devolvemos el dato inmediatamente sin consultar a eBird
        return JsonResponse(datos_cacheados, safe=False)

    # 4. Si no hay caché, construimos la URL hacia eBird
    url = f"https://api.ebird.org/v2/{ebird_path}"
    
    # Inyectar la API Key desde las variables de entorno de Render
    headers = {"X-eBirdApiToken": settings.EBIRD_API_KEY}
    
    # Pasar los parámetros originales (como locale=es_CL)
    params = request.GET.dict()
    
    try:
        response_ebird = requests.get(url, headers=headers, params=params)
        response_ebird.raise_for_status()
        
        datos_nuevos = response_ebird.json()
        cache.set(cache_key, datos_nuevos, 300)
        
        # 2. Le decimos al navegador que confiamos en este origen
        response = JsonResponse(datos_nuevos, safe=False)
            
        return response
        
    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=500)
    

def get_species_dict(request):
    """Lee el diccionario local y lo devuelve como JSON puro con CORS público"""
    file_path = os.path.join(settings.BASE_DIR, 'tienda', 'species.json')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # 1. Guardamos la respuesta en una variable en vez de retornarla de inmediato
        response = JsonResponse(data, safe=False)
        
        # 2. Le pegamos la cabecera CORS universal
        response["Access-Control-Allow-Origin"] = "*"
        
        # 3. Ahora sí, devolvemos la respuesta
        return response
        
    except FileNotFoundError:
        return JsonResponse({"error": "Archivo no encontrado"}, status=404)
    
@csrf_exempt
def webhook_mercadopago(request):
    """
    Esta es la ruta secreta que Mercado Pago visitará por detrás 
    cuando un cliente pague con éxito.
    """
    if request.method == 'POST':
        try:
            # 1. Leemos el mensaje en formato JSON que envía MP
            data = json.loads(request.body)
            
            # 2. Verificamos si nos están avisando de un "pago"
            if data.get("type") == "payment" or data.get("action") == "payment.created":
                # Capturamos el ID del pago
                payment_id = data.get("data", {}).get("id")
                
                if payment_id:
                    # 3. Consultamos directamente a MP para confirmar que no sea un aviso falso (Seguridad)
                    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
                    payment_info = sdk.payment().get(payment_id)
                    payment = payment_info.get("response")
                    
                    # 4. Si MP nos confirma que el pago está APROBADO 🟢
                    if payment and payment.get("status") == "approved":
                        # Rescatamos el ID de tu pedido (el que enviamos al crear la preferencia)
                        pedido_id = payment.get("external_reference")
                        
                        if pedido_id:
                            pago_procesado = False
                            pedido = None
                            with transaction.atomic():
                                # 5. Buscamos el pedido en tu base de datos y bloqueamos fila para evitar doble proceso
                                pedido = Pedido.objects.select_for_update().filter(id=pedido_id).first()
                                # Si el pedido existe y aún no estaba pagado...
                                if pedido and not pedido.pagado:
                                    # ¡MAGIA! Ejecutamos tu súper función que descuenta stock
                                    pedido.confirmar_pago()
                                    
                                    # Guardamos el ID de transacción de MP por si hay devoluciones a futuro
                                    pedido.id_transaccion = str(payment_id)
                                    pedido.save()
                                    pago_procesado = True
                            
                            if pago_procesado and pedido:
                                print(f"✅ ¡ÉXITO! Pedido #{pedido.id} pagado y stock descontado.")

                                asunto = f'¡Pago Recibido! Tu pedido #{pedido.codigo_orden} está en camino 🦉'
                                mensaje = f'''¡Hola {pedido.nombre_completo}!

Te escribimos de Rara Tienda para contarte que hemos recibido el pago de tu pedido #{pedido.codigo_orden} con éxito a través de Mercado Pago. ✨

¿Qué viene ahora?
Estamos preparando tu paquete con mucho cuidado para que llegue perfecto a tu casa. 

📍 Destino: {pedido.direccion}, {pedido.ciudad}.

En cuanto realicemos el envío, te contactaremos por WhatsApp al +56{pedido.telefono} para enviarte el comprobante y el número de seguimiento.

¡Gracias por confiar en Rara Tienda y apoyar el arte local!

Un gran abrazo,
El equipo de Rara Tienda.
www.raratienda.cl
'''
                                try:
                                    send_mail(
                                        asunto,
                                        mensaje,
                                        settings.DEFAULT_FROM_EMAIL,
                                        [pedido.email],
                                        fail_silently=False,
                                    )
                                    print(f"✅ Webhook: Pago procesado y correo enviado a {pedido.email}")
                                except Exception as mail_error:
                                    # Si el correo falla, igual el pago ya quedó registrado
                                    print(f"⚠️ Webhook: Pago OK pero falló el correo: {mail_error}")
                            elif pedido and pedido.pagado:
                                print(f"ℹ️ Webhook duplicado ignorado para pedido #{pedido.id}.")

            # SIEMPRE debemos responder 200 OK, sino MP pensará que falló y enviará el aviso de nuevo
            return JsonResponse({"status": "ok"}, status=200)

        except Exception as e:
            print(f"❌ Error en Webhook: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    # Si alguien intenta entrar por la URL normal (GET), lo rechazamos
    return JsonResponse({"status": "method not allowed"}, status=405)