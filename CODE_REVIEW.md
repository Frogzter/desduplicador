# Code Review Report - DesDuplicador

**Date:** 2026-06-08
**Scope:** app.py, static/js/app.js, templates/index.html, static/css/style.css

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| Critical | 3 | Bugs that cause crashes, data loss, or security vulnerabilities |
| High | 5 | Issues that cause performance degradation or reliability problems |
| Medium | 8 | Code smells, maintainability issues, missing best practices |
| Low | 6 | Minor improvements, style inconsistencies |

---

## Critical Issues

### CRIT-1: I/O Bomb in Filter Function (`app.py:56-73`)

**Problem:** `archivo_pasa_filtro()` calls `load_config()` **on every single file** during the scan. This reads `data/config.json` from disk repeatedly — potentially thousands or millions of times.

```python
def archivo_pasa_filtro(archivo_path, filtros_activos, tamano):
    ...
    if categoria == 'video' and 'video' in filtros_activos:
        tamano_min = load_config().get('tamano_min_video', TAMANO_MIN_VIDEO_DEFAULT)  # DISK READ!
```

**Impact:** Scanning 100,000 files = 100,000 disk reads of a small JSON file. This will make scanning **10x-100x slower** than it should be.

**Fix:** Pass `tamano_min_video` as a parameter:
```python
def archivo_pasa_filtro(archivo_path, filtros_activos, tamano, tamano_min_video=None):
    ...
    tamano_min = tamano_min_video or TAMANO_MIN_VIDEO_DEFAULT
```

---

### CRIT-2: Missing Dependency (`comtypes`) in requirements.txt

**Problem:** `_browse_ifiledialog()` imports `comtypes` and `comtypes.client`, but `comtypes` is **not** in `requirements.txt`. If the ctypes path fails and this function is reached, it will crash with `ModuleNotFoundError`.

```python
def _browse_ifiledialog(title, initial_dir):
    import comtypes          # NOT in requirements.txt
    from comtypes.client import CreateObject
```

**Fix:** Either add `comtypes` to `requirements.txt` or remove this dead code path entirely (see MED-1).

---

### CRIT-3: XSS Vulnerability via `innerHTML` with User Paths

**Problem:** `static/js/app.js` uses `innerHTML` to render file paths that come from the filesystem. A malicious file or folder name containing HTML/JS will execute in the browser.

```javascript
// Line 517 - file.path comes from the OS, could be: <img src=x onerror=alert(1)>
dom.duplicatesContainer().innerHTML = currentDuplicates
    .map((group, groupIndex) => renderGroup(group, groupIndex))
    .join('');
```

The `escapeHtml()` function only handles text content, not attribute contexts. The `data-file-id` attributes are generated from an internal map, but the path strings are rendered directly into HTML.

**Fix:** Use `document.createElement()` / `textContent` instead of `innerHTML` for rendering duplicates. Or at minimum, escape paths before inserting into HTML templates.

---

## High Issues

### HIGH-1: Race Condition on Config Writes (`app.py:91-93`)

**Problem:** `save_config()` is called from the background `scan_worker` thread AND from the main Flask thread simultaneously. Both threads can try to write to `data/config.json` at the same time.

```python
def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ...)
```

**Fix:** Add a `threading.Lock()` around config file operations.

---

### HIGH-2: No Path Validation on `/api/action` (`app.py:284-364`)

**Problem:** The action endpoint accepts arbitrary file paths from the client and performs `os.remove()`, `shutil.move()`, `shutil.copy2()` on them without any validation. A malicious client could:
- Delete any file the server process has access to
- Overwrite system files
- Move files outside intended directories

```python
@app.route('/api/action', methods=['POST'])
def handle_action():
    files = data.get('files', [])
    for filepath in files:
        src = Path(filepath)
        src.unlink()  # No validation!
```

**Fix:** Validate that paths are within the configured source directories before acting on them.

---

### HIGH-3: `fileIdentityMap` Key Collision Risk

