import re

# Plantillas aprobadas de descripción por categoría y subtipo.
# Los placeholders entre corchetes ([...]) se rellenan con datos reales del producto
# cuando existen; en el comando masivo, las líneas con placeholders sin datos se omiten
# para que nunca queden corchetes visibles en la tienda.

PLANTILLAS_DESCRIPCION = [
    {
        'key': 'calcetines_algodon',
        'label': 'Calcetines — Algodón ($6.000)',
        'template': (
            "Calcetines suaves y cómodos con diseño de [ESPECIE_O_MOTIVO], ideales para el uso diario o salidas a terreno.\n"
            "- Talla: [TALLA]\n"
            "- Composición: 80% algodón, poliéster y spandex\n"
            "- Promoción: Participa en el Pack 3 calcetines por $15.990 (combinables entre diseños)\n"
            "Cuidado: lavar con agua fría y secar a la sombra para conservar los colores."
        ),
    },
    {
        'key': 'calcetines_digital',
        'label': 'Calcetines — Impresión digital ($3.000)',
        'template': (
            "Calcetines livianos con estampado full color de [ESPECIE_O_MOTIVO], pensados para uso urbano y regalo.\n"
            "- Talla: Talla única (37-45)\n"
            "- Composición: 95% poliéster, 5% elastano\n"
            "- Técnica: Impresión digital de alta definición\n"
            "Cuidado: lavar con agua fría; no usar secadora ni plancha."
        ),
    },
    {
        'key': 'pins_estandar',
        'label': 'Pins esmaltados — Estándar ($4.000)',
        'template': (
            "Pin metálico esmaltado con diseño de [ESPECIE_O_MOTIVO], ideal para mochilas, chaquetas, gorros o bolsos de terreno.\n"
            "- Material: Metal esmaltado\n"
            "- Medidas: [MEDIDA_CM]\n"
            "- Fijación: Broche de goma"
        ),
    },
    {
        'key': 'pins_especiales',
        'label': 'Pins esmaltados — Formato especial ($8.000)',
        'template': (
            "Pin metálico esmaltado de mayor detalle y formato inspirado en [ESPECIE_O_MOTIVO] de la fauna nativa de Chile.\n"
            "- Material y acabado: [MATERIAL_ACABADO]\n"
            "- Medidas: [MEDIDA_CM]\n"
            "- Fijación: Broche de goma"
        ),
    },
    {
        'key': 'pins_crocs',
        'label': 'Pins para crocs-bamers ($3.000)',
        'template': (
            "Set de 5 pines decorativos con temática de [TEMATICA], para personalizar calzado tipo Crocs o bamers.\n"
            "- Contenido: Set de 5 unidades\n"
            "- Material: [MATERIAL]\n"
            "- Compatibilidad: Orificios estándar de calzado tipo Crocs / bamers"
        ),
    },
    {
        'key': 'accesorios_arnes',
        'label': 'Accesorios birding — Arneses (Confección propia)',
        'template': (
            "Arnés ajustable diseñado para distribuir el peso de tus binoculares y evitar molestias en el cuello durante salidas largas.\n"
            "- Origen: Confección propia Rara Tienda\n"
            "- Material: [TIPO_ELASTICO] [DETALLE_ESPALDA]\n"
            "- Ajuste: Regulable para distintas contexturas y equipos\n"
            "Nota: [ACLARACION_IMAGEN_O_USO]"
        ),
    },
    {
        'key': 'accesorios_otro',
        'label': 'Accesorios birding — Correas y accesorios ópticos',
        'template': (
            "Accesorio práctico para proteger y transportar tu equipo óptico de observación de aves en terreno.\n"
            "- Compatibilidad: [COMPATIBILIDAD]\n"
            "- Material: [MATERIAL]\n"
            "- Medidas / Especificación: [MEDIDA_CM]"
        ),
    },
    {
        'key': 'scrunchies',
        'label': 'Scrunchies (Confección propia)',
        'template': (
            "Coletero cómodo y resistente con estampado de [MOTIVO_Y_COLOR], pensado para el día a día y salidas al aire libre.\n"
            "- Origen: Confección propia Rara Tienda\n"
            "- Tela: Popelina [COMPOSICION_TELA]\n"
            "- Diseño: [TIPO_PLISADO]\n"
            "Cuidado: lavar a mano o en ciclo suave con agua fría."
        ),
    },
    {
        'key': 'bandanas',
        'label': 'Bandanas',
        'template': (
            "Bandana suave y versátil con diseño de [MOTIVO], ideal para protegerte del viento o el sol en terreno.\n"
            "- Material: [MATERIAL]\n"
            "- Medidas: [MEDIDA_CM]\n"
            "- Uso recomendado: Cuello, cabeza o muñeca en salidas al aire libre\n"
            "Cuidado: lavar con agua fría y secar a la sombra."
        ),
    },
    {
        'key': 'beanies',
        'label': 'Beanies (Bordado a mano)',
        'template': (
            "Gorro beanie negro abrigado con parche de [ESPECIE_O_HONGO] bordado a mano, ideal para días fríos de observación.\n"
            "- Detalle artesanal: Parche de fieltro bordado a mano\n"
            "- Color base: Negro\n"
            "- Material del gorro: [MATERIAL_GORRO]\n"
            "- Talla: [TALLA]"
        ),
    },
    {
        'key': 'bordados',
        'label': 'Bordados (Hecho a mano)',
        'template': (
            "Cuadro textil decorativo de [ESPECIE], una pieza única pensada para darle un toque natural a tus espacios.\n"
            "- Origen: Hecho a mano\n"
            "- Técnica y materiales: Bordado con hilos Étoile [TECNICA_EXTRA]\n"
            "- Medidas: [MEDIDA_CM]\n"
            "- Bastidor: Bastidor plástico [ACABADO_BASTIDOR]"
        ),
    },
    {
        'key': 'llaveros_madera',
        'label': 'Llaveros — Madera pintada a mano',
        'template': (
            "Llavero artesanal de [ESPECIE_O_HONGO], ideal para llevar un pedacito de la naturaleza nativa en tus llaves o mochila.\n"
            "- Origen: Hecho a mano en madera, pintado en acrílico\n"
            "- Acabado: Protegido con capas de barniz [DETALLE_REVERSO]\n"
            "- Medidas: [MEDIDA_CM]\n"
            "Cuidado: evitar golpes fuertes o exposición prolongada al agua."
        ),
    },
    {
        'key': 'llaveros_bordados',
        'label': 'Llaveros bordados',
        'template': (
            "Llavero textil bordado con diseño de [ESPECIE], liviano y resistente para llaves, mochilas o estuches.\n"
            "- Origen: [CONFECCION_O_BORDADO]\n"
            "- Material: [MATERIAL]\n"
            "- Medidas: [MEDIDA_CM]\n"
            "- Herraje: [TIPO_ARGOLLA]"
        ),
    },
    {
        'key': 'posavasos',
        'label': 'Posavasos (Hecho a mano)',
        'template': (
            "Posavaso artesanal ilustrado con [ESPECIE], ideal para proteger tus mesas con arte inspirado en la biodiversidad chilena.\n"
            "- Origen: Hecho a mano, pintado en acrílico\n"
            "- Acabado: Capa protectora de barniz supercristal; incluye el nombre de la especie al reverso\n"
            "- Base y medidas: [MATERIAL_BASE] · [MEDIDA_CM]\n"
            "Cuidado: limpiar con paño húmedo; no sumergir ni meter al lavavajillas."
        ),
    },
    {
        'key': 'casas_anideras',
        'label': 'Casas anideras (Hecho a mano)',
        'template': (
            "Refugio artesanal pensado para ofrecer un sitio seguro de anidación a pequeñas aves nativas de jardín o bosque.\n"
            "- Origen: Hecho a mano en madera reciclada\n"
            "- Orificio de entrada: 3,5 cm de diámetro\n"
            "- Detalles: [DETALLES_CONSTRUCTIVOS]\n"
            "- Medidas: [MEDIDA_CM]"
        ),
    },
    {
        'key': 'juegos_rompecabezas',
        'label': 'Juegos — Rompecabezas',
        'template': (
            "Rompecabezas ilustrado de [ESPECIE_O_MOTIVO], ideal para disfrutar en familia y acercarse a la fauna nativa pieza a pieza.\n"
            "- Cantidad de piezas: 1000 piezas\n"
            "- Medidas armado: [MEDIDA_ARMADO_CM]\n"
            "- Material: [MATERIAL_CARTON]"
        ),
    },
    {
        'key': 'libros_guias',
        'label': 'Libros y guías de campo',
        'template': (
            "Guía o libro ilustrado sobre [TEMATICA], pensado para apoyar la identificación en terreno y el aprendizaje de la fauna y flora de Chile.\n"
            "- Cobertura / Especies: [CANTIDAD_ESPECIES_O_ZONA]\n"
            "- Formato: [FORMATO_Y_PAGINAS]\n"
            "- Autor / Editorial: [AUTOR_EDITORIAL]"
        ),
    },
]

