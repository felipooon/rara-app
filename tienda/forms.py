from django import forms
from .models import Producto
from .models import Categoria

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = "__all__"

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "imagen"]