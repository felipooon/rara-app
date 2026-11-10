// Rara Tienda • Planificador - Real-time Species Radar & Field Checklist

let allRecentSpecies = [];
let allNotableSpecies = [];
let radarSeenSpecies = new Set();
let currentRadarView = 'list'; // 'list' or 'grid'
let loadedRadarRegion = null;

// Initialize seen species from localStorage
try {
  const saved = JSON.parse(localStorage.getItem('radar_seen_birds') || '[]');
  radarSeenSpecies = new Set(saved);
} catch (e) {
  radarSeenSpecies = new Set();
}

function getActiveRegionInfo() {
  const regionCode = document.getElementById('routeRegion')?.value || document.getElementById('radarRegionSelect')?.value || 'CL-LL';
  const cfg = (window.CHILE_REGIONS_CONFIG && window.CHILE_REGIONS_CONFIG[regionCode]) || null;
  return {
    code: regionCode,
    name: cfg ? cfg.name : 'Los Lagos (X)',
    shortName: cfg ? cfg.short_name : 'Los Lagos'
  };
}

async function loadSpeciesRadar(forceRegionCode = null) {
  const listContainer = document.getElementById('speciesListContainer');
  const gridContainer = document.getElementById('speciesGrid');
  const regInfo = getActiveRegionInfo();
  const regionCode = forceRegionCode || regInfo.code;
  const cfg = (window.CHILE_REGIONS_CONFIG && window.CHILE_REGIONS_CONFIG[regionCode]) || null;
  const regionName = cfg ? cfg.name : regInfo.name;
  const regionShort = cfg ? cfg.short_name : regInfo.shortName;

  const radarSelect = document.getElementById('radarRegionSelect');
  if (radarSelect && radarSelect.value !== regionCode) {
    radarSelect.value = regionCode;
  }

  const titleEl = document.getElementById('radarTitle');
  if (titleEl) {
    titleEl.textContent = `Radar de Especies — ${regionName}`;
  }

  if (listContainer) {
    listContainer.innerHTML = `
      <div style="text-align: center; padding: 3rem; color: var(--text-secondary);">
        <span class="loading-spinner"></span>
        <p style="margin-top: 1rem;">Cargando avistamientos recientes de eBird en ${regionShort}...</p>
      </div>
    `;
  }

  try {
    const apiBase = window.PLANIFICADOR_API_BASE || '/planificador/api';
    const [resRecent, resNotable] = await Promise.all([
      fetch(`${apiBase}/recent-observations/?region=${encodeURIComponent(regionCode)}&back=14`),
      fetch(`${apiBase}/notable-observations/?region=${encodeURIComponent(regionCode)}&back=14`)
    ]);

    allRecentSpecies = await resRecent.json();
    allNotableSpecies = await resNotable.json();
    loadedRadarRegion = regionCode;

    document.getElementById('radarTotalSpeciesCount').textContent = `${allRecentSpecies.length} Especies Recientes`;
    document.getElementById('radarNotableCount').textContent = `${allNotableSpecies.length} Rarezas`;
    updateRadarSeenBadge();

    applyRadarFilters();
  } catch (err) {
    console.error(err);
    if (listContainer) {
      listContainer.innerHTML = `<p style="color: var(--rose); text-align: center; padding: 2rem;">Error al cargar observaciones de eBird para ${regionShort}.</p>`;
    }
  }
}

function updateRadarSeenBadge() {
  const badge = document.getElementById('radarSeenBadge');
  if (badge) {
    badge.textContent = `${radarSeenSpecies.size} / ${allRecentSpecies.length} Registradas`;
  }
}

function filterSpecies(filterType) {
  document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
  const activeBtn = document.getElementById(`filter_${filterType}`);
  if (activeBtn) activeBtn.classList.add('active');

  applyRadarFilters();
}

