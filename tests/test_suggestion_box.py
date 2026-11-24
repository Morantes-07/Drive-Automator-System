"""Pruebas del desplegable de sugerencias de placeholders."""

import pytest

from src.patterns.placeholders import PLACEHOLDER_INFOS
from src.ui.suggestion_box import PlaceholderSuggestionBox
from src.ui.theme import Theme


@pytest.fixture
def box(tk_root):
    widget = PlaceholderSuggestionBox(tk_root, theme=Theme())
    yield widget
    widget.destroy()


def test_show_muestra_las_sugerencias(box):
    box.show(list(PLACEHOLDER_INFOS))
    assert box.is_visible
    assert [item.key for item in box.items] == [
        "numero",
        "letra",
        "palabra",
    ]


def test_show_vacio_oculta(box):
    box.show([])
    assert not box.is_visible
    assert box.items == ()


def test_hide_limpia_el_estado(box):
    box.show(list(PLACEHOLDER_INFOS))
    box.hide()
    assert not box.is_visible
    assert box.items == ()
    assert box.selected_index == 0


def test_move_selection_respeta_los_limites(box):
    box.show(list(PLACEHOLDER_INFOS))
    assert box.selected_index == 0

    box.move_selection(1)
    assert box.selected_index == 1

    box.move_selection(10)
    assert box.selected_index == 2

    box.move_selection(-10)
    assert box.selected_index == 0


def test_move_selection_sin_lista_no_hace_nada(box):
    box.move_selection(1)
    assert box.selected_index == 0


def test_accept_entrega_la_fila_resaltada(tk_root):
    picked = []
    box = PlaceholderSuggestionBox(
        tk_root,
        theme=Theme(),
        on_pick=picked.append,
    )
    try:
        box.show([PLACEHOLDER_INFOS[1]])
        box.accept()
        assert picked == [PLACEHOLDER_INFOS[1]]
        assert not box.is_visible
    finally:
        box.destroy()


def test_accept_sin_sugerencias_no_avisa(box):
    picked = []
    box._on_pick = picked.append
    box.accept()
    assert picked == []


def test_hover_cambia_la_fila_resaltada(box):
    box.show(list(PLACEHOLDER_INFOS))
    box._hover(PLACEHOLDER_INFOS[2])
    assert box.selected_index == 2


def test_pick_avisa_y_oculta(tk_root):
    picked = []
    box = PlaceholderSuggestionBox(
        tk_root,
        theme=Theme(),
        on_pick=picked.append,
    )
    try:
        box.show(list(PLACEHOLDER_INFOS))
        box._pick(PLACEHOLDER_INFOS[1])
        assert picked == [PLACEHOLDER_INFOS[1]]
        assert not box.is_visible
    finally:
        box.destroy()
