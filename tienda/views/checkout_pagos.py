import json
import re
import mercadopago
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db import transaction

from ..models import Producto, Pedido, ItemPedido, Cupon, LogProducto, LogPedido
from ..carrito import Carrito
from ..utils_email import enviar_correo_confirmacion_compra, enviar_alerta_nuevo_pedido_admin
from ..comunas_chile import (
    ORIGEN_TIENDA_COMUNA,
    ORIGEN_TIENDA_REGION,
    MONTO_MINIMO_ENTREGA_PRESENCIAL_GRATIS,
    COSTO_ENTREGA_PRESENCIAL_REDUCIDO,
    REGIONES_Y_COMUNAS,
    cargar_tarifas,
    cargar_puntos_lista,
    obtener_fecha_puntos,
    obtener_region_de_comuna,
    validar_comuna_existe,
    obtener_punto_blue_por_id,
    calcular_costo_envio,
    calcular_envio_detalle,
    detectar_comuna_por_ip_o_coords,
)


def api_blue_express_data(request):
    """Retorna comunas, regiones, tarifario y listado de Puntos Blue Express activos."""
    tarifas = cargar_tarifas()
    puntos = cargar_puntos_lista()
    return JsonResponse(
        {
            "origen_tienda_comuna": ORIGEN_TIENDA_COMUNA,
            "origen_tienda_region": ORIGEN_TIENDA_REGION,
            "regiones_y_comunas": REGIONES_Y_COMUNAS,
            "tarifas": tarifas,
            "puntos": puntos,
            "total_puntos": len(puntos),
            "updated_at": obtener_fecha_puntos(),
        }
    )


def api_blue_express_geolocalizar(request):
    """
    Autodetecta la comuna y el Punto Blue Express más cercano usando:
    - Coordenadas GPS (?lat=...&lng=...) enviadas por el navegador, o
    - La IP del cliente (o del servidor en desarrollo local).
    """
    lat = request.GET.get("lat")
    lng = request.GET.get("lng")
    city_hint = request.GET.get("city")

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "")

    res = detectar_comuna_por_ip_o_coords(ip=ip, lat=lat, lng=lng, city_hint=city_hint)
    return JsonResponse(res)


