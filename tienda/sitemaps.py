from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Producto, Categoria

class ProductoViewSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.9

    def items(self):
        return Producto.objects.filter(disponible=True)

class CategoriaViewSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Categoria.objects.all()

class StaticViewSitemap(Sitemap):
    priority = 0.7
    changefreq = 'weekly'

    def items(self):
        return ['index', 'menu_juegos']

    def location(self, item):
        return reverse(item)
