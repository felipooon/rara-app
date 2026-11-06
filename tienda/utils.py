def get_cloudinary_url(image_field_or_url, width=None, quality="auto", format_type="auto"):
    """
    Genera una URL optimizada de Cloudinary manteniendo compatibilidad con
    archivos locales en modo de desarrollo.

    - Reemplaza f_jpg por f_auto (o format_type especificado).
    - Aplica q_auto (o quality especificado).
    - Aplica ancho dinámico (w_{width}) si width se especifica.
    - No fuerza sufijos/extensiones .jpg al final de la URL.
    """
    if not image_field_or_url:
        return ""

    if hasattr(image_field_or_url, 'url'):
        try:
            url = image_field_or_url.url
        except Exception:
            return ""
    else:
        url = str(image_field_or_url)

    if not url:
        return ""

    # Si no es una URL de Cloudinary (ej: desarrollo local en /media/)
    if 'cloudinary.com' not in url:
        if url.startswith('http://') or url.startswith('https://'):
            if url.startswith('http://'):
                return 'https://' + url[7:]
            return url
        if not url.startswith('/'):
            url = '/' + url
        return f"https://www.raratienda.cl{url}"

    # Forzar HTTPS en Cloudinary
    if url.startswith('http://'):
        url = 'https://' + url[7:]

    # Construir segmento de transformaciones
    transformations = [f"f_{format_type}", f"q_{quality}"]
    if width:
        transformations.append(f"w_{width}")
    
    transform_str = ",".join(transformations)

    # Si contiene /upload/ en la URL:
    if '/upload/' in url:
        parts = url.split('/upload/')
        prefix = parts[0] + '/upload/'
        suffix = parts[1]

        # Eliminar transformaciones previas si existen en el primer segmento del sufijo
        first_segment = suffix.split('/')[0]
        if any(p.startswith(('f_', 'q_', 'w_', 'c_', 'h_', 'g_')) for p in first_segment.split(',')):
            rest = "/".join(suffix.split('/')[1:])
            suffix = rest

        url = f"{prefix}{transform_str}/{suffix}"

    return url


CODE128_PATTERNS = [
    '212222', '222122', '222221', '121223', '121322', '131222', '122213', '122312', '132212', '221213',
    '221312', '231212', '112232', '122132', '122231', '113222', '123122', '123221', '223211', '221132',
    '221231', '213212', '223112', '312131', '311222', '321122', '321221', '312212', '322112', '322211',
    '212123', '212321', '232121', '111323', '131123', '131321', '112313', '132113', '132311', '211313',
    '231113', '231311', '112133', '112331', '132131', '113123', '113321', '133121', '313121', '211331',
    '231131', '213113', '213311', '213131', '311123', '311321', '331121', '312113', '312311', '332111',
    '314111', '221411', '431111', '111224', '111422', '121124', '121421', '141122', '141221', '112214',
    '112412', '122114', '122411', '142112', '142211', '241211', '221114', '413111', '241112', '134111',
    '111242', '121142', '121241', '114212', '124112', '124211', '411212', '421112', '421211', '212141',
    '214121', '412121', '111143', '111341', '131141', '114113', '114311', '411113', '411311', '113141',
    '114131', '311141', '411131', '211412', '211214', '211232', '2331112'
]


def generar_codigo_sku(producto_id):
    """Retorna el código SKU de al menos 3 dígitos basado en el ID del producto."""
    return str(producto_id or 0).zfill(3)


def generar_codigo_barras_upca(producto_id):
    """
    Genera el código de barras numérico de 12 dígitos (prefijo 78049271 + SKU + dígito verificador UPC-A).
    """
    base = str(78049271000 + int(producto_id or 0))
    s_odd = sum(int(base[i]) for i in range(0, 11, 2))
    s_even = sum(int(base[i]) for i in range(1, 11, 2))
    chk = (10 - ((s_odd * 3 + s_even) % 10)) % 10
    return f"{base}{chk}"


