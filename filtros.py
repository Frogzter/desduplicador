
import os
import hashlib
import json
import shutil
import time
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, redirect, flash, jsonify
import webbrowser

app = Flask(__name__)
app.secret_key = 'nas-backup-comparator-2026'

# CONFIGURACION POR DEFECTO
RUTAS_RESPALDO = [
    r"\\10.1.10.10\backup\respaldos_antiguos",
    r"D:\Respaldos_Viejos",
    r"E:\Backups_2025",
]

CARPETA_DESTINO_DEFAULT = r"D:\Respaldos_Consolidados"

ESTADO_ARCHIVO = "estado_comparador.json"
PROGRESO_ARCHIVO = "progreso_scan.json"


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
TAMANO_MIN_VIDEO = 1 * 1024 * 1024  # 1 MB

def detectar_categoria(archivo_path):
    """Detecta la categoría de un archivo por su extensión."""
    ext = Path(archivo_path).suffix.lower()
    for categoria, extensiones in EXTENSIONES.items():
        if ext in extensiones:
            return categoria
    return 'otros'

def archivo_pasa_filtro(archivo_path, filtros_activos, tamano):
    """Verifica si un archivo pasa los filtros seleccionados."""
    if not filtros_activos:
        return True  # Sin filtros = todo pasa

    categoria = detectar_categoria(archivo_path)

    # Si la categoría no está en filtros activos, rechazar
    if categoria not in filtros_activos:
        return False

    # Filtro especial para videos por tamaño
    if categoria == 'video' and 'video' in filtros_activos:
        if tamano < TAMANO_MIN_VIDEO:
            return False

    return True

# Variables globales para el escaneo en segundo plano
scan_thread = None
scan_cancelado = False

# Cola para rutas seleccionadas desde el dialogo (acumulador temporal)
rutas_seleccionadas_dialogo = []

# ==================== FUNCIONES CORE ====================

def calcular_hash(archivo, tamano_bloque=65536):
    hasher = hashlib.md5()
    try:
        with open(archivo, 'rb') as f:
            for bloque in iter(lambda: f.read(tamano_bloque), b''):
                hasher.update(bloque)
        return hasher.hexdigest()
    except Exception as e:
        return f"ERROR:{str(e)}"