function applyRadarFilters() {
  const activeChip = document.querySelector('.filter-chip.active');
  const filterType = activeChip ? activeChip.id.replace('filter_', '') : 'all';
  const query = (document.getElementById('speciesSearchInput')?.value || '').toLowerCase().trim();

  let list = allRecentSpecies;

  if (filterType === 'notable') {
    list = allNotableSpecies;
  } else if (filterType === 'forest') {
    list = allRecentSpecies.filter(s => {
      const name = (s.comName + ' ' + s.sciName).toLowerCase();
      return name.includes('chucao') || name.includes('huet') || name.includes('hued') || name.includes('carpintero') ||
             name.includes('rayadito') || name.includes('churrín') || name.includes('comesebo') ||
             name.includes('colilarga') || name.includes('fío') || name.includes('concón') ||
             name.includes('turca') || name.includes('tapaculo') || name.includes('chiricoca') ||
             name.includes('picaflor') || name.includes('torcaza') || name.includes('choroy') ||
             name.includes('cachaña') || name.includes('tricahue') || name.includes('rara');
    });
  } else if (filterType === 'wetland') {
    list = allRecentSpecies.filter(s => {
      const name = (s.comName + ' ' + s.sciName).toLowerCase();
      return name.includes('cisne') || name.includes('zarapito') || name.includes('flamenco') ||
             name.includes('chorlo') || name.includes('playero') || name.includes('pato') ||
             name.includes('gaviota') || name.includes('gaviotín') || name.includes('quetru') ||
             name.includes('garza') || name.includes('pilpilén') || name.includes('tagua') ||
             name.includes('pimpollo') || name.includes('huala') || name.includes('cormorán') ||
             name.includes('pingüino') || name.includes('canquén') || name.includes('piuquén');
    });
  } else if (filterType === 'raptors') {
    list = allRecentSpecies.filter(s => {
      const name = (s.comName + ' ' + s.sciName).toLowerCase();
      return name.includes('águila') || name.includes('aguilucho') || name.includes('halcón') ||
             name.includes('chuncho') || name.includes('tiuque') || name.includes('traro') ||
             name.includes('bailarín') || name.includes('peuco') || name.includes('peuquito') ||
             name.includes('cóndor') || name.includes('jote') || name.includes('cernícalo') ||
             name.includes('tucúquere') || name.includes('lechuza') || name.includes('nuco');
    });
  }

  if (query) {
    list = list.filter(s =>
      (s.comName && s.comName.toLowerCase().includes(query)) ||
      (s.sciName && s.sciName.toLowerCase().includes(query)) ||
      (s.locName && s.locName.toLowerCase().includes(query))
    );
  }

  renderSpeciesChecklist(list);
  renderSpeciesCards(list);
}

