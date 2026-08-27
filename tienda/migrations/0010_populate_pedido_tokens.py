import uuid
from django.db import migrations

def populate_tokens(apps, schema_editor):
    Pedido = apps.get_model('tienda', 'Pedido')
    for p in Pedido.objects.all():
        p.token_resena = uuid.uuid4()
        p.save()

class Migration(migrations.Migration):
    dependencies = [
        ('tienda', '0009_pedido_token_resena_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_tokens, reverse_code=migrations.RunPython.noop),
    ]
