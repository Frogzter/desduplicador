# TODO - DesDuplicador

## Completado (Revisión 2026-06-09)

- [x] CRIT-1: Arreglar bomba de I/O en `archivo_pasa_filtro()`
- [x] CRIT-2: Eliminar código muerto `_browse_ifiledialog`
- [x] CRIT-3: Arreglar vulnerabilidad XSS via `innerHTML`
- [x] HIGH-1: Agregar `threading.Lock()` en config/progress
- [x] HIGH-2: Validar rutas en `/api/action`
- [x] HIGH-3: Usar rutas estables en vez de índices para fileIdentityMap
- [x] HIGH-4: Verificar copia antes de eliminar en consolidate
- [x] HIGH-5: Progress refleja archivos filtrados
- [x] MED-1: Eliminar `_browse_ifiledialog` (código muerto)
- [x] MED-2: Remover import `emit` no usado
- [x] MED-5: Remover `onclick` inline, usar event delegation
- [x] MED-6: Mover `subprocess`/`tempfile` al top
- [x] MED-7: Agregar tests pytest (20 tests)
- [x] MED-8: `escapeHtml` escapa comillas simples y dobles
- [x] LOW-1: Constante `CSIDL_DRIVES` en vez de número mágico
- [x] LOW-2: `logger` en vez de `print()`
- [x] LOW-3: `data/*.json` fuera de git tracking
- [x] LOW-4: TODO.md actualizado
- [x] LOW-6: `.editorconfig` agregado

## Pendiente (baja prioridad)

- [ ] LOW-5: CSS custom properties para colores del tema
- [ ] MED-3: Unificar nombres a un solo idioma
- [ ] MED-4: Type hints en funciones públicas