// Render in checklist list format with checkboxes
function renderSpeciesChecklist(speciesList) {
  const container = document.getElementById('speciesListContainer');
  if (!container) return;

  if (!speciesList || speciesList.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
        <p>No se encontraron especies con los filtros seleccionados.</p>
      </div>
    `;
    return;
  }

  let html = '';
  speciesList.forEach(sp => {
    const isChecked = radarSeenSpecies.has(sp.speciesCode);
    const isNotable = sp.obsReviewed || sp.subId?.includes('notable') || allNotableSpecies.some(n => n.speciesCode === sp.speciesCode);
    const dateStr = sp.obsDt ? sp.obsDt.split(' ')[0] : 'Reciente';

    html += `
      <div class="checklist-item-row ${isChecked ? 'checked' : ''}" id="radar_row_${sp.speciesCode}">
        <input 
          type="checkbox" 
          class="checklist-checkbox" 
          ${isChecked ? 'checked' : ''} 
          onchange="toggleRadarSpeciesSeen('${sp.speciesCode}')"
          id="radar_chk_${sp.speciesCode}"
        >
        <div class="spp-name-col">
          <label for="radar_chk_${sp.speciesCode}" class="spp-name" style="cursor: pointer;">
            ${sp.comName}
          </label>
          <span class="spp-sci">${sp.sciName}</span>
        </div>

        <div style="font-size: 0.8rem; color: var(--text-secondary); max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          <b>${sp.locName || 'Los Lagos'}</b>
        </div>

        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); white-space: nowrap;">${dateStr}</span>
          ${isNotable ? `<span style="background: rgba(244, 63, 94, 0.2); color: #f43f5e; font-size: 11px; padding: 1px 6px; border-radius: 4px; font-weight: 700; border: 1px solid #f43f5e;">Rareza</span>` : ''}
        </div>

        <div style="display: flex; gap: 0.5rem; align-items: center; white-space: nowrap;">
          <a href="https://ebird.org/species/${sp.speciesCode}" target="_blank" style="color: var(--emerald); text-decoration: none; font-size: 12px; font-weight: 600;" title="Ver taxon en eBird">
            eBird ↗
          </a>
          <a href="https://media.ebird.org/catalog?taxonCode=${sp.speciesCode}&mediaType=photo" target="_blank" style="color: var(--cyan); text-decoration: none; font-size: 12px; font-weight: 600;" title="Ver fotos en Macaulay Library">
            Macaulay Fotos ↗
          </a>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

function toggleRadarSpeciesSeen(speciesCode) {
  if (radarSeenSpecies.has(speciesCode)) {
    radarSeenSpecies.delete(speciesCode);
  } else {
    radarSeenSpecies.add(speciesCode);
  }

  // Save to localStorage
  try {
    localStorage.setItem('radar_seen_birds', JSON.stringify(Array.from(radarSeenSpecies)));
  } catch (e) {
    console.error(e);
  }

  const row = document.getElementById(`radar_row_${speciesCode}`);
  if (row) {
    row.classList.toggle('checked', radarSeenSpecies.has(speciesCode));
  }

  updateRadarSeenBadge();
}

function exportRadarSeenList() {
  const seenCount = radarSeenSpecies.size;
  if (seenCount === 0) {
    alert('Aún no has marcado ninguna especie como registrada. Haz clic en las casillas [ ] para marcar tus avistamientos.');
    return;
  }

  const regInfo = getActiveRegionInfo();
  let text = `AVISTAMIENTOS EN ${regInfo.name.toUpperCase()} (eBird Radar)\n`;
  text += `Total de especies registradas: ${seenCount} / ${allRecentSpecies.length}\n`;
  text += `Fecha de exportación: ${new Date().toLocaleDateString('es-CL')}\n\n`;

  allRecentSpecies.forEach(sp => {
    if (radarSeenSpecies.has(sp.speciesCode)) {
      text += `[X] ${sp.comName} (${sp.sciName}) - Localidad: ${sp.locName || regInfo.shortName}\n`;
    }
  });

  navigator.clipboard.writeText(text);
  alert(`${seenCount} especies registradas copiadas al portapapeles.`);
}

function resetRadarSeenList() {
  if (radarSeenSpecies.size === 0) return;
  if (confirm(`¿Deseas desmarcar las ${radarSeenSpecies.size} especies registradas?`)) {
    radarSeenSpecies.clear();
    localStorage.removeItem('radar_seen_birds');
    updateRadarSeenBadge();
    applyRadarFilters();
  }
}

function toggleRadarView() {
  const listEl = document.getElementById('speciesListContainer');
  const gridEl = document.getElementById('speciesGrid');
  const btn = document.getElementById('btnToggleRadarView');

  if (currentRadarView === 'list') {
    currentRadarView = 'grid';
    listEl.style.display = 'none';
    gridEl.style.display = 'grid';
    btn.textContent = 'Vista Lista con Checkbox';
  } else {
    currentRadarView = 'list';
    listEl.style.display = 'block';
    gridEl.style.display = 'none';
    btn.textContent = 'Vista Cuadrícula';
  }
}

// Render cards as alternative view
function renderSpeciesCards(speciesList) {
  const container = document.getElementById('speciesGrid');
  if (!container) return;

  if (!speciesList || speciesList.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-muted);">
        <p style="font-size: 1.1rem;">No se encontraron especies con los filtros seleccionados.</p>
      </div>
    `;
    return;
  }

  let html = '';
  speciesList.forEach(sp => {
    const isChecked = radarSeenSpecies.has(sp.speciesCode);
    const isNotable = sp.obsReviewed || sp.subId?.includes('notable') || allNotableSpecies.some(n => n.speciesCode === sp.speciesCode);
    const dateStr = sp.obsDt ? sp.obsDt.split(' ')[0] : 'Reciente';

    html += `
      <div class="species-card ${isChecked ? 'checked' : ''}" style="${isChecked ? 'border-color: var(--emerald); background: rgba(16, 185, 129, 0.07);' : ''}">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <input 
                type="checkbox" 
                class="checklist-checkbox" 
                ${isChecked ? 'checked' : ''} 
                onchange="toggleRadarSpeciesSeen('${sp.speciesCode}')"
              >
              <h4 style="${isChecked ? 'color: var(--emerald); text-decoration: line-through;' : ''}">${sp.comName}</h4>
            </div>
            ${isNotable ? `<span style="background: rgba(244, 63, 94, 0.2); color: #f43f5e; font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 700; border: 1px solid #f43f5e;">Rareza</span>` : ''}
          </div>
          <div class="scientific">${sp.sciName}</div>
          
          <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 6px;">
            <b>${sp.locName || 'Región de Los Lagos'}</b>
          </div>
        </div>

        <div>
          <div class="meta-row">
            <span>${dateStr}</span>
            <span>Cantidad: <b>${sp.howMany || 1} ej.</b></span>
          </div>

          <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center;">
            <a href="https://ebird.org/species/${sp.speciesCode}" target="_blank" style="color: var(--emerald); text-decoration: none; font-size: 12px; font-weight: 600;">
              Ficha en eBird ↗
            </a>
            <a href="https://media.ebird.org/catalog?taxonCode=${sp.speciesCode}&mediaType=photo" target="_blank" style="color: var(--cyan); text-decoration: none; font-size: 12px; font-weight: 600;">
              Fotos Macaulay ↗
            </a>
          </div>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}
