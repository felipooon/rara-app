from django.db import models
from django.utils.text import slugify

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    imagen = models.ImageField(upload_to='categorias/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    precio = models.IntegerField()
    imagen = models.ImageField(upload_to='productos/')

    disponible = models.BooleanField(default=True) 

    def __str__(self):
        return self.nombre