**Problem:** File identity map uses `${groupIndex}::${fileIndex}` as keys. If the results are re-rendered while actions are pending, the indices shift and actions could target wrong files.

```javascript
const fileId = `${groupIndex}::${fileIndex}`;
fileIdentityMap[fileId] = file.path;
```

**Fix:** Use the actual file path as the key, or use a stable UUID per file.

---

### HIGH-4: Silent Failure on `shutil.copy2` in Consolidate

**Problem:** If `shutil.copy2()` fails partway through (disk full, permission denied), the file is left in a partial state and the original is NOT deleted. But the success message says "Copiado a ..." regardless.

**Fix:** Verify the copied file exists and has the correct size before removing the original. Or use atomic copy-then-rename.

---

### HIGH-5: Progress Reported After Filtering but Not During

**Problem:** The progress bar shows `total = len(archivos_filtrados)`, but the initial "Contando archivos" step counts ALL files. If filters exclude many files, the progress bar jumps from 0% to a high percentage after filtering is done, with no visual indication of the filtering step.

**Fix:** Add a "Filtrando archivos..." progress step between counting and hashing.

---

## Medium Issues

### MED-1: Dead Code `_browse_ifiledialog` (`app.py:484-500`)

**Problem:** This function always raises an exception. It serves no purpose and adds an unnecessary dependency on `comtypes`.

```python
def _browse_ifiledialog(title, initial_dir):
    ...
    raise Exception("COM tipado no disponible, usar powershell")
```

**Fix:** Remove this function entirely. The PowerShell path works well.

---

### MED-2: Unused Import `emit` (`app.py:9`)

**Problem:** `emit` is imported from `flask_socketio` but never used directly. All emissions go through `socketio.emit()`.

**Fix:** Remove `emit` from the import.

---

### MED-3: Mixed Language Naming Convention

**Problem:** The codebase mixes Spanish and English identifiers inconsistently:
- Spanish: `detectar_categoria`, `archivo_pasa_filtro`, `tamano_min_video`
- English: `fileIdentityMap`, `scan_worker`, `currentDuplicates`, `REQUEST_TIMEOUT_MS`

**Impact:** Makes the code harder to read and maintain, especially for teams.

**Recommendation:** Choose one language (Spanish is fine since the UI is Spanish) and stick to it consistently.

---

### MED-4: Missing Type Hints

**Problem:** No type hints anywhere. This makes it harder to catch bugs early and harder for IDEs to provide autocomplete.

**Fix:** Add type hints to public functions, e.g.:
```python
def detectar_categoria(archivo_path: str | Path) -> str: ...
def archivo_pasa_filtro(archivo_path: str, filtros_activos: list[str], tamano: int) -> bool: ...
```

---

### MED-5: Inline `onclick` + Event Delegation Mixed (`templates/index.html`)

**Problem:** Some buttons use `onclick="browseFolder(this)"` in HTML, while others use event delegation in JS (`document.addEventListener('click', ...)`). The `browseFolder` inline handler references a function that also has event delegation logic, creating potential double-execution or confusion.

**Fix:** Remove all inline `onclick` attributes and handle everything through event delegation in JS.

---

### MED-6: `comtypes` and `tempfile` Imported Inside Functions

**Problem:** `_browse_ifiledialog` imports `comtypes` and `comtypes.client`, while `_browse_folder_powershell` imports `subprocess` and `tempfile` inside the function body. This defers import errors until runtime and prevents static analysis from catching missing dependencies.

**Fix:** Move all imports to the top of the file (with try/except for optional ones).

---

### MED-7: No Unit Tests

**Problem:** Zero test files. The only "tests" are ad-hoc inline scripts.

**Fix:** Add pytest tests for at least:
- `detectar_categoria()`
- `archivo_pasa_filtro()`
- `formatSize()` (JS)
- `escapeHtml()` (JS)
- Config save/load roundtrip

---

### MED-8: `escapeHtml` Doesn't Escape Attribute Contexts

**Problem:** The `escapeHtml` function only escapes for text content context, not for HTML attributes. A path like `test" onmouseover="alert(1)` could break out of an attribute.

