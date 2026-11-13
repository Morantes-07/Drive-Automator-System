"""Pruebas para src.drive.folder_tree."""

import pytest

from src.drive.folder_tree import (
    AmbiguousPathError,
    FolderNode,
    FolderTreeError,
    FolderTreeModel,
)


CARPETAS = [
    {"id": "r1", "name": "Power BI", "parents": ["root"]},
    {"id": "r2", "name": "Excel", "parents": ["root"]},
    {"id": "r1a", "name": "2024", "parents": ["r1"]},
    {"id": "r1b", "name": "2023", "parents": ["r1"]},
    {"id": "r2a", "name": "Datos", "parents": ["r2"]},
]


def modelo(folders=None, root_id="root", root_name="Mi Drive"):
    return FolderTreeModel(
        CARPETAS if folders is None else folders,
        root_id=root_id,
        root_name=root_name,
    )


def test_la_raiz_se_crea_aunque_no_venga_en_el_listado():
    arbol = modelo()
    assert arbol.root.id == "root"
    assert arbol.root.name == "Mi Drive"
    assert arbol.root.parent_ids == ()
    assert "root" in arbol
    assert len(arbol) == 6  # 5 carpetas + raíz


def test_los_hijos_se_ordenan_alfabeticamente():
    arbol = modelo()
    nombres = [nodo.name for nodo in arbol.children_of("root")]
    assert nombres == ["Excel", "Power BI"]
    assert [nodo.name for nodo in arbol.children_of("r1")] == ["2023", "2024"]


def test_el_orden_ignora_tildes_y_mayusculas():
    folders = [
        {"id": "z", "name": "Zorro", "parents": ["root"]},
        {"id": "a", "name": "árbol", "parents": ["root"]},
        {"id": "b", "name": "banco", "parents": ["root"]},
    ]
    arbol = modelo(folders)
    assert [nodo.name for nodo in arbol.children_of("root")] == [
        "árbol",
        "banco",
        "Zorro",
    ]


def test_has_children_distingue_hojas_y_carpetas_inexistentes():
    arbol = modelo()
    assert arbol.has_children("r1") is True
    assert arbol.has_children("r1a") is False
    assert arbol.has_children("no-existe") is False


def test_children_of_de_una_carpeta_desconocida_devuelve_tupla_vacia():
    arbol = modelo()
    assert arbol.children_of("no-existe") == ()


def test_get_y_require():
    arbol = modelo()
    assert arbol.get("r1a").name == "2024"
    assert arbol.get("no-existe") is None
    with pytest.raises(FolderTreeError, match="desconocida"):
        arbol.require("no-existe")


def test_path_of_construye_la_ruta_desde_la_raiz():
    arbol = modelo()
    assert arbol.path_of("root") == "Mi Drive"
    assert arbol.path_of("r1") == "Mi Drive/Power BI"
    assert arbol.path_of("r2a") == "Mi Drive/Excel/Datos"


def test_path_of_de_una_carpeta_desconocida_falla():
    arbol = modelo()
    with pytest.raises(FolderTreeError, match="desconocida"):
        arbol.path_of("no-existe")


def test_resolve_path_acepta_rutas_con_y_sin_la_raiz():
    arbol = modelo()
    assert arbol.resolve_path("Mi Drive/Power BI/2024").id == "r1a"
    assert arbol.resolve_path("Power BI/2024").id == "r1a"
    assert arbol.resolve_path("Mi Drive").id == "root"
    assert arbol.resolve_path("power bi/2024").id == "r1a"


def test_resolve_path_admite_barras_invertidas_y_espacios():
    arbol = modelo()
    assert arbol.resolve_path("Mi Drive \\ Power BI \\ 2024").id == "r1a"


def test_resolve_path_devuelve_none_si_no_existe():
    arbol = modelo()
    assert arbol.resolve_path("") is None
    assert arbol.resolve_path(None) is None
    assert arbol.resolve_path("Mi Drive/No existe") is None
    assert arbol.resolve_path("Power BI/2024/Enero") is None


def test_resolve_path_detecta_rutas_ambiguas():
    folders = CARPETAS + [
        {"id": "r2b", "name": "Datos", "parents": ["r2"]},
    ]
    arbol = modelo(folders)
    with pytest.raises(AmbiguousPathError) as error:
        arbol.resolve_path("Mi Drive/Excel/Datos")
    assert {nodo.id for nodo in error.value.candidates} == {"r2a", "r2b"}


def test_una_carpeta_con_varios_padres_aparece_en_ambos():
    folders = [
        {"id": "a", "name": "A", "parents": ["root"]},
        {"id": "b", "name": "B", "parents": ["root"]},
        {"id": "compartida", "name": "Compartida", "parents": ["a", "b"]},
    ]
    arbol = modelo(folders)
    assert [n.id for n in arbol.children_of("a")] == ["compartida"]
    assert [n.id for n in arbol.children_of("b")] == ["compartida"]
    # La ruta elige el primer padre conocido y es determinista.
    assert arbol.path_of("compartida") == "Mi Drive/A/Compartida"
    assert arbol.resolve_path("Mi Drive/B/Compartida").id == "compartida"


def test_un_ciclo_de_padres_no_bloquea_path_of():
    folders = [
        {"id": "a", "name": "A", "parents": ["b"]},
        {"id": "b", "name": "B", "parents": ["a"]},
    ]
    arbol = modelo(folders)
    ruta = arbol.path_of("a")
    assert set(ruta.split("/")) == {"A", "B"}


def test_un_id_duplicado_falla():
    folders = [
        {"id": "x", "name": "Uno", "parents": ["root"]},
        {"id": "x", "name": "Dos", "parents": ["root"]},
    ]
    with pytest.raises(FolderTreeError, match="duplicado"):
        modelo(folders)


def test_una_carpeta_sin_id_o_sin_nombre_falla():
    with pytest.raises(FolderTreeError, match="sin id"):
        modelo([{"name": "Sin id", "parents": ["root"]}])
    with pytest.raises(FolderTreeError, match="sin nombre"):
        modelo([{"id": "x", "parents": ["root"]}])


def test_admite_instancias_de_folder_node():
    folders = [
        FolderNode(id="a", name="A", parent_ids=("root",)),
        FolderNode(id="a1", name="A1", parent_ids=("a",)),
    ]
    arbol = modelo(folders)
    assert arbol.path_of("a1") == "Mi Drive/A/A1"


def test_un_padre_fuera_del_listado_se_ignora():
    folders = [
        {"id": "huerfana", "name": "Huérfana", "parents": ["desconocido"]},
    ]
    arbol = modelo(folders)
    assert arbol.children_of("root") == ()
    assert arbol.path_of("huerfana") == "Huérfana"


def test_la_raiz_del_listado_se_renombra():
    folders = [{"id": "root", "name": "Nombre de la API", "parents": []}]
    arbol = modelo(folders)
    assert arbol.root.name == "Mi Drive"
    assert len(arbol) == 1
