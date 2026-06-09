# Hallazgos de Revisión de Código - DesDuplicador

**Fecha:** 2026-06-09 (Segunda revisión post-arreglos)
**Alcance:** app.py, static/js/app.js, templates/index.html, static/css/style.css, tests/test_app.py

---

## Resumen Ejecutivo

La segunda revisión confirma que **todos los issues críticos y altos de la primera ronda fueron resueltos correctamente**. Se detectaron **2 issues menores** nuevos y **3 issues de baja prioridad** que persisten.

| Estado | Crítico | Alto | Medio | Bajo |
|--------|---------|------|-------|------|
| Resueltos ✅ | 3/3 | 5/5 | 6/8 | 3/6 |
| Pendientes ⏳ | 0 | 0 | 2 | 3 |
| Nuevos 🆕 | 0 | 0 | 1 | 1 |

---

## Issues Resueltos ✅

### Críticos (todos resueltos)

| ID | Issue | Arreglo aplicado | Verificado |
|----|-------|-------------------|------------|
| CRIT-1 | Bomba de I/O: `load_config()` por cada archivo | `tamano_min_video` pasa como parámetro a `archivo_pasa_filtro()` | ✅ Tests pasan |
| CRIT-2 | Código muerto `_browse_ifiledialog` requería `comtypes` | Función eliminada por completo | ✅ No aparece en el código |
| CRIT-3 | XSS vía `innerHTML` con rutas de usuario | `renderGroup()` reescrito con `document.createElement()` + `textContent` | ✅ Revisado línea por línea |

### Altos (todos resueltos)

| ID | Issue | Arreglo aplicado | Verificado |
|----|-------|-------------------|------------|
| HIGH-1 | Race condition en config/progress | `threading.Lock()` (`config_lock`) envuelve todas las operaciones de archivo | ✅ Revisado en `load_config`, `save_config`, `save_progress`, `load_progress` |
| HIGH-2 | Sin validación de rutas en `/api/action` | `_is_path_allowed()` verifica que cada archivo esté dentro de las rutas configuradas usando `Path.relative_to()` | ✅ Test `test_action_path_validation` pasa |
| HIGH-3 | `fileIdentityMap` con índices inestables | Eliminado completamente. Ahora `radio.value = file.path` y `data-file-id = file.path` | ✅ No hay mapa de índices |
| HIGH-4 | Copia parcial silenciosa en consolidate | Se verifica `dest.exists()` y `dest.stat().st_size == src.stat().st_size` antes de `src.unlink()` | ✅ Revisado en línea 411-414 |
| HIGH-5 | Progress no refleja filtrado | Paso intermedio "Filtrando archivos..." agregado con `filtrados_count` | ✅ Líneas 246-262 |

### Medios (resueltos)

| ID | Issue | Arreglo aplicado | Verificado |
|----|-------|-------------------|------------|
| MED-1 | Código muerto `_browse_ifiledialog` | Eliminado | ✅ |
| MED-2 | Import `emit` no usado | Removido de `from flask_socketio import SocketIO, emit` → `import SocketIO` | ✅ |
| MED-5 | `onclick` inline mezclado con event delegation | Todos los `onclick` removidos del HTML. Event delegation maneja todo vía `data-action`, clases CSS y `closest()` | ✅ `grep onclick templates/index.html` retorna vacío |
| MED-6 | Imports dentro de funciones | `subprocess`, `tempfile`, `logging`, `ctypes.wintypes` movidos a top-level | ✅ Revisado en imports |
| MED-7 | Sin tests | 24 tests pytest agregados con cobertura de categorías, filtros, format_size, escape_html, endpoints Flask, config roundtrip | ✅ `24 passed in 0.26s` |
| MED-8 | `escapeHtml` incompleto | Ahora escapa `& " ' < >` | ✅ Revisado línea 622-630 |

### Bajos (resueltos)

| ID | Issue | Arreglo aplicado | Verificado |
|----|-------|-------------------|------------|
| LOW-1 | Número mágico `17` | Constante `CSIDL_DRIVES = 0x0011` | ✅ Línea 40 |
| LOW-2 | `print()` en vez de logging | `logger.error()` / `logger.warning()` | ✅ Líneas 148, 453, 529, 564 |
| LOW-3 | `data/*.json` trackeado e ignorado | `git rm --cached` aplicado | ✅ `D data/config.json` en git status |
| LOW-4 | TODO.md sin actualizar | Actualizado con checklist completo | ✅ |
| LOW-6 | Sin `.editorconfig` | Agregado con reglas para Python, JS, HTML, CSS | ✅ |

---

## Nuevos Hallazgos 🆕

### NUEVO-MED-1: Logger sin configuración (app.py:39)

**Problema:** `logger = logging.getLogger('desduplicador')` se crea pero nunca se configura con un `Handler` o nivel. En Python, un logger sin handlers no emite mensajes por defecto (a menos que la raíz tenga un handler configurado).

**Impacto:** Los mensajes de `logger.error()` y `logger.warning()` se pierden silenciosamente.

