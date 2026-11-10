// Rara Tienda • Planificador de Pajareo - Route Planner & Map Integration

let routeMap = null;
let routeLayerGroup = null;
let currentRouteData = null;

function initRouteMap() {
  if (routeMap) return;

  const mapElement = document.getElementById('routeMap');
  if (!mapElement) return;

  // Center on Región de Los Lagos (Lake Llanquihue area)
  routeMap = L.map('routeMap', {
    center: [-41.35, -73.05],
    zoom: 9,
    zoomControl: true
  });

  // High-resolution Satellite & Terrain providers (Satellite Hybrid by default)
  const googleSatHybrid = L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
    subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
    attribution: 'Imágenes satelitales &copy; Google Maps',
    maxZoom: 20
  });

  const esriSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: '&copy; Esri, Maxar, Earthstar Geographics',
    maxZoom: 19
  });

  const googleTerrain = L.tileLayer('https://{s}.google.com/vt/lyrs=p&x={x}&y={y}&z={z}', {
    subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
    attribution: 'Terreno &copy; Google Maps',
    maxZoom: 20
  });

  const esriTopo = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; National Geographic, USGS, DeLorme',
    maxZoom: 19
  });

  const osmProxied = L.tileLayer('/planificador/api/tiles/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
  });

  // Default view: Satellite Hybrid (high-resolution satellite imagery + road/place labels)
  googleSatHybrid.addTo(routeMap);

  // Add layer switcher control in top-right
  const baseLayers = {
    'Satélite Híbrido con Rutas (Por defecto)': googleSatHybrid,
    'Satélite Puro sin Etiquetas (Esri)': esriSatellite,
    'Relieve y Terreno (Google)': googleTerrain,
    'Mapa Topográfico (Esri)': esriTopo,
    'OpenStreetMap (OSM)': osmProxied
  };

  L.control.layers(baseLayers, null, { position: 'topright' }).addTo(routeMap);

  routeLayerGroup = L.layerGroup().addTo(routeMap);
}

// Date formatting & Southern Hemisphere Season helpers
const SPANISH_DAYS = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
const SPANISH_MONTHS = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
const SPANISH_MONTHS_SHORT = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

function getLocalTodayIso() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function getSouthernSeason(month1to12, day) {
  const md = month1to12 * 100 + day;
  if (md >= 1221 || md < 320) return 'Verano austral';
  if (md >= 320 && md < 621) return 'Otoño austral';
  if (md >= 621 && md < 921) return 'Invierno austral';
  return 'Primavera austral';
}

function formatSpanishDateLabels(dateStr) {
  const fallback = getLocalTodayIso();
  const cleanStr = (dateStr && /^\d{4}-\d{2}-\d{2}$/.test(dateStr)) ? dateStr : fallback;
  const [y, m, d] = cleanStr.split('-').map(Number);
  const dt = new Date(y, m - 1, d, 12, 0, 0);
  const dayName = SPANISH_DAYS[dt.getDay()];
  const monthName = SPANISH_MONTHS[m - 1];
  const monthShort = SPANISH_MONTHS_SHORT[m - 1];
  return {
    iso: cleanStr,
    fullLabel: `${dayName}, ${d} de ${monthName}`,
    dayMonthLong: `${d} de ${monthName}`,
    shortLabel: `${d} ${monthShort}`,
    season: getSouthernSeason(m, d)
  };
}

function updateDateSelectorUI(dateStr) {
  const info = formatSpanishDateLabels(dateStr);
  const dateInput = document.getElementById('routeDate');
  if (dateInput && dateInput.value !== info.iso) {
    dateInput.value = info.iso;
  }
  const formattedEl = document.getElementById('routeDateFormatted');
  if (formattedEl) {
    formattedEl.textContent = info.fullLabel;
  }
  const seasonEl = document.getElementById('routeSeasonBadge');
  if (seasonEl) {
    seasonEl.textContent = info.season;
  }
  return info;
}

function setQuickRouteDate(preset) {
  const now = new Date();
  let targetIso;
  if (preset === 'tomorrow') {
    now.setDate(now.getDate() + 1);
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    targetIso = `${y}-${m}-${d}`;
  } else if (preset === 'bigday') {
    targetIso = `${now.getFullYear()}-10-10`;
  } else {
    targetIso = getLocalTodayIso();
  }
  updateDateSelectorUI(targetIso);
  generateOptimalRoute();
}

function applyRegionConfigToForm(regionCode, shouldRecalculate = false) {
  const allRegions = window.CHILE_REGIONS_CONFIG || {};
  const cfg = allRegions[regionCode] || allRegions['CL-LL'];
  if (!cfg) return;

  const macrozoneEl = document.getElementById('routeMacrozoneBadge');
  if (macrozoneEl) {
    macrozoneEl.textContent = cfg.macrozone || '';
  }

  // Update Punto de Partida (Base) hubs
  const hubSelect = document.getElementById('routeHub');
  if (hubSelect && cfg.hubs) {
    hubSelect.innerHTML = '';
    Object.entries(cfg.hubs).forEach(([hubId, hubInfo]) => {
      const opt = document.createElement('option');
      opt.value = hubId;
      opt.textContent = hubInfo.name;
      if (hubId === cfg.default_hub) opt.selected = true;
      hubSelect.appendChild(opt);
    });
  }

  // Update Corredor o Subzona
  const subzoneSelect = document.getElementById('routeSubzone');
  if (subzoneSelect && Array.isArray(cfg.subzones)) {
    subzoneSelect.innerHTML = '';
    cfg.subzones.forEach((sz, idx) => {
      const opt = document.createElement('option');
      opt.value = sz.id;
      opt.textContent = sz.name;
      if (idx === 0) opt.selected = true;
      subzoneSelect.appendChild(opt);
    });
  }

  // Update Enfoque de Observación
  const focusSelect = document.getElementById('routeFocus');
  if (focusSelect && Array.isArray(cfg.focus_options)) {
    focusSelect.innerHTML = '';
    cfg.focus_options.forEach((fo, idx) => {
      const opt = document.createElement('option');
      opt.value = fo.id;
      opt.textContent = fo.name;
      if (idx === 0) opt.selected = true;
      focusSelect.appendChild(opt);
    });
  }

  // Update Biological Strategy Tip Box
  const bioTitleEl = document.getElementById('bioTipTitle');
  if (bioTitleEl) {
    bioTitleEl.textContent = `Estrategia de Pajareo en ${cfg.short_name}`;
  }
  const bioTextEl = document.getElementById('bioTipText');
  if (bioTextEl && cfg.bio_strategy) {
    bioTextEl.textContent = cfg.bio_strategy;
  }

  // Recenter map on region
  if (routeMap && Array.isArray(cfg.center)) {
    routeMap.setView(cfg.center, cfg.zoom || 8);
  }

  // Sync Radar Region Selector & title
  const radarSelect = document.getElementById('radarRegionSelect');
  if (radarSelect && radarSelect.value !== regionCode) {
    radarSelect.value = regionCode;
  }
  const radarTitleEl = document.getElementById('radarTitle');
  if (radarTitleEl) {
    radarTitleEl.textContent = `Radar de Especies — ${cfg.name}`;
  }

  // If Radar tab is currently active, reload radar for the new region
  const radarPane = document.getElementById('pane-radar');
  if (radarPane && radarPane.classList.contains('active') && typeof loadSpeciesRadar === 'function') {
    loadSpeciesRadar(regionCode);
  }

  if (shouldRecalculate) {
    generateOptimalRoute();
  }
}

