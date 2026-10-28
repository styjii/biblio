"""Extensions de fichiers connues et types MIME complémentaires."""

WEB_EXT = {".html", ".htm", ".xhtml", ".svg"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".avif"}
VIDEO_EXT = {".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi", ".ogv"}
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".opus", ".aac"}

BINARY_EXT = {
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".iso", ".exe", ".dll",
    ".so", ".bin", ".o", ".pyc", ".class", ".jar", ".apk", ".deb", ".sqlite", ".sqlite3",
    ".db", ".xlsx", ".xls", ".docx", ".doc", ".pptx", ".odt", ".ods", ".ttf", ".otf",
    ".woff", ".woff2",
}

TEXT_EXT = {
    ".txt", ".srt", ".vtt", ".csv", ".tsv", ".log", ".ini", ".cfg", ".conf", ".env", ".lock",
    ".gitignore", ".rst", ".tex", ".bib", ".diff", ".patch", ".properties", ".service",
}

CODE_EXT = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".c", ".h", ".cpp", ".hpp",
    ".cc", ".rs", ".go", ".php", ".rb", ".sh", ".bash", ".zsh", ".sql", ".css", ".scss",
    ".json", ".yml", ".yaml", ".toml", ".xml", ".lua", ".md", ".ipynb",
}

MD_EXT = {".md", ".markdown", ".mdown", ".mkd"}   # fichiers Markdown : aperçu rendu (/preview)
CODE_EXT |= MD_EXT

EXTRA_MIME = {
    ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
    ".html": "text/html", ".htm": "text/html", ".svg": "image/svg+xml",
    ".json": "application/json", ".webp": "image/webp", ".avif": "image/avif",
    ".mkv": "video/x-matroska", ".m4a": "audio/mp4", ".woff2": "font/woff2",
    ".mjs": "text/javascript", ".wasm": "application/wasm", ".ftl": "text/plain", ".map": "application/json",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".opus": "audio/ogg",
    ".flac": "audio/flac", ".aac": "audio/aac",
}
