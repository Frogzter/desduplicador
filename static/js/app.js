/**
 * DesDuplicador Frontend Module
 *
 * Handles the UI for scanning duplicate files, managing paths,
 * applying filters, and executing bulk/single file actions.
 *
 * Security: All DOM rendering uses document.createElement() and
 * textContent/setAttribute() instead of innerHTML to prevent XSS.
 */

const socket = io();

let currentDuplicates = [];
const REQUEST_TIMEOUT_MS = 15000;

const dom = {
    pathsContainer: () => document.getElementById('paths-container'),
    outputPath: () => document.getElementById('output-path'),
    reviewPath: () => document.getElementById('review-path'),
    minVideoSize: () => document.getElementById('tamano-min-video'),
    btnScan: () => document.getElementById('btn-scan'),
    btnStop: () => document.getElementById('btn-stop'),
    progressSection: () => document.getElementById('progress-section'),
    progressFill: () => document.getElementById('progress-fill'),
    progressMessage: () => document.getElementById('progress-message'),
    progressPercent: () => document.getElementById('progress-percent'),
    resultsSection: () => document.getElementById('results-section'),
    duplicatesContainer: () => document.getElementById('duplicates-container'),
    stats: () => document.getElementById('stats'),
    filtrosGrid: () => document.getElementById('filtros-grid')
};

function normalizeError(err) {
    if (err instanceof Error) return err.message;
    return String(err);
}

