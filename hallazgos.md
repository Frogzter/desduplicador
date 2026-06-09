# Hallazgos de Revisión de Código - DesDuplicador

**Fecha:** 2026-06-08
**Alcance:** app.py, static/js/app.js, templates/index.html, static/css/style.css

---

## Resumen

| Severidad | Cantidad | Descripción |
|-----------|----------|-------------|
| Crítico | 3 | Bugs que causan crashes, pérdida de datos o vulnerabilidades de seguridad |
| Alto | 5 | Issues que causan degradación de rendimiento o problemas de confiabilidad |
| Medio | 8 | Code smells, problemas de mantenibilidad, faltan mejores prácticas |
| Bajo | 6 | Mejoras menores, inconsistencias de estilo |

---

## Issues Críticos

### CRIT-1: Bomba de I/O en la función de filtro (`app.py:69`)

**Problema:** `archivo_pasa_filtro()` llama `load_config()` **por cada archivo** durante el escaneo. Esto lee `data/config.json` del disco repetidamente — potencialmente miles o millones de veces.

```python
def archivo_pasa_filtro(archivo_path, filtros_activos, tamano):
    ...
    if categoria == 'video' and 'video' in filtros_activos:
        tamano_min = load_config().get('tamano_min_video', TAMANO_MIN_VIDEO_DEFAULT)  # ¡LECTURA DE DISCO!
```

**Impacto:** Escaneo de 100,000 archivos = 100,000 lecturas de disco. El escaneo puede ser **10x-100x más lento** de lo que debería.

**Fix:** Pasar `tamano_min_video` como parámetro.

---

### CRIT-2: Dependencia faltante `comtypes` en requirements.txt

**Problema:** `_browse_ifiledialog()` importa `comtypes` y `comtypes.client`, pero `comtypes` **no está** en `requirements.txt`. Si el path de ctypes falla y se alcanza esta función, crashea con `ModuleNotFoundError`.

**Fix:** Agregar `comtypes` a `requirements.txt` o eliminar este código muerto por completo.

---

### CRIT-3: Vulnerabilidad XSS vía `innerHTML` con rutas de usuario

**Problema:** `static/js/app.js` usa `innerHTML` para renderizar rutas de archivo que vienen del sistema operativo. Un nombre de archivo o carpeta malicioso con HTML/JS se ejecutará en el navegador.

```javascript
dom.duplicatesContainer().innerHTML = currentDuplicates
    .map((group, groupIndex) => renderGroup(group, groupIndex))
    .join('');
```

La función `escapeHtml()` solo maneja contexto de contenido de texto, no atributos HTML.

**Fix:** Usar `document.createElement()` / `textContent` en vez de `innerHTML` para renderizar duplicados.

---

## Issues Altos

### HIGH-1: Race condition en escrituras de config (`app.py:91`)

`save_config()` se llama desde el hilo de background `scan_worker` y desde el hilo principal de Flask simultáneamente. Ambos hilos pueden intentar escribir a `data/config.json` al mismo tiempo.

**Fix:** Agregar `threading.Lock()` alrededor de las operaciones de archivo de config.

### HIGH-2: Sin validación de rutas en `/api/action`

El endpoint de acción acepta rutas de archivo arbitrarias del cliente y ejecuta `os.remove()`, `shutil.move()`, `shutil.copy2()` sin validación. Un cliente malicioso podría borrar cualquier archivo al que el proceso tenga acceso.

**Fix:** Validar que las rutas están dentro de los directorios de origen configurados antes de actuar.

### HIGH-3: Riesgo de colisión de claves en `fileIdentityMap`

El mapa de identidad de archivos usa `${groupIndex}::${fileIndex}` como claves. Si los resultados se re-renderizan mientras hay acciones pendientes, los índices cambian y las acciones pueden apuntar a archivos equivocados.

**Fix:** Usar la ruta real del archivo como clave, o un UUID estable por archivo.

### HIGH-4: Fallo silencioso de `shutil.copy2` en Consolidar

Si `shutil.copy2()` falla a mitad de camino (disco lleno, permisos denegados), el archivo queda en estado parcial y el original NO se elimina. Pero el mensaje de éxito dice "Copiado a ..." de todas formas.

**Fix:** Verificar que el archivo copiado existe y tiene el tamaño correcto antes de eliminar el original.

### HIGH-5: El progreso no refleja el filtrado

La barra de progreso muestra `total = len(archivos_filtrados)`, pero el conteo inicial cuenta TODOS los archivos. Si los filtros excluyen muchos archivos, la barra salta de 0% a un porcentaje alto después del filtrado.

**Fix:** Agregar un paso de progreso "Filtrando archivos..." entre el conteo y el hashing.

---

## Issues Medios

