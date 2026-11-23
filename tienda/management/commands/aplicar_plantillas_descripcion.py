import csv
import json
from collections import Counter
from django.core.management.base import BaseCommand
from django.db import transaction

from tienda.models import Producto
from tienda.plantillas_descripcion import (
    aplicar_plantilla_a_producto,
    es_descripcion_completa_protegida,
)


class Command(BaseCommand):
    help = (
        "Aplica plantillas de descripción por categoría/subtipo a productos con "
        "descripción faltante o incompleta, omitiendo líneas con datos faltantes "
        "para no dejar corchetes visibles en la tienda."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra vista previa de cambios sin modificar la base de datos (comportamiento por defecto si no se pasa --apply).',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Guarda los cambios en la base de datos.',
        )
        parser.add_argument(
            '--categoria',
            type=str,
            default='',
            help='Filtrar solo productos de una categoría (coincidencia parcial).',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Sobrescribir incluso descripciones completas protegidas (libros, guías, Cachañando, paño microfibra).',
        )
        parser.add_argument(
            '--export',
            type=str,
            default='',
            help='Ruta opcional para exportar la vista previa en formato .json o .csv.',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        dry_run = options['dry_run'] or not apply_changes
        categoria_filtro = (options['categoria'] or '').strip()
        force = options['force']
        export_path = (options['export'] or '').strip()

        qs = Producto.objects.select_related('categoria').all().order_by('categoria__nombre', 'nombre')
        if categoria_filtro:
            qs = qs.filter(categoria__nombre__icontains=categoria_filtro)

        actualizados = []
        protegidos = []
        sin_plantilla = []
        con_placeholders_omitidos = []
        resumen_cat = Counter()

        for prod in qs:
            cat_nombre = prod.categoria.nombre if prod.categoria else 'Sin categoría'

            if not force and es_descripcion_completa_protegida(prod):
                protegidos.append((prod.id, prod.nombre, cat_nombre))
                continue

            nueva_desc, faltantes, tpl_key = aplicar_plantilla_a_producto(
                prod,
                omitir_lineas_con_placeholders=True,
            )

            if not tpl_key:
                sin_plantilla.append((prod.id, prod.nombre, cat_nombre))
                continue

            desc_anterior = (prod.descripcion or '').strip()
            if nueva_desc.strip() == desc_anterior:
                continue

            resumen_cat[cat_nombre] += 1
            registro = {
                'id': prod.id,
                'nombre': prod.nombre,
                'categoria': cat_nombre,
                'precio': prod.precio_actual,
                'plantilla': tpl_key,
                'descripcion_anterior': desc_anterior,
                'descripcion_nueva': nueva_desc,
                'placeholders_omitidos': faltantes,
            }
            actualizados.append((prod, registro))
            if faltantes:
                con_placeholders_omitidos.append(registro)

        modo_label = 'DRY-RUN (sin cambios en BD)' if dry_run else 'APPLY (guardado en BD)'
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {modo_label} ==="))
        self.stdout.write(f"Total evaluados: {qs.count()}")
        self.stdout.write(f"A actualizar: {len(actualizados)}")
        self.stdout.write(f"Protegidos (descripción completa): {len(protegidos)}")
        self.stdout.write(f"Sin plantilla asignada: {len(sin_plantilla)}")
        self.stdout.write(f"Con campos omitidos por falta de datos: {len(con_placeholders_omitidos)}")

        if resumen_cat:
            self.stdout.write("\nPor categoría a actualizar:")
            for cat, cnt in sorted(resumen_cat.items()):
                self.stdout.write(f"  - {cat}: {cnt}")

        if actualizados:
            self.stdout.write("\nMuestra de cambios (primeros 5):")
            for _, reg in actualizados[:5]:
                self.stdout.write(f"\n  [{reg['id']}] {reg['nombre']} ({reg['categoria']} | {reg['plantilla']})")
                self.stdout.write(f"    ANTES: {reg['descripcion_anterior']!r}")
                self.stdout.write(f"    NUEVA:\n      " + reg['descripcion_nueva'].replace('\n', '\n      '))
                if reg['placeholders_omitidos']:
                    self.stdout.write(self.style.WARNING(f"    OMITIDOS (completar luego): {', '.join(reg['placeholders_omitidos'])}"))

        if con_placeholders_omitidos:
            self.stdout.write(self.style.WARNING(
                f"\nProductos con datos faltantes omitidos ({len(con_placeholders_omitidos)}):"
            ))
            for reg in con_placeholders_omitidos:
                self.stdout.write(
                    f"  - [{reg['id']}] {reg['nombre']} ({reg['categoria']}) -> faltan: {', '.join(reg['placeholders_omitidos'])}"
                )

        if export_path:
            registros = [reg for _, reg in actualizados]
            if export_path.lower().endswith('.csv'):
                with open(export_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=[
                            'id', 'nombre', 'categoria', 'precio', 'plantilla',
                            'placeholders_omitidos', 'descripcion_anterior', 'descripcion_nueva',
                        ],
                    )
                    writer.writeheader()
                    for reg in registros:
                        row = dict(reg)
                        row['placeholders_omitidos'] = ', '.join(reg['placeholders_omitidos'])
                        writer.writerow(row)
            else:
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(registros, f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"\nVista previa exportada en: {export_path}"))

        if not dry_run and actualizados:
            with transaction.atomic():
                for prod, reg in actualizados:
                    prod.descripcion = reg['descripcion_nueva']
                    prod.save(update_fields=['descripcion'])
            self.stdout.write(self.style.SUCCESS(f"\n✅ Se actualizaron {len(actualizados)} productos en la base de datos."))
        elif dry_run:
            self.stdout.write(self.style.NOTICE("\nModo --dry-run activo: no se modificó la base de datos. Usa --apply para guardar."))

