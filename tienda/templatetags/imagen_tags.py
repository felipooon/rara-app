from django import template
from ..utils import get_cloudinary_url

register = template.Library()

@register.filter
def cloudinary_url(image_field_or_url, width=None):
    """
    Filtro de plantilla para formatear URLs optimizadas de Cloudinary.
    Uso en template: {{ producto.imagen|cloudinary_url:600 }}
    """
    if width is not None:
        try:
            width = int(width)
        except (ValueError, TypeError):
            width = None

    return get_cloudinary_url(image_field_or_url, width=width)

@register.filter
def clp(value):
    """
    Formatea un número o monto a formato chileno CLP: $25.000
    """
    if value is None or value == '':
        return '$0'
    try:
        val = int(value)
        return f"${val:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return f"${value}"
