import html
import math
import os
import hashlib
import json
import shutil
import threading
import ctypes
import logging
import subprocess
import tempfile
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

# Windows COM imports for folder dialog
import platform
WINFORMS_AVAILABLE = False

# Try pythonnet (clr) first - best for network paths
try:
    import clr
    clr.AddReference('System.Windows.Forms')
    from System.Windows.Forms import FolderBrowserDialog, DialogResult
    WINFORMS_AVAILABLE = True
except ImportError:
    WINFORMS_AVAILABLE = False

app = Flask(__name__)
app.config['SECRET_KEY'] = 'desduplicador-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

DATA_DIR = Path(__file__).parent / 'data'
DATA_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / 'config.json'
PROGRESS_FILE = DATA_DIR / 'progress.json'

config_lock = threading.Lock()
logger = logging.getLogger('desduplicador')
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
CSIDL_DRIVES = 0x0011

# === CATEGORIAS DE ARCHIVO ===
EXTENSIONES = {
    'musica': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.opus', '.aiff'],
    'video': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'],
    'documentos': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md', '.rtf', '.odt', '.ods', '.odp', '.csv'],
    'ejecutables': ['.exe', '.msi', '.bat', '.cmd', '.ps1', '.sh', '.jar', '.app', '.dmg', '.deb', '.rpm'],
    'imagenes': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tiff', '.tif', '.raw', '.cr2', '.nef'],
    'comprimidos': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.iso'],
}

# Tamaño mínimo para videos (en bytes) - 1MB por defecto
TAMANO_MIN_VIDEO_DEFAULT = 1 * 1024 * 1024  # 1 MB


def format_size(bytes_val):
    """Formatea un tamaño en bytes a una cadena legible."""
    if bytes_val == 0:
        return '0 B'
    k = 1024
    sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    i = int(math.floor(math.log(bytes_val) / math.log(k)))
    i = min(i, len(sizes) - 1)
    val = bytes_val / (k ** i)
    s = f"{val:.2f}"
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return f"{s} {sizes[i]}"


def escape_html(text):
    """Escapa caracteres HTML especiales."""
    return html.escape(str(text))


def detectar_categoria(archivo_path):
    """Detecta la categoría de un archivo por su extensión."""
    ext = Path(archivo_path).suffix.lower()
    for categoria, extensiones in EXTENSIONES.items():
        if ext in extensiones:
            return categoria
    return 'otros'


def archivo_pasa_filtro(archivo_path, filtros_activos, tamano, tamano_min_video=None):
    """Verifica si un archivo pasa los filtros seleccionados."""
    if not filtros_activos:
        return True  # Sin filtros = todo pasa

    categoria = detectar_categoria(archivo_path)

    # Si la categoría no está en filtros activos, rechazar
    if categoria not in filtros_activos:
        return False

    # Filtro especial para videos por tamaño
    if categoria == 'video' and 'video' in filtros_activos:
        if tamano_min_video is None:
            tamano_min_video = TAMANO_MIN_VIDEO_DEFAULT
        if tamano < tamano_min_video:
            return False

    return True


# Configuración por defecto
default_config = {
    'paths': [],
    'output_path': '',
    'review_path': '',
    'filtros_activos': list(EXTENSIONES.keys()) + ['otros'],
    'tamano_min_video': TAMANO_MIN_VIDEO_DEFAULT
}

def load_config():
    with config_lock:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default_config.copy()

def save_config(config):
    with config_lock:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

def save_progress(progress):
    with config_lock:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

def load_progress():
    with config_lock:
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'status': 'idle', 'current': 0, 'total': 0, 'message': ''}

def md5_file(filepath, chunk_size=8192):
    """Calcula el hash MD5 de un archivo."""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Error leyendo {filepath}: {e}")
        return None

# Variable global para controlar el escaneo
scan_stop_event = threading.Event()
scan_thread = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(load_config())

@app.route('/api/config', methods=['POST'])
def update_config():
    config = load_config()
    data = request.get_json()
    if 'paths' in data:
        config['paths'] = data['paths']
    if 'output_path' in data:
        config['output_path'] = data['output_path']
    if 'review_path' in data:
        config['review_path'] = data['review_path']
    if 'filtros_activos' in data:
        config['filtros_activos'] = data['filtros_activos']
    if 'tamano_min_video' in data:
        config['tamano_min_video'] = data['tamano_min_video']
    save_config(config)
    return jsonify(config)

