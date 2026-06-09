const socket = io();

let currentDuplicates = [];
let groupSelections = {};

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
    fetch('/api/config')
        .then(r => r.json())
        .then(config => {
            if (config.paths && config.paths.length > 0) {
                const container = document.getElementById('paths-container');
                container.innerHTML = '';
                config.paths.forEach((path, index) => {
                    addPath(path, index + 1);
                });
            }
            if (config.output_path) {
                document.getElementById('output-path').value = config.output_path;
            }
            if (config.review_path) {
                document.getElementById('review-path').value = config.review_path;
            }
            if (config.tamano_min_video !== undefined) {
                document.getElementById('tamano-min-video').value = Math.round(config.tamano_min_video / (1024 * 1024));
            }
        })
        .catch(err => console.error('Error cargando config:', err));
}

function loadFilters() {
    fetch('/api/filters')
        .then(r => r.json())
        .then(data => {
            renderFilters(data.categorias, data.filtros_activos);
        })
        .catch(err => console.error('Error cargando filtros:', err));
}

function renderFilters(categorias, filtrosActivos) {
    const container = document.getElementById('filtros-grid');
    if (!container) return;
    
    let html = '';
    for (const [categoria, exts] of Object.entries(categorias)) {
        const isActive = filtrosActivos.includes(categoria);
        html += `
            <div class="filtro-item ${isActive ? 'activo' : ''}" onclick="toggleFilter(this)">
                <input type="checkbox" value="${categoria}" ${isActive ? 'checked' : ''} onclick="event.stopPropagation();">
                <label>${capitalize(categoria)}</label>
                <span class="filtro-count">${exts.length} ext</span>
            </div>
        `;
    }
    // Categoria "otros"
    const otrosActive = filtrosActivos.includes('otros');
    html += `
        <div class="filtro-item ${otrosActive ? 'activo' : ''}" onclick="toggleFilter(this)">
            <input type="checkbox" value="otros" ${otrosActive ? 'checked' : ''} onclick="event.stopPropagation();">
            <label>Otros</label>
            <span class="filtro-count">resto</span>
        </div>
    `;
    
    container.innerHTML = html;
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
    fetch('/api/last_scan')
        .then(r => r.json())
        .then(data => {
            if (data && data.length > 0) {
                currentDuplicates = data;
                renderDuplicates();
            }
        })
        .catch(err => console.error('Error cargando último escaneo:', err));
}

function addPath(value = '', num = null) {
    const container = document.getElementById('paths-container');
    const rows = container.querySelectorAll('.ruta-item');
    const nextNum = num || rows.length + 1;
    
    const row = document.createElement('div');
    row.className = 'ruta-item';
    row.innerHTML = `
        <span class="ruta-num">${nextNum}</span>
        <input type="text" class="path-input" placeholder="C:\\\\Ruta\\\\Carpeta" value="${value}" />
        <button class="btn-icon btn-browse" onclick="browseFolder(this)" title="Examinar...">📂</button>
        <button class="btn-icon btn-remove" onclick="removePath(this)">✕</button>
    `;
    container.appendChild(row);
    renumberPaths();
}

function addPathWithDialog() {
    fetch('/api/browse_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: 'Seleccionar carpeta para comparar',
            initial_dir: ''
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success && data.path) {
            addPath(data.path);
            showToast('Carpeta agregada: ' + data.path, 'success');
        }
    })
    .catch(err => {
        showToast('Error abriendo diálogo: ' + err, 'error');
    });
}

function browseFolder(btn) {
    const row = btn.closest('.ruta-item');
    const input = row.querySelector('.path-input');
    const currentPath = input.value.trim();
    
    fetch('/api/browse_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: 'Seleccionar carpeta para comparar',
            initial_dir: currentPath
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success && data.path) {
            input.value = data.path;
            showToast('Carpeta seleccionada: ' + data.path, 'success');
        }
    })
    .catch(err => {
        showToast('Error abriendo diálogo: ' + err, 'error');
    });
}

