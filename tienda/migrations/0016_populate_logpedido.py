from django.db import migrations

def popular_pedidos_existentes(apps, schema_editor):
    Pedido = apps.get_model('tienda', 'Pedido')
    LogPedido = apps.get_model('tienda', 'LogPedido')

    for p in Pedido.objects.all():
        if not LogPedido.objects.filter(pedido_id=p.id, accion='CREACION').exists():
            codigo_fmt = f"{p.id:04d}"
            detalles_str = f"Registro inicial de pedido preexistente | Estado: {p.estado} | Pagado: {'Sí' if p.pagado else 'No'} | Ciudad: {p.ciudad}"
            if hasattr(p, 'numero_seguimiento') and p.numero_seguimiento:
                detalles_str += f" | Seguimiento: {getattr(p, 'empresa_transporte', '')} - {p.numero_seguimiento}"
            
            LogPedido.objects.create(
                pedido_id=p.id,
                codigo_orden=codigo_fmt,
                cliente_nombre=p.nombre_completo,
                cliente_email=p.email,
                accion='CREACION',
                detalles=detalles_str
            )

class Migration(migrations.Migration):

    dependencies = [
        ('tienda', '0015_alter_logproducto_accion_logpedido'),
    ]

    operations = [
        migrations.RunPython(popular_pedidos_existentes, reverse_code=migrations.RunPython.noop),
    ]