PLANTILLAS_POR_KEY = {p['key']: p for p in PLANTILLAS_DESCRIPCION}


def seleccionar_plantilla_key(categoria_nombre, nombre_producto="", precio=None, descripcion_actual=""):
    cat = (categoria_nombre or '').lower().strip()
    nom = (nombre_producto or '').lower().strip()
    desc = (descripcion_actual or '').lower().strip()

    if 'calcetin' in cat or 'calcet' in cat:
        if 'digital' in nom or '95% polyester' in desc or '95% poliéster' in desc or precio == 3000:
            return 'calcetines_digital'
        return 'calcetines_algodon'

    if 'crocs' in cat or 'bamer' in cat:
        return 'pins_crocs'

    if 'pin' in cat:
        if precio == 8000:
            return 'pins_especiales'
        return 'pins_estandar'

    if 'accesorios' in cat or 'birding' in cat:
        if 'arnés' in nom or 'arnes' in nom:
            return 'accesorios_arnes'
        return 'accesorios_otro'

    if 'scrunchie' in cat:
        return 'scrunchies'

    if 'bandana' in cat:
        return 'bandanas'

    if 'beanie' in cat:
        return 'beanies'

    if 'bordado' in cat and 'llavero' not in cat:
        return 'bordados'

    if 'llavero' in cat and 'bordado' in cat:
        return 'llaveros_bordados'

    if 'llavero' in cat:
        return 'llaveros_madera'

    if 'posavaso' in cat:
        return 'posavasos'

    if 'anidera' in cat or 'casa' in cat:
        return 'casas_anideras'

    if 'juego' in cat:
        if 'rompecabeza' in nom:
            return 'juegos_rompecabezas'
        return 'juegos_rompecabezas'

    if 'libro' in cat or 'guía' in cat or 'guia' in cat:
        return 'libros_guias'

    return ''


