# Hallazgos de Revisión de Código - DesDuplicador

**Fecha:** 2026-06-09 (Cuarta revisión)
**Alcance:** app.py, static/js/app.js, templates/index.html, static/css/style.css, tests/test_app.py

---

## Resumen Ejecutivo

Cuarta revisión post-implementación. **32 tests pasando, 0 issues críticos o altos**. Se detectaron **1 issue medio** y **4 issues bajos** nuevos. Todos los issues de revisiones anteriores permanecen resueltos.

| Estado | Crítico | Alto | Medio | Bajo |
|--------|---------|------|-------|------|
| Resueltos ✅ | 3/3 | 5/5 | 10/10 | 7/7 |
| Pendientes ⏳ | 0 | 0 | 1 | 4 |
| Nuevos 🆕 | 0 | 0 | 1 | 4 |

---

## Issues Resueltos ✅ (de revisiones anteriores)

Ver revisiones previas para detalle completo.

| Categoría | Count |
|-----------|-------|
| Críticos | 3 (I/O bomba, código muerto COM, XSS innerHTML) |
| Altos | 5 (race config, path validation, mapa inestable, copia verificada, progress filtrado) |
| Medios | 10 (imports, tests, escapeHtml, type hints, logger config, event delegation, etc.) |
| Bajos | 7 (constantes, logging, gitignore, editorconfig, CSS variables, addPath createElement) |

---

## Nuevos Hallazgos 🆕

### NUEVO-MED-1: SECRET_KEY hardcodeado (app.py:31) — RESUELTO ✅

**Problema:** `SECRET_KEY` hardcodeado.

**Fix aplicado:**
```python
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'desduplicador-secret-key-dev')
```

- Si existe la variable de entorno `SECRET_KEY`, la usa.
- Si no, usa un fallback explícito de desarrollo.
- `import os` ya estaba presente en el módulo.

---

### NUEVO-LOW-1: Inline styles en index.html

**Líneas:** 60, 78, 82

```html
<p style="font-size:11px; color:#808080; margin:8px 0 0 0;">
<div class="progreso-barra-fill" id="progress-fill" style="width: 0%">
<section id="results-section" style="display:none;">
```

**Impacto:** Bajo. Rompe separación de concerns. `style="width: 0%"` y `style="display:none;"` son necesarios para estado inicial pero podrían manejarse con clases CSS (`hidden`, `width-zero`) o desde JS al cargar.

**Fix recomendado:**
- Agregar clase `.help-text` para el párrafo de filtros
- Usar clase `.hidden` para `display: none`
- El `width: 0%` del progress bar puede inicializarse desde JS en `DOMContentLoaded`

---

### NUEVO-LOW-2: Código muerto en event delegation (app.js:825-832)

**Problema:** En el case `browse-folder` del event delegation:

```javascript
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
```

Las líneas 825-832 nunca se ejecutan porque los botones de output-path y review-path en el HTML tienen `data-action="browse-output"` y `data-action="browse-review"` (no `"browse-folder"`). Esos flujos se manejan en cases separados (líneas 836-841).

**Impacto:** Bajo. Código inalcanzable, confunde la lógica.

**Fix recomendado:** Eliminar las dos verificaciones `querySelector('#output-path')` y `querySelector('#review-path')` del case `browse-folder`.

---

### NUEVO-LOW-3: `_collect_files` como función anidada (app.py:234)

**Problema:** `_collect_files` se define dentro de `scan_worker`, por lo que se recompila en cada llamada al worker.

**Impacto:** Bajo. En Python las funciones anidadas tienen overhead mínimo, pero es anti-patrón para una función pura sin dependencias del closure.

**Fix recomendado:** Mover `_collect_files` al nivel de módulo (igual que `md5_file`, `format_size`, etc.).

---

### NUEVO-LOW-4: Lógica duplicada `formatSize` / `format_size`

**Problema:** `formatSize` en JS (línea 478) y `format_size` en Python (línea 62) implementan exactamente el mismo algoritmo de formato de bytes.

**Impacto:** Bajo. Cambios en formato requieren editar dos lugares.

**Fix recomendado:** No hay fix trivial sin que el backend formatee todo (ineficiente) o el frontend tenga que llamar al backend por cada número. Aceptable como duplicación conocida.

---

## Arquitectura: Estado Actual

### Seguridad de hilos ✅
- `config_lock` protege todas las operaciones de archivo.
- `scan_thread` chequeo `is_alive()` + lock de config.

### Rendimiento ✅
- `os.scandir()` reemplazó `os.walk()` en `_collect_files`.
- Sin lecturas de disco repetidas.

### Seguridad ⚠️
- Rutas validadas en `/api/action`.
- XSS mitigado (createElement + textContent).
- **NUEVO-MED-1:** SECRET_KEY hardcodeado.
- Sin CSRF protection (aceptable para uso local).

---

## Tests: Estado Actual

**32 tests, todos pasando.**

| Suite | Tests | Cobertura |
|-------|-------|-----------|
| `TestDetectarCategoria` | 8 | Categorías + case insensitive + otros |
| `TestArchivoPasaFiltro` | 5 | Sin filtros, activo/inactivo, video por tamaño |
| `TestFormatSize` | 4 | 0 B, KB, MB, GB |
| `TestEscapeHtml` | 1 | `< > & "` |
| `TestFlaskEndpoints` | 5 | GET/POST config, filters, last_scan, roundtrip |
| `TestConfigSaveLoad` | 1 | Save + load con monkeypatch |
| `TestActionEndpoint` | 5 | delete, rename, move_review, consolidate, path not allowed |
| `TestBrowseFolder` | 3 | PowerShell, ctypes, cancelado |

---

## Recomendaciones

### Prioridad Baja (no bloqueantes)
2. **NUEVO-LOW-1**: Mover inline styles del HTML a clases CSS.
3. **NUEVO-LOW-2**: Eliminar código muerto en event delegation (`browse-folder` case).
4. **NUEVO-LOW-3**: Mover `_collect_files` a nivel de módulo.
