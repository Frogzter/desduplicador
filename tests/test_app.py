import json
import os
import pytest
from pathlib import Path
from app import (
    app,
    detectar_categoria,
    archivo_pasa_filtro,
    format_size,
    escape_html,
    load_config,
    save_config,
)


@pytest.fixture(autouse=True)
def patch_data_dir(tmp_path, monkeypatch):
    """Aísla los archivos de datos para que los tests no afecten la config real."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("app.DATA_DIR", data_dir)
    monkeypatch.setattr("app.CONFIG_FILE", data_dir / "config.json")
    monkeypatch.setattr("app.PROGRESS_FILE", data_dir / "progress.json")


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestDetectarCategoria:
    def test_musica(self):
        assert detectar_categoria("song.mp3") == "musica"
        assert detectar_categoria("song.wav") == "musica"
        assert detectar_categoria("song.flac") == "musica"

    def test_video(self):
        assert detectar_categoria("movie.mp4") == "video"
        assert detectar_categoria("movie.avi") == "video"
        assert detectar_categoria("movie.mkv") == "video"

    def test_documentos(self):
        assert detectar_categoria("doc.pdf") == "documentos"
        assert detectar_categoria("sheet.xlsx") == "documentos"
        assert detectar_categoria("notes.txt") == "documentos"

    def test_ejecutables(self):
        assert detectar_categoria("app.exe") == "ejecutables"
        assert detectar_categoria("script.sh") == "ejecutables"
        assert detectar_categoria("installer.msi") == "ejecutables"

    def test_imagenes(self):
        assert detectar_categoria("photo.jpg") == "imagenes"
        assert detectar_categoria("image.png") == "imagenes"
        assert detectar_categoria("raw.cr2") == "imagenes"

    def test_comprimidos(self):
        assert detectar_categoria("archive.zip") == "comprimidos"
        assert detectar_categoria("backup.7z") == "comprimidos"
        assert detectar_categoria("disk.iso") == "comprimidos"

    def test_otros(self):
        assert detectar_categoria("unknown.xyz") == "otros"
        assert detectar_categoria("file.abc123") == "otros"
        assert detectar_categoria("noextension") == "otros"

    def test_case_insensitive(self):
        assert detectar_categoria("SONG.MP3") == "musica"
        assert detectar_categoria("Movie.MP4") == "video"
        assert detectar_categoria("Doc.PDF") == "documentos"


class TestArchivoPasaFiltro:
    def test_sin_filtros(self):
        assert archivo_pasa_filtro("song.mp3", [], 0) is True
        assert archivo_pasa_filtro("unknown.xyz", [], 0) is True
        assert archivo_pasa_filtro("movie.mp4", [], 10 * 1024 * 1024) is True

    def test_categoria_activa(self):
        assert archivo_pasa_filtro("song.mp3", ["musica"], 0) is True
        assert archivo_pasa_filtro("movie.mp4", ["video"], 10 * 1024 * 1024) is True
        assert archivo_pasa_filtro("doc.pdf", ["documentos"], 0) is True

    def test_categoria_inactiva(self):
        assert archivo_pasa_filtro("song.mp3", ["video"], 0) is False
        assert archivo_pasa_filtro("unknown.xyz", ["musica"], 0) is False
        assert archivo_pasa_filtro("movie.mp4", ["musica", "documentos"], 0) is False

    def test_video_tamano_pequeno(self):
        """Videos menores al tamaño mínimo deben ser filtrados."""
        assert archivo_pasa_filtro("movie.mp4", ["video"], 0) is False
        assert archivo_pasa_filtro("movie.mp4", ["video"], 512 * 1024) is False

    def test_video_tamano_grande(self):
        """Videos mayores al tamaño mínimo deben pasar."""
        assert archivo_pasa_filtro("movie.mp4", ["video"], 10 * 1024 * 1024) is True
        assert archivo_pasa_filtro("movie.mp4", ["video"], 1024 * 1024 * 1024) is True


class TestFormatSize:
    def test_zero_bytes(self):
        assert format_size(0) == "0 B"

    def test_kilobytes(self):
        assert format_size(1024) == "1 KB"
        assert format_size(1536) == "1.5 KB"
        assert format_size(2048) == "2 KB"

    def test_megabytes(self):
        assert format_size(1024 * 1024) == "1 MB"
        assert format_size(1.5 * 1024 * 1024) == "1.5 MB"
        assert format_size(2 * 1024 * 1024) == "2 MB"

    def test_gigabytes(self):
        assert format_size(1024 * 1024 * 1024) == "1 GB"
        assert format_size(2.5 * 1024 * 1024 * 1024) == "2.5 GB"


class TestEscapeHtml:
    def test_basic(self):
        assert escape_html("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
        assert escape_html("hello & world") == "hello &amp; world"
        assert escape_html('"quoted"') == '&quot;quoted&quot;'
        assert escape_html("normal text") == "normal text"


class TestFlaskEndpoints:
    def test_get_config(self, client):
        response = client.get("/api/config")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "paths" in data
        assert "filtros_activos" in data
        assert "tamano_min_video" in data

    def test_get_filters(self, client):
        response = client.get("/api/filters")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "categorias" in data
        assert "filtros_activos" in data
        assert "tamano_min_video" in data
        assert set(data["categorias"].keys()) == {
            "musica", "video", "documentos", "ejecutables", "imagenes", "comprimidos"
        }

    def test_post_config(self, client):
        payload = {
            "paths": ["/test/path1", "/test/path2"],
            "output_path": "/test/output",
            "review_path": "/test/review",
            "filtros_activos": ["musica", "video"],
            "tamano_min_video": 2097152,
        }
        response = client.post("/api/config", json=payload)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["paths"] == ["/test/path1", "/test/path2"]
        assert data["output_path"] == "/test/output"
        assert data["review_path"] == "/test/review"
        assert data["filtros_activos"] == ["musica", "video"]
        assert data["tamano_min_video"] == 2097152

    def test_get_last_scan_empty(self, client):
        response = client.get("/api/last_scan")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []

    def test_config_roundtrip(self, client):
        """Guarda config vía POST y la recupera vía GET."""
        payload = {
            "paths": ["/roundtrip/a", "/roundtrip/b"],
            "output_path": "/roundtrip/out",
            "review_path": "/roundtrip/rev",
            "filtros_activos": ["imagenes", "comprimidos"],
            "tamano_min_video": 5242880,
        }
        post_resp = client.post("/api/config", json=payload)
        assert post_resp.status_code == 200

        get_resp = client.get("/api/config")
        assert get_resp.status_code == 200
        data = json.loads(get_resp.data)
        assert data["paths"] == ["/roundtrip/a", "/roundtrip/b"]
        assert data["output_path"] == "/roundtrip/out"
        assert data["review_path"] == "/roundtrip/rev"
        assert data["filtros_activos"] == ["imagenes", "comprimidos"]
        assert data["tamano_min_video"] == 5242880


class TestConfigSaveLoad:
    def test_save_and_load(self, patch_data_dir):
        """Prueba el guardado y carga directo de funciones utilitarias."""
        test_config = {
            "paths": ["/a", "/b"],
            "output_path": "/out",
            "review_path": "/rev",
            "filtros_activos": ["imagenes"],
            "tamano_min_video": 1048576,
        }
        save_config(test_config)
        loaded = load_config()
        assert loaded == test_config


class TestActionEndpoint:
    def test_action_delete_allowed(self, client, tmp_path, patch_data_dir):
        """Elimina un archivo dentro de una ruta permitida."""
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        test_file = allowed / "file.txt"
        test_file.write_text("hello")

        save_config({"paths": [str(allowed)], "output_path": "", "review_path": ""})

        response = client.post("/api/action", json={
            "action": "delete",
            "files": [str(test_file)],
            "keep": "",
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert len(data["results"]) == 1
        assert data["results"][0]["success"] is True
        assert not test_file.exists()

    def test_action_path_not_allowed(self, client, tmp_path, patch_data_dir):
        """Rechaza archivos fuera de las rutas configuradas."""
        outside = tmp_path / "outside"
        outside.mkdir()
        test_file = outside / "file.txt"
        test_file.write_text("hello")

        allowed = tmp_path / "allowed"
        allowed.mkdir()
        save_config({"paths": [str(allowed)], "output_path": "", "review_path": ""})

        response = client.post("/api/action", json={
            "action": "delete",
            "files": [str(test_file)],
            "keep": "",
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Ruta no permitida" in data["message"]

    def test_action_rename_allowed(self, client, tmp_path, patch_data_dir):
        """Renombra un archivo dentro de una ruta permitida."""
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        test_file = allowed / "file.txt"
        test_file.write_text("hello")

        save_config({"paths": [str(allowed)], "output_path": "", "review_path": ""})

        response = client.post("/api/action", json={
            "action": "rename",
            "files": [str(test_file)],
            "keep": "",
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["results"][0]["success"] is True
        assert "Renombrado" in data["results"][0]["message"]
        assert not test_file.exists()
        assert list(allowed.glob("file_duplicado_*.txt"))

    def test_action_move_review_allowed(self, client, tmp_path, patch_data_dir):
        """Mueve un archivo a la carpeta de revisión."""
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        test_file = allowed / "file.txt"
        test_file.write_text("hello")
        review = tmp_path / "review"

        save_config({"paths": [str(allowed)], "output_path": "", "review_path": str(review)})

        response = client.post("/api/action", json={
            "action": "move_review",
            "files": [str(test_file)],
            "keep": "",
            "review_path": str(review),
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["results"][0]["success"] is True
        assert not test_file.exists()
        assert (review / "file.txt").exists()

    def test_action_consolidate_allowed(self, client, tmp_path, patch_data_dir):
        """Consolida un archivo copiándolo a output_path y eliminando el original."""
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        test_file = allowed / "file.txt"
        test_file.write_text("hello consolidate")
        output = tmp_path / "output"

        save_config({"paths": [str(allowed)], "output_path": str(output), "review_path": ""})

        response = client.post("/api/action", json={
            "action": "consolidate",
            "files": [str(test_file)],
            "keep": "",
            "output_path": str(output),
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["results"][0]["success"] is True
        assert not test_file.exists()
        assert (output / "file.txt").exists()
        assert (output / "file.txt").read_text() == "hello consolidate"


class TestBrowseFolder:
    def test_browse_folder_powershell(self, client, monkeypatch):
        """Simula selección de carpeta vía PowerShell fallback."""
        fake_path = r"C:\Users\Test\Documents"

        def fake_powershell(title, initial_dir):
            return fake_path

        monkeypatch.setattr("app._browse_folder_powershell", fake_powershell)
        monkeypatch.setattr("app.WINFORMS_AVAILABLE", False)
        monkeypatch.setattr("app.platform.system", lambda: "Windows")

        response = client.post("/api/browse_folder", json={"title": "Test"})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["path"] == fake_path

    def test_browse_folder_ctypes(self, client, monkeypatch):
        """Simula selección de carpeta vía ctypes fallback."""
        fake_path = r"Z:\NAS\Backup"

        def fake_ctypes(title, initial_dir):
            return fake_path

        monkeypatch.setattr("app._browse_folder_ctypes", fake_ctypes)
        monkeypatch.setattr("app._browse_folder_powershell", lambda t, i: None)
        monkeypatch.setattr("app.WINFORMS_AVAILABLE", False)
        monkeypatch.setattr("app.platform.system", lambda: "Windows")

        response = client.post("/api/browse_folder", json={"title": "Test"})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["path"] == fake_path

    def test_browse_folder_cancelled(self, client, monkeypatch):
        """Simula que el usuario cancela el diálogo."""
        monkeypatch.setattr("app._browse_folder_powershell", lambda t, i: None)
        monkeypatch.setattr("app._browse_folder_ctypes", lambda t, i: None)
        monkeypatch.setattr("app.WINFORMS_AVAILABLE", False)
        monkeypatch.setattr("app.platform.system", lambda: "Windows")

        response = client.post("/api/browse_folder", json={"title": "Test"})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False
        assert "No se selecciono" in data["message"]