def listar_plantillas_para_panel():
    return [
        {'key': p['key'], 'label': p['label'], 'template': p['template']}
        for p in PLANTILLAS_DESCRIPCION
    ]


def es_descripcion_completa_protegida(producto):
    """
    Protege descripciones completas y bien redactadas (libros, guías, Cachañando,
    paño de microfibra, kits limpiadores, tapas) para no sobrescribirlas.
    """
    cat = (producto.categoria.nombre if producto.categoria else '').lower()
    nom = (producto.nombre or '').lower()
    desc = (producto.descripcion or '').strip()
    desc_low = desc.lower()

    if 'libro' in cat or 'guía' in cat or 'guia' in cat:
        return True

    palabras_protegidas = ['cachañando', 'paño microfibra', 'kit limpiador', 'tapas binoculares']
    if any(p in nom for p in palabras_protegidas):
        return True

    if not desc or 'sin descripción' in desc_low:
        return False

    # Detectar descripciones que ya fueron migradas con nuestra estructura de viñetas
    if '\n- ' in desc and len(desc) >= 90:
        return True

    # Descripciones cortas o fragmentos técnicos sin estructura completa sí se enriquecen
    patrones_incompletos = [
        'talla ',
        '95% polyester',
        'algodón 80%',
        'set 5 pins',
        'set de 5 pins',
        '1000 piezas',
        'plisado de popelina',
        'suave y cómoda para a terreno',
        'bordado hilos etoile',
        'llavero de madera',
        'pintado a mano en acrílico',
        'beanie negro con parche',
        'madera reciclada, orificio',
        'cómodo arnés ajustable',
        'nuevo modelo de arnés',
    ]
    if any(pat in desc_low for pat in patrones_incompletos):
        return False

    return len(desc) >= 85


