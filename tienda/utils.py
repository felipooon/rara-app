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