function browseOutputPath() {
    const input = document.getElementById('output-path');
    const currentPath = input.value.trim();
    
    fetch('/api/browse_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: 'Seleccionar carpeta de consolidación',
            initial_dir: currentPath
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success && data.path) {
            input.value = data.path;
            showToast('Carpeta de consolidación: ' + data.path, 'success');
        }
    })
    .catch(err => {
        showToast('Error abriendo diálogo: ' + err, 'error');
    });
}

function browseReviewPath() {
    const input = document.getElementById('review-path');
    const currentPath = input.value.trim();
    
    fetch('/api/browse_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: 'Seleccionar carpeta de revisión',
            initial_dir: currentPath
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success && data.path) {
            input.value = data.path;
            showToast('Carpeta de revisión: ' + data.path, 'success');
        }
    })
    .catch(err => {
        showToast('Error abriendo diálogo: ' + err, 'error');
    });
}

function removePath(btn) {
    const rows = document.querySelectorAll('.ruta-item');
    if (rows.length <= 1) {
        showToast('Debe haber al menos una ruta', 'error');
        return;
    }
    btn.closest('.ruta-item').remove();
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
    const outputPath = document.getElementById('output-path').value.trim();
    const reviewPath = document.getElementById('review-path').value.trim();
    const filtrosActivos = getActiveFilters();
    const tamanoMinVideo = parseInt(document.getElementById('tamano-min-video').value || '1') * 1024 * 1024;

    fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths, output_path: outputPath, review_path: reviewPath, filtros_activos: filtrosActivos, tamano_min_video: tamanoMinVideo })
    })
    .then(r => r.json())
    .then(() => showToast('Configuracion guardada correctamente', 'success'))
    .catch(err => showToast('Error guardando configuracion: ' + err, 'error'));
}

function startScan() {
    const paths = getPaths();
    if (paths.length < 2) {
        showToast('Se necesitan al menos 2 rutas para comparar', 'error');
        return;
    }

    // Guardar filtros antes de escanear
    const filtrosActivos = getActiveFilters();
    const tamanoMinVideo = parseInt(document.getElementById('tamano-min-video').value || '1') * 1024 * 1024;

    fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths, filtros_activos: filtrosActivos, tamano_min_video: tamanoMinVideo })
    })
    .then(() => {
        document.getElementById('btn-scan').disabled = true;
        document.getElementById('btn-stop').disabled = false;
        document.getElementById('progress-section').style.display = 'block';
        document.getElementById('progress-section').classList.add('activo');
        document.getElementById('results-section').style.display = 'none';
        
        updateProgress(0, 100, 'Iniciando escaneo...');
        socket.emit('start_scan', { paths });
    })
    .catch(err => showToast('Error guardando filtros: ' + err, 'error'));
}

function stopScan() {
    socket.emit('stop_scan');
}

function resetScanUI() {
    document.getElementById('btn-scan').disabled = false;
    document.getElementById('btn-stop').disabled = true;
}

function updateProgress(current, total, message) {
    const percent = total > 0 ? Math.round((current / total) * 100) : 0;
    const fillEl = document.getElementById('progress-fill');
    fillEl.style.width = percent + '%';
    fillEl.textContent = percent + '%';
    document.getElementById('progress-message').textContent = message;
    document.getElementById('progress-percent').textContent = percent + '%';
}

