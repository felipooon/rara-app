from django.urls import path
from . import views

app_name = 'planificador'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/species/probable/', views.api_species_probable, name='species_probable'),
    path('api/hubs/', views.api_hubs, name='hubs'),
    path('api/regions/', views.api_regions, name='regions'),
    path('api/ebird/proxy/', views.api_ebird_proxy, name='ebird_proxy'),
    path('api/hotspots/', views.api_hotspots, name='hotspots'),
    path('api/recent-observations/', views.api_recent_observations, name='recent_obs'),
    path('api/notable-observations/', views.api_notable_observations, name='notable_obs'),
    path('api/weather/', views.api_weather, name='weather'),
    path('api/route/optimize/', views.api_optimize_route, name='optimize_route'),
    path('api/tides/', views.api_tides, name='tides'),
    path('api/tiles/<int:z>/<int:x>/<int:y>.png', views.api_osm_tile_proxy, name='osm_tile_proxy'),
]

