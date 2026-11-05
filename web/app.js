const $ = selector => document.querySelector(selector);
const state = { files: [], quality: 'draft', system: null, currentJob: null, jobs: [], viewer: null, viewerPromise: null, busy: false, pollBusy: false };
const labels = { front: 'Frontal', left: 'Izquierda', back: 'Trasera', right: 'Derecha' };
const statusLabels = { queued: 'EN COLA', running: 'GENERANDO', completed: 'COMPLETADO', failed: 'ERROR', cancelled: 'CANCELADO' };
let toastTimer;

function toast(message) {
  $('#toast').textContent = message;
  $('#toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').hidden = true, 7000);
}

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === 'string' ? error.detail : 'Revisa las imágenes y los valores ingresados.');
  }
  return response.json();
}

function updateGenerate() {
  $('#generate').disabled = !state.files.length || !state.system?.ready || state.busy;
  const engine = state.files.length ? (state.files.length > 1 ? 'multiview' : 'mini') : state.currentJob?.engine;
  $('#system-engine').textContent = engine === 'multiview' ? 'Hunyuan3D · Multivista' : 'Hunyuan3D · Mini Turbo';
  $('#single-view-note').hidden = state.files.length !== 1;
}

async function readSystem() {
  try {
    state.system = await api('/api/system');
    const gpu = state.system.gpu;
    $('#system-status').textContent = state.system.ready
      ? `${gpu.name.replace('NVIDIA GeForce ', '')} · ${(gpu.total_mb / 1024).toFixed(0)} GB VRAM · Motor disponible${state.system.models.mini ? '' : ' · Descarga inicial pendiente'}`
      : 'Instalación del motor pendiente · Ejecuta instalar.ps1 en la carpeta del proyecto';
  } catch { $('#system-status').textContent = 'Sin conexión con el servidor local'; }
  updateGenerate();
}

async function addFiles(files) {
  if (state.busy) return toast('Espera a que finalice la generación actual.');
  // FileList es vivo: limpiar el input tras el evento no debe truncar la carga.
  for (const file of Array.from(files)) {
    if (state.files.length >= 4) { toast('Puedes cargar hasta cuatro vistas del mismo objeto.'); break; }
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { toast(`${file.name}: usa PNG, JPG o WebP.`); continue; }
    if (file.size > 15 * 1024 * 1024) { toast(`${file.name}: supera los 15 MB.`); continue; }
    const url = URL.createObjectURL(file);
    try {
      const image = new Image();
      image.src = url;
      await image.decode();
      if (Math.min(image.width, image.height) < 64 || Math.max(image.width, image.height) > 4096) throw new Error('Usa imágenes de 64 a 4096 píxeles por lado.');
      const view = Object.keys(labels).find(key => !state.files.some(item => item.view === key));
      state.files.push({ file, url, view });
    } catch (error) { URL.revokeObjectURL(url); toast(`${file.name}: ${error.message}`); }
  }
  renderImages();
  updateGenerate();
}

function renderImages() {
  const list = $('#image-list');
  list.replaceChildren();
  state.files.forEach((item, index) => {
    const row = document.createElement('div');
    row.className = 'image-row';
    const img = document.createElement('img'); img.src = item.url; img.alt = `Referencia ${labels[item.view]}`;
    const info = document.createElement('div'); info.className = 'image-info';
    const name = document.createElement('span'); name.textContent = item.file.name; name.title = item.file.name;
    const select = document.createElement('select'); select.ariaLabel = `Vista de ${item.file.name}`;
    for (const [key, label] of Object.entries(labels)) {
      const option = document.createElement('option'); option.value = key; option.textContent = label; option.selected = key === item.view; select.append(option);
    }
    select.disabled = state.busy;
    select.onchange = () => {
      const other = state.files.find(file => file !== item && file.view === select.value);
      if (other) other.view = item.view;
      item.view = select.value;
      renderImages();
    };
    const remove = document.createElement('button'); remove.textContent = '×'; remove.ariaLabel = `Quitar ${item.file.name}`; remove.disabled = state.busy;
    remove.onclick = () => { URL.revokeObjectURL(item.url); state.files.splice(index, 1); renderImages(); updateGenerate(); };
    info.append(name, select); row.append(img, info, remove); list.append(row);
  });
}