def guardar_progreso(data):
    with open(PROGRESO_ARCHIVO, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def cargar_progreso():
    if os.path.exists(PROGRESO_ARCHIVO):
        with open(PROGRESO_ARCHIVO, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'estado': 'idle', 'mensaje': '', 'progreso': 0, 'total': 0, 'actual': 0, 'ruta_actual': ''}

def escanear_carpeta_con_progreso(ruta, progreso_global, filtros_activos=None):
    archivos_por_hash = {}
    ruta_base = Path(ruta)

    if not ruta_base.exists():
        return {}

    archivos_lista = [a for a in ruta_base.rglob('*') if a.is_file()]

    # Aplicar filtros si están configurados
    if filtros_activos:
        archivos_lista = [
            a for a in archivos_lista 
            if archivo_pasa_filtro(str(a), filtros_activos, a.stat().st_size)
        ]

    for archivo in archivos_lista:
        if scan_cancelado:
            break
        try:
            file_hash = calcular_hash(archivo)
            if file_hash not in archivos_por_hash:
                archivos_por_hash[file_hash] = []
            archivos_por_hash[file_hash].append({
                'ruta': str(archivo),
                'tamano': archivo.stat().st_size,
                'modificado': datetime.fromtimestamp(archivo.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                'carpeta': ruta
            })

            progreso_global['actual'] += 1
            pct = int((progreso_global['actual'] / progreso_global['total']) * 100) if progreso_global['total'] > 0 else 0
            guardar_progreso({
                'estado': 'escaneando',
                'mensaje': f"Escaneando: {ruta}",
                'progreso': pct,
                'total': progreso_global['total'],
                'actual': progreso_global['actual'],
                'ruta_actual': str(archivo)
            })
        except Exception as e:
            print(f"Error leyendo {archivo}: {e}")

    return archivos_por_hash

def encontrar_duplicados_con_progreso(rutas, filtros_activos=None):
    global scan_cancelado
    scan_cancelado = False

    guardar_progreso({
        'estado': 'contando',
        'mensaje': 'Contando archivos...',
        'progreso': 0,
        'total': 0,
        'actual': 0,
        'ruta_actual': ''
    })

    total_archivos = 0
    for ruta in rutas:
        if scan_cancelado:
            return {}
        ruta_base = Path(ruta)
        if ruta_base.exists():
            total_archivos += len([a for a in ruta_base.rglob('*') if a.is_file()])

    progreso_global = {'total': total_archivos, 'actual': 0}
    todos_los_hashes = {}

    for ruta in rutas:
        if scan_cancelado:
            return {}
        resultado = escanear_carpeta_con_progreso(ruta, progreso_global, filtros_activos)
        for h, archivos in resultado.items():
            if h not in todos_los_hashes:
                todos_los_hashes[h] = []
            todos_los_hashes[h].extend(archivos)

    if scan_cancelado:
        return {}

    guardar_progreso({
        'estado': 'procesando',
        'mensaje': 'Procesando resultados...',
        'progreso': 95,
        'total': total_archivos,
        'actual': progreso_global['actual'],
        'ruta_actual': ''
    })

    duplicados = {h: archivos for h, archivos in todos_los_hashes.items() if len(archivos) > 1}

    guardar_progreso({
        'estado': 'completado',
        'mensaje': f'Escaneo completo. {len(duplicados)} grupos de duplicados.',
        'progreso': 100,
        'total': total_archivos,
        'actual': progreso_global['actual'],
        'ruta_actual': ''
    })

    return duplicados

def cargar_estado():
    if os.path.exists(ESTADO_ARCHIVO):
        with open(ESTADO_ARCHIVO, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'acciones': {},
        'duplicados': {},
        'rutas': RUTAS_RESPALDO,
        'carpeta_destino': CARPETA_DESTINO_DEFAULT,
        'modo_consolidar': False,
        'filtros_activos': list(EXTENSIONES.keys()) + ['otros'],  # Todo activo por defecto
        'tamano_min_video': TAMANO_MIN_VIDEO
    }

def guardar_estado(estado):
    with open(ESTADO_ARCHIVO, 'w', encoding='utf-8') as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)

# ==================== INTERFAZ WEB ====================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Comparador de Respaldos NAS</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #1e1e1e; color: #d4d4d4; }
        h1 { color: #569cd6; }
        h2 { color: #ce9178; font-size: 18px; margin-top: 25px; }
        .grupo { background: #252526; border: 1px solid #3e3e42; margin: 15px 0; padding: 15px; border-radius: 6px; }
        .grupo-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .hash { font-family: monospace; color: #ce9178; font-size: 12px; }
        .archivo { display: flex; justify-content: space-between; align-items: center; padding: 8px; margin: 4px 0; background: #2d2d30; border-radius: 4px; }
        .archivo-info { flex: 1; }
        .ruta { color: #9cdcfe; font-size: 13px; }
        .meta { color: #808080; font-size: 11px; }
        .acciones { display: flex; gap: 8px; margin-left: 15px; }
        button { padding: 6px 14px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; }
        .btn-mantener { background: #4ec9b0; color: #000; }
        .btn-eliminar { background: #f48771; color: #000; }
        .btn-mover { background: #dcdcaa; color: #000; }
        .btn-escanear { background: #569cd6; color: #fff; padding: 12px 24px; font-size: 14px; }
        .estado { padding: 4px 8px; border-radius: 3px; font-size: 11px; font-weight: bold; }
        .estado-mantener { background: #4ec9b0; color: #000; }
        .estado-eliminar { background: #f48771; color: #000; }
        .estado-mover { background: #dcdcaa; color: #000; }
        .estado-consolidar { background: #569cd6; color: #fff; }
        .stats { display: flex; gap: 20px; margin: 15px 0; flex-wrap: wrap; }
        .stat-box { background: #252526; padding: 15px; border-radius: 6px; min-width: 150px; flex: 1; }
        .stat-num { font-size: 24px; font-weight: bold; color: #569cd6; }
        .stat-label { font-size: 12px; color: #808080; }
        .flash { background: #4ec9b0; color: #000; padding: 10px; border-radius: 4px; margin: 10px 0; }
        .flash-error { background: #f48771; color: #000; padding: 10px; border-radius: 4px; margin: 10px 0; }
        .config { background: #252526; padding: 15px; border-radius: 6px; margin-bottom: 20px; }
        input[type="text"] { width: 100%; padding: 8px; background: #3c3c3c; border: 1px solid #3e3e42; color: #d4d4d4; border-radius: 4px; margin: 5px 0; }
        .ejecutar { background: #c586c0; color: #fff; padding: 15px 30px; font-size: 16px; margin-top: 20px; }
        .warning { background: #f48771; color: #000; padding: 10px; border-radius: 4px; margin: 10px 0; }
        .info-box { background: #252526; padding: 15px; border-radius: 6px; margin: 15px 0; border-left: 4px solid #569cd6; }

        /* === EDITOR DE RUTAS === */
        .rutas-editor { margin-top: 10px; }
        .ruta-item {
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 6px 0;
            padding: 8px;
            background: #2d2d30;
            border-radius: 4px;
            border: 1px solid #3e3e42;
        }
        .ruta-item input { flex: 1; margin: 0; }
        .ruta-num { color: #569cd6; font-weight: bold; min-width: 24px; text-align: center; }
        .btn-icon {
            background: #3c3c3c; color: #d4d4d4; border: 1px solid #3e3e42;
            padding: 6px 10px; font-size: 14px; min-width: 32px;
        }
        .btn-icon:hover { background: #4e4e4e; }
        .btn-add { background: #4ec9b0; color: #000; padding: 8px 16px; font-size: 13px; margin-top: 8px; }
        .btn-browse { background: #dcdcaa; color: #000; padding: 8px 16px; font-size: 13px; margin-top: 8px; margin-left: 8px; }
        .btn-guardar { background: #569cd6; color: #fff; padding: 12px 24px; font-size: 14px; margin-top: 12px; }
        .btn-cancelar { background: #f48771; color: #000; padding: 12px 24px; font-size: 14px; margin-top: 12px; margin-left: 8px; }
        .ruta-vacia { color: #808080; font-style: italic; padding: 10px; text-align: center; }
        input[type="file"] { display: none; }

        /* === BARRA DE PROGRESO === */
        .progreso-container {
            display: none;
            background: #252526;
            border: 1px solid #3e3e42;
            border-radius: 6px;
            padding: 15px;
            margin: 15px 0;
        }
        .progreso-container.activo { display: block; }
        .progreso-info {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 13px;
        }
        .progreso-mensaje { color: #d4d4d4; }
        .progreso-pct { color: #569cd6; font-weight: bold; }
        .progreso-barra-bg {
            background: #3c3c3c;
            border-radius: 4px;
            height: 24px;
            overflow: hidden;
        }
        .progreso-barra-fill {
            background: linear-gradient(90deg, #569cd6, #4ec9b0);
            height: 100%;
            width: 0%;
            border-radius: 4px;
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 8px;
            font-size: 11px;
            color: #000;
            font-weight: bold;
        }
        .progreso-ruta {
            margin-top: 8px;
            font-size: 11px;
            color: #808080;
            font-family: monospace;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* === CONFIGURACION DESTINO === */
        .destino-config {
            background: #2d2d30;
            border: 1px solid #3e3e42;
            border-radius: 6px;
            padding: 15px;
            margin-top: 15px;
        }
        .destino-config h4 {
            color: #ce9178;
            margin-top: 0;
            margin-bottom: 10px;
        }
        .modo-toggle {
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 10px 0;
            padding: 10px;
            background: #252526;
            border-radius: 4px;
            cursor: pointer;
        }
        .modo-toggle input[type="checkbox"] {
            width: 18px;
            height: 18px;
            cursor: pointer;
        }
        .modo-toggle label {
            cursor: pointer;
            font-size: 13px;
        }
        .modo-activo {
            border: 1px solid #4ec9b0;
        }
        .modo-descripcion {
            font-size: 11px;
            color: #808080;
            margin-left: 28px;
        }

        /* === FILTROS DE CATEGORIA === */
        .filtros-section {
            background: #2d2d30;
            border: 1px solid #3e3e42;
            border-radius: 6px;
            padding: 15px;
            margin-top: 15px;
        }
        .filtros-section h4 {
            color: #ce9178;
            margin-top: 0;
            margin-bottom: 12px;
            font-size: 14px;
        }
        .filtros-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
        }
        .filtro-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: #252526;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.2s;
            border: 1px solid transparent;
        }
        .filtro-item:hover {
            background: #3c3c3c;
        }
        .filtro-item.activo {
            border-color: #4ec9b0;
            background: #252526;
        }
        .filtro-item input[type="checkbox"] {
            width: 16px;
            height: 16px;
            cursor: pointer;
            accent-color: #4ec9b0;
        }
        .filtro-item label {
            cursor: pointer;
            font-size: 13px;
            flex: 1;
        }
        .filtro-count {
            font-size: 11px;
            color: #808080;
            font-family: monospace;
        }
        .tamano-video-config {
            margin-top: 12px;
            padding: 10px;
            background: #252526;
            border-radius: 4px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .tamano-video-config label {
            font-size: 12px;
            color: #d4d4d4;
        }
        .tamano-video-config input {
            width: 80px;
            padding: 6px;
            background: #3c3c3c;
            border: 1px solid #3e3e42;
            color: #d4d4d4;
            border-radius: 4px;
            text-align: center;
        }
        .tamano-video-config span {
            font-size: 12px;
            color: #808080;
        }

    </style>
</head>
<body>
    <h1>[BUSCAR] Comparador de Respaldos NAS</h1>

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="flash{{ '-error' if category == 'error' else '' }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    <!-- Barra de progreso -->
    <div class="progreso-container" id="progreso-box">
        <div class="progreso-info">
            <span class="progreso-mensaje" id="progreso-mensaje">Iniciando...</span>
            <span class="progreso-pct" id="progreso-pct">0%</span>
        </div>
        <div class="progreso-barra-bg">
            <div class="progreso-barra-fill" id="progreso-fill">0%</div>
        </div>
        <div class="progreso-ruta" id="progreso-ruta"></div>
    </div>

    <!-- CONFIGURACION -->
    <div class="config">
        <h3>[CARPETA] Rutas de Respaldo (Fuentes)</h3>
        <form action="/configurar" method="post" id="form-rutas" onsubmit="return iniciarEscaneo(event)">
            <div class="rutas-editor" id="rutas-editor">
                {% if rutas %}
                    {% for r in rutas %}
                    <div class="ruta-item">
                        <span class="ruta-num">{{ loop.index }}</span>
                        <input type="text" name="ruta_{{ loop.index0 }}" value="{{ r }}" placeholder="C:\\Respaldos  o  \\\\NAS\\backup...">
                        <button type="button" class="btn-icon btn-up" onclick="moverRuta(this, -1)" title="Subir">^</button>
                        <button type="button" class="btn-icon btn-down" onclick="moverRuta(this, 1)" title="Bajar">v</button>
                        <button type="button" class="btn-icon btn-del" onclick="eliminarRuta(this)" title="Eliminar">x</button>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="ruta-vacia" id="sin-rutas">No hay rutas configuradas. Agrega una para comenzar.</div>
                {% endif %}
            </div>
            <button type="button" class="btn-add" onclick="agregarRuta()">+ Agregar ruta</button>
            <button type="button" class="btn-browse" onclick="abrirDialogoCarpeta()">[ABRIR] Buscar carpetas...</button>

            <!-- CONFIGURACION DE DESTINO -->
            <div class="destino-config">
                <h4>[DESTINO] Carpeta de Consolidacion</h4>
                <p style="font-size:12px; color:#808080; margin-top:0;">
                    Aqui se moveran los archivos marcados como "Consolidar". Se mantendra la estructura de carpetas relativa.
                </p>
                <input type="text" name="carpeta_destino" value="{{ carpeta_destino }}" placeholder="D:\\Respaldos_Consolidados">

                <div class="modo-toggle {{ 'modo-activo' if modo_consolidar else '' }}" id="modo-toggle-div" onclick="toggleModo()">
                    <input type="checkbox" name="modo_consolidar" id="modo_consolidar" value="1" {{ 'checked' if modo_consolidar else '' }} onclick="event.stopPropagation();">
                    <div>
                        <label for="modo_consolidar"><strong>Modo Consolidacion</strong></label>
                        <div class="modo-descripcion">
                            ON: "Mover" copia archivos a la carpeta destino y luego elimina los originales.<br>
                            OFF: "Mover" solo crea una subcarpeta "_revisar" en la ubicacion original.
                        </div>
                    </div>
                </div>
            </div>

            <!-- FILTROS DE CATEGORIA -->
            <div class="filtros-section">
                <h4>[FILTROS] Tipos de archivo a escanear</h4>
                <div class="filtros-grid" id="filtros-grid">
                    {% for categoria, exts in extensiones.items() %}
                    <div class="filtro-item {{ 'activo' if categoria in filtros_activos else '' }}" onclick="toggleFiltro(this)">
                        <input type="checkbox" name="filtros[]" value="{{ categoria }}" 
                               {{ 'checked' if categoria in filtros_activos else '' }} 
                               onclick="event.stopPropagation();">
                        <label>{{ categoria|capitalize }}</label>
                        <span class="filtro-count">{{ exts|length }} ext</span>
                    </div>
                    {% endfor %}
                    <div class="filtro-item {{ 'activo' if 'otros' in filtros_activos else '' }}" onclick="toggleFiltro(this)">
                        <input type="checkbox" name="filtros[]" value="otros" 
                               {{ 'checked' if 'otros' in filtros_activos else '' }} 
                               onclick="event.stopPropagation();">
                        <label>Otros</label>
                        <span class="filtro-count">resto</span>
                    </div>
                </div>
                <div class="tamano-video-config">
                    <label>Video mínimo:</label>
                    <input type="number" name="tamano_min_video" value="{{ tamano_min_video // (1024*1024) }}" min="0" step="1">
                    <span>MB (videos más pequeños se ignoran)</span>
                </div>
                <p style="font-size:11px; color:#808080; margin:8px 0 0 0;">
                    💡 Desactiva categorías que no quieras escanear. Los filtros se guardan entre sesiones.
                </p>
            </div>


            <br>
            <button type="submit" class="btn-guardar" id="btn-guardar">[GUARDAR] Guardar y Escanear</button>
            <button type="button" class="btn-cancelar" id="btn-cancelar" onclick="cancelarEscaneo()" style="display:none;">[X] Cancelar</button>
        </form>
    </div>

    {% if stats %}
    <div class="stats">
        <div class="stat-box">
            <div class="stat-num">{{ stats.total_grupos }}</div>
            <div class="stat-label">Grupos de duplicados</div>
        </div>
        <div class="stat-box">
            <div class="stat-num">{{ stats.total_archivos }}</div>
            <div class="stat-label">Archivos duplicados</div>
        </div>
        <div class="stat-box">
            <div class="stat-num">{{ stats.espacio_dup }}</div>
            <div class="stat-label">Espacio duplicado</div>
        </div>
        <div class="stat-box">
            <div class="stat-num">{{ stats.por_decidir }}</div>
            <div class="stat-label">Pendientes de decidir</div>
        </div>
    </div>
    {% endif %}

    {% if duplicados %}
    <h2>Duplicados Encontrados</h2>
    <div class="info-box">
        <strong>Acciones disponibles:</strong><br>
        [OK] <strong>Mantener</strong> - Conserva este archivo en su ubicacion original.<br>
        [X] <strong>Eliminar</strong> - Borra permanentemente este archivo.<br>
        {% if modo_consolidar %}
        [CONSOLIDAR] <strong>Consolidar</strong> - Copia a "{{ carpeta_destino }}" y elimina el original.
        {% else %}
        [MOVER] <strong>Mover</strong> - Mueve a una subcarpeta "_revisar" local.
        {% endif %}
    </div>

    <form action="/ejecutar" method="post" onsubmit="return confirm('Estas SEGURO de ejecutar las acciones marcadas? No se puede deshacer!');">
        <button type="submit" class="ejecutar">[EJECUTAR] EJECUTAR ACCIONES MARCADAS</button>

        {% for hash, archivos in duplicados.items() %}
        <div class="grupo">
            <div class="grupo-header">
                <span class="hash">Hash: {{ hash[:16] }}... ({{ archivos[0].tamano|filesizeformat }} cada uno)</span>
                <span>{{ archivos|length }} copias</span>
            </div>

            {% for archivo in archivos %}
            <div class="archivo">
                <div class="archivo-info">
                    <div class="ruta">{{ archivo.ruta }}</div>
                    <div class="meta">Modificado: {{ archivo.modificado }} | Carpeta: {{ archivo.carpeta }}</div>
                </div>
                <div class="acciones">
                    {% set key = hash + '|' + archivo.ruta %}
                    {% set accion = estado.get(key, '') %}

                    {% if accion == 'mantener' %}
                        <span class="estado estado-mantener">[OK] MANTENER</span>
                    {% elif accion == 'eliminar' %}
                        <span class="estado estado-eliminar">[X] ELIMINAR</span>
                    {% elif accion == 'mover' %}
                        {% if modo_consolidar %}
                            <span class="estado estado-consolidar">[CONSOLIDAR] CONSOLIDAR</span>
                        {% else %}
                            <span class="estado estado-mover">[MOVER] MOVER</span>
                        {% endif %}
                    {% else %}
                        <button type="button" class="btn-mantener" onclick="window.location.href='/accion?hash={{ hash }}&ruta={{ archivo.ruta|urlencode }}&tipo=mantener'">[OK] Mantener</button>
                        <button type="button" class="btn-eliminar" onclick="window.location.href='/accion?hash={{ hash }}&ruta={{ archivo.ruta|urlencode }}&tipo=eliminar'">[X] Eliminar</button>
                        {% if modo_consolidar %}
                        <button type="button" class="btn-escanear" onclick="window.location.href='/accion?hash={{ hash }}&ruta={{ archivo.ruta|urlencode }}&tipo=mover'">[CONSOLIDAR] Consolidar</button>
                        {% else %}
                        <button type="button" class="btn-mover" onclick="window.location.href='/accion?hash={{ hash }}&ruta={{ archivo.ruta|urlencode }}&tipo=mover'">[MOVER] Mover</button>
                        {% endif %}
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endfor %}

        <button type="submit" class="ejecutar">[EJECUTAR] EJECUTAR ACCIONES MARCADAS</button>
    </form>
    {% else %}
        {% if rutas %}
        <p>No se encontraron duplicados o aun no se ha escaneado. Presiona "Guardar y Escanear".</p>
        {% endif %}
    {% endif %}

    <div style="margin-top: 30px; padding: 15px; background: #252526; border-radius: 6px;">
        <h3>[INFO] Flujo de trabajo recomendado:</h3>
        <ol>
            <li><strong>Configura la Carpeta de Consolidacion</strong> - Ej: D:\\Respaldos_Consolidados</li>
            <li><strong>Activa "Modo Consolidacion"</strong> - Los archivos marcados como "Consolidar" iran alli</li>
            <li><strong>Agrega las rutas de origen</strong> - Tus carpetas de respaldo actuales</li>
            <li><strong>Escanear</strong> - Encuentra duplicados entre todas las fuentes</li>
            <li><strong>Para cada grupo:</strong> "Mantener" la mejor copia, "Consolidar" las que quieras mover al destino, "Eliminar" el resto</li>
            <li><strong>Ejecutar</strong> - Todo lo consolidado se copia al destino, los originales se eliminan</li>
            <li><strong>Resultado:</strong> Tus carpetas originales se vacian, todo queda en la carpeta destino depurada</li>
        </ol>
        <p style="color: #f48771; font-weight: bold;">ADVERTENCIA: Las eliminaciones son permanentes. En modo consolidacion, los archivos se COPIAN primero al destino y luego se eliminan los originales.</p>
    </div>

    <script>
        let pollInterval = null;

        function toggleModo() {
            const cb = document.getElementById('modo_consolidar');
            const div = document.getElementById('modo-toggle-div');
            cb.checked = !cb.checked;
            div.classList.toggle('modo-activo', cb.checked);
        }

        
        function toggleFiltro(item) {
            const cb = item.querySelector('input[type="checkbox"]');
            cb.checked = !cb.checked;
            item.classList.toggle('activo', cb.checked);
        }

function iniciarEscaneo(e) {
            e.preventDefault();
            const form = document.getElementById('form-rutas');
            const btnGuardar = document.getElementById('btn-guardar');
            const btnCancelar = document.getElementById('btn-cancelar');
            const progresoBox = document.getElementById('progreso-box');

            const formData = new FormData(form);
            fetch('/configurar', { method: 'POST', body: formData });

            btnGuardar.disabled = true;
            btnGuardar.textContent = 'Escaneando...';
            btnCancelar.style.display = 'inline-block';
            progresoBox.classList.add('activo');

            pollInterval = setInterval(actualizarProgreso, 500);
            return false;
        }

        function actualizarProgreso() {
            fetch('/progreso')
                .then(r => r.json())
                .then(data => {
                    const fill = document.getElementById('progreso-fill');
                    const pct = document.getElementById('progreso-pct');
                    const mensaje = document.getElementById('progreso-mensaje');
                    const ruta = document.getElementById('progreso-ruta');
                    const btnGuardar = document.getElementById('btn-guardar');
                    const btnCancelar = document.getElementById('btn-cancelar');

                    fill.style.width = data.progreso + '%';
                    fill.textContent = data.progreso + '%';
                    pct.textContent = data.progreso + '%';
                    mensaje.textContent = data.mensaje;
                    ruta.textContent = data.ruta_actual ? 'Archivo: ' + data.ruta_actual : '';

                    if (data.estado === 'completado' || data.estado === 'idle') {
                        clearInterval(pollInterval);
                        btnGuardar.disabled = false;
                        btnGuardar.textContent = '[GUARDAR] Guardar y Escanear';
                        btnCancelar.style.display = 'none';
                        if (data.estado === 'completado') {
                            setTimeout(() => location.reload(), 1000);
                        }
                    }
                });
        }

        function cancelarEscaneo() {
            fetch('/cancelar', { method: 'POST' });
            clearInterval(pollInterval);
            document.getElementById('btn-guardar').disabled = false;
            document.getElementById('btn-guardar').textContent = '[GUARDAR] Guardar y Escanear';
            document.getElementById('btn-cancelar').style.display = 'none';
            document.getElementById('progreso-box').classList.remove('activo');
        }

        function actualizarNumeros() {
            const items = document.querySelectorAll('.ruta-item');
            items.forEach((item, i) => {
                item.querySelector('.ruta-num').textContent = i + 1;
                item.querySelector('input').name = 'ruta_' + i;
            });
        }

        function moverRuta(btn, dir) {
            const item = btn.closest('.ruta-item');
            const editor = document.getElementById('rutas-editor');
            const items = [...editor.querySelectorAll('.ruta-item')];
            const idx = items.indexOf(item);
            const newIdx = idx + dir;
            if (newIdx < 0 || newIdx >= items.length) return;
            editor.insertBefore(dir > 0 ? items[newIdx] : item, dir > 0 ? item.nextSibling : items[newIdx]);
            actualizarNumeros();
        }

        function eliminarRuta(btn) {
            const item = btn.closest('.ruta-item');
            item.remove();
            actualizarNumeros();
            const editor = document.getElementById('rutas-editor');
            if (editor.querySelectorAll('.ruta-item').length === 0) {
                editor.innerHTML = '<div class="ruta-vacia" id="sin-rutas">No hay rutas configuradas. Agrega una para comenzar.</div>';
            }
        }

        function agregarRuta() {
            const editor = document.getElementById('rutas-editor');
            const sinRutas = document.getElementById('sin-rutas');
            if (sinRutas) sinRutas.remove();

            const div = document.createElement('div');
            div.className = 'ruta-item';
            const num = editor.querySelectorAll('.ruta-item').length + 1;
            div.innerHTML = `
                <span class="ruta-num">${num}</span>
                <input type="text" name="ruta_${num-1}" value="" placeholder="C:\\\\Respaldos  o  \\\\\\\\NAS\\\\backup...">
                <button type="button" class="btn-icon btn-up" onclick="moverRuta(this, -1)" title="Subir">^</button>
                <button type="button" class="btn-icon btn-down" onclick="moverRuta(this, 1)" title="Bajar">v</button>
                <button type="button" class="btn-icon btn-del" onclick="eliminarRuta(this)" title="Eliminar">x</button>
            `;
            editor.appendChild(div);
            div.querySelector('input').focus();
        }

        let dialogoAbierto = false;

        function abrirDialogoCarpeta() {
            if (dialogoAbierto) return;
            dialogoAbierto = true;

            fetch('/dialogo_carpeta')
                .then(r => r.json())
                .then(data => {
                    dialogoAbierto = false;
                    if (data.rutas && data.rutas.length > 0) {
                        const editor = document.getElementById('rutas-editor');
                        const sinRutas = document.getElementById('sin-rutas');
                        if (sinRutas) sinRutas.remove();

                        const existentes = [...editor.querySelectorAll('.ruta-item input')].map(inp => inp.value);

                        data.rutas.forEach(ruta => {
                            if (existentes.includes(ruta)) return;

                            const div = document.createElement('div');
                            div.className = 'ruta-item';
                            const num = editor.querySelectorAll('.ruta-item').length + 1;
                            div.innerHTML = `
                                <span class="ruta-num">${num}</span>
                                <input type="text" name="ruta_${num-1}" value="${ruta}" placeholder="C:\\\\Respaldos  o  \\\\\\\\NAS\\\\backup...">
                                <button type="button" class="btn-icon btn-up" onclick="moverRuta(this, -1)" title="Subir">^</button>
                                <button type="button" class="btn-icon btn-down" onclick="moverRuta(this, 1)" title="Bajar">v</button>
                                <button type="button" class="btn-icon btn-del" onclick="eliminarRuta(this)" title="Eliminar">x</button>
                            `;
                            editor.appendChild(div);
                        });

                        actualizarNumeros();

                        // Preguntar si quiere agregar mas
                        if (data.rutas.length === 1) {
                            setTimeout(() => {
                                if (confirm('Ruta agregada: ' + data.rutas[0] + '\\n\\nQuieres agregar otra carpeta?')) {
                                    abrirDialogoCarpeta();
                                }
                            }, 100);
                        }
                    }
                })
                .catch(err => {
                    dialogoAbierto = false;
                    console.error('Error abriendo dialogo:', err);
                    alert('No se pudo abrir el dialogo de carpeta. Escribe la ruta manualmente.');
                });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    estado = cargar_estado()
    rutas = estado.get('rutas', RUTAS_RESPALDO)
    duplicados = estado.get('duplicados', {})
    carpeta_destino = estado.get('carpeta_destino', CARPETA_DESTINO_DEFAULT)
    modo_consolidar = estado.get('modo_consolidar', False)

    stats = None
    if duplicados:
        total_archivos = sum(len(v) for v in duplicados.values())
        espacio_total = sum(
            sum(a.get('tamano', 0) for a in archivos) - archivos[0].get('tamano', 0)
            for archivos in duplicados.values()
        )

        por_decidir = 0
        for h, archivos in duplicados.items():
            for a in archivos:
                key = f"{h}|{a['ruta']}"
                if key not in estado.get('acciones', {}):
                    por_decidir += 1

        stats = {
            'total_grupos': len(duplicados),
            'total_archivos': total_archivos,
            'espacio_dup': f"{espacio_total / (1024**3):.1f} GB" if espacio_total > 1024**3 else f"{espacio_total / (1024**2):.1f} MB",
            'por_decidir': por_decidir
        }

    return render_template_string(HTML_TEMPLATE,
                                  rutas=rutas,
                                  duplicados=duplicados,
                                  estado=estado.get('acciones', {}),
                                  stats=stats,
                                  carpeta_destino=carpeta_destino,
                                  modo_consolidar=modo_consolidar,
                                  extensiones=EXTENSIONES,
                                  filtros_activos=estado.get('filtros_activos', list(EXTENSIONES.keys()) + ['otros']),
                                  tamano_min_video=estado.get('tamano_min_video', TAMANO_MIN_VIDEO))

@app.route('/configurar', methods=['POST'])
def configurar():
    global scan_thread, scan_cancelado

    # Recolectar rutas
    rutas = []
    i = 0
    while True:
        r = request.form.get(f'ruta_{i}')
        if r is None:
            break
        r = r.strip()
        if r:
            rutas.append(r)
        i += 1

    if not rutas:
        flash('ERROR: Debes agregar al menos una ruta valida.', 'error')
        return redirect('/')

    # Recolectar filtros activos
    filtros_activos = request.form.getlist('filtros[]')
    if not filtros_activos:
        filtros_activos = list(EXTENSIONES.keys()) + ['otros']

    # Recolectar tamaño mínimo de video
    tamano_min_video = request.form.get('tamano_min_video', '1')
    try:
        tamano_min_video = int(tamano_min_video) * 1024 * 1024
    except ValueError:
        tamano_min_video = TAMANO_MIN_VIDEO

    # Guardar configuracion
    estado = cargar_estado()
    estado['rutas'] = rutas
    estado['carpeta_destino'] = request.form.get('carpeta_destino', CARPETA_DESTINO_DEFAULT).strip()
    estado['modo_consolidar'] = request.form.get('modo_consolidar') == '1'
    estado['filtros_activos'] = filtros_activos
    estado['tamano_min_video'] = tamano_min_video
    guardar_estado(estado)

    # Iniciar escaneo en segundo plano
    scan_cancelado = False
    def scan_worker():
        duplicados = encontrar_duplicados_con_progreso(rutas, filtros_activos)
        if not scan_cancelado:
            estado = cargar_estado()
            estado['duplicados'] = duplicados
            guardar_estado(estado)

    scan_thread = threading.Thread(target=scan_worker, daemon=True)
    scan_thread.start()

    return jsonify({'ok': True})

@app.route('/dialogo_carpeta')
def dialogo_carpeta():
    """Abre un dialogo nativo de Windows para seleccionar carpeta y devuelve la ruta absoluta.
    Acumula selecciones en una lista temporal para permitir multiples carpetas."""
    global rutas_seleccionadas_dialogo
    try:
        # Usar PowerShell para abrir el dialogo de carpeta de Windows
        ps_script = r'''
Add-Type -AssemblyName System.Windows.Forms
$rutas = @()
$continuar = $true
while ($continuar) {
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = "Selecciona una carpeta de respaldo (Cancelar para terminar)"
    $dlg.ShowNewFolderButton = $false
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $rutas += $dlg.SelectedPath
        $result = [System.Windows.Forms.MessageBox]::Show(
            "Ruta agregada: " + $dlg.SelectedPath + "`n`nQuieres agregar otra carpeta?",
            "Agregar mas?",
            [System.Windows.Forms.MessageBoxButtons]::YesNo,
            [System.Windows.Forms.MessageBoxIcon]::Question
        )
        if ($result -eq [System.Windows.Forms.DialogResult]::No) {
            $continuar = $false
        }
    } else {
        $continuar = $false
    }
}
$rutas | ForEach-Object { Write-Output $_ }
'''
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command', ps_script],
            capture_output=True, text=True, timeout=120
        )
        # Parsear salida: una ruta por linea
        rutas = [line.strip() for line in result.stdout.strip().split('\n') if line.strip() and os.path.isdir(line.strip())]
        if rutas:
            return jsonify({'rutas': rutas})
        return jsonify({'rutas': []})
    except Exception as e:
        return jsonify({'rutas': [], 'error': str(e)})

@app.route('/progreso')
def progreso():
    return jsonify(cargar_progreso())

@app.route('/cancelar', methods=['POST'])
def cancelar():
    global scan_cancelado
    scan_cancelado = True
    guardar_progreso({
        'estado': 'idle',
        'mensaje': 'Escaneo cancelado.',
        'progreso': 0,
        'total': 0,
        'actual': 0,
        'ruta_actual': ''
    })
    return jsonify({'ok': True})

@app.route('/accion')
def marcar_accion():
    hash_val = request.args.get('hash')
    ruta = request.args.get('ruta')
    tipo = request.args.get('tipo')

    if not all([hash_val, ruta, tipo]):
        flash('ERROR: Parametros incompletos')
        return redirect('/')

    estado = cargar_estado()
    key = f"{hash_val}|{ruta}"

    if tipo == 'mantener':
        estado['acciones'][key] = 'mantener'
        for a in estado['duplicados'].get(hash_val, []):
            other_key = f"{hash_val}|{a['ruta']}"
            if other_key != key and other_key not in estado['acciones']:
                estado['acciones'][other_key] = 'eliminar'
    else:
        estado['acciones'][key] = tipo

    guardar_estado(estado)
    flash(f'OK: Marcado para {tipo.upper()}: {os.path.basename(ruta)}')
    return redirect('/')

@app.route('/ejecutar', methods=['POST'])
def ejecutar():
    estado = cargar_estado()
    acciones = estado.get('acciones', {})
    duplicados = estado.get('duplicados', {})
    carpeta_destino = estado.get('carpeta_destino', CARPETA_DESTINO_DEFAULT)
    modo_consolidar = estado.get('modo_consolidar', False)

    resultados = {'eliminados': 0, 'movidos': 0, 'consolidados': 0, 'errores': []}

    for key, accion in acciones.items():
        if accion == 'eliminar':
            try:
                _, ruta = key.split('|', 1)
                if os.path.exists(ruta):
                    os.remove(ruta)
                    resultados['eliminados'] += 1
            except Exception as e:
                resultados['errores'].append(f"Error eliminando {ruta}: {e}")

        elif accion == 'mover':
            try:
                _, ruta = key.split('|', 1)
                if os.path.exists(ruta):
                    if modo_consolidar and carpeta_destino:
                        # MODO CONSOLIDACION: Copiar a destino manteniendo estructura relativa
                        # Calculamos la ruta relativa respecto a la carpeta origen
                        ruta_origen_carpeta = None
                        for dup_hash, archivos in duplicados.items():
                            for a in archivos:
                                if a['ruta'] == ruta:
                                    ruta_origen_carpeta = a['carpeta']
                                    break
                            if ruta_origen_carpeta:
                                break

                        if ruta_origen_carpeta:
                            # Calcular ruta relativa dentro de la carpeta origen
                            rel_path = os.path.relpath(ruta, ruta_origen_carpeta)
                            destino = os.path.join(carpeta_destino, rel_path)
                        else:
                            # Fallback: solo el nombre del archivo
                            destino = os.path.join(carpeta_destino, os.path.basename(ruta))

                        # Crear directorios destino si no existen
                        os.makedirs(os.path.dirname(destino), exist_ok=True)

                        # Copiar (no mover, para mantener seguro hasta verificar)
                        shutil.copy2(ruta, destino)
                        resultados['consolidados'] += 1

                        # Eliminar original despues de copiar
                        os.remove(ruta)
                    else:
                        # MODO CLASICO: Mover a _revisar local
                        carpeta_revisar = os.path.join(os.path.dirname(ruta), '_revisar')
                        os.makedirs(carpeta_revisar, exist_ok=True)
                        destino = os.path.join(carpeta_revisar, os.path.basename(ruta))
                        shutil.move(ruta, destino)
                        resultados['movidos'] += 1
            except Exception as e:
                resultados['errores'].append(f"Error moviendo {ruta}: {e}")

    estado['acciones'] = {}
    guardar_estado(estado)

    msg = f"OK: Ejecutado: {resultados['eliminados']} eliminados"
    if modo_consolidar:
        msg += f", {resultados['consolidados']} consolidados a {carpeta_destino}"
    else:
        msg += f", {resultados['movidos']} movidos a _revisar"
    if resultados['errores']:
        msg += f". {len(resultados['errores'])} errores."

    flash(msg)
    return redirect('/')

def iniciar():
    print(">>> Iniciando Comparador de Respaldos...")
    print("Abre tu navegador en: http://localhost:5000")
    webbrowser.open('http://localhost:5000')
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    iniciar()