def generar_svg_code128c(code_str, width=320, height=96):
    """
    Genera el SVG vectorial en formato Code 128 Set C de alta nitidez (crispEdges),
    con barras más altas, mayor grosor de módulo y zona muda (quiet zone) amplia
    para máxima detección en cámaras de POS de baja resolución.
    """
    code_str = str(code_str).strip()
    if len(code_str) % 2 != 0:
        code_str = '0' + code_str

    values = [105]  # Start Code C
    for i in range(0, len(code_str), 2):
        values.append(int(code_str[i:i + 2]))

    checksum = values[0]
    for idx, val in enumerate(values[1:], start=1):
        checksum += idx * val
    values.append(checksum % 103)
    values.append(106)  # Stop

    quiet_zone = 30
    x = quiet_zone
    module_w = 3
    bar_height = 68
    rects = ['<rect width="100%" height="100%" fill="#ffffff" shape-rendering="crispEdges"/>']
    for val in values:
        pat = CODE128_PATTERNS[val]
        is_bar = True
        for ch in pat:
            w = int(ch) * module_w
            if is_bar:
                rects.append(
                    f'<rect x="{x}" y="6" width="{w}" height="{bar_height}" '
                    f'fill="#000000" shape-rendering="crispEdges"/>'
                )
            x += w
            is_bar = not is_bar

    total_w = x + quiet_zone
    cx = total_w // 2
    rects.append(
        f'<text x="{cx}" y="92" font-family="\'Consolas\', \'Courier New\', monospace" '
        f'font-size="18" font-weight="bold" text-anchor="middle" letter-spacing="3" '
        f'fill="#000000">{code_str}</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} 98" '
        f'width="{width}" height="{height}" shape-rendering="crispEdges" '
        f'style="shape-rendering: crispEdges; image-rendering: pixelated;">'
        + ''.join(rects) + '</svg>'
    )


def limpiar_nombre_pos(nombre):
    """
    Asegura que el nombre cumpla con las reglas de importación del POS:
    - Obligatorio, entre 3 y 120 caracteres.
    - No puede comenzar con número ni carácter especial.
    """
    import re
    texto = (nombre or "").strip()
    # Si empieza con número o carácter especial, anteponer 'Producto '
    if texto and not texto[0].isalpha():
        texto = f"Producto {texto}"
    if len(texto) < 3:
        texto = (texto + " Rara Tienda")[:120]
    return texto[:120]