@app.route('/api/filters', methods=['GET'])
def get_filters():
    """Devuelve las categorias disponibles y los filtros activos."""
    config = load_config()
    return jsonify({
        'categorias': EXTENSIONES,
        'filtros_activos': config.get('filtros_activos', list(EXTENSIONES.keys()) + ['otros']),
        'tamano_min_video': config.get('tamano_min_video', TAMANO_MIN_VIDEO_DEFAULT)
    })

@app.route('/api/progress', methods=['GET'])
def get_progress():
    return jsonify(load_progress())

@socketio.on('start_scan')
def handle_start_scan(data):
    global scan_thread, scan_stop_event
    
    if scan_thread and scan_thread.is_alive():
        socketio.emit('scan_error', {'message': 'Ya hay un escaneo en curso'})
        return
    
    paths = data.get('paths', [])
    if not paths or len(paths) < 2:
        socketio.emit('scan_error', {'message': 'Se necesitan al menos 2 rutas'})
        return
    
    # Guardar rutas en config
    config = load_config()
    config['paths'] = paths
    save_config(config)
    
    scan_stop_event.clear()
    scan_thread = threading.Thread(target=scan_worker, args=(paths,))
    scan_thread.start()

@socketio.on('stop_scan')
def handle_stop_scan():
    scan_stop_event.set()
    socketio.emit('scan_stopped', {})

