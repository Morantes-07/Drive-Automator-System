"""Pruebas de la integración de sugerencias en la pestaña de programas."""

from unittest.mock import Mock

import pytest

from src.patterns.placeholders import PLACEHOLDER_INFOS
from src.programs import ProgramDefinition
from src.ui.programs_tab import ProgramsTab


@pytest.fixture
def tab(tk_root):
    widget = ProgramsTab(tk_root)
    widget.pack(fill="both", expand=True)
    tk_root.update_idletasks()
    yield widget
    widget.destroy()


def _write_pattern(tab: ProgramsTab, text: str) -> None:
    entry = tab._pattern_entry
    entry.delete(0, "end")
    entry.insert(0, text)
    entry.icursor(len(text))


def _keys(tab: ProgramsTab) -> list[str]:
    return [item.key for item in tab._suggestions.items]


def test_escribir_llave_muestra_todo_el_catalogo(tab):
    _write_pattern(tab, "G{")
    tab._update_suggestions()
    assert tab._suggestions.is_visible
    assert _keys(tab) == ["numero", "letra", "palabra"]


def test_filtra_mientras_se_escribe(tab):
    _write_pattern(tab, "G{nu")
    tab._update_suggestions()
    assert _keys(tab) == ["numero"]


def test_cerrar_la_llave_oculta(tab):
    _write_pattern(tab, "G{número}")
    tab._update_suggestions()
    assert not tab._suggestions.is_visible


def test_insertar_completa_el_patron_y_el_cursor(tab):
    _write_pattern(tab, "G{nu")
    tab._update_suggestions()
    tab._insert_suggestion(PLACEHOLDER_INFOS[0])
    assert tab._pattern_entry.get() == "G{número}"
    assert tab._pattern_entry.index("insert") == 9
    assert not tab._suggestions.is_visible


def test_insertar_usa_el_texto_capturado_aunque_el_campo_se_vacie(tab):
    _write_pattern(tab, "G{nu")
    tab._update_suggestions()
    tab._pattern_entry.delete(0, "end")
    tab._insert_suggestion(PLACEHOLDER_INFOS[0])
    assert tab._pattern_entry.get() == "G{número}"


def test_tab_acepta_la_sugerencia(tab):
    _write_pattern(tab, "G{")
    tab._update_suggestions()
    assert tab._on_pattern_tab(None) == "break"
    assert tab._pattern_entry.get() == "G{número}"
    assert not tab._suggestions.is_visible


def test_tab_sin_sugerencias_no_intercepta(tab):
    _write_pattern(tab, "G3")
    tab._update_suggestions()
    assert tab._on_pattern_tab(None) is None


def test_return_acepta_si_hay_sugerencias(tab):
    _write_pattern(tab, "G{")
    tab._update_suggestions()
    tab._submit = Mock()
    assert tab._on_pattern_return(None) == "break"
    tab._submit.assert_not_called()
    assert tab._pattern_entry.get() == "G{número}"


def test_return_envia_si_no_hay_sugerencias(tab):
    _write_pattern(tab, "G3")
    tab._update_suggestions()
    tab._submit = Mock()
    assert tab._on_pattern_return(None) == "break"
    tab._submit.assert_called_once_with()


def test_escape_oculta_la_lista(tab):
    _write_pattern(tab, "G{")
    tab._update_suggestions()
    assert tab._on_pattern_escape(None) == "break"
    assert not tab._suggestions.is_visible


def test_flechas_mueven_la_seleccion(tab):
    _write_pattern(tab, "G{")
    tab._update_suggestions()
    assert tab._on_pattern_down(None) == "break"
    assert tab._suggestions.selected_index == 1
    assert tab._on_pattern_up(None) == "break"
    assert tab._suggestions.selected_index == 0


def test_flechas_sin_sugerencias_no_interceptan(tab):
    _write_pattern(tab, "G3")
    tab._update_suggestions()
    assert tab._on_pattern_down(None) is None
    assert tab._on_pattern_up(None) is None


def test_key_release_ignora_teclas_de_navegacion(tab):
    tab._update_suggestions = Mock()
    tab._on_pattern_key_release(Mock(keysym="Down"))
    tab._update_suggestions.assert_not_called()

    tab._on_pattern_key_release(Mock(keysym="n"))
    tab._update_suggestions.assert_called_once_with()


def test_click_actualiza_las_sugerencias(tab):
    _write_pattern(tab, "G{")
    tab._on_pattern_click(None)
    tab.update_idletasks()
    assert tab._suggestions.is_visible


def test_configure_reposiciona_sin_ocultar(tab):
    _write_pattern(tab, "G{")
    tab._update_suggestions()
    tab._on_pattern_configure(None)
    assert tab._suggestions.is_visible


def test_focus_out_oculta_la_lista(tab):
    _write_pattern(tab, "G{")
    tab._update_suggestions()
    tab._on_pattern_focus_out(None)
    tab._hide_suggestions_if_unfocused()
    assert not tab._suggestions.is_visible


def test_focus_out_no_oculta_si_el_foco_sigue_en_el_campo(tab):
    _write_pattern(tab, "G{")
    tab._update_suggestions()
    tab.focus_get = lambda: tab._pattern_entry._entry
    tab._hide_suggestions_if_unfocused()
    assert tab._suggestions.is_visible


def test_limpiar_el_formulario_oculta_la_lista(tab):
    _write_pattern(tab, "G{")
    tab._update_suggestions()
    tab._clear_form()
    assert not tab._suggestions.is_visible


def test_seleccionar_programa_oculta_la_lista(tab):
    tab.store.add(
        ProgramDefinition(
            program="Power BI",
            pattern="G{número}-Power BI",
            destination_path="Mi Drive/Power BI",
        )
    )
    tab._refresh_table()
    _write_pattern(tab, "G{")
    tab._update_suggestions()

    tab.tree.selection_set("0")
    tab._on_row_selected(None)

    assert not tab._suggestions.is_visible
    assert tab._pattern_entry.get() == "G{número}-Power BI"
