import os
import hashlib
import json
import shutil
import threading
import ctypes
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

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

# Configuración por defecto
default_config = {
    'paths': [],
    'output_path': '',
    'review_path': ''
}

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default_config.copy()

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def save_progress(progress):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def load_progress():
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
        print(f"Error leyendo {filepath}: {e}")
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
    save_config(config)
    return jsonify(config)

@app.route('/api/progress', methods=['GET'])
def get_progress():
    return jsonify(load_progress())

@socketio.on('start_scan')
def handle_start_scan(data):
    global scan_thread, scan_stop_event
    
    if scan_thread and scan_thread.is_alive():
        emit('scan_error', {'message': 'Ya hay un escaneo en curso'})
        return
    
    paths = data.get('paths', [])
    if not paths or len(paths) < 2:
        emit('scan_error', {'message': 'Se necesitan al menos 2 rutas'})
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
    emit('scan_stopped', {})

def scan_worker(paths):
    """Worker que escanea archivos y encuentra duplicados."""
    try:
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
        
        total = len(all_files)
        save_progress({'status': 'scanning', 'current': 0, 'total': total, 'message': f'Escaneando {total} archivos...'})
        socketio.emit('scan_progress', {'current': 0, 'total': total, 'message': f'Escaneando {total} archivos...'})
        
        # Segundo: calcular hashes
        hashes = {}
        for i, filepath in enumerate(all_files):
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
                results.append({'file': filepath, 'success': True, 'message': f'Copiado a {dest}'})
            
            else:
                results.append({'file': filepath, 'success': False, 'message': 'Acción desconocida'})
        
        except Exception as e:
            results.append({'file': filepath, 'success': False, 'message': str(e)})
    
    return jsonify({'success': True, 'results': results})

@app.route('/api/browse_folder', methods=['POST'])
def browse_folder():
    """Abre el diálogo nativo de Windows para seleccionar carpetas locales o de red."""
    data = request.get_json() or {}
    title = data.get('title', 'Seleccionar carpeta')
    initial_dir = data.get('initial_dir', '')
    
    selected_path = None
    
    if WINFORMS_AVAILABLE:
        try:
            dialog = FolderBrowserDialog()
            dialog.Description = title
            dialog.ShowNewFolderButton = True
            
            if initial_dir and os.path.exists(initial_dir):
                dialog.SelectedPath = initial_dir
            
            result = dialog.ShowDialog()
            if result == DialogResult.OK:
                selected_path = dialog.SelectedPath
        except Exception as e:
            print(f"Error con WinForms dialog: {e}")
            selected_path = None
    
    # Fallback: usar SHBrowseForFolderW via ctypes
    if not selected_path and platform.system() == 'Windows':
        selected_path = _browse_folder_ctypes(title, initial_dir)
    
    if selected_path:
        return jsonify({'success': True, 'path': selected_path})
    else:
        return jsonify({'success': False, 'message': 'No se seleccionó ninguna carpeta'})


def _browse_folder_ctypes(title, initial_dir):
    """Fallback usando SHBrowseForFolderW via ctypes (soporta rutas de red)."""
    try:
        from ctypes import wintypes
        
        BIF_RETURNONLYFSDIRS = 0x00000001
        BIF_DONTGOBELOWDOMAIN = 0x00000002
        BIF_NEWDIALOGSTYLE = 0x00000040
        BIF_SHAREABLE = 0x00008000
        BIF_NONEWFOLDERBUTTON = 0x00000200
        BIF_BROWSEINCLUDEURLS = 0x00000080
        BIF_USENEWUI = BIF_NEWDIALOGSTYLE | BIF_SHAREABLE
        
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
        
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        
        # CoInitialize para COM
        ole32.CoInitialize(None)
        
        display_name = ctypes.create_unicode_buffer(260)
        
        bi = BROWSEINFO()
        bi.hwndOwner = 0
        bi.pidlRoot = None
        bi.pszDisplayName = ctypes.cast(display_name, wintypes.LPWSTR)
        bi.lpszTitle = title
        bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_USENEWUI
        bi.lpfn = None
        bi.lParam = 0
        bi.iImage = 0
        
        pidl = shell32.SHBrowseForFolderW(ctypes.byref(bi))
        
        if pidl:
            path_buffer = ctypes.create_unicode_buffer(260)
            # Pass the buffer directly - ctypes handles the conversion
            ret = shell32.SHGetPathFromIDListW(pidl, path_buffer)
            
            # Liberar PIDL
            ole32.CoTaskMemFree(pidl)
            
            result = path_buffer.value
            ole32.CoUninitialize()
            return result if result else None
        
        ole32.CoUninitialize()
        return None
        
    except Exception as e:
        print(f"Error con ctypes dialog: {e}")
        return None


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
