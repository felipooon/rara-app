from django import forms
from .models import Producto
from .models import Categoria

class ProductoForm(forms.ModelForm):
    # Sobreescribimos el campo precio para recibirlo como texto primero
    precio = forms.CharField(widget=forms.TextInput(attrs={'type': 'text'}))
    precio_oferta = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'type': 'text', 'placeholder': 'Ej: 15000'}),
        label="Precio de Oferta Final ($)"
    )
    descuento_porcentaje = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=99,
        widget=forms.NumberInput(attrs={'min': '1', 'max': '99', 'placeholder': 'Ej: 20'}),
        label="% de Descuento"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and self.initial.get('stock') is None:
            self.initial['stock'] = 1
        if self.instance.pk:
            if self.instance.precio_oferta:
                self.initial['precio_oferta'] = self.instance.precio_oferta
            if self.instance.tiene_descuento:
                self.initial['descuento_porcentaje'] = self.instance.porcentaje_descuento

    class Meta:
        model = Producto
        exclude = ['slug']
        widgets = {
            'stock': forms.NumberInput(attrs={'min': '0', 'style': 'text-align: center; font-weight: 700; font-size: 1.05rem;'}),
            'especie_nombre_comun': forms.TextInput(attrs={'placeholder': 'Ej: Cometocino Patagónico, Amanita muscaria'}),
            'especie_nombre_cientifico': forms.TextInput(attrs={'placeholder': 'Ej: Phrygilus patagonicus'}),
            'especie_habitat': forms.TextInput(attrs={'placeholder': 'Ej: Bosques templados y cordillera del sur de Chile'}),
            'especie_estado_conservacion': forms.TextInput(attrs={'placeholder': 'Ej: Preocupación menor (LC), Vulnerable (VU)'}),
            'especie_dato_curioso': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ej: Ave muy sociable que suele acompañar las excursiones...'}),
        }
        labels = {
            'en_oferta': 'Activar Oferta / Descuento Especial',
            'precio_oferta': 'Precio de Oferta Final ($)',
            'descuento_porcentaje': '% de Descuento',
            'tiene_ficha_especie': 'Incluir Ficha de Especie / Dato Curioso sobre esta especie',
            'especie_nombre_comun': 'Nombre Común de la Especie',
            'especie_nombre_cientifico': 'Nombre Científico',
            'especie_habitat': 'Hábitat / Distribución',
            'especie_estado_conservacion': 'Estado de Conservación',
            'especie_dato_curioso': 'Dato Curioso / Reseña Educativa',
        }

    def clean_precio(self):
        data = self.cleaned_data.get('precio')
        if not data:
            raise forms.ValidationError("El precio es obligatorio.")
        
        # 1. Quitamos puntos, signo peso y espacios por si acaso escribió "$ 18.000 "
        data_str = str(data).replace('.', '').replace(' ', '').replace('$', '').strip()
        
        try:
            # 2. Intentamos convertirlo a entero
            precio_final = int(data_str)
        except ValueError:
            raise forms.ValidationError("Por favor, ingresa un precio válido sin letras.")

        # 3. Validación de no negativo ni cero
        if precio_final <= 0:
            raise forms.ValidationError("El precio debe ser mayor a 0.")
            
        return precio_final

    def clean_precio_oferta(self):
        data = self.cleaned_data.get('precio_oferta')
        if not data:
            return None
        if isinstance(data, int):
            return data
        data_str = str(data).replace('.', '').replace(' ', '').replace('$', '').strip()
        if not data_str:
            return None
        try:
            precio_val = int(data_str)
        except ValueError:
            raise forms.ValidationError("Por favor, ingresa un precio de oferta válido sin letras.")
        if precio_val <= 0:
            raise forms.ValidationError("El precio de oferta debe ser mayor a 0.")
        return precio_val

    def clean(self):
        cleaned_data = super().clean()
        en_oferta = cleaned_data.get('en_oferta')
        precio = cleaned_data.get('precio')
        precio_oferta = cleaned_data.get('precio_oferta')
        descuento_porcentaje = cleaned_data.get('descuento_porcentaje')

        if en_oferta:
            if not precio:
                return cleaned_data
            
            if not precio_oferta and not descuento_porcentaje:
                self.add_error('precio_oferta', "Para activar la oferta, debes ingresar un precio de oferta o un porcentaje de descuento.")
                return cleaned_data
            
            if descuento_porcentaje and not precio_oferta:
                if descuento_porcentaje < 1 or descuento_porcentaje > 99:
                    self.add_error('descuento_porcentaje', "El porcentaje debe estar entre 1% y 99%.")
                else:
                    precio_oferta = int(round(precio * (1 - (descuento_porcentaje / 100))))
                    cleaned_data['precio_oferta'] = precio_oferta
            elif precio_oferta and not descuento_porcentaje:
                if precio_oferta >= precio:
                    self.add_error('precio_oferta', "El precio de oferta debe ser menor al precio normal.")
                else:
                    descuento_porcentaje = max(1, round((1 - (precio_oferta / precio)) * 100))
                    cleaned_data['descuento_porcentaje'] = descuento_porcentaje
            elif precio_oferta and descuento_porcentaje:
                if precio_oferta >= precio:
                    self.add_error('precio_oferta', "El precio de oferta debe ser menor al precio normal.")
                if descuento_porcentaje < 1 or descuento_porcentaje > 99:
                    self.add_error('descuento_porcentaje', "El porcentaje debe estar entre 1% y 99%.")
                if precio_oferta < precio:
                    # Sincronizamos porcentaje con el precio oferta ingresado
                    cleaned_data['descuento_porcentaje'] = max(1, round((1 - (precio_oferta / precio)) * 100))
        return cleaned_data

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