function applyRouteModePreset(mode) {
  const stopsEl = document.getElementById('routeStops');
  const durEl = document.getElementById('routeDuration');
  const paceEl = document.getElementById('routePace');
  if (!stopsEl || !durEl || !paceEl) return;

  if (mode === 'half_day') {
    stopsEl.value = '4';
    durEl.value = '6';
    paceEl.value = 'relaxed';
  } else if (mode === 'extended') {
    stopsEl.value = '8';
    durEl.value = '12';
    paceEl.value = 'tactical';
  } else if (mode === 'big_day') {
    stopsEl.value = '10';
    durEl.value = '14';
    paceEl.value = 'blitz';
  } else {
    // full_day (default flexible)
    stopsEl.value = '6';
    durEl.value = '12';
    paceEl.value = 'standard';
  }
  generateOptimalRoute();
}

function scrollToRouteChecklist() {
  const el = document.getElementById('routeSpeciesSection');
  if (el) {
    el.scrollIntoView({ behavior: 'smooth' });
  }
}

// Custom Leaflet marker icons with numbers and habitat colors
function createCustomPin(number, color = '#10b981') {
  return L.divIcon({
    className: 'custom-map-pin',
    html: `
      <div style="
        background: ${color};
        color: #fff;
        width: 32px;
        height: 32px;
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        border: 2px solid #ffffff;
      ">
        <span style="
          transform: rotate(45deg);
          font-family: 'Outfit', sans-serif;
          font-weight: 700;
          font-size: 13px;
        ">${number}</span>
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 32],
    popupAnchor: [0, -32]
  });
}

async function generateOptimalRoute() {
  const btn = document.getElementById('btnCalculateRoute');
  const btnText = document.getElementById('btnCalculateRouteText');
  const spinner = document.getElementById('btnCalculateRouteSpinner');

  const region = document.getElementById('routeRegion')?.value || 'CL-LL';
  const hub = document.getElementById('routeHub').value;
  const subzone = document.getElementById('routeSubzone').value;
  const focus = document.getElementById('routeFocus').value;
  const duration = parseFloat(document.getElementById('routeDuration').value);
  const maxStops = parseInt(document.getElementById('routeStops').value);
  const startTime = document.getElementById('routeStartTime').value;
  const pace = document.getElementById('routePace') ? document.getElementById('routePace').value : 'blitz';

  let customStartLat = null;
  let customStartLng = null;
  if (hub && hub.startsWith('custom_')) {
    const parts = hub.split('_');
    if (parts.length >= 3) {
      customStartLat = parseFloat(parts[1]);
      customStartLng = parseFloat(parts[2]);
    }
  }

  btn.disabled = true;
  btnText.textContent = 'Calculando ruta óptima...';
  spinner.style.display = 'inline-block';

  const todayStr = getLocalTodayIso();
  const targetDate = document.getElementById('routeDate')?.value || todayStr;
  updateDateSelectorUI(targetDate);
  const apiBase = window.PLANIFICADOR_API_BASE || '/planificador/api';

  try {
    const res = await fetch(`${apiBase}/route/optimize/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        region,
        hub,
        start_lat: customStartLat,
        start_lng: customStartLng,
        date: targetDate,
        subzone,
        focus,
        duration_hours: duration,
        max_stops: maxStops,
        start_time: startTime,
        pace: pace,
        is_big_day: maxStops >= 7 || pace === 'blitz'
      })
    });

    if (!res.ok) throw new Error('Error al optimizar la ruta');

    const data = await res.json();
    currentRouteData = data;
    renderRouteResults(data);
  } catch (err) {
    console.error(err);
    alert('No se pudo generar la ruta. Verifica la conexión o los parámetros.');
  } finally {
    btn.disabled = false;
    btnText.textContent = 'Actualizar Planificación';
    spinner.style.display = 'none';
  }
}

