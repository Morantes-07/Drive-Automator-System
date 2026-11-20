"""Pruebas para src.drive.file_types."""

import pytest

from src.drive.file_types import (
    CATEGORIES,
    CATEGORY_LABELS,
    FileTypeRules,
    categories_of,
    filter_files,
    is_folder,
)


def archivo(name: str, mime_type: str) -> dict:
    return {"name": name, "mimeType": mime_type}


def test_categories_of_video_mp4():
    assert categories_of(archivo("grabacion.mp4", "video/mp4")) == {"videos"}


def test_categories_of_video_quicktime():
    assert categories_of(
        archivo("grabacion.mov", "video/quicktime")
    ) == {"videos"}


def test_categories_of_imagen():
    assert categories_of(archivo("foto.png", "image/png")) == {"imagenes"}


def test_categories_of_audio():
    assert categories_of(archivo("podcast.mp3", "audio/mpeg")) == {"audio"}


def test_categories_of_google_doc():
    assert categories_of(
        archivo("informe", "application/vnd.google-apps.document")
    ) == {"documentos"}


def test_categories_of_google_sheet():
    assert categories_of(
        archivo("datos", "application/vnd.google-apps.spreadsheet")
    ) == {"hojas"}


def test_categories_of_google_slides():
    assert categories_of(
        archivo("presentacion", "application/vnd.google-apps.presentation")
    ) == {"presentaciones"}


def test_categories_of_pdf():
    assert categories_of(
        archivo("informe.pdf", "application/pdf")
    ) == {"pdf"}


def test_categories_of_markdown_se_solapa_con_texto():
    assert categories_of(
        archivo("notas.md", "text/markdown")
    ) == {"markdown", "texto_codigo"}


def test_categories_of_csv_se_solapa_con_texto():
    assert categories_of(
        archivo("datos.csv", "text/csv")
    ) == {"hojas", "texto_codigo"}


def test_categories_of_txt_se_solapa_con_texto():
    assert categories_of(
        archivo("notas.txt", "text/plain")
    ) == {"documentos", "texto_codigo"}


def test_categories_of_comprimido():
    assert categories_of(
        archivo("respaldo.zip", "application/zip")
    ) == {"comprimidos"}


def test_categories_of_desconocido_devuelve_otros():
    assert categories_of(
        archivo("dato.xyz", "application/octet-stream")
    ) == {"otros"}


def test_categories_of_fallback_por_extension():
    assert categories_of(
        archivo("grabacion.mp4", "application/octet-stream")
    ) == {"videos"}


def test_categories_of_carpeta_devuelve_conjunto_vacio():
    assert categories_of(
        archivo("carpeta", "application/vnd.google-apps.folder")
    ) == set()


def test_is_folder():
    assert is_folder(
        archivo("carpeta", "application/vnd.google-apps.folder")
    )
    assert not is_folder(archivo("video.mp4", "video/mp4"))


def test_filter_files_sin_categorias_devuelve_todos_menos_carpetas():
    files = [
        archivo("video.mp4", "video/mp4"),
        archivo("informe.pdf", "application/pdf"),
        archivo("carpeta", "application/vnd.google-apps.folder"),
    ]
    result = filter_files(files)
    assert [file["name"] for file in result] == [
        "video.mp4",
        "informe.pdf",
    ]


def test_filter_files_una_categoria():
    files = [
        archivo("video.mp4", "video/mp4"),
        archivo("informe.pdf", "application/pdf"),
    ]
    result = filter_files(files, {"videos"})
    assert [file["name"] for file in result] == ["video.mp4"]


def test_filter_files_varias_categorias():
    files = [
        archivo("video.mp4", "video/mp4"),
        archivo("notas.md", "text/markdown"),
        archivo("informe.pdf", "application/pdf"),
    ]
    result = filter_files(files, {"videos", "markdown"})
    assert [file["name"] for file in result] == [
        "video.mp4",
        "notas.md",
    ]


def test_filter_files_otros_solo_no_clasificados():
    files = [
        archivo("video.mp4", "video/mp4"),
        archivo("dato.xyz", "application/octet-stream"),
    ]
    result = filter_files(files, {"otros"})
    assert [file["name"] for file in result] == ["dato.xyz"]


def test_filter_files_categoria_desconocida_lanza_error():
    with pytest.raises(ValueError, match="desconocidas"):
        filter_files([], {"inexistente"})


def test_category_labels_cubren_todas_las_categorias():
    assert set(CATEGORY_LABELS) == set(CATEGORIES)


def test_file_type_rules_por_defecto_estan_vacias():
    rules = FileTypeRules()
    assert rules.mime_prefixes == ()
    assert rules.mime_types == ()
    assert rules.extensions == ()
