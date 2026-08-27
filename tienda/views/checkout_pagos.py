import json
import re
import mercadopago
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db import transaction

from ..models import Producto, Pedido, ItemPedido, Cupon, LogProducto, LogPedido
from ..carrito import Carrito


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


def obtener_descuento_cupon(request, total_carrito):
    codigo = request.session.get('cupon_codigo')
    if not codigo:
        return None, 0
    try:
        cupon = Cupon.objects.get(codigo__iexact=codigo)
        valido, _ = cupon.es_valido()
        if valido:
            descuento = cupon.calcular_descuento(total_carrito)
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
            valido, msg = cupon.es_valido()
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


def agregar_al_carrito(request, producto_id):
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
    
    cantidad = int(request.POST.get('cantidad', 1) if request.method == 'POST' else 1)

    if producto.hay_stock():
        agregado_exitosamente = carrito.agregar(producto, cantidad)
        if agregado_exitosamente:
            messages.success(request, f'¡{producto.nombre} agregado a tu nido! 🪹')
        else:
            messages.warning(request, f'¡Límite alcanzado! Solo nos quedan {producto.stock} unidades de {producto.nombre} y ya están en tu nido. 🪹')
    else:
        messages.error(request, f'Lo sentimos, {producto.nombre} está agotado por ahora.')
        
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
    url_anterior = request.META.get('HTTP_REFERER', '/')
    if '?' in url_anterior:
        return redirect(url_anterior + '&cart=open')
    else:
        return redirect(url_anterior + '?cart=open')


def quitar_del_carrito(request, producto_id):
    carrito = Carrito(request)
    producto = get_object_or_404(Producto, id=producto_id)
    carrito.eliminar(producto)
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

    total_bruto = carrito.get_total()
    cupon_obj, descuento_aplicado = obtener_descuento_cupon(request, total_bruto)
    total_final = max(0, total_bruto - descuento_aplicado)

    if request.method == 'POST':
        rut_ingresado = request.POST.get('rut', '')
        terminos_aceptados = request.POST.get('terminos_aceptados')

        if not terminos_aceptados:
            context = {
                'carrito': carrito,
                'cupon': cupon_obj,
                'descuento': descuento_aplicado,
                'total_final': total_final,
                'error_terminos': "Debes aceptar los Términos y Condiciones y Políticas de Devolución para realizar tu pedido.",
                'datos_previos': request.POST
            }
            return render(request, 'checkout.html', context)

        if not validar_rut_chileno(rut_ingresado):
            context = {
                'carrito': carrito,
                'cupon': cupon_obj,
                'descuento': descuento_aplicado,
                'total_final': total_final,
                'error_rut': "El RUT ingresado no es válido. Por favor, revísalo y escríbelo correctamente.",
                'datos_previos': request.POST
            }
            return render(request, 'checkout.html', context)

        pedido = Pedido.objects.create(
            nombre_completo=request.POST.get('nombre_completo'),
            rut=rut_ingresado,
            email=request.POST.get('email'),
            telefono=request.POST.get('telefono'),
            direccion=request.POST.get('direccion'),
            ciudad=request.POST.get('ciudad', 'Puerto Montt'),
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
        detalles_creacion = f"Pedido iniciado por total ${total_final} | Ítems: {items_summary} | Dirección: {pedido.direccion}, {pedido.ciudad} | RUT: {pedido.rut} | Teléfono: +56{pedido.telefono}"
        if cupon_obj:
            detalles_creacion += f" | Cupón: {cupon_obj.codigo} (-${descuento_aplicado})"

        LogPedido.objects.create(
            pedido_id=pedido.id,
            codigo_orden=pedido.codigo_orden,
            cliente_nombre=pedido.nombre_completo,
            cliente_email=pedido.email,
            accion='CREACION',
            detalles=detalles_creacion
        )

        if getattr(settings, 'EMAIL_HOST_USER', None):
            try:
                asunto_admin = f"🚨 NUEVO PEDIDO RARATIENDA#{pedido.codigo_orden} - {pedido.nombre_completo}"
                mensaje_admin = f"""¡Atención! Acaba de entrar un nuevo pedido.

Cliente: {pedido.nombre_completo}
Ciudad: {pedido.ciudad}
Total: ${total_final}
Teléfono: +56{pedido.telefono}

Revisa el panel de administración para ver el detalle completo.
www.raratienda.cl/panel
"""
                send_mail(
                    asunto_admin,
                    mensaje_admin,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.EMAIL_HOST_USER],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Error silencioso al enviar alerta de pedido: {e}")

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

            if descuento_aplicado > 0 and cupon_obj:
                items_mp.append({
                    "title": f"Descuento Cupón ({cupon_obj.codigo})",
                    "quantity": 1,
                    "unit_price": -int(descuento_aplicado),
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
        'descuento': descuento_aplicado,
        'total_final': total_final
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
                                    print(f"⚠️ Webhook: Pago OK pero falló el correo: {mail_error}")
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
