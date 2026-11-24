"""Patrones simples definidos por el usuario para organizar archivos en Drive."""

from .placeholders import (
    PLACEHOLDERS,
    PLACEHOLDER_INFOS,
    PlaceholderInfo,
    UnknownPlaceholderError,
    normalize,
    fragment,
    tokenize,
)
from .suggestions import (
    PlaceholderQuery,
    apply_suggestion,
    find_placeholder_query,
    move_selection,
    suggest_placeholders,
)
from .compiler import (
    PatternSpec,
    CompiledPattern,
    CompileError,
    RenderError,
    compile_pattern,
    compile_patterns,
    render_folder_name,
)
from .matcher import (
    FileMatch,
    MatchReport,
    match_file,
    match_files,
)

__all__ = [
    "PLACEHOLDERS",
    "PLACEHOLDER_INFOS",
    "PlaceholderInfo",
    "UnknownPlaceholderError",
    "normalize",
    "fragment",
    "tokenize",
    "PlaceholderQuery",
    "apply_suggestion",
    "find_placeholder_query",
    "move_selection",
    "suggest_placeholders",
    "PatternSpec",
    "CompiledPattern",
    "CompileError",
    "RenderError",
    "compile_pattern",
    "compile_patterns",
    "render_folder_name",
    "FileMatch",
    "MatchReport",
    "match_file",
    "match_files",
]