function showTab(tab) {
  $('#studio').hidden = tab !== 'studio'; $('#history').hidden = tab !== 'history';
  $('#studio-tab').classList.toggle('active', tab === 'studio'); $('#history-tab').classList.toggle('active', tab === 'history');
  if (tab === 'history') renderHistory(); else state.viewer?.resize();
}

function setBusy(busy) {
  state.busy = busy;
  $('#progress-overlay').hidden = !busy;
  $('#images').disabled = busy;
  $('#generation-form').querySelectorAll('input,button').forEach(input => input.disabled = busy);
  renderImages();
  updateGenerate();
}

async function ensureViewer() {
  if (state.viewer) return state.viewer;
  if (!state.viewerPromise) state.viewerPromise = import('/static/viewer.js').then(({ ModelViewer }) => {
    state.viewer = new ModelViewer($('#viewport'));
    $('#auto-rotate').setAttribute('aria-pressed', String(state.viewer.controls.autoRotate));
    return state.viewer;
  }).catch(error => {state.viewerPromise = null; throw error;});
  return state.viewerPromise;
}

async function displayJob(job) {
  const previous = state.currentJob;
  state.currentJob = job;
  localStorage.setItem('gen-stl:last-job', job.id);
  const busy = ['queued', 'running'].includes(job.status);
  setBusy(busy);
  $('#viewer-title').textContent = job.name;
  $('#model-status').textContent = statusLabels[job.status];
  $('#viewer-error').hidden = true;
  $('#viewer-dot').classList.toggle('ready', job.status === 'completed');
  $('#download').disabled = job.status !== 'completed';
  $('#viewer-toolbar').hidden = job.status !== 'completed';
  $('#model-stats').hidden = job.status !== 'completed';
  $('#depth-notice').hidden = true;
  if (busy) {
    $('#progress-title').textContent = job.status === 'queued' ? 'Tu modelo está en cola' : 'Dando forma a tu idea';
    $('#progress-stage').textContent = job.stage;
    $('#progress-bar').style.width = `${job.progress}%`;
    $('#progress-percent').textContent = `${job.progress}%`;
    $('#cancel').disabled = false;
    return;
  }
  if (job.status === 'completed') {
    $('#empty-state').hidden = true;
    const stats = job.stats;
    const [width, depth, height] = stats.dimensions_mm;
    const lowDepth = stats.low_depth ?? depth / Math.max(width, height) < 0.12;
    $('#depth-notice').hidden = !lowDepth;
    if (lowDepth) $('#depth-notice-text').textContent = `El modelo tiene ${depth} mm de fondo y ${height} mm de alto. Si buscabas una figura completa, la IA pudo interpretar la referencia como una lámina. Una malla cerrada también puede ser plana. Prueba un render 3D en tres cuartos o vistas frontal, lateral y trasera consistentes. Si buscabas un relieve, este resultado puede ser intencional.`;
    $('#model-stats').replaceChildren();
    for (const text of [`${stats.faces.toLocaleString('es-CL')} caras`, `${stats.vertices.toLocaleString('es-CL')} vértices`, `${stats.dimensions_mm.join(' × ')} mm`, stats.watertight ? '✓ Malla cerrada' : '△ Revisar agujeros antes de imprimir']) {
      const span = document.createElement('span'); span.textContent = text;
      if (text.startsWith('△')) span.className = 'warning';
      $('#model-stats').append(span);
    }
    $('#export-description').textContent = `Geometría sin texturas · Semilla ${job.options.seed}`;
    if (previous?.id !== job.id || previous?.status !== 'completed' || !state.viewer?.model) {
      try {
        const viewer = await ensureViewer();
        if (state.currentJob?.id !== job.id) return;
        await viewer.load(`/api/jobs/${job.id}/model/glb?inline=true`);
        if (state.currentJob?.id === job.id) $('#camera-angle').value = 'perspective';
      } catch (error) {
        if (state.currentJob?.id !== job.id) return;
        $('#viewer-error').textContent = 'No se pudo abrir el visor 3D. Los archivos siguen disponibles para descargar. ' + error.message;
        $('#viewer-error').hidden = false;
      }
    }
  } else {
    state.viewer?.clear();
    $('#empty-state').hidden = false;
    if (job.status === 'failed') {
      $('#viewer-error').textContent = job.error || job.stage;
      $('#viewer-error').hidden = false;
    }
  }
}