function renderRouteResults(data) {
  const summary = data.summary;
  const stops = data.stops || [];
  const dateInfo = formatSpanishDateLabels(summary.target_date || document.getElementById('routeDate')?.value);
  const probableList = data.all_probable_species || [];

  // Render Compact Metric Ribbon
  const spCountEl = document.getElementById('metricSpeciesCount');
  if (spCountEl) {
    spCountEl.textContent = `${stops.length} paradas • ${probableList.length || summary.estimated_total_species} esp.`;
  }
  const kmEl = document.getElementById('metricTotalKm');
  if (kmEl) {
    kmEl.textContent = `${summary.total_km} km totales`;
  }
  const sunTimesEl = document.getElementById('metricSunTimes');
  if (sunTimesEl) {
    sunTimesEl.textContent = `${summary.sunrise} – ${summary.sunset}`;
  }

  const sunLabelEl = document.getElementById('metricSunLabel');
  if (sunLabelEl) {
    sunLabelEl.textContent = `Luz Solar (${dateInfo.shortLabel})`;
  }

  const tideLabelEl = document.getElementById('metricTideLabel');
  const tideEl = document.getElementById('metricTideTimes');
  if (summary.tides && summary.tides.is_coastal === false) {
    if (tideLabelEl) tideLabelEl.textContent = `Zona Interior (${dateInfo.shortLabel})`;
    if (tideEl) tideEl.textContent = 'Sin influencia mareal directa';
  } else {
    if (tideLabelEl) {
      const shortPhase = summary.tides?.short_phase || 'Mareas';
      const portName = summary.tides?.port_name ? ` (${summary.tides.port_name})` : '';
      tideLabelEl.textContent = `${shortPhase}${portName}`;
    }
    if (tideEl) {
      if (summary.tides && summary.tides.events && summary.tides.events.length >= 2) {
        const lows = summary.tides.events.filter(e => e.type === 'Bajamar');
        const highs = summary.tides.events.filter(e => e.type === 'Pleamar');
        const b1 = lows[0] || summary.tides.events[0];
        const p1 = highs[highs.length > 1 ? 1 : 0] || summary.tides.events[1];
        tideEl.textContent = `Baja ${b1.time} (${b1.height_m}m) / Alta ${p1.time} (${p1.height_m}m)`;
      } else {
        tideEl.textContent = 'Baja 07:55 (0.7m) / Alta 14:15 (6.5m)';
      }
    }
  }

  const itineraryTitleEl = document.getElementById('itineraryTitle');
  if (itineraryTitleEl) {
    itineraryTitleEl.textContent = `Ruta Sugerida por Bloques (${dateInfo.dayMonthLong})`;
  }

  // Update Guide tab tide card to match selected date
  const guideHeading = document.getElementById('guideTideHeading');
  if (guideHeading) {
    guideHeading.textContent = `Humedales Costeros y Dinámica de Mareas (${dateInfo.dayMonthLong})`;
  }
  const guideSubheading = document.getElementById('guideTideSubheading');
  if (guideSubheading) {
    guideSubheading.textContent = `Régimen de Mareas del ${dateInfo.dayMonthLong}:`;
  }
  const guideList = document.getElementById('guideTideList');
  if (guideList) {
    if (summary.tides && summary.tides.is_coastal === false) {
      guideList.innerHTML = `• Zona interior / valles precordilleranos sin influencia de mareas astronómicas directas.<br>• El ritmo biológico está determinado por el amanecer (${summary.sunrise}), la temperatura ambiente y la disponibilidad de alimento en el dosel y matorrales.`;
    } else if (summary.tides && summary.tides.events) {
      const evLines = summary.tides.events.map(ev => {
        const desc = ev.type === 'Bajamar'
          ? 'Planicies intermareales expuestas; alimentación activa de limícolas y flamencos.'
          : 'Agua alta cubre los llanos; las aves se concentran en dormideros costeros.';
        return `• <b>${ev.time} hrs (${ev.height_m}m) - ${ev.label}:</b> ${desc}`;
      }).join('<br>');
      guideList.innerHTML = `• Puerto de referencia: <b>${summary.tides.port_name || 'Litoral'}</b> • Fase Lunar: <b>${summary.tides.lunar_phase}</b> (amplitud ~${summary.tides.tidal_range_m}m).<br>${evLines}`;
    }
  }

  // Update Map: Connect Punto Base + Intermediate Stops + Tentative Corridor in a complete circuit
  initRouteMap();
  routeLayerGroup.clearLayers();

  const allBoundsLatLngs = [];
  const stopLatLngs = [];
  const origin = data.origin;
  allBoundsLatLngs.push([origin.lat, origin.lng]);

  const originMarker = L.marker([origin.lat, origin.lng], {
    icon: createCustomPin('★', '#06b6d4')
  }).bindPopup(`
    <div style="font-family: sans-serif; padding: 4px; min-width: 180px;">
      <div style="font-size: 11px; text-transform: uppercase; color: #0284c7; font-weight: 800;">
        Punto Base (Partida y Retorno)
      </div>
      <h4 style="margin: 4px 0 2px 0; font-size: 13px; font-weight: 700; color: #0f172a;">${origin.name}</h4>
      <div style="font-size: 11.5px; color: #475569; margin-top: 4px;">
        Salida: <b>${data.summary.start_time} hrs</b><br>
        Retorno estimado: <b>${data.summary.finish_time} hrs</b>
      </div>
    </div>
  `);
  routeLayerGroup.addLayer(originMarker);

  stops.forEach((stop) => {
    allBoundsLatLngs.push([stop.lat, stop.lng]);
    stopLatLngs.push([stop.lat, stop.lng]);
    const blockText = stop.day_block_short || 'En ruta';
    const isEnRoute = stop.stop_role === 'en_route';
    const pinColor = isEnRoute ? '#0284c7' : '#ea580c';
    const roleBadgeText = isEnRoute ? 'Punto Intermedio de Camino' : (stop.stop_role_label || 'Ruta Tentativa');

    const marker = L.marker([stop.lat, stop.lng], {
      icon: createCustomPin(stop.stop_number, pinColor)
    }).bindPopup(`
      <div style="font-family: sans-serif; min-width: 215px; padding: 4px;">
        <div style="font-size: 11px; text-transform: uppercase; color: ${isEnRoute ? '#0284c7' : '#ea580c'}; font-weight: 700;">
          Parada ${stop.stop_number} • ${roleBadgeText}
        </div>
        <h4 style="margin: 4px 0; font-size: 14px; font-weight: 700; color: #0f172a;">${stop.locName}</h4>
        <div style="font-size: 12px; color: #475569; margin-bottom: 6px;">
          ${stop.habitat_label}
        </div>
        <div style="font-size: 12px; background: #f1f5f9; padding: 6px; border-radius: 6px; margin-bottom: 8px;">
          <b>${stop.activity.temp_c}°C</b> | Lluvia: <b>${stop.activity.rain_prob}%</b> | Viento: <b>${stop.activity.wind_kmh} km/h</b>
          ${stop.tide ? `<div style="margin-top: 4px; color: #0284c7; font-weight: 600;">Marea: ${stop.tide.status_label} (${stop.tide.height_m}m)</div>` : ''}
        </div>
        <a href="https://ebird.org/hotspot/${stop.locId}" target="_blank" style="color: #0284c7; text-decoration: none; font-size: 12px; font-weight: 600;">
          Ver hotspot en eBird ↗
        </a>
      </div>
    `);
    routeLayerGroup.addLayer(marker);
  });

  // Render Notable / Rare Species nearby on map
  window._notableMarkers = {};
  const nearbyNotables = data.nearby_notables || [];
  nearbyNotables.forEach(n => {
    allBoundsLatLngs.push([n.lat, n.lng]);
    const key = `${Number(n.lat).toFixed(4)},${Number(n.lng).toFixed(4)}`;
    const nMarker = L.marker([n.lat, n.lng], {
      icon: createCustomPin('⚡', '#f43f5e')
    }).bindPopup(`
      <div style="font-family: sans-serif; min-width: 215px; padding: 4px;">
        <div style="font-size: 11px; text-transform: uppercase; color: #f43f5e; font-weight: 800; display: flex; align-items: center; gap: 4px;">
          <span>⚡ Registro Destacado eBird</span>
        </div>
        <h4 style="margin: 4px 0 2px 0; font-size: 13.5px; font-weight: 700; color: #0f172a;">${n.comName}</h4>
        <div style="font-size: 11.5px; font-style: italic; color: #64748b; margin-bottom: 4px;">${n.sciName}</div>
        <div style="font-size: 11.8px; color: #334155; margin-bottom: 6px; line-height: 1.4;">
          📍 <b>${n.locName}</b><br>
          🗓 <b>${n.obsDt}</b> ${n.howMany ? `• Cant.: <b>${n.howMany}</b>` : ''}<br>
          📏 A <b>${n.distance_km} km</b> de la ruta (${n.nearest_stop_name || 'parada cercana'})
        </div>
        <div style="display: flex; gap: 8px; margin-top: 6px;">
          ${n.subId ? `<a href="https://ebird.org/checklist/${n.subId}" target="_blank" style="color: #f43f5e; font-size: 11.5px; font-weight: 700; text-decoration: none;">Ver Lista eBird ↗</a>` : `<a href="https://ebird.org/hotspot/${n.locId}" target="_blank" style="color: #f43f5e; font-size: 11.5px; font-weight: 700; text-decoration: none;">Ver Hotspot ↗</a>`}
        </div>
      </div>
    `);
    routeLayerGroup.addLayer(nMarker);
    window._notableMarkers[key] = nMarker;
  });

  // 1. Connection line from Punto Base to First Stop (Approach / Intermediate stop)
  if (stops.length > 0) {
    L.polyline([[origin.lat, origin.lng], [stops[0].lat, stops[0].lng]], {
      color: '#06b6d4',
      weight: 3.5,
      opacity: 0.85,
      dashArray: '6, 6',
      lineCap: 'round'
    }).addTo(routeLayerGroup);
  }

  // 2. Main route polyline connecting birding stops
  if (stopLatLngs.length >= 2) {
    L.polyline(stopLatLngs, {
      color: '#ea580c',
      weight: 4.5,
      opacity: 0.95,
      lineCap: 'round',
      lineJoin: 'round'
    }).addTo(routeLayerGroup);
  }

  // 3. Return polyline from Last Stop back to Punto Base
  if (stops.length > 0) {
    const lastStop = stops[stops.length - 1];
    L.polyline([[lastStop.lat, lastStop.lng], [origin.lat, origin.lng]], {
      color: '#94a3b8',
      weight: 2.8,
      opacity: 0.75,
      dashArray: '8, 8',
      lineCap: 'round'
    }).addTo(routeLayerGroup);
  }

  // Fit bounds to show both the Base and all route stops
  if (allBoundsLatLngs.length > 0) {
    routeMap.fitBounds(L.latLngBounds(allBoundsLatLngs), { padding: [50, 50] });
  }

  // Group Stops into 3 Flexible Day Blocks (Mañana, Mediodía, Tarde)
  const subzoneSelectEl = document.getElementById('routeSubzone');
  const activeCorridorLabel = subzoneSelectEl && subzoneSelectEl.selectedIndex >= 0
    ? subzoneSelectEl.options[subzoneSelectEl.selectedIndex].text
    : 'Corredor Regional';
  const firstStop = stops[0];
  const enRouteCount = data.summary.en_route_count || 0;

  const blocksConfig = [
    {
      key: 'morning',
      title: 'Bloque Mañana (Amanecer – 11:00 hrs)',
      subtitle: 'Primera luz y mayor actividad vocal en bosques, quebradas e interior',
      accent: '#059669',
      bg: 'rgba(5, 150, 105, 0.06)'
    },
    {
      key: 'midday',
      title: 'Bloque Mediodía (11:00 – 15:30 hrs)',
      subtitle: 'Humedales, riberas lacustres y sectores abiertos con buena visibilidad',
      accent: '#0284c7',
      bg: 'rgba(2, 132, 199, 0.06)'
    },
    {
      key: 'afternoon',
      title: 'Bloque Tarde (15:30 hrs – Ocaso)',
      subtitle: 'Estuarios, costa y retorno gradual aprovechando la luz de la tarde',
      accent: '#d97706',
      bg: 'rgba(217, 119, 6, 0.06)'
    }
  ];

  const timelineEl = document.getElementById('timelineContainer');

  let notablesBannerHtml = '';
  if (nearbyNotables && nearbyNotables.length > 0) {
    let pillsHtml = '';
    nearbyNotables.forEach(n => {
      const safeLoc = (n.locName || '').replace(/'/g, "\\'");
      const checklistUrl = n.subId ? `https://ebird.org/checklist/${n.subId}` : `https://ebird.org/hotspot/${n.locId}`;
      pillsHtml += `
        <div class="notable-pill-card">
          <div style="min-width: 200px; flex: 1;">
            <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
              <span style="font-weight: 700; color: #e11d48; font-size: 0.88rem;">⚡ ${n.comName}</span>
              <span style="font-size: 0.77rem; font-style: italic; color: var(--text-muted);">(${n.sciName})</span>
              <span style="background: rgba(244, 63, 94, 0.12); color: #e11d48; font-size: 0.68rem; font-weight: 700; padding: 1px 7px; border-radius: 999px;">
                a ${n.distance_km} km de la ruta
              </span>
            </div>
            <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px;">
              📍 ${n.locName} • 🗓 ${n.obsDt} ${n.howMany ? `(${n.howMany} ind.)` : ''}
            </div>
          </div>
          <div style="display: flex; gap: 6px; align-items: center;">
            <button type="button" class="btn-secondary" onclick="focusNotableOnMap(${n.lat}, ${n.lng}, '${safeLoc}')" style="padding: 3px 8px; font-size: 0.72rem; border-color: rgba(244, 63, 94, 0.4); color: #e11d48;">
              📍 Ver en Mapa
            </button>
            <a href="${checklistUrl}" target="_blank" class="stop-ebird-link" style="color: #e11d48; border-color: rgba(244, 63, 94, 0.35);">
              Lista eBird ↗
            </a>
          </div>
        </div>
      `;
    });

    notablesBannerHtml = `
      <div class="notable-alert-panel">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; flex-wrap: wrap; gap: 0.5rem;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1.15rem;">⚡</span>
            <div>
              <h4 style="margin: 0; font-family: var(--font-heading); font-size: 0.94rem; font-weight: 700; color: #e11d48;">
                Rarezas y Registros Notables Cercanos (${nearbyNotables.length})
              </h4>
              <p style="margin: 2px 0 0 0; font-size: 0.75rem; color: var(--text-secondary);">
                Aves inusuales reportadas en eBird en los últimos 14 días a &le; 32 km de tu itinerario
              </p>
            </div>
          </div>
          <span style="background: rgba(244, 63, 94, 0.12); color: #be123c; font-size: 0.7rem; font-weight: 700; padding: 2px 8px; border-radius: 999px;">
            Últimos 14 días
          </span>
        </div>
        <div class="notable-pills-row">
          ${pillsHtml}
        </div>
      </div>
    `;
  }

  let timelineHtml = notablesBannerHtml + `
    <!-- Base Point & Corridor Circuit Summary Card -->
    <div class="base-route-summary-grid">
      <div class="base-route-summary-card base-card">
        <div class="base-route-icon" style="background: #06b6d4;">
          ★
        </div>
        <div style="min-width: 0;">
          <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; color: #0284c7; font-weight: 800;">
            Punto Base (Salida y Retorno)
          </div>
          <div style="font-size: 0.94rem; font-weight: 700; color: var(--text-primary); margin-top: 1px;">
            ${origin.name}
          </div>
          <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px;">
            Salida: <b>${data.summary.start_time} hrs</b> • Retorno est.: <b>${data.summary.finish_time} hrs</b>
          </div>
        </div>
      </div>

      <div class="base-route-summary-card route-card">
        <div class="base-route-icon" style="background: #ea580c; font-size: 0.88rem;">
          1–${stops.length}
        </div>
        <div style="min-width: 0;">
          <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; color: #c2410c; font-weight: 800;">
            Ruta Tentativa Seleccionada
          </div>
          <div style="font-size: 0.94rem; font-weight: 700; color: var(--text-primary); margin-top: 1px;">
            ${activeCorridorLabel}
          </div>
          <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px;">
            ${stops.length} paradas ${enRouteCount > 0 ? `(${enRouteCount} punto${enRouteCount > 1 ? 's' : ''} intermedio${enRouteCount > 1 ? 's' : ''} de camino)` : 'en circuito continuo'}
          </div>
        </div>
      </div>
    </div>
  `;

  blocksConfig.forEach(block => {
    const blockStops = stops.filter(s => (s.day_block || 'morning') === block.key);
    if (blockStops.length === 0) return;

    timelineHtml += `
      <div class="day-block-group" style="margin-bottom: 1.35rem;">
        <div class="day-block-header" style="background: ${block.bg}; border-left: 4px solid ${block.accent};">
          <div>
            <h4 style="margin: 0; font-family: var(--font-heading); font-size: 0.98rem; font-weight: 700; color: var(--text-primary);">
              ${block.title}
            </h4>
            <p style="margin: 2px 0 0 0; font-size: 0.77rem; color: var(--text-secondary);">
              ${block.subtitle}
            </p>
          </div>
          <span class="day-block-count" style="color: ${block.accent};">
            ${blockStops.length} ${blockStops.length === 1 ? 'parada sugerida' : 'paradas sugeridas'}
          </span>
        </div>

        <div style="display: flex; flex-direction: column; gap: 0.85rem;">
    `;

    blockStops.forEach(stop => {
      const isEnRoute = stop.stop_role === 'en_route';
      const rainColor = stop.activity.rain_prob > 40 ? '#f43f5e' : '#10b981';
      const transferLabel = stop.stop_number === 1
        ? `Desde Punto Base (${origin.name.split('(')[0].trim()}): ~${stop.drive_time_from_prev_min} min (${stop.distance_from_prev_km} km)`
        : `Traslado anterior: ~${stop.drive_time_from_prev_min} min (${stop.distance_from_prev_km} km)`;

      const roleBadge = isEnRoute ? `
        <span style="font-size: 0.72rem; background: rgba(2, 132, 199, 0.12); color: #0284c7; border: 1px solid rgba(2, 132, 199, 0.3); padding: 2px 8px; border-radius: 999px; font-weight: 700;">
          Punto Intermedio de Camino
        </span>
      ` : '';

      const tideChip = stop.tide ? `
        <span class="stop-tide-chip">
          Marea: ${stop.tide.status_label} (${stop.tide.height_m}m)
        </span>
      ` : '';

      let birdPills = '';
      (stop.target_species || []).forEach(sp => {
        birdPills += `
          <span class="bird-pill ${sp.isTarget ? 'target-highlight' : ''}">
            <b>${sp.comName}</b>
            <span class="sci-name">(${sp.sciName})</span>
          </span>
        `;
      });

      timelineHtml += `
        <div class="timeline-card stop-card-item" style="${isEnRoute ? 'border-left: 3px solid #0284c7;' : ''}">
          <div class="stop-card-top">
            <div class="stop-card-main-info">
              <div class="stop-card-title-row">
                <span class="stop-number-badge" style="background: ${isEnRoute ? '#0284c7' : block.accent};">Parada ${stop.stop_number}</span>
                <span class="stop-title">${stop.locName}</span>
                ${roleBadge}
              </div>
              <div class="stop-card-meta-row">
                <span class="habitat-badge" style="margin: 0;">${stop.habitat_label}</span>
                <span class="stop-meta-dot">•</span>
                <span class="stop-transfer-text">${transferLabel}</span>
              </div>
            </div>

            <div class="stop-card-weather-row">
              ${tideChip}
              <div class="weather-chip" style="padding: 3px 8px; font-size: 0.75rem;">
                <span class="temp">${stop.activity.temp_c}°C</span>
                <span class="rain" style="color: ${rainColor};">Lluvia ${stop.activity.rain_prob}%</span>
                <span class="wind">${stop.activity.wind_kmh} km/h</span>
              </div>
              <a href="https://ebird.org/hotspot/${stop.locId}" target="_blank" class="stop-ebird-link">
                eBird ↗
              </a>
              <div class="ebird-tip-anchor">
                <button type="button" class="ebird-tip-pill-btn" onclick="toggleEbirdStopTip(event, ${stop.stop_number})" title="Ver consejo para registrar este sitio en eBird">
                  ℹ Tip eBird
                </button>
                <div id="ebirdStopTip_${stop.stop_number}" class="ebird-tip-popover" style="display: none;" onclick="event.stopPropagation()">
                  <div class="ebird-popover-arrow"></div>
                  <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
                    <span style="font-size: 0.78rem; font-weight: 700; color: #0284c7; display: flex; align-items: center; gap: 4px;">
                      💡 Consejo eBird:
                    </span>
                    <button type="button" onclick="toggleEbirdStopTip(event, ${stop.stop_number})" style="background: none; border: none; font-size: 1.15rem; line-height: 1; cursor: pointer; color: var(--text-muted); padding: 0 4px;">&times;</button>
                  </div>
                  <p style="margin: 5px 0 7px 0; font-size: 0.75rem; color: var(--text-secondary); line-height: 1.45;">
                    ${getStopEbirdAdvice(stop)}
                  </p>
                  <div style="display: flex; gap: 6px; flex-wrap: wrap; align-items: center; justify-content: space-between; border-top: 1px dashed rgba(2, 132, 199, 0.2); padding-top: 5px; margin-top: 4px;">
                    <span style="font-size: 0.69rem; color: var(--text-muted);">
                      Protocolo: <b>${isEnRoute ? 'Con desplazamiento (< 1 km)' : 'Desplazamiento (1-2 km) o Estacionario'}</b>
                    </span>
                    <a href="https://ebird.org/submit" target="_blank" class="ebird-open-submit-btn" style="padding: 2px 8px; font-size: 0.71rem;">
                      Subir Lista ↗
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="stop-card-species-box">
            <div style="font-size: 0.74rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 0.35rem;">
              Especies clave en este punto (${stop.numSpeciesAllTime} históricas en eBird):
            </div>
            <div class="target-species-list" style="margin-top: 0;">
              ${birdPills}
            </div>
          </div>
        </div>
      `;
    });

    timelineHtml += `
        </div>
      </div>
    `;
  });

  // Add final circuit card: Return to Punto Base
  timelineHtml += `
    <div class="timeline-card" style="padding: 0.9rem 1.15rem; background: rgba(148, 163, 184, 0.05); border: 1px dashed var(--border-color); border-radius: var(--radius-md); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.5rem;">
      <div style="display: flex; align-items: center; gap: 0.75rem;">
        <div style="width: 32px; height: 32px; border-radius: 50%; background: #64748b; color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.95rem; flex-shrink: 0;">
          ↩
        </div>
        <div>
          <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); font-weight: 800;">
            Retorno a Punto Base
          </div>
          <div style="font-size: 0.94rem; font-weight: 700; color: var(--text-primary); margin-top: 1px;">
            ${origin.name}
          </div>
        </div>
      </div>
      <div style="font-size: 0.78rem; color: var(--text-secondary); text-align: right;">
        Traslado final: <b>~${data.summary.return_drive_minutes || 35} min</b> (${data.summary.return_distance_km || 25} km)<br>
        Llegada estimada: <b>${data.summary.finish_time} hrs</b>
      </div>
    </div>
  `;

  timelineEl.innerHTML = timelineHtml;
  document.getElementById('routeResultsSection').style.display = 'block';

  // Render Route-Specific Probable Species Checklist
  currentProbableSpecies = probableList;
  renderProbableSpeciesChecklist(currentProbableSpecies);
}

// Master Probable Species Checklist Logic
let currentProbableSpecies = [];
let checkedSpecies = new Set();
let currentGroupFilter = 'all';

function renderProbableSpeciesChecklist(speciesList) {
  const container = document.getElementById('probableSpeciesContainer');
  if (!container) return;

  const countBadge = document.getElementById('checklistProgressBadge');
  const subtitle = document.getElementById('masterChecklistSubtitle');

  const total = currentProbableSpecies.length;
  const checked = checkedSpecies.size;

  if (countBadge) {
    countBadge.textContent = `✓ ${checked} / ${total} Marcadas`;
  }

  if (subtitle) {
    const regName = currentRouteData?.summary?.region_name || 'la región seleccionada';
    subtitle.textContent = `Mostrando ${speciesList.length} de ${total} especies asociadas a tu ruta en ${regName}`;
  }

  if (!speciesList || speciesList.length === 0) {
    container.innerHTML = `
      <div style="padding: 2rem; text-align: center; color: var(--text-muted);">
        <p>No se encontraron especies con ese filtro.</p>
      </div>
    `;
    return;
  }

  let html = `<div class="checklist-table-wrapper">`;

  speciesList.forEach((sp) => {
    const isChecked = checkedSpecies.has(sp.speciesCode);
    let probTagClass = 'ocasional';
    if (sp.probability.includes('Muy Alta')) probTagClass = 'muy-alta';
    else if (sp.probability.includes('Alta')) probTagClass = 'alta';
    else if (sp.probability.includes('Media')) probTagClass = 'media';

    html += `
      <div class="checklist-item-row ${isChecked ? 'checked' : ''}" id="row_sp_${sp.speciesCode}">
        <input 
          type="checkbox" 
          class="checklist-checkbox" 
          ${isChecked ? 'checked' : ''} 
          onchange="toggleSpeciesCheck('${sp.speciesCode}')"
          id="chk_${sp.speciesCode}"
        >
        <div class="spp-name-col">
          <label for="chk_${sp.speciesCode}" class="spp-name" style="cursor: pointer;">
            ${sp.comName}
          </label>
          <span class="spp-sci">${sp.sciName}</span>
          <span class="spp-mobile-stop">Parada #${sp.best_stop_number || 1}: ${sp.best_stop_name}</span>
        </div>
        <span class="group-badge">${sp.groupName}</span>
        <span class="prob-tag ${probTagClass}">${sp.probability}</span>
        <span class="best-stop-pill" title="Parada sugerida en la ruta">
          Parada #${sp.best_stop_number || 1}: ${sp.best_stop_name}
        </span>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
}

function toggleSpeciesCheck(speciesCode) {
  if (checkedSpecies.has(speciesCode)) {
    checkedSpecies.delete(speciesCode);
  } else {
    checkedSpecies.add(speciesCode);
  }

  const row = document.getElementById(`row_sp_${speciesCode}`);
  if (row) {
    row.classList.toggle('checked', checkedSpecies.has(speciesCode));
  }

  const countBadge = document.getElementById('checklistProgressBadge');
  if (countBadge) {
    countBadge.textContent = `✓ ${checkedSpecies.size} / ${currentProbableSpecies.length} Marcadas`;
  }
}

function filterProbableSpecies(group) {
  currentGroupFilter = group;

  document.querySelectorAll('.probable-filter-chip').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-group') === group);
  });

  applyProbableFilters();
}

function applyProbableFilters() {
  const query = (document.getElementById('probableSearchInput')?.value || '').toLowerCase().trim();

  let list = currentProbableSpecies;

  if (currentGroupFilter !== 'all') {
    list = list.filter(sp => sp.group === currentGroupFilter);
  }

  if (query) {
    list = list.filter(sp =>
      sp.comName.toLowerCase().includes(query) ||
      sp.sciName.toLowerCase().includes(query) ||
      (sp.best_stop_name && sp.best_stop_name.toLowerCase().includes(query))
    );
  }

  renderProbableSpeciesChecklist(list);
}

function exportChecklistToClipboard() {
  if (!currentProbableSpecies || currentProbableSpecies.length === 0) return;

  const regName = currentRouteData?.summary?.region_name || 'Chile';
  const dateInfo = formatSpanishDateLabels(currentRouteData?.summary?.target_date);
  let text = `RARA TIENDA • HOJA DE RUTA Y ESPECIES (${regName.toUpperCase()})\n`;
  text += `Fecha: ${dateInfo.fullLabel} | Paradas: ${currentRouteData?.stops?.length || 0} | Especies: ${currentProbableSpecies.length}\n`;
  text += `Marcadas en terreno: ${checkedSpecies.size} / ${currentProbableSpecies.length}\n\n`;

  let currentGrp = '';
  currentProbableSpecies.forEach(sp => {
    if (sp.groupName !== currentGrp) {
      currentGrp = sp.groupName;
      text += `\n--- ${currentGrp} ---\n`;
    }
    const check = checkedSpecies.has(sp.speciesCode) ? '[X]' : '[ ]';
    text += `${check} ${sp.comName} (${sp.sciName}) — Parada #${sp.best_stop_number || 1}: ${sp.best_stop_name}\n`;
  });

  navigator.clipboard.writeText(text);
  alert('¡Lista copiada al portapapeles!');
}

function resetChecklistTicks() {
  if (checkedSpecies.size === 0) return;
  if (confirm('¿Deseas desmarcar todas las especies registradas?')) {
    checkedSpecies.clear();
    applyProbableFilters();
  }
}

// Hook search input, date selector & region selector listeners
document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('probableSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', applyProbableFilters);
  }

  const regionSelect = document.getElementById('routeRegion');
  if (regionSelect) {
    applyRegionConfigToForm(regionSelect.value || 'CL-LL', false);
    regionSelect.addEventListener('change', () => {
      applyRegionConfigToForm(regionSelect.value, true);
    });
  }

  ['routeHub', 'routeSubzone', 'routeFocus', 'routeStops', 'routePace'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => {
        generateOptimalRoute();
      });
    }
  });

  const dateInput = document.getElementById('routeDate');
  if (dateInput) {
    if (!dateInput.value) {
      dateInput.value = getLocalTodayIso();
    }
    updateDateSelectorUI(dateInput.value);
    dateInput.addEventListener('change', () => {
      updateDateSelectorUI(dateInput.value);
      generateOptimalRoute();
    });
  }
});

