// Rara Tienda • Planificador - eBird API Explorer

let lastApiResponseData = null;

const ENDPOINT_PRESETS = {
  recent_obs: {
    name: 'Observaciones Recientes en Región',
    method: 'GET',
    endpoint: 'data/obs/{{region}}/recent',
    params: { back: '7', maxResults: '50', sppLocale: 'es_CL' },
    desc: 'Últimas especies observadas y validadas en la región especificada.'
  },
  notable_obs: {
    name: 'Observaciones Notables / Rarezas',
    method: 'GET',
    endpoint: 'data/obs/{{region}}/recent/notable',
    params: { back: '14', maxResults: '30', sppLocale: 'es_CL', detail: 'full' },
    desc: 'Registros de aves raras o inusuales para la zona y época del año.'
  },
  hotspots_region: {
    name: 'Hotspots (Sitios de Interés) de la Región',
    method: 'GET',
    endpoint: 'ref/hotspot/{{region}}',
    params: { fmt: 'json' },
    desc: 'Todos los hotspots oficiales de eBird en la región con sus coordenadas y número histórico de especies.'
  },
  hotspots_geo: {
    name: 'Hotspots Cercanos por GPS',
    method: 'GET',
    endpoint: 'ref/hotspot/geo',
    params: { lat: '-41.3195', lng: '-72.9854', dist: '30', fmt: 'json' },
    desc: 'Hotspots dentro de un radio de kilómetros (ej. Puerto Varas).'
  },
  hotspot_obs: {
    name: 'Observaciones en un Hotspot Específico',
    method: 'GET',
    endpoint: 'data/obs/L774634/recent',
    params: { back: '14', sppLocale: 'es_CL' },
    desc: 'Últimas especies registradas en un punto concreto (ej. L774634 Achao).'
  },
  taxonomy: {
    name: 'Taxonomía Oficial eBird',
    method: 'GET',
    endpoint: 'ref/taxonomy/ebird',
    params: { fmt: 'json', species: 'scerub1,pypalb1' },
    desc: 'Nombres científicos, familias y códigos taxonómicos oficiales.'
  }
};

function selectPreset(presetKey) {
  const preset = ENDPOINT_PRESETS[presetKey];
  if (!preset) return;

  // Highlight active preset button
  document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
  const activeBtn = document.getElementById(`preset_${presetKey}`);
  if (activeBtn) activeBtn.classList.add('active');

  const region = document.getElementById('apiRegionInput').value || 'CL-LL';
  const endpoint = preset.endpoint.replace('{{region}}', region);

  document.getElementById('apiEndpointInput').value = endpoint;
  document.getElementById('apiMethodSelect').value = preset.method;
  document.getElementById('endpointDescription').textContent = preset.desc;

  // Render params editor
  renderParamsInputs(preset.params);
}

function renderParamsInputs(paramsObj) {
  const container = document.getElementById('apiParamsContainer');
  let html = '';

  Object.entries(paramsObj).forEach(([k, v]) => {
    html += `
      <div class="form-row" style="margin-bottom: 8px;">
        <input type="text" class="form-control param-key" value="${k}" placeholder="Parámetro" style="font-family: var(--font-mono); font-size: 13px;">
        <input type="text" class="form-control param-val" value="${v}" placeholder="Valor" style="font-family: var(--font-mono); font-size: 13px;">
      </div>
    `;
  });

  container.innerHTML = html;
}

function addQueryParamRow() {
  const container = document.getElementById('apiParamsContainer');
  const div = document.createElement('div');
  div.className = 'form-row';
  div.style.marginBottom = '8px';
  div.innerHTML = `
    <input type="text" class="form-control param-key" placeholder="clave" style="font-family: var(--font-mono); font-size: 13px;">
    <input type="text" class="form-control param-val" placeholder="valor" style="font-family: var(--font-mono); font-size: 13px;">
  `;
  container.appendChild(div);
}

