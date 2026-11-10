// Rara Tienda • Planificador - Core App Controller

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  setupNavigation();
  setupEventListeners();

  // Initialize Route Planner on load
  initRouteMap();
  generateOptimalRoute();

  // Load default preset in API explorer
  selectPreset('recent_obs');
});

// Theme Management (Modo Claro / Modo Oscuro)
function initTheme() {
  const savedTheme = localStorage.getItem('rara_planificador_theme') || 'light'; // Default to light mode as requested
  applyTheme(savedTheme);
}

function applyTheme(theme) {
  const root = document.documentElement;
  const body = document.body;
  const toggleBtn = document.getElementById('themeToggleBtn');

  if (theme === 'light') {
    root.setAttribute('data-theme', 'light');
    body.classList.add('light-mode');
    if (toggleBtn) {
      toggleBtn.innerHTML = 'Modo Oscuro';
      toggleBtn.title = 'Cambiar a Modo Oscuro';
    }
    localStorage.setItem('rara_planificador_theme', 'light');
  } else {
    root.removeAttribute('data-theme');
    body.classList.remove('light-mode');
    if (toggleBtn) {
      toggleBtn.innerHTML = 'Modo Claro';
      toggleBtn.title = 'Cambiar a Modo Claro';
    }
    localStorage.setItem('rara_planificador_theme', 'dark');
  }
}

function toggleTheme() {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light' || document.body.classList.contains('light-mode');
  const nextTheme = isLight ? 'dark' : 'light';
  applyTheme(nextTheme);
}

function setupNavigation() {
  const tabs = document.querySelectorAll('.nav-tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      const targetPaneId = tab.getAttribute('data-tab');
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      const activePane = document.getElementById(targetPaneId);
      if (activePane) {
        activePane.classList.add('active');
      }

      // If switching to map, trigger Leaflet resize
      if (targetPaneId === 'pane-optimizer' && routeMap) {
        setTimeout(() => {
          routeMap.invalidateSize();
        }, 150);
      }

      // If switching to species radar, load data if empty or if region changed
      const activeRegion = document.getElementById('routeRegion')?.value || 'CL-LL';
      if (targetPaneId === 'pane-radar' && (allRecentSpecies.length === 0 || loadedRadarRegion !== activeRegion)) {
        loadSpeciesRadar(activeRegion);
      }
    });
  });
}

function setupEventListeners() {
  // Sync Radar tab region selector with main region selector
  const radarRegionSelect = document.getElementById('radarRegionSelect');
  if (radarRegionSelect) {
    radarRegionSelect.addEventListener('change', () => {
      const newReg = radarRegionSelect.value;
      const mainRegionSelect = document.getElementById('routeRegion');
      if (mainRegionSelect && mainRegionSelect.value !== newReg) {
        mainRegionSelect.value = newReg;
        if (typeof applyRegionConfigToForm === 'function') {
          applyRegionConfigToForm(newReg, true);
        }
      }
      loadSpeciesRadar(newReg);
    });
  }
  // Form submit for route planner
  const routeForm = document.getElementById('routeForm');
  if (routeForm) {
    routeForm.addEventListener('submit', (e) => {
      e.preventDefault();
      generateOptimalRoute();
    });
  }

  // Geolocation button
  const btnGeo = document.getElementById('btnUseMyGps');
  if (btnGeo) {
    btnGeo.addEventListener('click', () => {
      if (!navigator.geolocation) {
        alert('La geolocalización no está soportada en tu navegador.');
        return;
      }
      btnGeo.textContent = 'Obteniendo GPS...';
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          btnGeo.textContent = 'GPS Listo';
          // Add custom option to select
          const sel = document.getElementById('routeHub');
          let customOpt = document.getElementById('optCustomGps');
          if (!customOpt) {
            customOpt = document.createElement('option');
            customOpt.id = 'optCustomGps';
            sel.prepend(customOpt);
          }
          customOpt.value = `custom_${pos.coords.latitude}_${pos.coords.longitude}`;
          customOpt.textContent = `Mi Ubicación GPS (${pos.coords.latitude.toFixed(3)}, ${pos.coords.longitude.toFixed(3)})`;
          sel.value = customOpt.value;
        },
        (err) => {
          console.error(err);
          btnGeo.textContent = 'Error GPS';
          alert('No se pudo acceder a tu ubicación.');
        }
      );
    });
  }

  // Species search input
  const searchInput = document.getElementById('speciesSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const activeChip = document.querySelector('.filter-chip.active');
      const filterType = activeChip ? activeChip.id.replace('filter_', '') : 'all';
      filterSpecies(filterType);
    });
  }
}
