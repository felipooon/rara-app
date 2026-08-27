from django.db import migrations

def popular_logs_existentes(apps, schema_editor):
    Producto = apps.get_model('tienda', 'Producto')
    LogProducto = apps.get_model('tienda', 'LogProducto')

    for prod in Producto.objects.all():
        if not LogProducto.objects.filter(producto_id=prod.id, accion='CREACION').exists():
            cat_nombre = prod.categoria.nombre if prod.categoria else 'Sin categoría'
            LogProducto.objects.create(
                producto_id=prod.id,
                nombre_producto=prod.nombre,
                accion='CREACION',
                detalles=f"Registro inicial de producto preexistente | Precio: ${prod.precio} | Stock: {prod.stock} | Categoría: {cat_nombre}"
            )

class Migration(migrations.Migration):

    dependencies = [
        ('tienda', '0013_logproducto'),
    ]

    operations = [
        migrations.RunPython(popular_logs_existentes, reverse_code=migrations.RunPython.noop),
    ]