async function refreshJobs() {
  if (state.pollBusy) return;
  state.pollBusy = true;
  try {
    state.jobs = await api('/api/jobs');
    $('#history-count').textContent = state.jobs.length;
    if (state.currentJob) {
      const job = state.jobs.find(item => item.id === state.currentJob.id);
      if (job && (state.busy || job.status !== state.currentJob.status)) await displayJob(job);
    }
    if (!$('#history').hidden) renderHistory();
  } catch (error) { if (state.busy) $('#progress-stage').textContent = 'Reconectando con el servidor local…'; }
  finally { state.pollBusy = false; }
}

function renderHistory() {
  const grid = $('#history-grid'); grid.replaceChildren();
  if (!state.jobs.length) { const empty = document.createElement('p'); empty.className = 'history-empty'; empty.textContent = 'Aquí aparecerán tus modelos. Tu primera creación está a una imagen de distancia.'; grid.append(empty); return; }
  for (const job of state.jobs) {
    const card = document.createElement('button'); card.className = 'history-card';
    const img = document.createElement('img'); img.src = `/api/jobs/${job.id}/image/${job.views[0]}`; img.alt = job.name; img.loading = 'lazy';
    const body = document.createElement('div'); body.className = 'history-body';
    const title = document.createElement('h3'); title.textContent = job.name;
    const badge = document.createElement('span'); badge.className = 'job-tag'; badge.textContent = statusLabels[job.status];
    const date = document.createElement('p'); date.textContent = new Date(job.created_at).toLocaleString('es-CL');
    const info = document.createElement('p'); info.textContent = `${job.views.length} vista${job.views.length > 1 ? 's' : ''} · ${job.options.size_mm} mm · ${{draft:'Borrador',standard:'Estándar',high:'Alta'}[job.options.quality]}`;
    body.append(title, badge, date, info); card.append(img, body);
    card.onclick = async () => {
      if (state.busy && state.currentJob.id !== job.id) return toast('Espera o cancela la generación actual para abrir otro modelo.');
      showTab('studio'); await displayJob(job);
    };
    grid.append(card);
  }
}

