from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("categoria/<slug:slug>/", views.categoria_detail, name="categoria"),

    # PANEL
    path("panel/", views.panel_home, name="panel_home"),
    path("panel/productos/", views.panel_productos, name="panel_productos"),
    path("panel/productos/crear/", views.crear_producto, name="crear_producto"),
    path("panel/categorias/crear/", views.crear_categoria, name="crear_categoria"),
    path("panel/productos/<int:id>/toggle/", views.toggle_producto, name="toggle_producto"),

]