@csrf_exempt
def api_blue_express_calcular(request):
    """Calcula el costo de envío entre origen y destino según peso/talla y modalidad."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
        res = calcular_envio_detalle(
            origen_comuna=payload.get("origen_comuna", ORIGEN_TIENDA_COMUNA),
            destino_comuna=payload.get("destino_comuna", ORIGEN_TIENDA_COMUNA),
            origen_region=payload.get("origen_region"),
            destino_region=payload.get("destino_region"),
            peso_kg=payload.get("peso_kg", 0.4),
            talla=payload.get("talla"),
            tipo_entrega=payload.get("tipo_entrega", "PUNTO_BLUE"),
            punto_origen_id=payload.get("punto_origen_id"),
            punto_destino_id=payload.get("punto_destino_id"),
            total_carrito=payload.get("total_carrito", 0),
        )
        return JsonResponse(res)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)


def validar_rut_chileno(rut):
    rut_limpio = rut.replace(".", "").replace("-", "").replace(" ", "").upper()
    if not re.match(r'^\d{7,8}[0-9K]$', rut_limpio):
        return False
        
    cuerpo = rut_limpio[:-1]
    dv_ingresado = rut_limpio[-1]
    
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
        
    return dv_ingresado == dv_esperado


def obtener_descuento_cupon(request, total_carrito, carrito=None):
    codigo = request.session.get('cupon_codigo')
    if not codigo:
        return None, 0
    try:
        cupon = Cupon.objects.get(codigo__iexact=codigo)
        valido, _ = cupon.es_valido(total=total_carrito, carrito=carrito)
        if valido:
            descuento = cupon.calcular_descuento(total_carrito, carrito=carrito)
            return cupon, descuento
    except Cupon.DoesNotExist:
        pass
    return None, 0


def aplicar_cupon(request):
    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip().upper()
        if not codigo:
            messages.error(request, "Por favor ingresa un código de cupón.")
            return redirect('procesar_pedido')
        
        try:
            cupon = Cupon.objects.get(codigo__iexact=codigo)
            carrito = Carrito(request)
            total_carrito = carrito.get_total()
            valido, msg = cupon.es_valido(total=total_carrito, carrito=carrito)
            if not valido:
                messages.error(request, msg)
            else:
                request.session['cupon_codigo'] = cupon.codigo
                messages.success(request, f"¡Cupón '{cupon.codigo}' aplicado exitosamente!")
        except Cupon.DoesNotExist:
            messages.error(request, "El código de cupón ingresado no existe.")
            
    return redirect('procesar_pedido')


def quitar_cupon(request):
    if 'cupon_codigo' in request.session:
        del request.session['cupon_codigo']
        messages.info(request, "Cupón removido.")
    return redirect('procesar_pedido')


def _es_ajax_carrito(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _respuesta_carrito_ajax(request, carrito, message='', level='success', ok=True):
    drawer_html = render_to_string('includes/carrito_contenido.html', {'carrito': carrito}, request=request)
    return JsonResponse({
        'ok': ok,
        'message': message,
        'level': level,
        'total_items': carrito.total_items,
        'total': carrito.get_total(),
        'pack_info': carrito.info_pack_calcetines,
        'drawer_html': drawer_html,
    })


def agregar_al_carrito(request, producto_id):
    carrito = Carrito(request)
    producto = get_object_or_404(Producto, id=producto_id)

    try:
        cantidad = int(request.POST.get('cantidad', 1) if request.method == 'POST' else 1)
        if cantidad <= 0:
            if _es_ajax_carrito(request):
                return _respuesta_carrito_ajax(request, carrito, "La cantidad debe ser un número positivo.", level='error', ok=False)
            messages.error(request, "La cantidad debe ser un número positivo.")
            return redirect(request.META.get('HTTP_REFERER', '/'))
    except ValueError:
        if _es_ajax_carrito(request):
            return _respuesta_carrito_ajax(request, carrito, "Cantidad no válida.", level='error', ok=False)
        messages.error(request, "Cantidad no válida.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    if producto.hay_stock():
        agregado_exitosamente = carrito.agregar(producto, cantidad)
        if agregado_exitosamente:
            msg = f'¡{producto.nombre} agregado a tu nido! 🪹'
            level = 'success'
            if not _es_ajax_carrito(request):
                messages.success(request, msg)
        else:
            msg = f'¡Límite alcanzado! Solo nos quedan {producto.stock} unidades de {producto.nombre} en tu nido. 🪹'
            level = 'warning'
            if not _es_ajax_carrito(request):
                messages.warning(request, msg)
    else:
        msg = f'Lo sentimos, {producto.nombre} está agotado por ahora.'
        level = 'error'
        if not _es_ajax_carrito(request):
            messages.error(request, msg)
        if _es_ajax_carrito(request):
            return _respuesta_carrito_ajax(request, carrito, msg, level=level, ok=False)

    if _es_ajax_carrito(request):
        return _respuesta_carrito_ajax(request, carrito, msg, level=level, ok=True)

    url_anterior = request.META.get('HTTP_REFERER', '/')
    if '?' in url_anterior:
        return redirect(url_anterior + '&cart=open')
    else:
        return redirect(url_anterior + '?cart=open')


def ver_carrito(request):
    return redirect('/?cart=open')


def restar_del_carrito(request, producto_id):
    carrito = Carrito(request)
    producto = get_object_or_404(Producto, id=producto_id)
    carrito.restar(producto)
    if _es_ajax_carrito(request):
        return _respuesta_carrito_ajax(request, carrito, f'{producto.nombre} actualizado en tu nido.', level='info', ok=True)
    url_anterior = request.META.get('HTTP_REFERER', '/')
    if '?' in url_anterior:
        return redirect(url_anterior + '&cart=open')
    else:
        return redirect(url_anterior + '?cart=open')


def quitar_del_carrito(request, producto_id):
    carrito = Carrito(request)
    producto = get_object_or_404(Producto, id=producto_id)
    carrito.eliminar(producto)
    if _es_ajax_carrito(request):
        return _respuesta_carrito_ajax(request, carrito, f'{producto.nombre} quitado de tu nido.', level='info', ok=True)
    url_anterior = request.META.get('HTTP_REFERER', '/')
    if '?' in url_anterior:
        return redirect(url_anterior + '&cart=open')
    else:
        return redirect(url_anterior + '?cart=open')


def limpiar_carrito(request):
    carrito = Carrito(request)
    carrito.limpiar()
    return redirect('ver_carrito')


def procesar_pedido(request):
    carrito = Carrito(request)
    
    if len(carrito.carrito) == 0:
        messages.warning(request, "Tu nido está vacío. ¡Ve a pajarear al catálogo!")
        return redirect('index')
    
    for item_data in carrito:
        producto = item_data.get('producto_real')
        cantidad_pedida = item_data['cantidad']
        
        if not producto:
            messages.error(request, "Un producto de tu nido ya no está disponible.")
            return redirect('ver_carrito')
            
        if cantidad_pedida <= 0:
            messages.error(request, "Se detectó una cantidad inválida en tu nido. Por favor, revisa tus productos.")
            return redirect('ver_carrito')
            
        if cantidad_pedida > producto.stock:
            messages.warning(request, f"¡Atención! Mientras pensabas, el stock de '{producto.nombre}' bajó a {producto.stock} unidades. Por favor ajusta tu carrito.")
            return redirect('ver_carrito')

    total_bruto = carrito.get_total_bruto()
    pack_info = carrito.info_pack_calcetines
    descuento_pack = pack_info['descuento_pack']
    total_con_pack = max(0, total_bruto - descuento_pack)
    cupon_obj, descuento_cupon = obtener_descuento_cupon(request, total_con_pack, carrito=carrito)
    descuento_aplicado = descuento_pack + descuento_cupon
    subtotal_productos = max(0, total_bruto - descuento_aplicado)

    comuna_default = ORIGEN_TIENDA_COMUNA
    tipo_entrega_default = 'PUNTO_BLUE'
    talla_carrito = carrito.get_talla_envio()
    puntos_caja = carrito.puntos_caja
    costo_envio_inicial = calcular_costo_envio(
        comuna_default,
        total_carrito=subtotal_productos,
        tipo_entrega=tipo_entrega_default,
        origen_comuna=ORIGEN_TIENDA_COMUNA,
        talla=talla_carrito,
    )
    costo_retiro_actual = calcular_costo_envio(
        comuna_default,
        total_carrito=subtotal_productos,
        tipo_entrega='RETIRO',
    )
    falta_entrega_gratis = max(0, MONTO_MINIMO_ENTREGA_PRESENCIAL_GRATIS - subtotal_productos)
    porcentaje_entrega_gratis = (
        min(100, int(round((subtotal_productos / MONTO_MINIMO_ENTREGA_PRESENCIAL_GRATIS) * 100)))
        if subtotal_productos > 0
        else 0
    )
    total_final = subtotal_productos + costo_envio_inicial

    if request.method == 'POST':
        rut_ingresado = request.POST.get('rut', '')
        terminos_aceptados = request.POST.get('terminos_aceptados')
        ciudad_raw = request.POST.get('ciudad', comuna_default)
        comuna_canonica = validar_comuna_existe(ciudad_raw)
        tipo_entrega = request.POST.get('tipo_entrega', 'PUNTO_BLUE')
        if tipo_entrega not in ('PUNTO_BLUE', 'DOMICILIO', 'RETIRO'):
            tipo_entrega = 'PUNTO_BLUE'

        comuna_para_calculo = comuna_canonica or comuna_default
        costo_envio = calcular_costo_envio(
            comuna_para_calculo,
            total_carrito=subtotal_productos,
            tipo_entrega=tipo_entrega,
            origen_comuna=ORIGEN_TIENDA_COMUNA,
            talla=talla_carrito,
        )
        total_final = subtotal_productos + costo_envio

        base_context = {
            'carrito': carrito,
            'cupon': cupon_obj,
            'descuento': descuento_cupon,
            'descuento_pack': descuento_pack,
            'pack_info': pack_info,
            'subtotal_productos': subtotal_productos,
            'costo_envio': costo_envio,
            'costo_retiro_actual': costo_retiro_actual,
            'minimo_entrega_gratis': MONTO_MINIMO_ENTREGA_PRESENCIAL_GRATIS,
            'costo_entrega_reducido': COSTO_ENTREGA_PRESENCIAL_REDUCIDO,
            'falta_entrega_gratis': falta_entrega_gratis,
            'porcentaje_entrega_gratis': porcentaje_entrega_gratis,
            'talla_envio': talla_carrito,
            'puntos_caja': puntos_caja,
            'total_final': total_final,
            'origen_tienda': ORIGEN_TIENDA_COMUNA,
            'datos_previos': request.POST,
        }

        if not terminos_aceptados:
            base_context['error_terminos'] = "Debes aceptar los Términos y Condiciones y Políticas de Devolución para realizar tu pedido."
            return render(request, 'checkout.html', base_context)

        if not validar_rut_chileno(rut_ingresado):
            base_context['error_rut'] = "El RUT ingresado no es válido. Por favor, revísalo y escríbelo correctamente."
            return render(request, 'checkout.html', base_context)

        if tipo_entrega == 'RETIRO':
            ciudad_retiro = (request.POST.get('ciudad_retiro') or '').strip()
            if ciudad_retiro not in ('Puerto Montt', 'Puerto Varas'):
                ciudad_retiro = 'Puerto Montt'
            comuna_canonica = ciudad_retiro
        elif not comuna_canonica:
            base_context['error_envio'] = "Por favor selecciona una comuna válida del listado de Chile."
            return render(request, 'checkout.html', base_context)

        region_destino = obtener_region_de_comuna(comuna_canonica)
        punto_blue_id = None
        punto_blue_nombre = ''
        punto_blue_direccion = ''
        empresa_transporte = 'Blue Express'

        if tipo_entrega == 'PUNTO_BLUE':
            punto_obj = obtener_punto_blue_por_id(request.POST.get('punto_blue_id'))
            if not punto_obj:
                base_context['error_envio'] = "Por favor selecciona el Punto Blue Express / Copec donde retirarás tu pedido, o cambia la modalidad de entrega."
                return render(request, 'checkout.html', base_context)
            punto_blue_id = punto_obj.get('id')
            punto_blue_nombre = punto_obj.get('nombre', '')
            punto_blue_direccion = punto_obj.get('direccion_completa', '')
            direccion_guardar = f"Punto Blue: {punto_blue_nombre} ({punto_blue_direccion})"
        elif tipo_entrega == 'RETIRO':
            empresa_transporte = 'Reparto Local'
            nota_retiro = (request.POST.get('nota_retiro') or '').strip()
            direccion_guardar = (
                f"Reparto Local en {comuna_canonica}: {nota_retiro}"
                if nota_retiro
                else f"Reparto Local en {comuna_canonica} (A coordinar por WhatsApp)"
            )
        else:
            direccion_domicilio = (request.POST.get('direccion') or '').strip()
            if not direccion_domicilio:
                base_context['error_envio'] = "Por favor ingresa tu dirección exacta (calle y número) para el despacho a domicilio."
                return render(request, 'checkout.html', base_context)
            direccion_guardar = direccion_domicilio

        pedido = Pedido.objects.create(
            nombre_completo=request.POST.get('nombre_completo'),
            rut=rut_ingresado,
            email=request.POST.get('email'),
            telefono=request.POST.get('telefono'),
            direccion=direccion_guardar,
            ciudad=comuna_canonica,
            region=region_destino,
            tipo_entrega=tipo_entrega,
            punto_blue_id=punto_blue_id,
            punto_blue_nombre=punto_blue_nombre,
            punto_blue_direccion=punto_blue_direccion,
            talla_envio=talla_carrito if tipo_entrega != 'RETIRO' else '-',
            costo_envio=costo_envio,
            empresa_transporte=empresa_transporte,
            cupon=cupon_obj,
            descuento_aplicado=descuento_aplicado
        )
        
        if cupon_obj:
            cupon_obj.usos_actuales += 1
            cupon_obj.save()
            if 'cupon_codigo' in request.session:
                del request.session['cupon_codigo']

        request.session['pedido_autorizado'] = str(pedido.id)
        
        for item in carrito:
            ItemPedido.objects.create(
                pedido=pedido,
                producto=item['producto_real'],
                precio=item['precio'],
                cantidad=item['cantidad']
            )
            LogProducto.objects.create(
                producto_id=item['producto_real'].id,
                nombre_producto=item['producto_real'].nombre,
                accion='VENTA',
                detalles=f"Vendido {item['cantidad']} unidad(es) en Pedido #{pedido.codigo_orden} | Cliente: {pedido.nombre_completo} ({pedido.email})"
            )

        items_summary = ", ".join([f"{item['producto_real'].nombre} (x{item['cantidad']})" for item in carrito])
        if tipo_entrega == "PUNTO_BLUE":
            modalidad_label = "Punto Blue Express"
        elif tipo_entrega == "RETIRO":
            modalidad_label = "Reparto Local"
        else:
            modalidad_label = "Domicilio Blue Express"
        detalles_creacion = (
            f"Pedido iniciado por total ${total_final} (Productos: ${subtotal_productos} + Envío {modalidad_label}: ${costo_envio}) | "
            f"Ítems: {items_summary} | Destino: {pedido.direccion}, {pedido.ciudad} ({pedido.region}) | "
            f"RUT: {pedido.rut} | Teléfono: +56{pedido.telefono}"
        )
        if descuento_pack > 0:
            detalles_creacion += f" | Pack Calcetines ({pack_info['packs_completos']}x3: -${descuento_pack})"
        if cupon_obj:
            detalles_creacion += f" | Cupón: {cupon_obj.codigo} (-${descuento_cupon})"

        LogPedido.objects.create(
            pedido_id=pedido.id,
            codigo_orden=pedido.codigo_orden,
            cliente_nombre=pedido.nombre_completo,
            cliente_email=pedido.email,
            accion='CREACION',
            detalles=detalles_creacion
        )

        enviar_alerta_nuevo_pedido_admin(pedido)

        if not settings.MP_ACCESS_TOKEN:
            messages.info(request, "Entorno local: MERCADOPAGO_ACCESS_TOKEN no configurado en .env. Pedido registrado correctamente.")
            return redirect('pedido_confirmado', pedido_id=pedido.id)

        try:
            sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)

            items_mp = []
            for item in carrito:
                items_mp.append({
                    "title": item['producto_real'].nombre,
                    "quantity": int(item['cantidad']),
                    "unit_price": int(item['precio']),
                    "currency_id": "CLP"
                })

            if descuento_pack > 0:
                items_mp.append({
                    "title": f"Descuento Pack Calcetines ({pack_info['packs_completos']}x 3 pares por $15.990)",
                    "quantity": 1,
                    "unit_price": -int(descuento_pack),
                    "currency_id": "CLP"
                })

            if descuento_cupon > 0 and cupon_obj:
                items_mp.append({
                    "title": f"Descuento Cupón ({cupon_obj.codigo})",
                    "quantity": 1,
                    "unit_price": -int(descuento_cupon),
                    "currency_id": "CLP"
                })

            if costo_envio > 0:
                items_mp.append({
                    "title": f"Envío {modalidad_label} ({pedido.ciudad})",
                    "quantity": 1,
                    "unit_price": int(costo_envio),
                    "currency_id": "CLP"
                })

            url_exito = f"https://raratienda.cl/pedido-confirmado/{pedido.id}/"
            url_fallo = "https://raratienda.cl/?cart=open"
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
                "auto_return": "approved",
                "external_reference": str(pedido.id),
                "notification_url": url_webhook,
            }

            preference_response = sdk.preference().create(preference_data)

            print("\n=== RESPUESTA DE MERCADO PAGO ===")
            print(preference_response)
            print("=================================\n")

            if "init_point" not in preference_response.get("response", {}):
                LogPedido.objects.create(
                    pedido_id=pedido.id,
                    codigo_orden=pedido.codigo_orden,
                    cliente_nombre=pedido.nombre_completo,
                    cliente_email=pedido.email,
                    accion='ERROR',
                    detalles=f"Respuesta de MercadoPago sin init_point: {preference_response}"
                )
                messages.error(request, "Hubo un problema al contactar a la pasarela de pago. Por favor intenta de nuevo.")
                return redirect('ver_carrito')
            
            init_point = preference_response["response"]["init_point"]
            return redirect(init_point)
        except Exception as e:
            LogPedido.objects.create(
                pedido_id=pedido.id,
                codigo_orden=pedido.codigo_orden,
                cliente_nombre=pedido.nombre_completo,
                cliente_email=pedido.email,
                accion='ERROR',
                detalles=f"Excepción al conectar con Mercado Pago: {e}"
            )
            print(f"Error al conectar con Mercado Pago: {e}")
            messages.error(request, f"Error con la pasarela de pago: {e}")
            return redirect('pedido_confirmado', pedido_id=pedido.id)

    return render(request, 'checkout.html', {
        'carrito': carrito,
        'cupon': cupon_obj,
        'descuento': descuento_cupon,
        'descuento_pack': descuento_pack,
        'pack_info': pack_info,
        'subtotal_productos': subtotal_productos,
        'costo_envio': costo_envio_inicial,
        'costo_retiro_actual': costo_retiro_actual,
        'minimo_entrega_gratis': MONTO_MINIMO_ENTREGA_PRESENCIAL_GRATIS,
        'costo_entrega_reducido': COSTO_ENTREGA_PRESENCIAL_REDUCIDO,
        'falta_entrega_gratis': falta_entrega_gratis,
        'porcentaje_entrega_gratis': porcentaje_entrega_gratis,
        'talla_envio': talla_carrito,
        'puntos_caja': puntos_caja,
        'total_final': total_final,
        'origen_tienda': ORIGEN_TIENDA_COMUNA,
    })


def pedido_confirmado(request, pedido_id):
    pedido_autorizado = request.session.get('pedido_autorizado')
    if str(pedido_autorizado) != str(pedido_id):
        return redirect('index')

    pedido = get_object_or_404(Pedido, id=pedido_id)
    carrito = Carrito(request)
    carrito.limpiar()
    return render(request, 'pedido_confirmado.html', {'pedido': pedido})


@csrf_exempt
def webhook_mercadopago(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if data.get("type") == "payment" or data.get("action") == "payment.created":
                payment_id = data.get("data", {}).get("id")
                
                if payment_id:
                    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
                    payment_info = sdk.payment().get(payment_id)
                    payment = payment_info.get("response")
                    
                    if payment and payment.get("status") == "approved":
                        pedido_id = payment.get("external_reference")
                        
                        if pedido_id:
                            pago_procesado = False
                            pedido = None
                            with transaction.atomic():
                                pedido = Pedido.objects.select_for_update().filter(id=pedido_id).first()
                                if pedido and not pedido.pagado:
                                    pedido.confirmar_pago()
                                    pedido.id_transaccion = str(payment_id)
                                    pedido.save()
                                    pago_procesado = True
                            
                            if pago_procesado and pedido:
                                LogPedido.objects.create(
                                    pedido_id=pedido.id,
                                    codigo_orden=pedido.codigo_orden,
                                    cliente_nombre=pedido.nombre_completo,
                                    cliente_email=pedido.email,
                                    accion='PAGO_OK',
                                    detalles=f"Pago confirmado exitosamente por Webhook MercadoPago | ID Transacción MP: {payment_id}"
                                )
                                print(f"✅ ¡ÉXITO! Pedido #{pedido.id} pagado y stock descontado.")

                                ok_mail, msg_mail = enviar_correo_confirmacion_compra(pedido)
                                if ok_mail:
                                    print(f"✅ Webhook: Pago procesado y correo HTML enviado a {pedido.email}")
                                else:
                                    print(f"⚠️ Webhook: Pago OK pero falló el correo HTML a {pedido.email}: {msg_mail}")
                            elif pedido and pedido.pagado:
                                print(f"ℹ️ Webhook duplicado ignorado para pedido #{pedido.id}.")
                    elif payment and payment.get("status") != "approved":
                        pedido_id = payment.get("external_reference")
                        if pedido_id:
                            pedido_obj = Pedido.objects.filter(id=pedido_id).first()
                            if pedido_obj:
                                mp_status = payment.get("status")
                                accion_log = 'CANCELADO' if mp_status in ['cancelled', 'refunded'] else 'ERROR'
                                LogPedido.objects.create(
                                    pedido_id=pedido_obj.id,
                                    codigo_orden=pedido_obj.codigo_orden,
                                    cliente_nombre=pedido_obj.nombre_completo,
                                    cliente_email=pedido_obj.email,
                                    accion=accion_log,
                                    detalles=f"Notificación de Webhook MercadoPago | Estado MP: '{mp_status}' | Detalle MP: '{payment.get('status_detail', 'Sin detalle')}' | ID Transacción MP: {payment_id}"
                                )

            return JsonResponse({"status": "ok"}, status=200)

        except Exception as e:
            print(f"❌ Error en Webhook: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    return JsonResponse({"status": "method not allowed"}, status=405)