$('#images').onchange = event => { addFiles(event.target.files); event.target.value = ''; };
$('#dropzone').onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); $('#images').click(); } };
for (const name of ['dragenter', 'dragover']) $('#dropzone').addEventListener(name, event => { event.preventDefault(); $('#dropzone').classList.add('dragover'); });
for (const name of ['dragleave', 'drop']) $('#dropzone').addEventListener(name, event => { event.preventDefault(); $('#dropzone').classList.remove('dragover'); });
$('#dropzone').addEventListener('drop', event => addFiles(event.dataTransfer.files));
document.querySelectorAll('[data-quality]').forEach(button => button.onclick = () => {
  state.quality = button.dataset.quality;
  document.querySelectorAll('[data-quality]').forEach(other => other.classList.toggle('selected', other === button));
  $('#quality-hint').textContent = {draft:'128³ · Menor uso de memoria. Ideal para una primera prueba.', standard:'192³ · Más detalle y mayor tiempo de generación.', high:'256³ · Mayor detalle. Puede superar la memoria de una GPU de 6 GB.'}[state.quality];
});
$('#random-seed').onclick = () => $('#seed').value = crypto.getRandomValues(new Uint32Array(1))[0] % 2147483648;
$('#generation-form').onsubmit = async event => {
  event.preventDefault();
  if (!state.files.length || state.busy) return;
  if (!state.files.some(item => item.view === 'front')) return toast('Asigna una imagen a la vista Frontal.');
  const form = new FormData();
  state.files.forEach(item => form.append('images', item.file));
  form.append('views', JSON.stringify(state.files.map(item => item.view)));
  form.append('quality', state.quality); form.append('size_mm', $('#size').value);
  form.append('seed', $('#seed').value); form.append('remove_background', $('#remove-background').checked);
  form.append('name', $('#model-name').value || 'Mi modelo');
  $('#generate').disabled = true;
  try { const job = await api('/api/jobs', { method:'POST', body:form }); await displayJob(job); await refreshJobs(); }
  catch (error) { toast(error.message); updateGenerate(); }
};
$('#cancel').onclick = async () => {
  if (!state.currentJob) return;
  $('#cancel').disabled = true;
  try { await displayJob(await api(`/api/jobs/${state.currentJob.id}/cancel`, { method:'POST' })); }
  catch (error) { toast(error.message); $('#cancel').disabled = false; }
};
$('#download').onclick = () => {
  if (state.currentJob?.status !== 'completed') return;
  const link = document.createElement('a'); link.href = `/api/jobs/${state.currentJob.id}/model/${$('#format').value}`; link.download = ''; document.body.append(link); link.click(); link.remove();
};
$('#reset-camera').onclick = () => { if (state.viewer) { $('#camera-angle').value = 'perspective'; state.viewer.reset(); } };
$('#camera-angle').onchange = event => {
  if (!state.viewer) return;
  state.viewer.controls.autoRotate = false;
  $('#auto-rotate').setAttribute('aria-pressed', 'false');
  state.viewer.reset(event.target.value);
};
$('#wireframe').onclick = () => { if (state.viewer) { state.viewer.material.wireframe = !state.viewer.material.wireframe; $('#wireframe').setAttribute('aria-pressed', String(state.viewer.material.wireframe)); } };
$('#auto-rotate').onclick = () => { if (state.viewer) { state.viewer.controls.autoRotate = !state.viewer.controls.autoRotate; $('#auto-rotate').setAttribute('aria-pressed', String(state.viewer.controls.autoRotate)); } };
$('#model-color').oninput = event => state.viewer?.material.color.set(event.target.value);
$('#studio-tab').onclick = () => showTab('studio');
$('#history-tab').onclick = () => showTab('history');
$('#new-model').onclick = () => { showTab('studio'); $('#model-name').focus(); };
$('#help-button').onclick = () => $('#help-dialog').showModal();
$('#depth-help').onclick = () => { $('#help-dialog').showModal(); $('#volume-help').scrollIntoView({block:'center'}); };
$('.dialog-close').onclick = () => $('#help-dialog').close();
$('#help-dialog').onclick = event => {if (event.target === $('#help-dialog')) {const rect = event.target.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.target.close();}};
setInterval(refreshJobs, 2000);
setInterval(() => {
  if (!state.busy || !state.currentJob) return;
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(state.currentJob.created_at)) / 1000));
  $('#progress-time').textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}, 1000);
await readSystem();
await refreshJobs();
const last = localStorage.getItem('gen-stl:last-job');
const saved = state.jobs.find(job => ['queued', 'running'].includes(job.status)) || state.jobs.find(job => job.id === last);
if (saved) await displayJob(saved);
setInterval(readSystem, 30000);
