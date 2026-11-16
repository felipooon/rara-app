from django.core.management.base import BaseCommand
from tienda.comunas_chile import actualizar_puntos_desde_api


class Command(BaseCommand):
    help = 'Descarga y actualiza el catálogo local de Puntos Blue Express (Copec y Pick-up)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Descargando catálogo oficial de Puntos Blue Express..."))
        try:
            res = actualizar_puntos_desde_api()
            self.stdout.write(
                self.style.SUCCESS(
                    f"¡Éxito! Total activos: {res['total_nuevo']} "
                    f"(+{res['nuevos_count']} nuevos, -{res['eliminados_count']} eliminados)."
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error descargando datos de Blue Express: {e}"))

