# AGENTS.md

## Commands

- Venv is `venv/` (Python 3.14.7, gitignored). Use `venv/Scripts/python.exe`; install with `venv/Scripts/pip install -r requirements.txt`.
- Run: `venv/Scripts/python -m src.main` from the repo root. Absolute `src.*` imports and `find_root_project()` depend on the package layout, so don't run `python src/main.py`. The VS Code debug config (`.vscode/launch.json`) also launches module `src.main`.
- `requirements.txt` is UTF-16LE with CRLF (Windows `pip freeze >` behavior). `pip` reads it fine; read/edit it as UTF-16 so editors don't corrupt it.
- No tests (`src/tests/` is an empty package), no linter/typecheck/CI. Verification means running `src.main`, which hits the real Drive API and writes an `.xlsx`.

## Architecture

- Flow: `src/main.py` → `src/auth.py` (`get_credentials`) → `src/drive_client.py` (`get_service` + `list_files`, paginating on `nextPageToken`) → `src/utils.py` (`build_df`) → `df.to_excel(BASE_DIR/"output"/"reporte_ejemplo.xlsx")`. Output path/filename is hard-coded in `main.py`; `output/` is a tracked package (`__init__.py`) but `*.xlsx` is gitignored.
- `main.py` only exports files matching `QUERY_OWNED`; `QUERY_SHARED` is defined but unused.
- `src/drive_client.py` `FIELDS` is coupled to `build_df`: it derives `owner` (first element of `owners`) and `parent_id` (first of `parents`) from those fields, so removing them breaks `build_df`.
- `list_folders`, `get_root_id`, and `src/processing.py` (`build_children` → `build_tree` → `flatten`, maps full folder paths to IDs, raises on missing/duplicate folder names) are implemented but not wired into `main.py`.
- `src/utils.py` `find_root_project()` locates the repo root by walking up from the module file for `.git`/`requirements.txt`/`.gitignore`, so it is independent of cwd.
- `src/config.py` holds `SCOPES` (Drive + Sheets); `gspread` is installed for a future Sheets export but unused.

## Auth / environment gotchas

- `credentials.json` (OAuth client secret) and `token.json` (cached user token, rewritten by `auth.py` on every run) are gitignored. Never commit, print, or log their contents.
- Auth uses a hard-coded Chrome path (`C:\Program Files\Google\Chrome\Application\chrome.exe`) opened incognito; a re-consent flow fails on machines without Chrome there. Deleting `token.json` forces re-consent; adding/removing a scope in `config.py` also requires deleting it, since the cached token won't cover new scopes.
- Comment and docstring style is Spanish — match it when editing.