```javascript
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;  // Only safe for text content, NOT attributes
}
```

**Fix:** Use a proper escaping function that handles quotes for attribute contexts:
```javascript
function escapeAttr(text) {
    return text.replace(/[&"'<>]/g, c => ({'&':'&amp;','"':'&quot;',"'":'&#39;','<':'&lt;','>':'&gt;'}[c]));
}
```

---

## Low Issues

### LOW-1: Magic Number `17` for `RootFolder` (`app.py:385`)

```python
dialog.RootFolder = 17  # MyComputer = CSIDL_DRIVES
```

**Fix:** Use a named constant:
```python
CSIDL_DRIVES = 0x0011
```

---

### LOW-2: `print()` Instead of Logging (`app.py`)

**Problem:** Error messages use `print()` instead of a proper logging framework. This means errors go to stdout, which may be lost or mixed with HTTP logs.

**Fix:** Use Python's `logging` module:
```python
import logging
logger = logging.getLogger('desduplicador')
```

---

### LOW-3: `data/config.json` Tracked AND Ignored

**Problem:** `data/config.json` was previously tracked in git but is now in `.gitignore`. Git will still track it (since it was already in the index), causing confusion.

**Fix:** Run `git rm --cached data/config.json` to untrack it.

---

### LOW-4: TODO.md Has Unchecked Item

```markdown
- [ ] Run thorough validation of updated UI flows and interactions.
```

**Fix:** Complete or remove this item.

---

### LOW-5: CSS File is 770 Lines

**Problem:** `style.css` is approaching 800 lines with no organization beyond comments. No CSS variables are used for the theme colors.

**Fix:** Consider extracting CSS custom properties:
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

### LOW-6: No `package.json` or `eslint` for JS

**Problem:** No linting or formatting tools configured for the JavaScript code.

**Fix:** Add a simple `eslint` config or at minimum a `.editorconfig`.

---

## Architecture Concerns

### Thread Safety
The app uses a global `scan_thread` and `scan_stop_event` shared between Flask's request handler (main thread) and the scan worker. The check `if scan_thread and scan_thread.is_alive()` is not atomic — two rapid clicks could start two scans.

### Scalability
- `md5_file()` reads the entire file into memory in chunks. For very large files (100GB+), this is fine, but for millions of small files, the overhead of `os.walk()` + `Path.stat()` dominates.
- Consider using `os.scandir()` instead of `os.walk()` + `rglob` for better performance.

### Security
- No CSRF protection on POST endpoints (Flask's `SECRET_KEY` is set but not used for CSRF).
- No rate limiting on action endpoints.
- File paths are accepted verbatim from the client without sanitization.

---

## Positive Findings

| Finding | File | Notes |
|---------|------|-------|
| Event delegation in JS | `app.js` | Clean pattern for dynamically added elements |
| API abstraction layer | `app.js:29-64` | `apiRequest`, `apiGet`, `apiPost` with timeout |
| DOM helper object | `app.js:7-22` | Centralized DOM access with null safety |
| Error normalization | `app.js:24-27` | Consistent error handling |
| Config persistence | `app.py:85-93` | JSON-based config with defaults |
| Filter system | `app.py:34-73` | Clean category-based filtering |
| Theme consistency | `style.css` | Matches `tema_colores_estilos.md` |
| PowerShell dialog fallback | `app.py:503-537` | Robust cross-method fallback |

---

## Recommended Priority Order

1. **Fix CRIT-1** (I/O bomb) — one-line change, massive performance improvement
2. **Fix CRIT-3** (XSS) — security fix, use `textContent` instead of `innerHTML`
3. **Fix HIGH-1** (race condition) — add `threading.Lock()`
4. **Fix HIGH-2** (path validation) — security fix
5. **Fix CRIT-2 / MED-1** (remove dead code + missing dependency)
6. **Fix MED-3** (naming consistency) — refactor pass
7. **Add MED-7** (tests) — start with `detectar_categoria` and `archivo_pasa_filtro`
