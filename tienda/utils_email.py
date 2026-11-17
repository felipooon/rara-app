import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def formatear_clp(monto):
    """Auxiliar para formatear números como CLP en texto plano."""
    try:
        val = int(monto or 0)
        return f"${val:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return f"${monto}"


def generar_mensaje_texto_plano(pedido, items):
    """Genera una versión en texto plano clara y completa del pedido."""
    lineas_items = []
    for item in items:
        lineas_items.append(f"- {item.cantidad}x {item.producto.nombre} ({formatear_clp(item.precio)} c/u) = {formatear_clp(item.get_costo())}")

    texto_items = "\n".join(lineas_items)

    if pedido.tipo_entrega == 'PUNTO_BLUE':
        info_entrega = (
            f"Modalidad: Punto Blue Express / Copec\n"
            f"Punto: {pedido.punto_blue_nombre}\n"
            f"Dirección: {pedido.punto_blue_direccion}\n"
            f"Comuna/Región: {pedido.ciudad} ({pedido.region})"
        )
    else:
        info_entrega = (
            f"Modalidad: {pedido.get_tipo_entrega_display()}\n"
            f"Dirección: {pedido.direccion}\n"
            f"Comuna/Región: {pedido.ciudad} ({pedido.region})"
        )

    descuento_txt = ""
    if pedido.descuento_aplicado > 0:
        descuento_txt = f"\nDescuento Cupón: -{formatear_clp(pedido.descuento_aplicado)}"

    costo_envio_txt = "GRATIS" if (pedido.costo_envio or 0) == 0 else formatear_clp(pedido.costo_envio)

    return f"""¡Hola {pedido.nombre_completo}!

Hemos recibido el pago de tu compra con éxito a través de Mercado Pago. ¡Muchas gracias por tu pedido en Rara Tienda! 🦉✨

--------------------------------------------------
RESUMEN DE TU ORDEN #{pedido.codigo_orden}
--------------------------------------------------
Fecha: {pedido.fecha_creacion.strftime('%d/%m/%Y %H:%M') if pedido.fecha_creacion else 'Hoy'}

PRODUCTOS:
{texto_items}

Subtotal Productos: {formatear_clp(pedido.get_total_cost())}{descuento_txt}
Envío Blue Express: {costo_envio_txt}
TOTAL PAGADO: {formatear_clp(pedido.get_total_final())}

--------------------------------------------------
DATOS DE DESPACHO:
--------------------------------------------------
{info_entrega}

¿QUÉ VIENE AHORA?
Estamos preparando tu paquete con mucho cuidado en nuestro taller. Apenas Blue Express retire el envío, te contactaremos por WhatsApp al +56{pedido.telefono} para compartirte el comprobante y el número de seguimiento.

¿Tienes dudas? Escríbenos directamente a nuestro WhatsApp: +56 9 3002 7170
Web: https://www.raratienda.cl/
Instagram: @lararatienda

¡Gracias por tu compra!
El equipo de Rara Tienda.
"""


def enviar_correo_confirmacion_compra(pedido):
    """
    Envía el correo enriquecido en HTML (con respaldo en texto plano)
    al cliente una vez confirmado el pago de su pedido.
    """
    if not pedido.email:
        logger.warning(f"Pedido #{pedido.id} no tiene correo de cliente registrado.")
        return False, "Sin correo de destino"

    items = list(pedido.items.select_related('producto').all())

    asunto = f"¡Pago Confirmado! Tu pedido #{pedido.codigo_orden} está en camino 🦉 — Rara Tienda"

    context = {
        'pedido': pedido,
        'items': items,
        'subtotal': pedido.get_total_cost(),
        'descuento': pedido.descuento_aplicado,
        'costo_envio': pedido.costo_envio,
        'total': pedido.get_total_final(),
    }

    try:
        html_content = render_to_string('emails/confirmacion_compra.html', context)
        plain_content = generar_mensaje_texto_plano(pedido, items)

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Rara Tienda <contacto@raratienda.cl>')

        send_mail(
            subject=asunto,
            message=plain_content,
            from_email=from_email,
            recipient_list=[pedido.email],
            html_message=html_content,
            fail_silently=False,
        )
        logger.info(f"✅ Correo HTML de confirmación enviado exitosamente a {pedido.email} para pedido #{pedido.codigo_orden}")
        return True, "Enviado con éxito"
    except Exception as e:
        logger.error(f"❌ Error al enviar correo de confirmación a {pedido.email} para pedido #{pedido.codigo_orden}: {e}", exc_info=True)
        return False, str(e)


def enviar_alerta_nuevo_pedido_admin(pedido):
    """
    Envía una alerta HTML enriquecida al correo del administrador cuando se
    registra un nuevo pedido en la tienda.
    """
    admin_email = getattr(settings, 'EMAIL_HOST_USER', None)
    if not admin_email:
        return False, "EMAIL_HOST_USER no configurado"

    items = list(pedido.items.select_related('producto').all())
    subtotal = pedido.get_total_cost()
    descuento = pedido.descuento_aplicado or 0
    costo_envio = pedido.costo_envio or 0
    total = pedido.get_total_final()

    asunto = f"🚨 NUEVO PEDIDO RARATIENDA #{pedido.codigo_orden} — {pedido.nombre_completo}"

    lineas_items = "\n".join(
        f"- {item.cantidad}x {item.producto.nombre} ({formatear_clp(item.precio)}) = {formatear_clp(item.get_costo())}"
        for item in items
    )

    plain_content = f"""¡Atención! Acaba de entrar un nuevo pedido.

Orden: #{pedido.codigo_orden}
Cliente: {pedido.nombre_completo} ({pedido.rut})
Email: {pedido.email}
Teléfono: +56{pedido.telefono}
Modalidad de Envío: {pedido.get_tipo_entrega_display()}
Destino: {pedido.punto_blue_nombre or pedido.direccion}, {pedido.ciudad} ({pedido.region})

PRODUCTOS:
{lineas_items}

Subtotal Productos: {formatear_clp(subtotal)}
Envío Blue Express (Talla {pedido.talla_envio}): {formatear_clp(costo_envio)}
Total Final: {formatear_clp(total)}

Ver pedido en el panel:
https://www.raratienda.cl/panel/pedidos/{pedido.id}/
"""

    context = {
        'pedido': pedido,
        'items': items,
        'subtotal': subtotal,
        'descuento': descuento,
        'costo_envio': costo_envio,
        'total': total,
    }

    try:
        html_content = render_to_string('emails/alerta_nuevo_pedido_admin.html', context)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Rara Tienda <contacto@raratienda.cl>')

        send_mail(
            subject=asunto,
            message=plain_content,
            from_email=from_email,
            recipient_list=[admin_email],
            html_message=html_content,
            fail_silently=True,
        )
        return True, "Alerta enviada"
    except Exception as e:
        logger.error(f"Error silencioso al enviar alerta de pedido: {e}", exc_info=True)
        return False, str(e)