def _limpiar_motivo_nombre(nombre):
    prefijos = [
        'calcetín impresión digital ',
        'calcetin impresion digital ',
        'calcetín ',
        'calcetin ',
        'pins crocs-bamers ',
        'pin ',
        'scrunchie ',
        'bandana ',
        'beanie ',
        'bordado ',
        'llavero madera ',
        'llavero bordado ',
        'posavaso ',
        'rompecabezas ',
    ]
    motivo = (nombre or '').strip()
    motivo_low = motivo.lower()
    for pref in prefijos:
        if motivo_low.startswith(pref):
            motivo = motivo[len(pref):].strip()
            break

    # Quitar sufijos de tamaño en calcetines ("chica", "chico", "grande", "largo", "corto") si aplica para especie
    return motivo or nombre


def extraer_datos_reales(producto):
    """Extrae únicamente datos reales presentes en el producto o su descripción actual."""
    desc = (producto.descripcion or '').strip()
    desc_low = desc.lower()
    nombre = (producto.nombre or '').strip()
    especie = (producto.especie_nombre_comun or '').strip()
    motivo_limpio = _limpiar_motivo_nombre(nombre)

    # Para especie/motivo priorizamos especie_nombre_comun si existe, si no el motivo del nombre
    especie_o_motivo = especie or motivo_limpio

    valores = {
        'ESPECIE_O_MOTIVO': especie_o_motivo,
        'ESPECIE': especie_o_motivo,
        'ESPECIE_O_HONGO': especie_o_motivo,
        'MOTIVO': motivo_limpio,
        'MOTIVO_Y_COLOR': motivo_limpio,
        'TEMATICA': motivo_limpio,
    }

    # Talla en calcetines (ej: 35-40, 41-45, 41-46, 37-45)
    m_talla = re.search(r'(?:talla\s*(?:única\s*)?)?(\d{2}\s*-\s*\d{2})', desc_low)
    if m_talla:
        valores['TALLA'] = m_talla.group(1).replace(' ', '')

    # Medidas en cm (ej: 15,7x15,5 cm, 16x15 cm, 4,5 cm, 3 cm)
    m_medida = re.search(r'(\d+(?:[.,]\d+)?(?:\s*x\s*\d+(?:[.,]\d+)?)?\s*cm)', desc, re.IGNORECASE)
    if m_medida:
        valores['MEDIDA_CM'] = m_medida.group(1).strip()

    # Arneses
    m_elast = re.search(r'(el[aá]stico\s+(?:grueso|simple)[^.\n]*)', desc, re.IGNORECASE)
    if m_elast:
        valores['TIPO_ELASTICO'] = m_elast.group(1).strip().capitalize()
    if 'espalda de cuero' in desc_low:
        m_cuero = re.search(r'(espalda de cuero[^.\n]*)', desc, re.IGNORECASE)
        valores['DETALLE_ESPALDA'] = f"({m_cuero.group(1).strip()})" if m_cuero else "(espalda de cuero)"
    else:
        # Si ya tiene elástico pero no espalda de cuero, dejar vacío para no inventar ni romper la línea
        if 'TIPO_ELASTICO' in valores:
            valores['DETALLE_ESPALDA'] = ''

    if 'imagen de referencia' in desc_low:
        valores['ACLARACION_IMAGEN_O_USO'] = "Primera imagen de referencia; la imagen 2 corresponde al producto."

    # Scrunchies
    if 'poliéster' in desc_low or 'poliester' in desc_low:
        valores['COMPOSICION_TELA'] = "(poliéster)"
    else:
        valores['COMPOSICION_TELA'] = ""

    if 'mini plisado' in desc_low:
        valores['TIPO_PLISADO'] = "Mini plisado"
    elif 'plisado' in desc_low:
        valores['TIPO_PLISADO'] = "Plisado"

    # Bordados
    if 'acrílico' in desc_low or 'acrilico' in desc_low:
        valores['TECNICA_EXTRA'] = "y técnica mixta en acrílico"
    else:
        valores['TECNICA_EXTRA'] = ""

    if 'simula madera' in desc_low:
        valores['ACABADO_BASTIDOR'] = "(simil madera)"
    elif 'bastidor' in desc_low:
        valores['ACABADO_BASTIDOR'] = ""

    # Llaveros madera
    if 'parte posterior' in desc_low or 'reverso' in desc_low:
        valores['DETALLE_REVERSO'] = "(incluye el nombre de la especie en la parte posterior)"
    elif 'barniz' in desc_low:
        valores['DETALLE_REVERSO'] = ""

    # Casas anideras
    detalles_casa = []
    if 'diseño de bosque en acrílico' in desc_low:
        detalles_casa.append("Diseño de bosque pintado en acrílico")
    if 'tapa con bisagras' in desc_low:
        detalles_casa.append("Tapa con bisagras")
    if 'ganchos para colgar' in desc_low:
        detalles_casa.append("Ganchos para colgar")
    if detalles_casa:
        valores['DETALLES_CONSTRUCTIVOS'] = ", ".join(detalles_casa)

    return valores