function scanCompleted(data) {
    resetScanUI();
    updateProgress(100, 100, 'Escaneo completado');
    
    currentDuplicates = data.duplicates || [];
    groupSelections = {};
    
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

function renderDuplicates() {
    const container = document.getElementById('duplicates-container');
    const resultsSection = document.getElementById('results-section');
    
    if (!currentDuplicates || currentDuplicates.length === 0) {
        resultsSection.style.display = 'block';
        container.innerHTML = `
            <div class="empty-state">
                <h3>No se encontraron duplicados</h3>
                <p>Los archivos en las rutas seleccionadas son únicos.</p>
            </div>
        `;
        document.getElementById('stats').innerHTML = '';
        return;
    }
    
    resultsSection.style.display = 'block';
    
    const totalGroups = currentDuplicates.length;
    const totalFiles = currentDuplicates.reduce((sum, g) => sum + g.count, 0);
    const totalSize = currentDuplicates.reduce((sum, g) => sum + (g.size * g.count), 0);
    const wastedSpace = currentDuplicates.reduce((sum, g) => sum + (g.size * (g.count - 1)), 0);
    
    document.getElementById('stats').innerHTML = `
        <div class="stat-box">
            <div class="stat-num">${totalGroups}</div>
            <div class="stat-label">Grupos de duplicados</div>
        </div>
        <div class="stat-box">
            <div class="stat-num">${totalFiles}</div>
            <div class="stat-label">Archivos duplicados</div>
        </div>
        <div class="stat-box">
            <div class="stat-num">${formatSize(totalSize)}</div>
            <div class="stat-label">Espacio total</div>
        </div>
        <div class="stat-box">
            <div class="stat-num">${formatSize(wastedSpace)}</div>
            <div class="stat-label">Espacio desperdiciado</div>
        </div>
    `;
    
    container.innerHTML = currentDuplicates.map((group, groupIndex) => {
        const groupId = `group-${groupIndex}`;
        return `
            <div class="grupo" id="${groupId}">
                <div class="grupo-header">
                    <span class="hash">${group.hash}</span>
                    <div class="group-info">
                        <div>${group.count} archivos</div>
                        <div>${formatSize(group.size)} c/u</div>
                    </div>
                </div>
                <div class="group-files">
                    ${group.files.map((file, fileIndex) => `
                        <div class="archivo">
                            <input type="radio" 
                                   name="keep-${groupIndex}" 
                                   value="${escapeHtml(file.path)}"
                                   ${fileIndex === 0 ? 'checked' : ''}
                                   onchange="groupSelections[${groupIndex}] = '${escapeHtml(file.path)}'">
                            <div class="archivo-info">
                                <div class="ruta">${escapeHtml(file.path)}</div>
                                <div class="meta">
                                    ${escapeHtml(file.name)} | ${formatSize(file.size)} | ${formatDate(file.modified)}
                                </div>
                            </div>
                            <div class="acciones">
                                <button class="btn-eliminar" onclick="singleAction('delete', '${escapeHtml(file.path)}')">🗑️ Eliminar</button>
                                <button class="btn-mover" onclick="singleAction('move_review', '${escapeHtml(file.path)}')">📂 Revisar</button>
                                <button class="btn-icon" onclick="singleAction('rename', '${escapeHtml(file.path)}')">🏷️ Renombrar</button>
                                <button class="btn-mantener" onclick="singleAction('consolidate', '${escapeHtml(file.path)}')">📦 Consolidar</button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }).join('');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getSelectedKeepPath(groupIndex) {
    const radio = document.querySelector(`input[name="keep-${groupIndex}"]:checked`);
    return radio ? radio.value : null;
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
            const radio = document.querySelector(`input[name="keep-${index}"][value="${CSS.escape(selectedPath)}"]`);
            if (radio) radio.checked = true;
            groupSelections[index] = selectedPath;
        }
    });
    
    showToast(`Conservar ${strategy === 'first' ? 'primero' : strategy === 'largest' ? 'más grande' : 'más reciente'} de cada grupo seleccionado`, 'success');
}

function applyBulkAction(action) {
    const filesToProcess = [];
    const keepPaths = [];
    
    currentDuplicates.forEach((group, index) => {
        const keep = getSelectedKeepPath(index);
        if (!keep) return;
        
        keepPaths.push(keep);
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
    
    const outputPath = document.getElementById('output-path').value.trim();
    const reviewPath = document.getElementById('review-path').value.trim();
    
    fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action,
            files: filesToProcess,
            output_path: outputPath,
            review_path: reviewPath
        })
    })
    .then(r => r.json())
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
    .catch(err => showToast('Error: ' + err, 'error'));
}

function singleAction(action, filepath) {
    const outputPath = document.getElementById('output-path').value.trim();
    const reviewPath = document.getElementById('review-path').value.trim();
    
    if (action === 'delete') {
        if (!confirm(`¿Eliminar ${filepath}?`)) return;
    }
    
    fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action,
            files: [filepath],
            output_path: outputPath,
            review_path: reviewPath
        })
    })
    .then(r => r.json())
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
    .catch(err => showToast('Error: ' + err, 'error'));
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 4000);
}
