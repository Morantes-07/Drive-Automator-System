"""Punto de entrada de la aplicación.

Uso:
    python -m src.main          # interfaz gráfica (por defecto)
    python -m src.main --cli    # flujo de consola

Las importaciones pesadas se hacen dentro de cada rama para que el arranque de
la interfaz no cargue pandas ni el cliente de Drive antes de tiempo.
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Define los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Organizador de archivos de Google Drive.",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Ejecuta el flujo de consola en lugar de abrir la interfaz.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Abre la interfaz gráfica o ejecuta el flujo de consola."""
    args = build_parser().parse_args(argv)
    if args.cli:
        from src.cli import run_cli

        run_cli()
        return

    from src.ui.app import run_app

    run_app()


if __name__ == "__main__":
    main()