async function executeApiRequest() {
  const endpoint = document.getElementById('apiEndpointInput')?.value.trim();
  const apiKey = document.getElementById('customApiKey')?.value.trim() || '';

  if (!endpoint) {
    alert('Ingresa un endpoint de eBird (ej: data/obs/CL-LL/recent)');
    return;
  }

  const btn = document.getElementById('btnSendApiRequest');
  btn.disabled = true;
  btn.innerHTML = `<span class="loading-spinner"></span> Consultando eBird API...`;

  // Collect query parameters
  const paramKeys = document.querySelectorAll('.param-key');
  const paramVals = document.querySelectorAll('.param-val');

  const queryParams = new URLSearchParams();
  queryParams.append('endpoint', endpoint);
  queryParams.append('key', apiKey);

  for (let i = 0; i < paramKeys.length; i++) {
    const k = paramKeys[i].value.trim();
    const v = paramVals[i].value.trim();
    if (k) {
      queryParams.append(k, v);
    }
  }

  const startTime = performance.now();

  try {
    const apiBase = window.PLANIFICADOR_API_BASE || '/planificador/api';
    const res = await fetch(`${apiBase}/ebird/proxy/?${queryParams.toString()}`, {
      headers: {
        'X-eBirdApiToken': apiKey
      }
    });

    const elapsed = Math.round(performance.now() - startTime);
    const json = await res.json();
    lastApiResponseData = json.data;

    // Update Status Badges
    const statusBadge = document.getElementById('apiStatusBadge');
    statusBadge.textContent = `${res.status} ${res.statusText || 'OK'}`;
    statusBadge.className = `status-badge ${res.ok ? 'ok' : 'err'}`;

    document.getElementById('apiLatencyBadge').textContent = `⚡ ${json.elapsed_ms || elapsed} ms`;

    const count = Array.isArray(json.data) ? json.data.length : (typeof json.data === 'object' ? Object.keys(json.data).length : 1);
    document.getElementById('apiItemCountBadge').textContent = `📦 ${count} elementos`;

    // Render formatted JSON
    renderJsonViewer(json.data);

    // If array of items, render tabular preview
    renderTablePreview(json.data);

  } catch (err) {
    console.error(err);
    document.getElementById('apiJsonViewer').textContent = JSON.stringify({ error: err.message }, null, 2);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `🚀 Enviar Petición a eBird`;
  }
}

function renderJsonViewer(data) {
  const viewer = document.getElementById('apiJsonViewer');
  const formatted = JSON.stringify(data, null, 2);
  viewer.textContent = formatted;
}

function renderTablePreview(data) {
  const container = document.getElementById('apiTableContainer');
  if (!Array.isArray(data) || data.length === 0) {
    container.innerHTML = `<p style="color: var(--text-muted); font-size: 13px;">La respuesta no es una lista de registros tabulares.</p>`;
    return;
  }

  const sample = data[0];
  const keys = Object.keys(sample).slice(0, 7); // First 7 columns

  let tableHtml = `
    <div style="overflow-x: auto; margin-top: 1rem;">
      <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: left;">
        <thead>
          <tr style="border-bottom: 2px solid var(--border-color); color: var(--emerald);">
            ${keys.map(k => `<th style="padding: 8px 12px; font-weight: 600;">${k}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
  `;

  data.slice(0, 50).forEach(row => {
    tableHtml += `<tr style="border-bottom: 1px solid var(--border-color);">`;
    keys.forEach(k => {
      const val = row[k] !== undefined && row[k] !== null ? String(row[k]) : '-';
      tableHtml += `<td style="padding: 8px 12px; color: var(--text-primary);">${val}</td>`;
    });
    tableHtml += `</tr>`;
  });

  tableHtml += `
        </tbody>
      </table>
    </div>
  `;

  container.innerHTML = tableHtml;
}

function copyApiResponseJson() {
  if (!lastApiResponseData) return;
  navigator.clipboard.writeText(JSON.stringify(lastApiResponseData, null, 2));
  alert('¡JSON copiado al portapapeles!');
}