### MED-1: Código muerto `_browse_ifiledialog`

Esta función siempre lanza una excepción. No sirve para nada y agrega una dependencia innecesaria en `comtypes`.

### MED-2: Import `emit` no usado

`emit` se importa de `flask_socketio` pero nunca se usa directamente. Todas las emisiones van por `socketio.emit()`.

### MED-3: Convención de nombres mezclada español/inglés

- Español: `detectar_categoria`, `archivo_pasa_filtro`, `tamano_min_video`
- Inglés: `fileIdentityMap`, `scan_worker`, `currentDuplicates`, `REQUEST_TIMEOUT_MS`

**Impacto:** Hace el código más difícil de leer y mantener.

### MED-4: Sin type hints

Ninguna función tiene type hints. Esto hace más difícil detectar bugs temprano y que los IDEs den autocompletado.

### MED-5: Mezcla de `onclick` inline + event delegation

Algunos botones usan `onclick="browseFolder(this)"` en HTML, mientras otros usan event delegation en JS. Crea potencial doble-ejecución o confusión.

### MED-6: Imports dentro de funciones

`comtypes`, `subprocess` y `tempfile` se importan dentro del cuerpo de funciones. Esto retrasa errores de importación hasta runtime.

### MED-7: Sin tests unitarios

Cero archivos de test. Los únicos "tests" son scripts ad-hoc inline.

### MED-8: `escapeHtml` no escapa atributos

La función solo escapa para contexto de contenido de texto, no para atributos HTML. Una ruta como `test" onmouseover="alert(1)` podría romper fuera de un atributo.

---

## Issues Bajos

### LOW-1: Número mágico `17` para `RootFolder`

```python
dialog.RootFolder = 17  # MyComputer = CSIDL_DRIVES
```

### LOW-2: `print()` en vez de logging

Los mensajes de error usan `print()` en vez de un framework de logging apropiado.

### LOW-3: `data/config.json` trackeado E ignorado

`data/config.json` fue trackeado previamente en git pero ahora está en `.gitignore`. Git todavía lo trackea, causando confusión.

### LOW-4: TODO.md tiene item sin chequear

```markdown
- [ ] Run thorough validation of updated UI flows and interactions.
```

### LOW-5: Archivo CSS de 770 líneas sin variables

`style.css` se acerca a 800 líneas sin organización más allá de comentarios. No usa CSS custom properties para los colores del tema.

### LOW-6: Sin `package.json` ni `eslint`

No hay herramientas de linting o formatting configuradas para el código JavaScript.

---

## Preocupaciones de Arquitectura

### Seguridad de hilos
La app usa `scan_thread` y `scan_stop_event` globales compartidos entre el handler de requests de Flask (hilo principal) y el worker de escaneo. El chequeo `if scan_thread and scan_thread.is_alive()` no es atómico — dos clicks rápidos podrían iniciar dos escaneos.

### Escalabilidad
- `md5_file()` lee el archivo completo en chunks. Para millones de archivos pequeños, el overhead de `os.walk()` + `Path.stat()` domina.
- Considerar usar `os.scandir()` en vez de `os.walk()` para mejor rendimiento.

### Seguridad
- Sin protección CSRF en endpoints POST (la `SECRET_KEY` está seteada pero no se usa para CSRF).
- Sin rate limiting en endpoints de acción.
- Las rutas de archivo se aceptan literalmente del cliente sin sanitización.

---

## Hallazgos Positivos

| Hallazgo | Archivo | Notas |
|----------|---------|-------|
| Event delegation en JS | `app.js` | Patrón limpio para elementos dinámicos |
| Capa de abstracción API | `app.js` | `apiRequest`, `apiGet`, `apiPost` con timeout |
| Helper DOM | `app.js` | Acceso a DOM centralizado con null-safety |
| Normalización de errores | `app.js` | Manejo consistente de errores |
| Persistencia de config | `app.py` | Config JSON con defaults |
| Sistema de filtros | `app.py` | Filtrado limpio por categoría |
| Consistencia de tema | `style.css` | Coincide con `tema_colores_estilos.md` |
| Fallback de diálogo | `app.py` | Fallback robusto entre métodos |

---

## Orden de Prioridad Recomendado

1. Arreglar **CRIT-1** (bomba I/O) — cambio de una línea, mejora masiva de performance
2. Arreglar **CRIT-3** (XSS) — fix de seguridad
3. Arreglar **HIGH-1** (race condition) — agregar `threading.Lock()`
4. Arreglar **HIGH-2** (validación de rutas) — fix de seguridad
5. Arreglar **CRIT-2 + MED-1** (eliminar código muerto)
6. Arreglar **MED-3** (consistencia de nombres)
7. Agregar **MED-7** (tests)
