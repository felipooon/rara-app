# Rara Tienda

Plataforma e-commerce y panel de gestión integral desarrollada con Python y Django, orientada a la venta de productos ilustrados sobre flora y fauna nativa, divulgación didáctica y educación ambiental.

---

## Características Principales

### 🛒 Tienda y Experiencia de Usuario
- **Catálogo Dinámico**: Filtrado por categorías, ordenamiento por precio, novedades y nombre, con indicadores de stock disponible y agotado.
- **Carrito de Compras**: Persistencia en sesión, modal interactivo, cálculo de descuentos mediante cupones y desglose de totales.
- **Proceso de Checkout**: Validación de RUT chileno, selección de dirección de despacho, integración con pasarela de pagos Mercado Pago y generación de órdenes únicas.
- **Sistema de Reseñas Verificadas**: Generación de enlaces tokenizados para evaluar compras completas o productos individuales con distinción de comprador verificado y calificación por estrellas.
- **Sección Educativa y Minijuegos**:
  - Catálogo didáctico e integración con API eBird para avistamientos.
  - Radar de aves nativas en tiempo real (`/juegos/radar-realtime/`).
  - Minijuegos interactivos (Memorice, Letras Locas, Rosco y Quiz de Aves).
- **Blog Educativo**: Publicación de artículos didácticos, autoría personalizada, formateador de texto HTML, integración de videos de YouTube en 16:9 y vinculación con productos destacados.
- **Páginas de Error Personalizadas**: Vistas diseñadas para errores 404 (página no encontrada) y 500 (error de servidor).

### 🧑‍💻 Panel de Administración Personalizado (`/panel/`)
- **Dashboard Ejecutivo**: Métricas de ventas mensuales, control de pedidos pendientes/pagados, alertas de stock agotado y ranking de productos más vendidos.
- **Gestión de Productos**:
  - Filtros por categoría y estado.
  - Exportación de catálogo completo a Excel (`.xlsx`).
  - Generador de enlaces de valoración ⭐ con modal sutil y accesos directos para copiar o enviar por WhatsApp.
- **Gestión de Pedidos y Despachos**: Cambio de estados (Pendiente, Pagado, Enviado, Entregado, Cancelado), asignación de empresa de transporte, número de seguimiento y envío automático de correos con la guía de despacho.
- **Gestión de Cupones**: Creación de cupones de porcentaje o monto fijo, límite de usos y fecha de expiración.
- **Moderación de Reseñas y Blog**: Editor de entradas de blog y panel de aprobación/ocultamiento de testimonios de clientes.
- **Configuración del Sitio**: Control de visibilidad pública del blog y reseñas.
- **Guía del Panel**: Manual de uso integrado con índice de navegación en `/panel/guia/`.

### 🛡️ Sistema de Auditoría y Trazabilidad (Django Admin `/phytotoma-rara/`)
- **`LogProducto`**: Registro automatizado de creación, modificaciones especificando campos alterados (precio anterior vs. nuevo, stock), cambios de visibilidad, ventas realizadas (`VENTA`) y eliminación física de productos.
- **`LogPedido`**: Historial técnico de transacciones, creación de órdenes, respuestas de la pasarela de pago (incluyendo diagnósticos en caso de fallos en la pasarela), cambios de estado y registros de despachos.

---

## Tecnologías Utilizadas

- **Backend**: Python, Django, Gunicorn, PostgreSQL, `dj-database-url`.
- **Frontend**: HTML5, Vanilla CSS (Diseño responsivo y Glassmorphism), JavaScript (ES6+), Font Awesome, Google Fonts (Inter, Outfit).
- **Integraciones & Herramientas**: Mercado Pago SDK, eBird API, WhiteNoise (Gestión de archivos estáticos en producción), OpenPyXL (Reportes Excel).
- **SEO**: Sitemap XML dinámico (`django.contrib.sitemaps`) y configuración de `robots.txt`.

---

## Estructura de Rutas Principales

### Públicas
- `/` — Portada y productos destacados.
- `/categoria/<slug>/` — Catálogo filtrado por categoría.
- `/producto/<slug>/` — Detalle del producto y reseñas verificadas.
- `/ver-carrito/` / `/checkout/` — Carrito de compras y proceso de pago.
- `/pedido-confirmado/<id>/` — Confirmación y resumen de la compra.
- `/blog/` / `/blog/<slug>/` — Artículos del blog educativo.
- `/juegos/` — Menú de juegos y herramientas didácticas.
- `/evaluar-compra/<token>/` — Formulario de evaluación tokenizado.

### Administración
- `/panel/` — Dashboard del panel de administración.
- `/panel/productos/` — Gestión de inventario y generador de enlaces de reseña.
- `/panel/pedidos/` — Control de ventas y envíos.
- `/panel/cupones/` — Administración de descuentos.
- `/panel/blog/` — Editor y lista de artículos.
- `/panel/guia/` — Manual del panel de administración.
- `/phytotoma-rara/` — Django Admin nativo para consulta de auditoría y logs.

---

## Configuración e Instalación Local

1. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/felipooon/rara-app.git
   cd rara-app
   ```

2. **Crear y activar entorno virtual**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Linux/macOS
   # venv\Scripts\activate   # En Windows
   ```

3. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno (`.env`)**:
   ```env
   DEBUG=True
   SECRET_KEY=tu_secret_key
   MERCADOPAGO_ACCESS_TOKEN=tu_access_token
   EBIRD_API_KEY=tu_ebird_key
   ```

5. **Ejecutar migraciones e iniciar servidor**:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

---

## Autor

**Felipe Godoy**  
Proyecto personal — Rara Tienda