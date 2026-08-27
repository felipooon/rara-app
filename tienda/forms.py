from django import forms
from .models import Producto
from .models import Categoria

class ProductoForm(forms.ModelForm):
    # Sobreescribimos el campo precio para recibirlo como texto primero
    precio = forms.CharField(widget=forms.TextInput(attrs={'type': 'text'}))

    class Meta:
        model = Producto
        exclude = ['slug']

    def clean_precio(self):
        data = self.cleaned_data.get('precio')
        
        # 1. Quitamos puntos y espacios por si acaso escribió "18.000 "
        data = data.replace('.', '').replace(' ', '')
        
        try:
            # 2. Intentamos convertirlo a entero
            precio_final = int(data)
        except ValueError:
            raise forms.ValidationError("Por favor, ingresa un precio válido sin letras.")

        # 3. Validación de negativo
        if precio_final < 0:
            raise forms.ValidationError("El precio no puede ser negativo.")
            
        return precio_final

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "imagen"]

from .models import Cupon

class CuponForm(forms.ModelForm):
    class Meta:
        model = Cupon
        fields = ["codigo", "descuento_porcentaje", "descuento_monto", "activo", "usos_maximos", "fecha_expiracion"]
        widgets = {
            'fecha_expiracion': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo', '').strip().upper()
        if not codigo:
            raise forms.ValidationError("Ingresa un código de cupón válido.")
        return codigo


from .models import BlogPost, ResenaProducto, ConfiguracionSitio

class BlogPostForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = ['titulo', 'autor', 'resumen', 'contenido', 'imagen', 'publicado']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Título del artículo'}),
            'autor': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del autor (Ej: Rara Tienda, Felipe, etc.)'}),
            'resumen': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Breve resumen para las tarjetas'}),
            'contenido': forms.Textarea(attrs={'class': 'form-control', 'rows': 12, 'id': 'editor-contenido', 'placeholder': 'Escribe el contenido de tu artículo...'}),
        }

class ResenaForm(forms.ModelForm):
    class Meta:
        model = ResenaProducto
        fields = ['nombre_cliente', 'email_cliente', 'calificacion', 'comentario']
        widgets = {
            'nombre_cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tu nombre'}),
            'email_cliente': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Tu correo (opcional)'}),
            'calificacion': forms.Select(choices=[(i, f"{i} Estrella{'s' if i > 1 else ''}") for i in range(5, 0, -1)], attrs={'class': 'form-control'}),
            'comentario': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '¿Qué te pareció este producto?'}),
        }

class ConfiguracionSitioForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionSitio
        fields = ['mostrar_blog', 'mostrar_resenas']
        labels = {
            'mostrar_blog': 'Activar Sección de Blog en la tienda (Navbar y menú)',
            'mostrar_resenas': 'Activar Reseñas y Calificaciones con Estrellas en productos',
        }