// Generate Google Maps navigation link with all waypoints
function openGoogleMapsRoute() {
  if (!currentRouteData || !currentRouteData.stops.length) return;

  const origin = currentRouteData.origin;
  const stops = currentRouteData.stops;

  let url = `https://www.google.com/maps/dir/${origin.lat},${origin.lng}/`;
  stops.forEach(s => {
    url += `${s.lat},${s.lng}/`;
  });
  url += `${origin.lat},${origin.lng}`;

  window.open(url, '_blank');
}

// Generate clean Printable / Save-as-PDF Field Sheet (Flexible Itinerary + Species Checklist)
function downloadRouteFieldPdf() {
  if (!currentRouteData || !currentRouteData.stops) {
    alert('Primero calcula una ruta para generar el PDF de Hoja de Campo.');
    return;
  }

  const summary = currentRouteData.summary || {};
  const origin = currentRouteData.origin || { name: 'Punto Base' };
  const stops = currentRouteData.stops || [];
  const speciesList = currentProbableSpecies || currentRouteData.all_probable_species || [];
  const dateInfo = formatSpanishDateLabels(summary.target_date);
  const logoUrl = window.location.origin + (window.RARA_LOGO_URL || '/static/img/logo_rara.png');

  let tideSummaryStr = 'Sin marea relevante';
  if (summary.tides && summary.tides.is_coastal === false) {
    tideSummaryStr = 'Zona Interior (sin influencia mareal)';
  } else if (summary.tides && Array.isArray(summary.tides.events) && summary.tides.events.length >= 2) {
    const portPrefix = summary.tides.port_name ? `${summary.tides.port_name}: ` : '';
    tideSummaryStr = portPrefix + summary.tides.events.map(e => `${e.type} ${e.time} (${e.height_m}m)`).join(' • ');
  }

  const blockLabels = {
    morning: 'Mañana (Amanecer – 11:00)',
    midday: 'Mediodía (11:00 – 15:30)',
    afternoon: 'Tarde (15:30 – Ocaso)'
  };

  let stopsRowsHtml = `
    <tr style="background: rgba(6, 182, 212, 0.05);">
      <td style="font-weight: 800; color: #0284c7; text-align: center; width: 34px;">★</td>
      <td style="width: 120px; font-weight: 700; color: #0284c7;">Partida (~${summary.start_time || '06:30'})</td>
      <td>
        <div style="font-weight: 700; color: #0f172a; font-size: 11px;">${origin.name}</div>
        <div style="font-size: 9.5px; color: #64748b;">Punto Base (Salida / Alojamiento)</div>
      </td>
      <td style="font-size: 9.5px; color: #64748b;">Inicio de ruta</td>
      <td style="font-size: 9.5px; color: #64748b;">Punto de reunión</td>
    </tr>
  `;

  stops.forEach(s => {
    const isEnRoute = s.stop_role === 'en_route';
    const topBirds = (s.target_species || []).slice(0, 6).map(b => b.comName).join(', ');
    const blockLabel = blockLabels[s.day_block] || s.day_block_short || 'Flexible';
    const transferStr = s.stop_number === 1
      ? `Desde Base: ~${s.drive_time_from_prev_min} min (${s.distance_from_prev_km} km)`
      : `Traslado: ~${s.drive_time_from_prev_min} min (${s.distance_from_prev_km} km)`;
    const condStr = `${s.activity?.temp_c ?? 14}°C, Lluvia ${s.activity?.rain_prob ?? 0}%` + (s.tide ? ` • ${s.tide.status_label} (${s.tide.height_m}m)` : '');
    const roleTag = isEnRoute ? '<span style="color: #0284c7; font-weight: 700;">[Punto Intermedio]</span> ' : '';

    stopsRowsHtml += `
      <tr>
        <td style="font-weight: 800; color: ${isEnRoute ? '#0284c7' : '#047857'}; text-align: center; width: 34px;">#${s.stop_number}</td>
        <td style="width: 120px; font-weight: 600; color: #334155;">${blockLabel}</td>
        <td>
          <div style="font-weight: 700; color: #0f172a; font-size: 11px;">${roleTag}${s.locName}</div>
          <div style="font-size: 9.5px; color: #64748b;">${s.habitat_label} • ${transferStr}</div>
        </td>
        <td style="font-size: 9.5px; color: #334155; width: 135px;">${condStr}</td>
        <td style="font-size: 9.5px; color: #065f46; font-weight: 600;">${topBirds || 'Aves del sector'}</td>
      </tr>
    `;
  });

  stopsRowsHtml += `
    <tr style="background: rgba(148, 163, 184, 0.08);">
      <td style="font-weight: 800; color: #64748b; text-align: center; width: 34px;">↩</td>
      <td style="width: 120px; font-weight: 700; color: #475569;">Retorno (~${summary.finish_time || '18:30'})</td>
      <td>
        <div style="font-weight: 700; color: #0f172a; font-size: 11px;">${origin.name}</div>
        <div style="font-size: 9.5px; color: #64748b;">Regreso a Base: ~${summary.return_drive_minutes || 35} min (${summary.return_distance_km || 25} km)</div>
      </td>
      <td style="font-size: 9.5px; color: #64748b;">Fin de jornada</td>
      <td style="font-size: 9.5px; color: #64748b;">Cierre de ruta y conteo de lista</td>
    </tr>
  `;

  // Group species by ecological group for the 2-column checklist
  let speciesChecklistHtml = '';
  let currentGroup = '';
  speciesList.forEach(sp => {
    if (sp.groupName !== currentGroup) {
      currentGroup = sp.groupName;
      speciesChecklistHtml += `
        <div class="spp-group-header">${currentGroup}</div>
      `;
    }
    const isTicked = checkedSpecies.has(sp.speciesCode);
    speciesChecklistHtml += `
      <div class="spp-item">
        <span class="chk-box">${isTicked ? '✓' : ''}</span>
        <div class="spp-text">
          <b>${sp.comName}</b> <i>(${sp.sciName})</i>
        </div>
        <span class="spp-stop">P#${sp.best_stop_number || 1}</span>
      </div>
    `;
  });

  const printWin = window.open('', '_blank', 'width=980,height=860');
  if (!printWin) {
    alert('Por favor permite las ventanas emergentes para descargar el PDF.');
    return;
  }

  const docHtml = `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Hoja de Campo Rara Tienda - ${summary.region_short_name || 'Chile'} (${summary.target_date})</title>
  <style>
    @page { size: A4 portrait; margin: 11mm 12mm; }
    * { box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #0f172a;
      margin: 0;
      padding: 0;
      font-size: 10.5px;
      line-height: 1.35;
      background: #fff;
    }
    .no-print-bar {
      background: #0f172a;
      color: #fff;
      padding: 10px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
      border-radius: 8px;
    }
    .no-print-bar button {
      background: #10b981;
      color: #fff;
      border: none;
      padding: 7px 16px;
      border-radius: 6px;
      font-weight: 700;
      cursor: pointer;
      font-size: 12px;
    }
    .sheet-container {
      max-width: 210mm;
      margin: 0 auto;
      padding: 4px;
    }
    .header-box {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid #059669;
      padding-bottom: 10px;
      margin-bottom: 10px;
    }
    .brand-left {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .brand-left img {
      width: 40px;
      height: 40px;
      border-radius: 8px;
      object-fit: cover;
      border: 1px solid #cbd5e1;
    }
    .brand-title {
      font-size: 16px;
      font-weight: 800;
      color: #0f172a;
      margin: 0;
    }
    .brand-sub {
      font-size: 10.5px;
      color: #059669;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.4px;
      margin-top: 1px;
    }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 8px 10px;
      margin-bottom: 12px;
    }
    .meta-cell .lbl {
      font-size: 8.5px;
      text-transform: uppercase;
      color: #64748b;
      font-weight: 700;
    }
    .meta-cell .val {
      font-size: 10.5px;
      font-weight: 700;
      color: #0f172a;
      margin-top: 1px;
    }
    .section-title {
      font-size: 12px;
      font-weight: 800;
      color: #047857;
      text-transform: uppercase;
      letter-spacing: 0.4px;
      margin: 10px 0 6px 0;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    table.itinerary-table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 12px;
    }
    table.itinerary-table th {
      background: #ecfdf5;
      color: #065f46;
      font-size: 9px;
      text-transform: uppercase;
      text-align: left;
      padding: 5px 7px;
      border: 1px solid #a7f3d0;
    }
    table.itinerary-table td {
      padding: 5px 7px;
      border: 1px solid #e2e8f0;
      vertical-align: top;
    }
    .checklist-columns {
      column-count: 2;
      column-gap: 14px;
    }
    .spp-group-header {
      background: #f1f5f9;
      color: #0f172a;
      font-weight: 800;
      font-size: 9.5px;
      padding: 3px 6px;
      border-left: 3px solid #059669;
      margin: 6px 0 3px 0;
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .spp-item {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 2.5px 4px;
      border-bottom: 1px dotted #e2e8f0;
      break-inside: avoid;
      page-break-inside: avoid;
      font-size: 9.8px;
    }
    .chk-box {
      width: 12px;
      height: 12px;
      border: 1.4px solid #334155;
      border-radius: 2px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 9px;
      font-weight: 800;
      flex-shrink: 0;
    }
    .spp-text {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .spp-text i {
      color: #64748b;
      font-size: 8.8px;
    }
    .spp-stop {
      font-size: 8.5px;
      font-weight: 700;
      color: #047857;
      background: #ecfdf5;
      padding: 1px 5px;
      border-radius: 4px;
      flex-shrink: 0;
    }
    .notes-box {
      margin-top: 10px;
      border: 1px dashed #94a3b8;
      border-radius: 6px;
      padding: 7px 10px;
      page-break-inside: avoid;
    }
    .notes-line {
      border-bottom: 1px solid #e2e8f0;
      height: 16px;
    }
    @media print {
      .no-print-bar { display: none !important; }
      .sheet-container { max-width: 100%; padding: 0; }
    }
  </style>
</head>
<body>
  <div class="sheet-container">
    <div class="no-print-bar">
      <div>
        <b>Rara Tienda • Hoja de Campo Lista para Imprimir o Guardar como PDF</b>
        <span style="font-size: 11px; opacity: 0.85; margin-left: 8px;">(En Destino selecciona "Guardar como PDF")</span>
      </div>
      <button onclick="window.print()">Imprimir / Guardar PDF</button>
    </div>

    <div class="header-box">
      <div class="brand-left">
        <img src="${logoUrl}" alt="Rara Tienda" onerror="this.style.display='none'">
        <div>
          <h1 class="brand-title">Rara Tienda • Hoja de Campo y Ruta</h1>
          <div class="brand-sub">${summary.region_name || 'Chile'} • ${dateInfo.fullLabel} (${dateInfo.season})</div>
        </div>
      </div>
      <div style="text-align: right; font-size: 9.5px; color: #475569;">
        <div><b>Base:</b> ${origin.name}</div>
        <div><b>Recorrido total aprox.:</b> ${summary.total_km || 0} km (${stops.length} paradas)</div>
      </div>
    </div>

    <div class="meta-grid">
      <div class="meta-cell">
        <div class="lbl">Fecha de Salida</div>
        <div class="val">${dateInfo.fullLabel}</div>
      </div>
      <div class="meta-cell">
        <div class="lbl">Luz Solar (Amanecer / Ocaso)</div>
        <div class="val">${summary.sunrise || '07:00'} hrs / ${summary.sunset || '20:00'} hrs</div>
      </div>
      <div class="meta-cell">
        <div class="lbl">Especies en esta Planificación</div>
        <div class="val">${speciesList.length} especies probables</div>
      </div>
      <div class="meta-cell">
        <div class="lbl">Mareas de Referencia</div>
        <div class="val" style="font-size: 9.2px;">${tideSummaryStr}</div>
      </div>
    </div>

    <div class="section-title">
      <span>1. Itinerario Flexible Sugerido por Bloques</span>
      <span style="font-size: 9px; font-weight: 600; color: #64748b; text-transform: none;">Orden adaptable en terreno según ritmo del grupo</span>
    </div>
    <table class="itinerary-table">
      <thead>
        <tr>
          <th style="text-align: center;">#</th>
          <th>Bloque Sugerido</th>
          <th>Hotspot eBird / Ambiente y Traslado</th>
          <th>Clima / Marea Est.</th>
          <th>Especies Clave a Buscar</th>
        </tr>
      </thead>
      <tbody>
        ${stopsRowsHtml}
      </tbody>
    </table>

    <div class="section-title">
      <span>2. Checklist de Especies de la Planificación (${speciesList.length} especies)</span>
      <span style="font-size: 9px; font-weight: 600; color: #64748b; text-transform: none;">P# indica la parada sugerida de la ruta para buscarla</span>
    </div>
    <div class="checklist-columns">
      ${speciesChecklistHtml}
    </div>

    <div class="notes-box">
      <div style="font-size: 9px; font-weight: 800; color: #475569; text-transform: uppercase; margin-bottom: 3px;">
        Notas de Campo / Otras Especies Observadas:
      </div>
      <div class="notes-line"></div>
      <div class="notes-line"></div>
    </div>
  </div>
  <script>
    window.addEventListener('load', () => {
      setTimeout(() => { window.print(); }, 350);
    });
  </script>
</body>
</html>`;

  printWin.document.open();
  printWin.document.write(docHtml);
  printWin.document.close();
}

