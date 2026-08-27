from django.urls import path
from . import views
from .views import CustomLoginView
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path("", views.index, name="index"),
    path("categoria/<slug:slug>/", views.categoria_detail, name="categoria"),
    path("terminos/", views.terminos_condiciones, name="terminos"),

    # PANEL
    path("panel/", views.panel_home, name="panel_home"),
    path("panel/productos/", views.panel_productos, name="panel_productos"),
    path("panel/productos/crear/", views.crear_producto, name="crear_producto"),
    path("panel/categorias/crear/", views.crear_categoria, name="crear_categoria"),
    path("panel/productos/<int:id>/toggle/", views.toggle_producto, name="toggle_producto"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    path("producto/<slug:slug>/", views.producto_detail, name="producto_detail_slug"),
    path("producto/<int:id>/", views.producto_detail_by_id, name="producto_detail"),


    path('panel/productos/editar/<int:id>/', views.editar_producto, name='editar_producto'),
    path('panel/productos/eliminar/<int:id>/', views.eliminar_producto, name='eliminar_producto'),

    path('panel/pedidos/', views.panel_pedidos, name='panel_pedidos'),
    path('panel/pedidos/<int:id>/', views.detalle_pedido, name='detalle_pedido'),
    path('panel/pedidos/<int:id>/confirmar/', views.confirmar_pago_pedido, name='confirmar_pago_pedido'),
    path('panel/productos/exportar/', views.exportar_stock_excel, name='exportar_stock_excel'),

    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/agregar/<int:producto_id>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/restar/<int:producto_id>/', views.restar_del_carrito, name='restar_del_carrito'),
    path('carrito/quitar/<int:producto_id>/', views.quitar_del_carrito, name='quitar_del_carrito'),
    path('carrito/limpiar/', views.limpiar_carrito, name='limpiar_carrito'),
    path('checkout/', views.procesar_pedido, name='procesar_pedido'),
    path('pedido-confirmado/<int:pedido_id>/', views.pedido_confirmado, name='pedido_confirmado'),

    path('webhook/mercadopago/', views.webhook_mercadopago, name='webhook_mercadopago'),

    

    # API Búsqueda en vivo y Cupones
    path('api/buscar-productos/', views.api_buscar_productos, name='api_buscar_productos'),
    path('carrito/aplicar-cupon/', views.aplicar_cupon, name='aplicar_cupon'),
    path('carrito/quitar-cupon/', views.quitar_cupon, name='quitar_cupon'),

    # Panel - Cupones
    path('panel/cupones/', views.panel_cupones, name='panel_cupones'),
    path('panel/cupones/crear/', views.crear_cupon, name='crear_cupon'),
    path('panel/cupones/editar/<int:id>/', views.editar_cupon, name='editar_cupon'),
    path('panel/cupones/<int:id>/toggle/', views.toggle_cupon, name='toggle_cupon'),

    # Panel - Pedidos avanzadas
    path('panel/pedidos/exportar/', views.exportar_pedidos_excel, name='exportar_pedidos_excel'),
    path('panel/pedidos/<int:id>/actualizar-estado/', views.actualizar_estado_pedido, name='actualizar_estado_pedido'),
    path('panel/pedidos/<int:id>/enviar-seguimiento/', views.enviar_seguimiento_email, name='enviar_seguimiento_email'),

    # Ruta pública para acceder al radar
    path('api/ebird/<path:ebird_path>', views.ebird_proxy, name='ebird_proxy'),
    path('api/diccionario-especies/', views.get_species_dict, name='species_dict'),
    
    # Juegos
    path('juegos/', views.menu_juegos, name='menu_juegos'),
    path('juegos/quien-es-esta-ave/', views.quien_es_esta_ave, name='quien_es_esta_ave'),
    path('juegos/memorice/', views.memorice, name='memorice'),
    path('juegos/letras-locas/', views.letras_locas, name='letras_locas'),
    path('juegos/trivia-cientifica/', views.minijuego, name='minijuego'),
    path('juegos/rosco/', views.rosco, name='rosco'),
    path('juegos/aves-en-tu-zona/', views.aves_en_tu_zona, name='aves_en_tu_zona'),
    path('juegos/radar-realtime/', views.radar_realtime, name='radar_realtime'),

    # Blog y Reseñas Públicas
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('producto/<int:producto_id>/resena/', views.agregar_resena, name='agregar_resena'),

    # Panel Admin - Configuración, Blog y Reseñas
    path('panel/configuracion/', views.panel_configuracion, name='panel_configuracion'),
    path('panel/blog/', views.panel_blog, name='panel_blog'),
    path('panel/blog/crear/', views.crear_blog_post, name='crear_blog_post'),
    path('panel/blog/editar/<int:id>/', views.editar_blog_post, name='editar_blog_post'),
    path('panel/blog/eliminar/<int:id>/', views.eliminar_blog_post, name='eliminar_blog_post'),
    path('panel/resenas/', views.panel_resenas, name='panel_resenas'),
    path('panel/resenas/<int:id>/toggle/', views.toggle_resena, name='toggle_resena'),
    path('panel/resenas/<int:id>/eliminar/', views.eliminar_resena, name='eliminar_resena'),

]  