async function apiRequest(url, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status} en ${url}`);
        }

        return response.json();
    } catch (err) {
        if (err.name === 'AbortError') {
            throw new Error(`Tiempo de espera agotado en ${url}`);
        }
        throw err;
    } finally {
        clearTimeout(timeout);
    }
}

async function apiGet(url) {
    return apiRequest(url);
}

async function apiPost(url, payload) {
    return apiRequest(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
}

function getCurrentConfigValues() {
    const outputInput = dom.outputPath();
    const reviewInput = dom.reviewPath();
    const minVideoInput = dom.minVideoSize();

    const tamanoMinMb = Number.parseInt(minVideoInput?.value || '1', 10);
    return {
        outputPath: outputInput ? outputInput.value.trim() : '',
        reviewPath: reviewInput ? reviewInput.value.trim() : '',
        tamanoMinVideo: tamanoMinMb * 1024 * 1024
    };
}

async function pickFolder({ title, initialDir = '' }) {
    return apiPost('/api/browse_folder', {
        title,
        initial_dir: initialDir
    });
}

// Cargar configuración al iniciar
document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    loadFilters();
    loadLastScan();
});

// Socket.IO eventos
socket.on('scan_progress', (data) => {
    updateProgress(data.current, data.total, data.message);
});

socket.on('scan_complete', (data) => {
    scanCompleted(data);
});

socket.on('scan_error', (data) => {
    showToast(data.message, 'error');
    resetScanUI();
});

socket.on('scan_stopped', () => {
    showToast('Escaneo detenido', 'info');
    resetScanUI();
});

function loadConfig() {
    apiGet('/api/config')
        .then(config => {
            const container = dom.pathsContainer();
            if (config.paths && config.paths.length > 0 && container) {
                container.innerHTML = '';
                config.paths.forEach((path, index) => {
                    addPath(path, index + 1);
                });
            }

            const output = dom.outputPath();
            if (config.output_path && output) {
                output.value = config.output_path;
            }

            const review = dom.reviewPath();
            if (config.review_path && review) {
                review.value = config.review_path;
            }

            const minVideo = dom.minVideoSize();
            if (config.tamano_min_video !== undefined && minVideo) {
                minVideo.value = Math.round(config.tamano_min_video / (1024 * 1024));
            }
        })
        .catch(err => {
            console.error('Error cargando config:', normalizeError(err));
            showToast('No se pudo cargar la configuración', 'error');
        });
}

function loadFilters() {
    apiGet('/api/filters')
        .then(data => {
            renderFilters(data.categorias, data.filtros_activos || []);
        })
        .catch(err => {
            console.error('Error cargando filtros:', normalizeError(err));
            showToast('No se pudieron cargar los filtros', 'error');
        });
}

function createFilterItem({ value, label, countText, isActive }) {
    const item = document.createElement('div');
    item.className = `filtro-item ${isActive ? 'activo' : ''}`;

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = value;
    checkbox.checked = !!isActive;
    checkbox.addEventListener('click', (event) => event.stopPropagation());

    const labelEl = document.createElement('label');
    labelEl.textContent = label;

    const countEl = document.createElement('span');
    countEl.className = 'filtro-count';
    countEl.textContent = countText;

    item.appendChild(checkbox);
    item.appendChild(labelEl);
    item.appendChild(countEl);

    return item;
}

function renderFilters(categorias, filtrosActivos) {
    const container = dom.filtrosGrid();
    if (!container) return;

    container.innerHTML = '';

    for (const [categoria, exts] of Object.entries(categorias || {})) {
        const isActive = filtrosActivos.includes(categoria);
        const item = createFilterItem({
            value: categoria,
            label: capitalize(categoria),
            countText: `${exts.length} ext`,
            isActive
        });
        container.appendChild(item);
    }

    const otrosActive = filtrosActivos.includes('otros');
    const otrosItem = createFilterItem({
        value: 'otros',
        label: 'Otros',
        countText: 'resto',
        isActive: otrosActive
    });
    container.appendChild(otrosItem);
}

function toggleFilter(item) {
    const cb = item.querySelector('input[type="checkbox"]');
    cb.checked = !cb.checked;
    item.classList.toggle('activo', cb.checked);
}

function getActiveFilters() {
    const checkboxes = document.querySelectorAll('#filtros-grid input[type="checkbox"]');
    return Array.from(checkboxes).filter(cb => cb.checked).map(cb => cb.value);
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function loadLastScan() {
    apiGet('/api/last_scan')
        .then(data => {
            if (data && data.length > 0) {
                currentDuplicates = data;
                renderDuplicates();
            }
        })
        .catch(err => {
            console.error('Error cargando último escaneo:', normalizeError(err));
            showToast('No se pudo cargar el último escaneo', 'error');
        });
}

function addPath(value = '', num = null) {
    const container = dom.pathsContainer();
    if (!container) return;

    const rows = container.querySelectorAll('.ruta-item');
    const nextNum = num || rows.length + 1;
    
    const row = document.createElement('div');
    row.className = 'ruta-item';

    const numSpan = document.createElement('span');
    numSpan.className = 'ruta-num';
    numSpan.textContent = nextNum;

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'path-input';
    input.placeholder = 'C:\\\\Ruta\\\\Carpeta';
    input.value = value;

    const browseBtn = document.createElement('button');
    browseBtn.className = 'btn-icon btn-browse';
    browseBtn.type = 'button';
    browseBtn.title = 'Examinar...';
    browseBtn.setAttribute('data-action', 'browse-folder');
    browseBtn.textContent = '📂';

    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn-icon btn-remove';
    removeBtn.type = 'button';
    removeBtn.setAttribute('data-action', 'remove-path');
    removeBtn.textContent = '✕';

    row.appendChild(numSpan);
    row.appendChild(input);
    row.appendChild(browseBtn);
    row.appendChild(removeBtn);
    
    container.appendChild(row);
    renumberPaths();
}

function addPathWithDialog() {
    const addBtn = document.querySelector('[data-action="add-path"]');
    if (addBtn) addBtn.setAttribute('disabled', 'disabled');

    pickFolder({
        title: 'Seleccionar carpeta para comparar',
        initialDir: ''
    })
        .then(data => {
            if (data.success && data.path) {
                addPath(data.path);
                showToast('Carpeta agregada: ' + data.path, 'success');
                return;
            }

            const msg = data && data.message
                ? data.message
                : 'No se seleccionó ninguna carpeta';
            showToast(msg, 'info');
        })
        .catch(err => {
            showToast('Error abriendo diálogo: ' + normalizeError(err), 'error');
        })
        .finally(() => {
            if (addBtn) addBtn.removeAttribute('disabled');
        });
}

function browseFolder(btn) {
    const row = btn?.closest('.ruta-item');
    const input = row?.querySelector('.path-input');
    if (!input) return;

    const currentPath = input.value.trim();

    pickFolder({
        title: 'Seleccionar carpeta para comparar',
        initialDir: currentPath
    })
        .then(data => {
            if (data.success && data.path) {
                input.value = data.path;
                showToast('Carpeta seleccionada: ' + data.path, 'success');
            }
        })
        .catch(err => {
            showToast('Error abriendo diálogo: ' + normalizeError(err), 'error');
        });
}

function browseOutputPath() {
    const input = dom.outputPath();
    if (!input) return;

    const currentPath = input.value.trim();

    pickFolder({
        title: 'Seleccionar carpeta de consolidación',
        initialDir: currentPath
    })
        .then(data => {
            if (data.success && data.path) {
                input.value = data.path;
                showToast('Carpeta de consolidación: ' + data.path, 'success');
            }
        })
        .catch(err => {
            showToast('Error abriendo diálogo: ' + normalizeError(err), 'error');
        });
}

function browseReviewPath() {
    const input = dom.reviewPath();
    if (!input) return;

    const currentPath = input.value.trim();

    pickFolder({
        title: 'Seleccionar carpeta de revisión',
        initialDir: currentPath
    })
        .then(data => {
            if (data.success && data.path) {
                input.value = data.path;
                showToast('Carpeta de revisión: ' + data.path, 'success');
            }
        })
        .catch(err => {
            showToast('Error abriendo diálogo: ' + normalizeError(err), 'error');
        });
}

function removePath(btn) {
    const rows = document.querySelectorAll('.ruta-item');
    if (rows.length <= 1) {
        showToast('Debe haber al menos una ruta', 'error');
        return;
    }

    const row = btn?.closest('.ruta-item');
    if (!row) return;

    row.remove();
    renumberPaths();
}

function renumberPaths() {
    const rows = document.querySelectorAll('.ruta-item');
    rows.forEach((row, index) => {
        const numEl = row.querySelector('.ruta-num');
        if (numEl) {
            numEl.textContent = index + 1;
        }
    });
}

function getPaths() {
    const inputs = document.querySelectorAll('.path-input');
    return Array.from(inputs).map(i => i.value.trim()).filter(v => v);
}

function savePaths() {
    const paths = getPaths();
    const filtrosActivos = getActiveFilters();
    const { outputPath, reviewPath, tamanoMinVideo } = getCurrentConfigValues();

    apiPost('/api/config', {
        paths,
        output_path: outputPath,
        review_path: reviewPath,
        filtros_activos: filtrosActivos,
        tamano_min_video: tamanoMinVideo
    })
        .then(() => showToast('Configuracion guardada correctamente', 'success'))
        .catch(err => showToast('Error guardando configuracion: ' + normalizeError(err), 'error'));
}

function startScan() {
    if (!dom.btnScan() || !dom.btnStop() || !dom.progressSection() || !dom.resultsSection()) {
        showToast('Faltan elementos de interfaz para iniciar escaneo', 'error');
        return;
    }
    const paths = getPaths();
    if (paths.length < 2) {
        showToast('Se necesitan al menos 2 rutas para comparar', 'error');
        return;
    }

    const filtrosActivos = getActiveFilters();
    const { tamanoMinVideo } = getCurrentConfigValues();

    apiPost('/api/config', {
        paths,
        filtros_activos: filtrosActivos,
        tamano_min_video: tamanoMinVideo
    })
        .then(() => {
            dom.btnScan().disabled = true;
            dom.btnStop().disabled = false;
            dom.progressSection().style.display = 'block';
            dom.progressSection().classList.add('activo');
            dom.resultsSection().style.display = 'none';

            updateProgress(0, 100, 'Iniciando escaneo...');
            socket.emit('start_scan', { paths });
        })
        .catch(err => showToast('Error guardando filtros: ' + normalizeError(err), 'error'));
}

function stopScan() {
    socket.emit('stop_scan');
}

function resetScanUI() {
    const btnScan = dom.btnScan();
    const btnStop = dom.btnStop();
    if (btnScan) btnScan.disabled = false;
    if (btnStop) btnStop.disabled = true;
}

function updateProgress(current, total, message) {
    const percent = total > 0 ? Math.round((current / total) * 100) : 0;
    const fillEl = dom.progressFill();
    const progressMessage = dom.progressMessage();
    const progressPercent = dom.progressPercent();

    if (fillEl) {
        fillEl.style.width = percent + '%';
        fillEl.textContent = percent + '%';
    }
    if (progressMessage) progressMessage.textContent = message;
    if (progressPercent) progressPercent.textContent = percent + '%';
}

function scanCompleted(data) {
    resetScanUI();
    updateProgress(100, 100, 'Escaneo completado');
    
    currentDuplicates = data.duplicates || [];
    
    renderDuplicates();
    showToast(`Escaneo completado: ${data.total_groups} grupos de duplicados encontrados`, 'success');
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(timestamp) {
    return new Date(timestamp * 1000).toLocaleString('es-ES');
}

function renderStats(duplicates) {
    const totalGroups = duplicates.length;
    const totalFiles = duplicates.reduce((sum, g) => sum + g.count, 0);
    const totalSize = duplicates.reduce((sum, g) => sum + (g.size * g.count), 0);
    const wastedSpace = duplicates.reduce((sum, g) => sum + (g.size * (g.count - 1)), 0);

    const statsEl = dom.stats();
    if (!statsEl) return;
    
    statsEl.innerHTML = '';

    const stats = [
        { num: totalGroups, label: 'Grupos de duplicados' },
        { num: totalFiles, label: 'Archivos duplicados' },
        { num: formatSize(totalSize), label: 'Espacio total' },
        { num: formatSize(wastedSpace), label: 'Espacio desperdiciado' }
    ];

    stats.forEach(({ num, label }) => {
        const box = document.createElement('div');
        box.className = 'stat-box';
        
        const numDiv = document.createElement('div');
        numDiv.className = 'stat-num';
        numDiv.textContent = num;
        
        const labelDiv = document.createElement('div');
        labelDiv.className = 'stat-label';
        labelDiv.textContent = label;
        
        box.appendChild(numDiv);
        box.appendChild(labelDiv);
        statsEl.appendChild(box);
    });
}

function renderEmptyState() {
    const container = dom.duplicatesContainer();
    if (!container) return;
    
    container.innerHTML = '';
    
    const emptyState = document.createElement('div');
    emptyState.className = 'empty-state';
    
    const h3 = document.createElement('h3');
    h3.textContent = 'No se encontraron duplicados';
    
    const p = document.createElement('p');
    p.textContent = 'Los archivos en las rutas seleccionadas son únicos.';
    
    emptyState.appendChild(h3);
    emptyState.appendChild(p);
    container.appendChild(emptyState);
    
    const statsEl = dom.stats();
    if (statsEl) statsEl.innerHTML = '';
}

function renderGroup(group, groupIndex) {
    const groupEl = document.createElement('div');
    groupEl.className = 'grupo';
    groupEl.id = `group-${groupIndex}`;

    const header = document.createElement('div');
    header.className = 'grupo-header';

    const hashSpan = document.createElement('span');
    hashSpan.className = 'hash';
    hashSpan.textContent = group.hash;

    const groupInfo = document.createElement('div');
    groupInfo.className = 'group-info';

    const countDiv = document.createElement('div');
    countDiv.textContent = `${group.count} archivos`;

    const sizeDiv = document.createElement('div');
    sizeDiv.textContent = `${formatSize(group.size)} c/u`;

    groupInfo.appendChild(countDiv);
    groupInfo.appendChild(sizeDiv);

    header.appendChild(hashSpan);
    header.appendChild(groupInfo);

    const filesContainer = document.createElement('div');
    filesContainer.className = 'group-files';

    group.files.forEach((file, fileIndex) => {
        const fileEl = document.createElement('div');
        fileEl.className = 'archivo';

        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = `keep-${groupIndex}`;
        radio.value = file.path;
        if (fileIndex === 0) {
            radio.checked = true;
        }

        const infoDiv = document.createElement('div');
        infoDiv.className = 'archivo-info';

        const pathDiv = document.createElement('div');
        pathDiv.className = 'ruta';
        pathDiv.textContent = file.path;

        const metaDiv = document.createElement('div');
        metaDiv.className = 'meta';
        metaDiv.textContent = `${file.name} | ${formatSize(file.size)} | ${formatDate(file.modified)}`;

        infoDiv.appendChild(pathDiv);
        infoDiv.appendChild(metaDiv);

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'acciones';

        const actions = [
            { cls: 'btn-eliminar', action: 'delete', label: '🗑️ Eliminar' },
            { cls: 'btn-mover', action: 'move_review', label: '📂 Revisar' },
            { cls: 'btn-icon', action: 'rename', label: '🏷️ Renombrar' },
            { cls: 'btn-mantener', action: 'consolidate', label: '📦 Consolidar' }
        ];

        actions.forEach(({ cls, action, label }) => {
            const btn = document.createElement('button');
            btn.className = `${cls} file-action-btn`;
            btn.type = 'button';
            btn.setAttribute('data-action', action);
            btn.setAttribute('data-file-path', file.path);
            btn.textContent = label;
            actionsDiv.appendChild(btn);
        });

        fileEl.appendChild(radio);
        fileEl.appendChild(infoDiv);
        fileEl.appendChild(actionsDiv);

        filesContainer.appendChild(fileEl);
    });

    groupEl.appendChild(header);
    groupEl.appendChild(filesContainer);

    return groupEl;
}

function renderDuplicates() {
    const resultsSection = dom.resultsSection();
    const duplicatesContainer = dom.duplicatesContainer();
    if (!resultsSection || !duplicatesContainer) return;

    if (!currentDuplicates || currentDuplicates.length === 0) {
        resultsSection.style.display = 'block';
        renderEmptyState();
        return;
    }

    resultsSection.style.display = 'block';
    renderStats(currentDuplicates);
    duplicatesContainer.innerHTML = '';
    currentDuplicates.forEach((group, groupIndex) => {
        duplicatesContainer.appendChild(renderGroup(group, groupIndex));
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeAttr(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function getSelectedKeepPath(groupIndex) {
    const radio = document.querySelector(`input[name="keep-${groupIndex}"]:checked`);
    if (!radio) return null;
    return radio.value || null;
}

function selectAllKeep(strategy) {
    currentDuplicates.forEach((group, index) => {
        let selectedPath;
        
        if (strategy === 'first') {
            selectedPath = group.files[0].path;
        } else if (strategy === 'largest') {
            const largest = group.files.reduce((max, f) => f.size > max.size ? f : max, group.files[0]);
            selectedPath = largest.path;
        } else if (strategy === 'newest') {
            const newest = group.files.reduce((max, f) => f.modified > max.modified ? f : max, group.files[0]);
            selectedPath = newest.path;
        }
        
        if (selectedPath) {
            const radios = document.querySelectorAll(`input[name="keep-${index}"]`);
            for (const radio of radios) {
                if (radio.value === selectedPath) {
                    radio.checked = true;
                    break;
                }
            }
        }
    });
    
    showToast(`Conservar ${strategy === 'first' ? 'primero' : strategy === 'largest' ? 'más grande' : 'más reciente'} de cada grupo seleccionado`, 'success');
}

function applyBulkAction(action) {
    const filesToProcess = [];

    currentDuplicates.forEach((group, index) => {
        const keep = getSelectedKeepPath(index);
        if (!keep) return;

        group.files.forEach(file => {
            if (file.path !== keep) {
                filesToProcess.push(file.path);
            }
        });
    });

    if (filesToProcess.length === 0) {
        showToast('No hay archivos para procesar', 'info');
        return;
    }

    const confirmMsg = action === 'delete'
        ? `¿Eliminar ${filesToProcess.length} archivos duplicados? Esta acción no se puede deshacer.`
        : `¿${action === 'move_review' ? 'Mover' : action === 'rename' ? 'Renombrar' : 'Consolidar'} ${filesToProcess.length} archivos?`;

    if (!confirm(confirmMsg)) return;

    const { outputPath, reviewPath } = getCurrentConfigValues();

    apiPost('/api/action', {
        action,
        files: filesToProcess,
        output_path: outputPath,
        review_path: reviewPath
    })
        .then(data => {
            if (data.success) {
                const successCount = data.results.filter(r => r.success).length;
                const failCount = data.results.filter(r => !r.success).length;
                showToast(`${successCount} archivos procesados. ${failCount} errores.`, successCount > 0 ? 'success' : 'error');

                data.results.forEach(result => {
                    if (result.success) {
                        currentDuplicates.forEach(group => {
                            group.files = group.files.filter(f => f.path !== result.file);
                        });
                    }
                });

                currentDuplicates = currentDuplicates.filter(g => g.files.length > 1);
                renderDuplicates();
            } else {
                showToast(data.message, 'error');
            }
        })
        .catch(err => showToast('Error: ' + normalizeError(err), 'error'));
}

function singleAction(action, filepath) {
    const { outputPath, reviewPath } = getCurrentConfigValues();

    if (action === 'delete') {
        if (!confirm(`¿Eliminar ${filepath}?`)) return;
    }

    apiPost('/api/action', {
        action,
        files: [filepath],
        output_path: outputPath,
        review_path: reviewPath
    })
        .then(data => {
            if (data.success && data.results.length > 0) {
                const result = data.results[0];
                showToast(result.message, result.success ? 'success' : 'error');

                if (result.success) {
                    currentDuplicates.forEach(group => {
                        group.files = group.files.filter(f => f.path !== filepath);
                    });
                    currentDuplicates = currentDuplicates.filter(g => g.files.length > 1);
                    renderDuplicates();
                }
            }
        })
        .catch(err => showToast('Error: ' + normalizeError(err), 'error'));
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;

    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 4000);
}

document.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;

    const filterItem = target.closest('.filtro-item');
    if (filterItem) {
        if (!target.matches('input[type="checkbox"]')) {
            toggleFilter(filterItem);
        }
        return;
    }

    const actionBtn = target.closest('[data-action]');
    if (!actionBtn) return;

    const action = actionBtn.getAttribute('data-action');

    switch (action) {
        case 'browse-folder': {
            const row = actionBtn.closest('.ruta-item');
            if (!row) return;
            if (row.querySelector('#output-path')) {
                browseOutputPath();
                return;
            }
            if (row.querySelector('#review-path')) {
                browseReviewPath();
                return;
            }
            browseFolder(actionBtn);
            return;
        }
        case 'browse-output':
            browseOutputPath();
            return;
        case 'browse-review':
            browseReviewPath();
            return;
        case 'remove-path':
            removePath(actionBtn);
            return;
        case 'add-path':
            addPathWithDialog();
            return;
        case 'scan-start':
            startScan();
            return;
        case 'scan-stop':
            stopScan();
            return;
        case 'save-paths':
            savePaths();
            return;
        case 'select-all-keep': {
            const strategy = actionBtn.getAttribute('data-strategy');
            if (strategy) selectAllKeep(strategy);
            return;
        }
        case 'apply-bulk-action': {
            const bulkAction = actionBtn.getAttribute('data-bulk-action');
            if (bulkAction) applyBulkAction(bulkAction);
            return;
        }
        case 'delete':
        case 'move_review':
        case 'rename':
        case 'consolidate': {
            const filepath = actionBtn.getAttribute('data-file-path');
            if (filepath) singleAction(action, filepath);
            return;
        }
        default:
            return;
    }
});