**Fix recomendado:**
```python
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
```

O más conservador, solo si no hay handlers configurados:
```python
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
```

**Severidad:** Medio (los errores se pierden en producción)

---

### NUEVO-LOW-1: `addPath()` aún usa `innerHTML` (app.js:243)

**Problema:** `addPath()` usa `innerHTML` para construir la fila de ruta:
```javascript
row.innerHTML = `
    <span class="ruta-num">${nextNum}</span>
    <input type="text" class="path-input" ... value="${escapeHtml(value)}" />
    ...
`;
```

Aunque `escapeHtml()` escapa correctamente para atributos HTML, el patrón `innerHTML` con templates sigue siendo un vector potencial si alguien olvida escapar una variable en el futuro.

**Impacto:** Bajo. Actualmente está protegido por `escapeHtml(value)`.

**Fix recomendado:** Reescribir `addPath()` con `document.createElement()` como se hizo con `renderGroup()`.

---

## Issues Persistentes ⏳

### MED-3: Mezcla de español/inglés en identificadores

Sigue presente. Ejemplos:
- Español: `detectar_categoria`, `archivo_pasa_filtro`, `tamano_min_video`
- Inglés: `currentDuplicates`, `REQUEST_TIMEOUT_MS`, `normalizeError`, `pickFolder`

**Impacto:** Mantenibilidad. Dificulta la navegación del código para desarrolladores nuevos.

**Fix recomendado:** Refactorizar a un idioma consistente (español recomendado dado que la UI y el dominio son en español).

---

### MED-4: Sin type hints

Ninguna función tiene anotaciones de tipo. Ejemplos que beneficiarían:
```python
def detectar_categoria(archivo_path: str | Path) -> str: ...
def archivo_pasa_filtro(archivo_path: str, filtros_activos: list[str], tamano: int, tamano_min_video: int | None = None) -> bool: ...
def format_size(bytes_val: int) -> str: ...
```

**Impacto:** Los IDEs no pueden dar autocompletado preciso. Los errores de tipo solo se detectan en runtime.

---

### LOW-5: CSS sin custom properties

`style.css` tiene 770+ líneas con colores hardcodeados. No usa CSS custom properties (`:root { --color: #value }`).

**Impacto:** Cambiar un color del tema requiere buscar y reemplazar múltiples ocurrencias.

**Fix recomendado:**
```css
:root {
    --bg-page: #1e1e1e;
    --bg-section: #252526;
    --accent-blue: #569cd6;
    --accent-green: #4ec9b0;
    --accent-red: #f48771;
}
```

---

## Arquitectura: Estado Actual

### Seguridad de hilos ✅
- `config_lock` protege todas las operaciones de archivo de configuración.
- `scan_thread` sigue siendo global, pero el chequeo `is_alive()` + el lock de config reduce el riesgo de race conditions.

### Rendimiento ✅
- Ya no hay lecturas de disco repetidas durante el escaneo.
- `os.walk()` sigue siendo el cuello de botella para millones de archivos pequeños. `os.scandir()` sería un 2-3x más rápido.

### Seguridad ✅
- Rutas validadas en `/api/action`.
- XSS mitigado en el renderizado de duplicados.
- Sin CSRF protection explícita (Flask no lo tiene habilitado por defecto). Aceptable para uso local.

---

## Tests: Estado Actual

**24 tests, todos pasando.**

| Suite | Tests | Cobertura |
|-------|-------|-----------|
| `TestDetectarCategoria` | 8 | Todas las categorías + case insensitive + otros |
| `TestArchivoPasaFiltro` | 5 | Sin filtros, activo/inactivo, video por tamaño |
| `TestFormatSize` | 4 | 0 B, KB, MB, GB |
| `TestEscapeHtml` | 1 | `< > & "` |
| `TestFlaskEndpoints` | 5 | GET/POST config, filters, last_scan, roundtrip |
| `TestConfigSaveLoad` | 1 | Save + load con `monkeypatch` de DATA_DIR |

**Calidad de tests:**
- ✅ Usan `monkeypatch` para aislar `DATA_DIR` (no contaminan config real)
- ✅ `autouse=True` en el fixture de patch
- ✅ Cobertura de casos edge (0 bytes, case insensitive, video pequeño)
- ⏳ Falta: test del endpoint `/api/action` con path permitida
- ⏳ Falta: test de `/api/browse_folder` (difícil de testear por dependencia de Windows)

---

## Recomendaciones

### Prioridad Inmediata (antes del siguiente release)
1. **NUEVO-MED-1**: Configurar el logger para que los errores sean visibles.

### Prioridad Media (próxima iteración)
2. **MED-3**: Estandarizar nombres a un solo idioma.
3. **MED-4**: Agregar type hints a funciones públicas.
4. **NUEVO-LOW-1**: Reescribir `addPath()` sin `innerHTML`.

### Prioridad Baja (cuando haya tiempo)
5. **LOW-5**: CSS custom properties.
6. Agregar test de `/api/action` con ruta permitida.
7. Considerar `os.scandir()` para mejorar rendimiento del escaneo.
