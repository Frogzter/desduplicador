import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app import (
    app, detectar_categoria, archivo_pasa_filtro,
    EXTENSIONES, TAMANO_MIN_VIDEO_DEFAULT
)


class TestDetectarCategoria:
    def test_mp3_es_musica(self):
        assert detectar_categoria('cancion.mp3') == 'musica'

    def test_mp4_es_video(self):
        assert detectar_categoria('pelicula.mp4') == 'video'

    def test_pdf_es_documento(self):
        assert detectar_categoria('doc.pdf') == 'documentos'

    def test_exe_es_ejecutable(self):
        assert detectar_categoria('app.exe') == 'ejecutables'

    def test_jpg_es_imagen(self):
        assert detectar_categoria('foto.jpg') == 'imagenes'

    def test_zip_es_comprimido(self):
        assert detectar_categoria('backup.zip') == 'comprimidos'

    def test_desconocido_es_otros(self):
        assert detectar_categoria('archivo.xyz') == 'otros'

    def test_case_insensitive(self):
        assert detectar_categoria('foto.JPG') == 'imagenes'
        assert detectar_categoria('Cancion.MP3') == 'musica'


class TestArchivoPasaFiltro:
    def test_sin_filtros_pasa_todo(self):
        assert archivo_pasa_filtro('test.mp3', [], 1000) is True

    def test_categoria_incluida_pasa(self):
        assert archivo_pasa_filtro('test.mp3', ['musica'], 1000) is True

    def test_categoria_excluida_no_pasa(self):
        assert archivo_pasa_filtro('test.mp3', ['video'], 1000) is False

    def test_video_grande_pasa(self):
        tamano = 10 * 1024 * 1024  # 10 MB
        assert archivo_pasa_filtro('test.mp4', ['video'], tamano, tamano) is True

    def test_video_pequeno_no_pasa(self):
        tamano = 100  # 100 bytes
        min_video = 1024 * 1024  # 1 MB
        assert archivo_pasa_filtro('test.mp4', ['video'], tamano, min_video) is False

    def test_video_pequeno_sin_filtro_video_pasa(self):
        tamano = 100
        assert archivo_pasa_filtro('test.mp4', ['musica'], tamano) is False

    def test_varias_categorias(self):
        assert archivo_pasa_filtro('test.mp3', ['musica', 'video'], 1000) is True
        assert archivo_pasa_filtro('test.mp4', ['musica', 'video'], 10 * 1024 * 1024, 1024 * 1024) is True


class TestFlaskEndpoints:
    @pytest.fixture
    def client(self):
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_get_filters(self, client):
        resp = client.get('/api/filters')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'categorias' in data
        assert 'filtros_activos' in data
        assert 'tamano_min_video' in data
        assert set(data['categorias'].keys()) == set(EXTENSIONES.keys())

    def test_get_config(self, client):
        resp = client.get('/api/config')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'paths' in data
        assert 'filtros_activos' in data

    def test_post_config(self, client):
        resp = client.post('/api/config', json={
            'paths': ['C:/test'],
            'filtros_activos': ['musica'],
            'tamano_min_video': 5 * 1024 * 1024
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['filtros_activos'] == ['musica']
        assert data['tamano_min_video'] == 5242880

    def test_get_last_scan(self, client):
        resp = client.get('/api/last_scan')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_action_path_validation(self, client):
        # First set paths in config
        client.post('/api/config', json={'paths': ['C:/allowed']})
        resp = client.post('/api/action', json={
            'action': 'delete',
            'files': ['C:/notallowed/file.txt'],
            'output_path': '',
            'review_path': ''
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is False
