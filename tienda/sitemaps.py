from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Producto, Categoria, BlogPost

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

class BlogPostViewSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return BlogPost.objects.filter(publicado=True)

class StaticViewSitemap(Sitemap):
    priority = 0.7
    changefreq = 'weekly'

    def items(self):
        return ['index', 'menu_juegos', 'blog_list', 'terminos']

    def location(self, item):
        return reverse(item)
