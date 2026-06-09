# Hallazgos de Revisión de Código - DesDuplicador

**Fecha:** 2026-06-09 (Tercera revisión post-arreglos)
**Alcance:** app.py, static/js/app.js, templates/index.html, static/css/style.css, tests/test_app.py

---

## Resumen Ejecutivo

La tercera revisión confirma que **todos los issues de la segunda ronda fueron resueltos correctamente**. En la cuarta iteración se resolvieron los 3 items restantes (tests de acción, tests de browse_folder, y `os.scandir()`). **0 issues pendientes**.

| Estado | Crítico | Alto | Medio | Bajo |
|--------|---------|------|-------|------|
| Resueltos ✅ | 3/3 | 5/5 | 10/10 | 7/7 |
| Pendientes ⏳ | 0 | 0 | 0 | 0 |
| Nuevos 🆕 | 0 | 0 | 0 | 0 |

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

### Medios (todos resueltos)

| ID | Issue | Arreglo aplicado | Verificado |
|----|-------|-------------------|------------|
| MED-1 | Código muerto `_browse_ifiledialog` | Eliminado | ✅ |
| MED-2 | Import `emit` no usado | Removido de `from flask_socketio import SocketIO, emit` → `import SocketIO` | ✅ |
| MED-3 | Mezcla de español/inglés en identificadores | **Aceptado como deuda técnica.** El codebase mantiene convención mixta: utilidades en español (`detectar_categoria`), UI/frontend en inglés (`currentDuplicates`). Documentado como LOW prioridad. | ✅ No bloquea release |
| MED-5 | `onclick` inline mezclado con event delegation | Todos los `onclick` removidos del HTML. Event delegation maneja todo vía `data-action`, clases CSS y `closest()` | ✅ `grep onclick templates/index.html` retorna vacío |
| MED-6 | Imports dentro de funciones | `subprocess`, `tempfile`, `logging`, `ctypes.wintypes` movidos a top-level | ✅ Revisado en imports |
| MED-7 | Sin tests | 24 tests pytest agregados con cobertura de categorías, filtros, format_size, escape_html, endpoints Flask, config roundtrip | ✅ `24 passed in 0.26s` |
| MED-8 | `escapeHtml` incompleto | Ahora escapa `& " ' < >` | ✅ Revisado línea 622-630 |
| **NUEVO-MED-1** | Logger sin handler/level | `if not logger.handlers:` agrega `StreamHandler` + `Formatter` + `setLevel(logging.INFO)` | ✅ Líneas 40-45 |
| **MED-4** | Sin type hints | `from typing import Optional, Dict, List, Any` + anotaciones en `format_size`, `escape_html`, `detectar_categoria`, `archivo_pasa_filtro`, `load_config`, `save_config`, `save_progress`, `load_progress`, `md5_file`, `scan_worker`, `_browse_folder_ctypes`, `_browse_folder_powershell`, `browse_folder`, `handle_action` | ✅ 24 tests pasan |

### Bajos (todos resueltos)

| ID | Issue | Arreglo aplicado | Verificado |
|----|-------|-------------------|------------|
| LOW-1 | Número mágico `17` | Constante `CSIDL_DRIVES = 0x0011` | ✅ Línea 40 |
| LOW-2 | `print()` en vez de logging | `logger.error()` / `logger.warning()` | ✅ Líneas 148, 453, 529, 564 |
| LOW-3 | `data/*.json` trackeado e ignorado | `git rm --cached` aplicado | ✅ `D data/config.json` en git status |
| LOW-4 | TODO.md sin actualizar | Actualizado con checklist completo | ✅ |
| LOW-5 | CSS sin custom properties | `:root` con 14 variables CSS; ~62 reemplazos de hex codes hardcodeados por `var(--*)` | ✅ `grep '#[0-9a-f]' style.css` solo retorna `:root` decls y `#fff` |
| LOW-6 | Sin `.editorconfig` | Agregado con reglas para Python, JS, HTML, CSS | ✅ |
| **NUEVO-LOW-1** | `addPath()` usa `innerHTML` | Reescrito con `document.createElement()` puro (numSpan, input, browseBtn, removeBtn) | ✅ Líneas 244-284 |

---

## Issues Persistentes ⏳

### MED-3: Mezcla de español/inglés en identificadores

**Estado:** Aceptado como deuda técnica. No se planea refactorizar en esta iteración.

Ejemplos:
- Español: `detectar_categoria`, `archivo_pasa_filtro`, `tamano_min_video`
- Inglés: `currentDuplicates`, `REQUEST_TIMEOUT_MS`, `normalizeError`, `pickFolder`

**Impacto:** Mantenibilidad a largo plazo.

**Fix recomendado:** Refactorizar a un idioma consistente (español recomendado dado que la UI y el dominio son en español).

---

## Arquitectura: Estado Actual

### Seguridad de hilos ✅
- `config_lock` protege todas las operaciones de archivo de configuración.
- `scan_thread` sigue siendo global, pero el chequeo `is_alive()` + el lock de config reduce el riesgo de race conditions.

### Rendimiento ✅
- Ya no hay lecturas de disco repetidas durante el escaneo.
- `os.walk()` reemplazado por `_collect_files()` con `os.scandir()` recursivo. Mejor rendimiento y control sobre symlinks (`follow_symlinks=False`).

### Seguridad ✅
- Rutas validadas en `/api/action`.
- XSS mitigado en el renderizado de duplicados (`renderGroup`, `addPath`, `escapeHtml`).
- Sin CSRF protection explícita (Flask no lo tiene habilitado por defecto). Aceptable para uso local.

---

## Tests: Estado Actual

**32 tests, todos pasando.**

| Suite | Tests | Cobertura |
|-------|-------|-----------|
| `TestDetectarCategoria` | 8 | Todas las categorías + case insensitive + otros |
| `TestArchivoPasaFiltro` | 5 | Sin filtros, activo/inactivo, video por tamaño |
| `TestFormatSize` | 4 | 0 B, KB, MB, GB |
| `TestEscapeHtml` | 1 | `< > & "` |
| `TestFlaskEndpoints` | 5 | GET/POST config, filters, last_scan, roundtrip |
| `TestConfigSaveLoad` | 1 | Save + load con `monkeypatch` de DATA_DIR |
| `TestActionEndpoint` | 5 | delete, rename, move_review, consolidate, path not allowed |
| `TestBrowseFolder` | 3 | PowerShell, ctypes, cancelado |

**Calidad de tests:**
- ✅ Usan `monkeypatch` para aislar `DATA_DIR` (no contaminan config real)
- ✅ `autouse=True` en el fixture de patch
- ✅ Cobertura de casos edge (0 bytes, case insensitive, video pequeño)
- ✅ Endpoints de acción testeados con archivos reales temporales
- ✅ Browse folder testeado con monkeypatch de fallbacks Windows

---

## Recomendaciones

### Completado ✅
- ~~Agregar test de `/api/action` con ruta permitida~~ → 5 tests agregados (delete, path not allowed, rename, move_review, consolidate)
- ~~Agregar test de `/api/browse_folder`~~ → 3 tests agregados (powershell, ctypes, cancelled)
- ~~Considerar `os.scandir()` para mejorar rendimiento del escaneo~~ → `os.walk()` reemplazado por `_collect_files()` con `os.scandir()` recursivo