def scan_worker(paths):
    """Worker que escanea archivos y encuentra duplicados."""
    try:
        # Cargar configuracion de filtros
        config = load_config()
        filtros_activos = config.get('filtros_activos', list(EXTENSIONES.keys()) + ['otros'])
        
        # Primero: recopilar todos los archivos
        all_files = []
        for path in paths:
            p = Path(path)
            if not p.exists():
                socketio.emit('scan_error', {'message': f'La ruta no existe: {path}'})
                return
            if p.is_file():
                all_files.append(p)
            else:
                for root, _, files in os.walk(path):
                    if scan_stop_event.is_set():
                        socketio.emit('scan_stopped', {})
                        return
                    for filename in files:
                        all_files.append(Path(root) / filename)
        
        # Aplicar filtros por categoria
        save_progress({'status': 'scanning', 'current': 0, 'total': len(all_files), 'message': 'Filtrando archivos...'})
        socketio.emit('scan_progress', {'current': 0, 'total': len(all_files), 'message': 'Filtrando archivos...'})
        
        archivos_filtrados = []
        tamano_min_video = config.get('tamano_min_video', TAMANO_MIN_VIDEO_DEFAULT)
        for filepath in all_files:
            try:
                tamano = filepath.stat().st_size
                if archivo_pasa_filtro(str(filepath), filtros_activos, tamano, tamano_min_video):
                    archivos_filtrados.append(filepath)
            except Exception:
                pass  # Si no podemos leer el archivo, lo saltamos
        
        total = len(archivos_filtrados)
        filtrados_count = len(all_files) - total
        save_progress({'status': 'scanning', 'current': 0, 'total': total, 'message': f'Escaneando {total} archivos...'})
        socketio.emit('scan_progress', {'current': 0, 'total': total, 'message': f'Escaneando {total} archivos ({filtrados_count} filtrados)...'})
        
        # Segundo: calcular hashes
        hashes = {}
        for i, filepath in enumerate(archivos_filtrados):
            if scan_stop_event.is_set():
                save_progress({'status': 'idle', 'current': 0, 'total': 0, 'message': 'Escaneo cancelado'})
                socketio.emit('scan_stopped', {})
                return
            
            file_hash = md5_file(str(filepath))
            if file_hash:
                if file_hash not in hashes:
                    hashes[file_hash] = []
                hashes[file_hash].append({
                    'path': str(filepath),
                    'name': filepath.name,
                    'size': filepath.stat().st_size,
                    'modified': filepath.stat().st_mtime
                })
            
            if (i + 1) % 10 == 0 or i == total - 1:
                save_progress({'status': 'scanning', 'current': i + 1, 'total': total, 'message': f'Procesando {i+1}/{total}...'})
                socketio.emit('scan_progress', {'current': i + 1, 'total': total, 'message': f'Procesando {i+1}/{total}...'})
        
        # Tercero: filtrar solo duplicados
        duplicates = {h: files for h, files in hashes.items() if len(files) > 1}
        
        # Ordenar por nombre para mejor visualización
        result = []
        for h, files in duplicates.items():
            files_sorted = sorted(files, key=lambda x: x['path'])
            result.append({
                'hash': h,
                'files': files_sorted,
                'count': len(files_sorted),
                'size': files_sorted[0]['size']
            })
        
        result.sort(key=lambda x: x['count'], reverse=True)
        
        # Guardar resultado
        with open(DATA_DIR / 'last_scan.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        save_progress({'status': 'completed', 'current': total, 'total': total, 'message': f'Escaneo completado. {len(result)} grupos de duplicados encontrados.'})
        socketio.emit('scan_complete', {'duplicates': result, 'total_groups': len(result), 'total_files': sum(d['count'] for d in result)})
        
    except Exception as e:
        save_progress({'status': 'error', 'current': 0, 'total': 0, 'message': str(e)})
        socketio.emit('scan_error', {'message': str(e)})

@app.route('/api/last_scan', methods=['GET'])
def get_last_scan():
    scan_file = DATA_DIR / 'last_scan.json'
    if scan_file.exists():
        with open(scan_file, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route('/api/action', methods=['POST'])
def handle_action():
    data = request.get_json()
    action = data.get('action')
    files = data.get('files', [])
    keep = data.get('keep', '')
    output_path = data.get('output_path', '')
    review_path = data.get('review_path', '')
    
    if not files:
        return jsonify({'success': False, 'message': 'No hay archivos para procesar'})
    
    config = load_config()
    allowed_paths = [Path(p).resolve() for p in config.get('paths', [])]
    
    def _is_path_allowed(target_path):
        target = Path(target_path).resolve()
        for allowed in allowed_paths:
            try:
                target.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False
    
    for filepath in files:
        if not _is_path_allowed(filepath):
            return jsonify({'success': False, 'message': f'Ruta no permitida: {filepath}'})
    
    results = []
    
    for filepath in files:
        if filepath == keep:
            continue
        
        try:
            src = Path(filepath)
            if not src.exists():
                results.append({'file': filepath, 'success': False, 'message': 'No existe'})
                continue
            
            if action == 'delete':
                src.unlink()
                results.append({'file': filepath, 'success': True, 'message': 'Eliminado'})
            
            elif action == 'move_review':
                if not review_path:
                    results.append({'file': filepath, 'success': False, 'message': 'Ruta de revisión no configurada'})
                    continue
                dest_dir = Path(review_path)
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / src.name
                counter = 1
                while dest.exists():
                    stem = src.stem
                    suffix = src.suffix
                    dest = dest_dir / f"{stem}_{counter:03d}{suffix}"
                    counter += 1
                shutil.move(str(src), str(dest))
                results.append({'file': filepath, 'success': True, 'message': f'Movido a {dest}'})
            
            elif action == 'rename':
                parent = src.parent
                stem = src.stem
                suffix = src.suffix
                counter = 1
                new_name = f"{stem}_duplicado_{counter:03d}{suffix}"
                new_path = parent / new_name
                while new_path.exists():
                    counter += 1
                    new_name = f"{stem}_duplicado_{counter:03d}{suffix}"
                    new_path = parent / new_name
                src.rename(new_path)
                results.append({'file': filepath, 'success': True, 'message': f'Renombrado a {new_name}'})
            
            elif action == 'consolidate':
                if not output_path:
                    results.append({'file': filepath, 'success': False, 'message': 'Ruta de salida no configurada'})
                    continue
                dest_dir = Path(output_path)
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / src.name
                counter = 1
                while dest.exists():
                    stem = src.stem
                    suffix = src.suffix
                    dest = dest_dir / f"{stem}_{counter:03d}{suffix}"
                    counter += 1
                shutil.copy2(str(src), str(dest))
                if not dest.exists() or dest.stat().st_size != src.stat().st_size:
                    results.append({'file': filepath, 'success': False, 'message': 'Error de copia: tamaño no coincide'})
                    continue
                src.unlink()
                results.append({'file': filepath, 'success': True, 'message': f'Consolidado a {dest}'})
            
            else:
                results.append({'file': filepath, 'success': False, 'message': 'Acción desconocida'})
        
        except Exception as e:
            results.append({'file': filepath, 'success': False, 'message': str(e)})
    
    return jsonify({'success': True, 'results': results})

@app.route('/api/browse_folder', methods=['POST'])
def browse_folder():
    """Abre el dialogo nativo de Windows para seleccionar carpetas locales o de red."""
    data = request.get_json() or {}
    title = data.get('title', 'Seleccionar carpeta')
    initial_dir = data.get('initial_dir', '')
    
    selected_path = None
    
    # Metodo 1: PowerShell + Windows Forms (el mas completo, muestra todo)
    if platform.system() == 'Windows':
        selected_path = _browse_folder_powershell(title, initial_dir)
    
    # Metodo 2: WinForms directo (si pythonnet esta disponible)
    if not selected_path and WINFORMS_AVAILABLE:
        try:
            dialog = FolderBrowserDialog()
            dialog.Description = title
            dialog.ShowNewFolderButton = True
            dialog.RootFolder = CSIDL_DRIVES
            
            if initial_dir and os.path.exists(initial_dir):
                dialog.SelectedPath = initial_dir
            
            result = dialog.ShowDialog()
            if result == DialogResult.OK:
                selected_path = dialog.SelectedPath
        except Exception as e:
            logger.error(f"Error con WinForms dialog: {e}")
            selected_path = None
    
    # Metodo 3: SHBrowseForFolderW via ctypes
    if not selected_path and platform.system() == 'Windows':
        selected_path = _browse_folder_ctypes(title, initial_dir)
    
    if selected_path:
        return jsonify({'success': True, 'path': selected_path})
    else:
        return jsonify({'success': False, 'message': 'No se selecciono ninguna carpeta'})


def _browse_folder_ctypes(title, initial_dir):
    """Abre el dialogo nativo de Windows usando SHBrowseForFolderW.
    Muestra unidades locales, mapeadas y de red."""
    try:
        from ctypes import wintypes
        
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        
        # CoInitialize para COM
        ole32.CoInitialize(None)
        
        BIF_RETURNONLYFSDIRS = 0x00000001
        BIF_NEWDIALOGSTYLE = 0x00000040
        BIF_SHAREABLE = 0x00008000
        BIF_NONEWFOLDERBUTTON = 0x00000200
        
        class BROWSEINFO(ctypes.Structure):
            _fields_ = [
                ("hwndOwner", wintypes.HWND),
                ("pidlRoot", wintypes.LPCVOID),
                ("pszDisplayName", wintypes.LPWSTR),
                ("lpszTitle", wintypes.LPCWSTR),
                ("ulFlags", wintypes.UINT),
                ("lpfn", wintypes.LPCVOID),
                ("lParam", wintypes.LPARAM),
                ("iImage", wintypes.INT),
            ]
        
        # Obtener PIDL de "Este equipo" para mostrar TODAS las unidades
        pidl_root = ctypes.c_void_p()
        shell32.SHGetSpecialFolderLocation(0, CSIDL_DRIVES, ctypes.byref(pidl_root))
        
        display_name = ctypes.create_unicode_buffer(260)
        
        bi = BROWSEINFO()
        bi.hwndOwner = 0
        bi.pidlRoot = pidl_root
        bi.pszDisplayName = ctypes.cast(display_name, wintypes.LPWSTR)
        bi.lpszTitle = title
        bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE | BIF_SHAREABLE
        bi.lpfn = None
        bi.lParam = 0
        bi.iImage = 0
        
        pidl_selected = shell32.SHBrowseForFolderW(ctypes.byref(bi))
        
        # Liberar PIDL root
        if pidl_root:
            ole32.CoTaskMemFree(pidl_root)
        
        if pidl_selected:
            path_buffer = ctypes.create_unicode_buffer(260)
            shell32.SHGetPathFromIDListW(pidl_selected, path_buffer)
            result = path_buffer.value
            ole32.CoTaskMemFree(pidl_selected)
            ole32.CoUninitialize()
            return result if result else None
        
        ole32.CoUninitialize()
        return None
        
    except Exception as e:
        logger.error(f"Error con dialogo nativo: {e}")
        return None


def _browse_folder_powershell(title, initial_dir):
    """Ultimo recurso: usar Windows Forms via powershell para un dialogo completo."""
    
    ps_script = '''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "''' + title.replace('"', '""') + '''"
$dialog.ShowNewFolderButton = $true
$dialog.RootFolder = [System.Environment+SpecialFolder]::MyComputer
''' + (f'$dialog.SelectedPath = "{initial_dir}"\n' if initial_dir else '') + '''
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.SelectedPath
}
'''
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as f:
            f.write(ps_script)
            ps_file = f.name
        
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps_file],
            capture_output=True, text=True, timeout=120
        )
        
        os.unlink(ps_file)
        
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except Exception as e:
        logger.error(f"Error con PowerShell dialog: {e}")
        return None


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
