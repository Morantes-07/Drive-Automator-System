# AGENTS.md

## Commands

- Install deps: 'venv/Scripts/pip install -r requirements.txt'
- Run: venv/Scripts/python -m src.main" (from the repo root)
- Test: 'venv/Scripts/python -m pytest"

## Rules
**Always**
- Run as a module (`-m src.main`), because the `src.*` imports depend on the package layout.
- Read and edit `requirements.txt` as UTF-16LE.
- Write comments and docstrings in Spanish.
- Write variables, classes, functions, etc., in English
- Ask before change code in build mode, unless the developer says you can change code without asking

**Never**
- Run `python src/main.py`.
- Commit, print, or log `credentials.json` or `token.json`.
- Commit without asking for confirmation
- Remove `owners` or `parents` from `FIELDS` in `drive_client.py` (it breaks `build_df`).

## Architecture
- `find_root_project()` locates the repo root regardless of the cwd.
- The codebase strictly adheres to a modular design principle; complex functionalities and distinct responsibilities must be split into small, reusable modules within src/.
- Test codes go inside tests folder (same level at src folder)

## Environment and authentication
- Venv in `venv/` (Python 3.14.7).
- If you change `SCOPES` in `config.py`, delete `token.json` to force re-consent.
- Auth uses Chrome (incognito) at a hard-coded Windows path; it fails if Chrome isn't there.

## Not yet wired up
- `QUERY_SHARED`, `list_folders`, `get_root_id`, `processing.py`, and `gspread`.