def aplicar_plantilla_a_producto(producto, omitir_lineas_con_placeholders=True):
    """
    Genera la nueva descripción para un producto existente usando su plantilla.
    Retorna (texto_final, placeholders_faltantes, plantilla_key).
    Si omitir_lineas_con_placeholders=True, elimina las líneas que tengan [PLACEHOLDER] sin datos.
    """
    cat_nombre = producto.categoria.nombre if producto.categoria else ''
    key = seleccionar_plantilla_key(
        cat_nombre,
        nombre_producto=producto.nombre,
        precio=producto.precio_actual,
        descripcion_actual=producto.descripcion,
    )
    plantilla_obj = PLANTILLAS_POR_KEY.get(key)
    if not plantilla_obj:
        return producto.descripcion, [], ''

    valores = extraer_datos_reales(producto)
    lineas_originales = plantilla_obj['template'].splitlines()
    lineas_finales = []
    placeholders_faltantes = []

    for linea in lineas_originales:
        nueva_linea = linea
        for k, v in valores.items():
            nueva_linea = nueva_linea.replace(f'[{k}]', v)

        # Limpiar espacios dobles si un placeholder opcional se reemplazó por ""
        nueva_linea = re.sub(r'\s{2,}', ' ', nueva_linea).strip()

        restantes = re.findall(r'\[([A-Z0-9_]+)\]', nueva_linea)
        if restantes:
            for r in restantes:
                if r not in placeholders_faltantes:
                    placeholders_faltantes.append(r)
            if not omitir_lineas_con_placeholders:
                lineas_finales.append(nueva_linea)
        else:
            if nueva_linea:
                lineas_finales.append(nueva_linea)

    return "\n".join(lineas_finales), placeholders_faltantes, key

