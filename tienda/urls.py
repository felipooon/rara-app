from django.contrib import admin
from django.urls import path, include
from . import views
from .views import CustomLoginView
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path("", views.index, name="index"),
    path("categoria/<slug:slug>/", views.categoria_detail, name="categoria"),

    # PANEL
    path("panel/", views.panel_home, name="panel_home"),
    path("panel/productos/", views.panel_productos, name="panel_productos"),
    path("panel/productos/crear/", views.crear_producto, name="crear_producto"),
    path("panel/categorias/crear/", views.crear_categoria, name="crear_categoria"),
    path("panel/productos/<int:id>/toggle/", views.toggle_producto, name="toggle_producto"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    path("producto/<int:id>/", views.producto_detail, name="producto_detail"),


    path('panel/productos/editar/<int:id>/', views.editar_producto, name='editar_producto'),
    path('panel/productos/eliminar/<int:id>/', views.eliminar_producto, name='eliminar_producto'),

    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/agregar/<int:producto_id>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/restar/<int:producto_id>/', views.restar_del_carrito, name='restar_del_carrito'),
    path('carrito/quitar/<int:producto_id>/', views.quitar_del_carrito, name='quitar_del_carrito'),
    path('carrito/limpiar/', views.limpiar_carrito, name='limpiar_carrito'),
    path('checkout/', views.procesar_pedido, name='procesar_pedido'),
    path('pedido-confirmado/<int:pedido_id>/', views.pedido_confirmado, name='pedido_confirmado'),

    path('panel/pedidos/', views.panel_pedidos, name='panel_pedidos'),
    path('panel/pedidos/<int:id>/', views.detalle_pedido, name='detalle_pedido'),
    path('panel/pedidos/<int:id>/confirmar/', views.confirmar_pago_pedido, name='confirmar_pago_pedido'),
    path('panel/productos/exportar/', views.exportar_stock_excel, name='exportar_stock_excel'),

    # Ruta pública para acceder al radar
    path('radar-bigday/', views.render_radar, name='radar_bigday'),
    
    # Ruta interna para que el JavaScript consulte a eBird
    path('api/ebird/<path:ebird_path>', views.ebird_proxy, name='ebird_proxy'),

]  