def generar_excel_catalogo_pos(productos):
    """
    Genera los bytes de un archivo .xlsx en el formato exacto de 'catalogo_importacion_rara_tienda.xlsx'
    basado en 'modulobarcode/plantilla_importación_catálogo.xlsx', preservando comentarios, estilos y metadatos.
    """
    import io
    import os
    import zipfile
    from xml.sax.saxutils import escape
    from django.conf import settings

    plantilla_path = os.path.join(settings.BASE_DIR, 'modulobarcode', 'plantilla_importación_catálogo.xlsx')

    shared_strings = [
        'NOMBRE', 'DESCRIPCIÓN', 'PESO', 'PRECIO', 'PRECIO COSTO',
        '¿EXENTO?', 'CÓDIGO SKU', 'CÓDIGO DE BARRAS', '¿ACTIVO?', 'MARCA', 'CATEGORIA',
        'N', 'S'
    ]
    str_to_idx = {s: i for i, s in enumerate(shared_strings)}

    def get_sst_idx(val):
        val = str(val)
        if val not in str_to_idx:
            str_to_idx[val] = len(shared_strings)
            shared_strings.append(val)
        return str_to_idx[val]

    rows_data = []
    for p in productos:
        nom_idx = get_sst_idx(limpiar_nombre_pos(p.nombre))
        sku_idx = get_sst_idx(p.codigo_sku)
        bc_idx = get_sst_idx(p.codigo_barras)
        activo_idx = 12 if (p.stock > 0 and p.disponible) else 11
        precio_val = float(p.precio_actual)
        rows_data.append((nom_idx, precio_val, 11, sku_idx, bc_idx, activo_idx))

    total_sst_refs = 11 + len(rows_data) * 5

    sst_lines = [
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
        f'<sst count="{total_sst_refs}" uniqueCount="{len(shared_strings)}" xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    ]
    for s in shared_strings:
        sst_lines.append(f'  <si>\n    <t>{escape(s)}</t>\n  </si>')
    sst_lines.append('</sst>')
    sst_xml = '\r\n'.join(sst_lines).encode('utf-8')

    cols_L_to_Z = ['L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
    cols_A_to_I = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']

    sheet_lines = [
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:mx="http://schemas.microsoft.com/office/mac/excel/2008/main" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:mv="urn:schemas-microsoft-com:mac:vml" '
        'xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" '
        'xmlns:x15="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main" '
        'xmlns:x14ac="http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac" '
        'xmlns:xm="http://schemas.microsoft.com/office/excel/2006/main">',
        '  <sheetPr>\n    <pageSetUpPr />\n  </sheetPr>',
        '  <sheetViews>\n    <sheetView workbookViewId="0" />\n  </sheetViews>',
        '  <sheetFormatPr customHeight="1" defaultColWidth="11.22" defaultRowHeight="15.0" />',
        '  <cols>',
        '    <col customWidth="1" min="1" max="7" width="14.67" />',
        '    <col customWidth="1" min="8" max="8" width="18.0" />',
        '    <col customWidth="1" min="9" max="9" width="14.67" />',
        '    <col customWidth="1" min="10" max="26" width="10.56" />',
        '  </cols>',
        '  <sheetData>',
        '    <row r="1" ht="15.75" customHeight="1">'
    ]
    for idx, col in enumerate(cols_A_to_I):
        sheet_lines.append(f'      <c r="{col}1" s="1" t="s">\n        <v>{idx}</v>\n      </c>')
    sheet_lines.append('      <c r="J1" s="2" t="s">\n        <v>9</v>\n      </c>')
    sheet_lines.append('      <c r="K1" s="3" t="s">\n        <v>10</v>\n      </c>')
    for col in cols_L_to_Z:
        sheet_lines.append(f'      <c r="{col}1" s="4" />')
    sheet_lines.append('    </row>')

    max_rows = max(1000, len(rows_data) + 1)
    for r in range(2, max_rows + 1):
        sheet_lines.append(f'    <row r="{r}" ht="15.75" customHeight="1">')
        data_idx = r - 2
        if data_idx < len(rows_data):
            nom_idx, precio_val, exento_idx, sku_idx, bc_idx, activo_idx = rows_data[data_idx]
            sheet_lines.append(f'      <c r="A{r}" s="5" t="s">\n        <v>{nom_idx}</v>\n      </c>')
            sheet_lines.append(f'      <c r="B{r}" s="1" />')
            sheet_lines.append(f'      <c r="C{r}" s="1" />')
            sheet_lines.append(f'      <c r="D{r}" s="5">\n        <v>{precio_val}</v>\n      </c>')
            sheet_lines.append(f'      <c r="E{r}" s="1" />')
            sheet_lines.append(f'      <c r="F{r}" s="5" t="s">\n        <v>{exento_idx}</v>\n      </c>')
            sheet_lines.append(f'      <c r="G{r}" s="5" t="s">\n        <v>{sku_idx}</v>\n      </c>')
            sheet_lines.append(f'      <c r="H{r}" s="5" t="s">\n        <v>{bc_idx}</v>\n      </c>')
            sheet_lines.append(f'      <c r="I{r}" s="5" t="s">\n        <v>{activo_idx}</v>\n      </c>')
        else:
            for col in cols_A_to_I:
                sheet_lines.append(f'      <c r="{col}{r}" s="1" />')
        sheet_lines.append(f'      <c r="J{r}" s="3" />')
        sheet_lines.append(f'      <c r="K{r}" s="3" />')
        for col in cols_L_to_Z:
            sheet_lines.append(f'      <c r="{col}{r}" s="4" />')
        sheet_lines.append('    </row>')

    sheet_lines.extend([
        '  </sheetData>',
        '  <printOptions />',
        '  <pageMargins bottom="0.75" footer="0.0" header="0.0" left="0.7" right="0.7" top="0.75" />',
        '  <pageSetup orientation="landscape" />',
        '  <drawing r:id="rId2" />',
        '  <legacyDrawing r:id="rId3" />',
        '</worksheet>'
    ])
    sheet_xml = '\r\n'.join(sheet_lines).encode('utf-8')

    out_buf = io.BytesIO()
    if os.path.exists(plantilla_path):
        with zipfile.ZipFile(plantilla_path, 'r') as zin:
            with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename == 'xl/worksheets/sheet1.xml':
                        zout.writestr(item, sheet_xml)
                    elif item.filename == 'xl/sharedStrings.xml':
                        zout.writestr(item, sst_xml)
                    else:
                        zout.writestr(item, zin.read(item.filename))
        return out_buf.getvalue()

    # Fallback con openpyxl si no existiera el archivo plantilla en disco
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Productos"
    ws.append(shared_strings[:11])
    for p in productos:
        activo_str = 'S' if (p.stock > 0 and p.disponible) else 'N'
        ws.append([
            limpiar_nombre_pos(p.nombre), None, None, float(p.precio_actual),
            None, 'N', p.codigo_sku, p.codigo_barras, activo_str, None, None
        ])
    wb.save(out_buf)
    return out_buf.getvalue()


def generar_html_codigos_barra(productos):
    """
    Genera el documento HTML autocontenido de catálogo de códigos de barra (formato idéntico a codigos_de_barra_rara_tienda.html).
    """
    from xml.sax.saxutils import escape

    cards_html = []
    for p in productos:
        nombre = limpiar_nombre_pos(p.nombre)
        sku = p.codigo_sku
        barcode = p.codigo_barras
        precio_str = f"${p.precio_actual} ({p.porcentaje_descuento}% OFF)" if p.tiene_descuento else f"${p.precio_actual}"
        search_str = escape(f"{nombre.lower()} {sku} {barcode}")
        svg = generar_svg_code128c(barcode)
        cards_html.append(
            f'    <div class="item-card" data-search="{search_str}">\n'
            f'      <div class="item-header">\n'
            f'        <div class="item-name">{escape(nombre)}</div>\n'
            f'        <div class="item-meta">SKU: {sku} &bull; Precio: {escape(precio_str)}</div>\n'
            f'      </div>\n'
            f'      <div class="barcode-box">\n'
            f'        {svg}\n'
            f'      </div>\n'
            f'    </div>'
        )

    total = len(cards_html)
    body_cards = "".join(cards_html)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Listado de Códigos de Barra - Rara Tienda</title>
<style>
  :root {{
    --border-color: #d1d5db;
    --text-main: #111827;
    --text-muted: #4b5563;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    color: var(--text-main);
    margin: 0;
    padding: 20px;
    background: #f9fafb;
  }}
  .toolbar {{
    max-width: 1050px;
    margin: 0 auto 20px auto;
    background: #ffffff;
    padding: 16px 24px;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }}
  .toolbar h1 {{
    margin: 0;
    font-size: 20px;
  }}
  .toolbar .controls {{
    display: flex;
    gap: 10px;
    align-items: center;
  }}
  .toolbar input {{
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 14px;
    width: 240px;
  }}
  .toolbar button {{
    padding: 8px 14px;
    border: 1px solid var(--border-color);
    background: #ffffff;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
  }}
  .toolbar button.primary {{
    background: #111827;
    color: #ffffff;
    border-color: #111827;
  }}
  .container {{
    max-width: 1050px;
    margin: 0 auto;
    background: #ffffff;
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  .grid-view {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }}
  .item-card {{
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    text-align: center;
    background: #ffffff;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .item-header {{
    width: 100%;
    margin-bottom: 6px;
  }}
  .item-name {{
    font-size: 13px;
    font-weight: 600;
    line-height: 1.25;
    color: var(--text-main);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 32px;
  }}
  .item-meta {{
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
  }}
  .barcode-box svg {{
    display: block;
    max-width: 100%;
    height: auto;
  }}
  .table-view .item-card {{
    flex-direction: row;
    text-align: left;
    padding: 8px 16px;
  }}
  .table-view {{
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .table-view .item-header {{
    margin-bottom: 0;
    padding-right: 16px;
  }}
  .table-view .item-name {{
    font-size: 14px;
    min-height: unset;
  }}
  @media print {{
    body {{
      background: #ffffff;
      padding: 0;
    }}
    .toolbar {{
      display: none !important;
    }}
    .container {{
      box-shadow: none;
      padding: 0;
      max-width: 100%;
    }}
    .grid-view {{
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
    }}
    .item-card {{
      padding: 8px;
      border: 1px solid #9ca3af;
    }}
  }}
</style>
</head>
<body>
<div class="toolbar">
  <div>
    <h1>Catálogo de Códigos de Barra — Rara Tienda ({total} productos)</h1>
  </div>
  <div class="controls">
    <input type="text" id="searchInput" placeholder="Buscar producto, SKU o código..." oninput="filterItems()">
    <button onclick="setView('grid-view')">Vista Tarjetas (3 col)</button>
    <button onclick="setView('table-view')">Vista Lista (Tabla)</button>
    <button class="primary" onclick="window.print()">Imprimir / Guardar PDF</button>
  </div>
</div>
<div class="container">
  <div id="catalog" class="grid-view">{body_cards}  </div>
</div>
<script>
function setView(cls) {{
  document.getElementById('catalog').className = cls;
}}
function filterItems() {{
  const q = document.getElementById('searchInput').value.toLowerCase().trim();
  const cards = document.querySelectorAll('.item-card');
  cards.forEach(c => {{
    c.style.display = c.getAttribute('data-search').includes(q) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""



