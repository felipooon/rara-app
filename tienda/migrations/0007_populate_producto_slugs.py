from django.db import migrations
from django.utils.text import slugify

def populate_slugs(apps, schema_editor):
    Producto = apps.get_model('tienda', 'Producto')
    for p in Producto.objects.all():
        if not p.slug:
            base_slug = slugify(p.nombre) or f"producto-{p.id}"
            candidate = base_slug
            counter = 1
            while Producto.objects.filter(slug=candidate).exclude(pk=p.pk).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            p.slug = candidate
            p.save()

class Migration(migrations.Migration):
    dependencies = [
        ('tienda', '0006_producto_slug'),
    ]

    operations = [
        migrations.RunPython(populate_slugs, reverse_code=migrations.RunPython.noop),
    ]
