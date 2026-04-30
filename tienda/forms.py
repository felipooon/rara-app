from django import forms
from .models import Producto
from .models import Categoria

class ProductoForm(forms.ModelForm):
    # Sobreescribimos el campo precio para recibirlo como texto primero
    precio = forms.CharField(widget=forms.TextInput(attrs={'type': 'text'}))

    class Meta:
        model = Producto
        fields = "__all__"

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