function printFieldChecklist() {
  downloadRouteFieldPdf();
}

// ----------------------------------------------------------------------------
// eBird Best Practices, Trip Reports & Rare Species Map Focus Helpers
// ----------------------------------------------------------------------------

function getStopEbirdAdvice(stop) {
  const hab = (stop.habitat || stop.habitat_label || '').toLowerCase();
  const isEnRoute = stop.stop_role === 'en_route';

  if (isEnRoute) {
    return 'Al ser una parada intermedia rápida (15 a 30 min), usa protocolo <b>"Con Desplazamiento"</b> corto (&lt; 1 km) o <b>"Estacionario"</b>. Registra todos los individuos detectados y asocia la lista a este hotspot para mantener la coherencia geográfica.';
  }
  if (hab.includes('humedal') || hab.includes('costa') || hab.includes('estuario') || hab.includes('marino') || hab.includes('lago') || hab.includes('playa')) {
    return 'En humedales y costas ingresa conteos numéricos reales o estimados (evita usar solo "X"). Si observas chorlos, playeros o gaviotas poco comunes, añade notas de plumaje, pico o comportamiento para facilitar la validación del revisor de eBird.';
  }
  if (hab.includes('bosque') || hab.includes('selva') || hab.includes('cordillera') || hab.includes('parque')) {
    return 'En bosque templado y sotobosque, la mayoría de los registros serán auditivos (Chucao, Tapaculo, Huet-huet). Camina en silencio y apóyate en Merlin Sound ID o grabaciones de audio de respaldo si dudas de la identificación.';
  }
  return 'Abre la app eBird Móvil apenas inicies el recorrido en este sitio. Si reportas todas las especies identificadas con esfuerzo dedicado, responde <b>"Sí"</b> a la pregunta de lista completa.';
}

