"""Pruebas para src.patterns.suggestions."""

from src.patterns.placeholders import PLACEHOLDER_INFOS
from src.patterns.suggestions import (
    PlaceholderQuery,
    apply_suggestion,
    find_placeholder_query,
    move_selection,
    suggest_placeholders,
)


def _suggest(text: str, caret: int) -> list[str]:
    query = find_placeholder_query(text, caret)
    assert query is not None
    return [info.key for info in suggest_placeholders(query)]


# -- detección del placeholder abierto ------------------------------------
def test_sin_llave_abierta_no_hay_consulta():
    assert find_placeholder_query("G3-Power BI", 5) is None
    assert find_placeholder_query("G{número}", 9) is None


def test_llave_al_final_abre_consulta_vacia():
    query = find_placeholder_query("G{", 2)
    assert query == PlaceholderQuery(start=1, caret=2, text="", close=None)


def test_texto_parcial_es_la_consulta():
    query = find_placeholder_query("G{nu", 4)
    assert query is not None
    assert query.start == 1
    assert query.caret == 4
    assert query.text == "nu"
    assert query.close is None


def test_cursor_dentro_de_placeholder_cerrado_guarda_el_cierre():
    query = find_placeholder_query("G{número}", 4)
    assert query is not None
    assert query.text == "nú"
    assert query.close == 8


def test_usa_la_ultima_llave_abierta():
    query = find_placeholder_query("G{a{b", 5)
    assert query is not None
    assert query.start == 3
    assert query.text == "b"


def test_cursor_antes_de_la_llave_no_genera_consulta():
    assert find_placeholder_query("G{", 1) is None


def test_cursor_fuera_de_rango_se_ajusta():
    assert find_placeholder_query("G{", 99) is not None
    assert find_placeholder_query("G{", -3) is None


def test_otra_apertura_antes_del_cierre_invalida_el_cierre():
    query = find_placeholder_query("G{|a{b}", 2)
    assert query is not None
    assert query.close is None


# -- filtrado --------------------------------------------------------------
def test_sin_texto_devuelve_todo_el_catalogo():
    assert _suggest("G{", 2) == ["numero", "letra", "palabra"]


def test_filtra_por_prefijo():
    assert _suggest("G{nu", 4) == ["numero"]
    assert _suggest("G{l", 3) == ["letra"]
    assert _suggest("G{pa", 4) == ["palabra"]


def test_filtra_sin_distinguir_tildes_ni_mayusculas():
    assert _suggest("G{nú", 4) == ["numero"]
    assert _suggest("G{NUM", 5) == ["numero"]


def test_sin_coincidencias_devuelve_lista_vacia():
    assert _suggest("G{x", 3) == []
    assert _suggest("G{na", 4) == []
    assert _suggest("G{ ", 3) == []


# -- sustitución -----------------------------------------------------------
def test_sustituye_placeholder_abierto():
    info = PLACEHOLDER_INFOS[0]
    query = find_placeholder_query("G{nu", 4)
    assert query is not None

    text, caret = apply_suggestion("G{nu", query, info)
    assert text == "G{número}"
    assert caret == 9


def test_sustituye_el_token_completo_si_estaba_cerrado():
    info = PLACEHOLDER_INFOS[0]
    query = find_placeholder_query("G{número}", 4)
    assert query is not None

    text, caret = apply_suggestion("G{número}", query, info)
    assert text == "G{número}"
    assert caret == 9


def test_conserva_prefijo_y_sufijo():
    info = PLACEHOLDER_INFOS[1]
    query = find_placeholder_query("A{le-B", 4)
    assert query is not None

    text, caret = apply_suggestion("A{le-B", query, info)
    assert text == "A{letra}-B"
    assert caret == 8


def test_conserva_sufijo_tras_un_token_cerrado():
    info = PLACEHOLDER_INFOS[0]
    query = find_placeholder_query("A{número}-B", 3)
    assert query is not None

    text, caret = apply_suggestion("A{número}-B", query, info)
    assert text == "A{número}-B"
    assert caret == 9


def test_rellena_un_token_vacio():
    info = PLACEHOLDER_INFOS[0]
    query = find_placeholder_query("G{}", 2)
    assert query is not None

    text, caret = apply_suggestion("G{}", query, info)
    assert text == "G{número}"
    assert caret == 9


def test_solo_sustituye_el_token_del_cursor():
    info = PLACEHOLDER_INFOS[1]
    query = find_placeholder_query("{número}-{le", 12)
    assert query is not None

    text, caret = apply_suggestion("{número}-{le", query, info)
    assert text == "{número}-{letra}"
    assert caret == 16


# -- selección -------------------------------------------------------------
def test_move_selection_respeta_los_extremos():
    assert move_selection(0, 1, 3) == 1
    assert move_selection(2, 1, 3) == 2
    assert move_selection(0, -1, 3) == 0
    assert move_selection(1, -5, 3) == 0
    assert move_selection(0, 1, 0) == -1