function focusNotableOnMap(lat, lng, locName) {
  if (!routeMap) return;
  const mapEl = document.getElementById('routeMap');
  if (mapEl) {
    mapEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  routeMap.setView([lat, lng], 13, { animate: true });
  const key = `${Number(lat).toFixed(4)},${Number(lng).toFixed(4)}`;
  if (window._notableMarkers && window._notableMarkers[key]) {
    window._notableMarkers[key].openPopup();
  }
}

let activeStopTipId = null;

function toggleEbirdStopTip(event, stopNumber) {
  if (event) {
    event.stopPropagation();
  }
  const targetId = `ebirdStopTip_${stopNumber}`;
  const el = document.getElementById(targetId);
  if (!el) return;

  const isAlreadyOpen = el.style.display === 'block';

  // Close any other open popovers and reset card/block z-indices
  document.querySelectorAll('.ebird-tip-popover').forEach(pop => {
    pop.style.display = 'none';
  });
  document.querySelectorAll('.stop-card-item').forEach(card => {
    card.classList.remove('active-tip-card');
  });
  document.querySelectorAll('.day-block-group').forEach(blk => {
    blk.classList.remove('active-tip-block');
  });

  if (!isAlreadyOpen) {
    el.style.display = 'block';
    activeStopTipId = targetId;

    const parentCard = el.closest('.stop-card-item');
    if (parentCard) {
      parentCard.classList.add('active-tip-card');
      const parentBlock = parentCard.closest('.day-block-group');
      if (parentBlock) {
        parentBlock.classList.add('active-tip-block');
      }
    }
  } else {
    activeStopTipId = null;
  }
}

// Global click-outside listener to dismiss the floating balloon
document.addEventListener('click', (e) => {
  if (activeStopTipId) {
    const pop = document.getElementById(activeStopTipId);
    if (pop && !pop.contains(e.target) && !e.target.closest('.ebird-tip-pill-btn')) {
      pop.style.display = 'none';
      activeStopTipId = null;
      document.querySelectorAll('.stop-card-item').forEach(card => {
        card.classList.remove('active-tip-card');
      });
      document.querySelectorAll('.day-block-group').forEach(blk => {
        blk.classList.remove('active-tip-block');
      });
    }
  }
});

function toggleTripReportHelpModal() {
  const el = document.getElementById('ebirdTripReportModal');
  if (!el) return;
  if (el.style.display === 'none' || el.style.display === '') {
    el.style.display = 'block';
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } else {
    el.style.display = 'none';
  }
}

function copySuggestedTripTitle() {
  const regSelect = document.getElementById('routeRegion');
  const regName = regSelect && regSelect.selectedIndex >= 0 ? regSelect.options[regSelect.selectedIndex].text.split('(')[0].trim() : 'Chile';
  const dateVal = document.getElementById('routeDate')?.value || new Date().toISOString().slice(0, 10);
  const dateParts = dateVal.split('-');
  const y = dateParts[0];
  const m = dateParts[1];
  const d = dateParts[2];
  const title = `Pajareo en ${regName} - ${d}/${m}/${y} [Rara App]`;

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(title).then(() => {
      const feedback = document.getElementById('tripTitleCopiedFeedback');
      if (feedback) {
        feedback.style.display = 'inline';
        setTimeout(() => {
          feedback.style.display = 'none';
        }, 3500);
      }
    }).catch(() => {
      prompt('Copia el título sugerido:', title);
    });
  } else {
    prompt('Copia el título sugerido:', title);
  }
}
