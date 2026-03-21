# ui/dashboard_theme.py
"""Thème visuel partagé pour le Dashboard."""

_BG_DEEP  = "#0f172a"
_BG_CARD  = "#1e293b"
_BG_HDR   = "#162032"
_BORDER   = "#334155"
_TXT1     = "#f1f5f9"
_TXT2     = "#94a3b8"
_TXT3     = "#64748b"
_GRID     = "#1e293b"

_C_NAVY   = "#3b82f6"
_C_GREEN  = "#22c55e"
_C_AMBER  = "#f59e0b"
_C_BLUE   = "#6366f1"

_USER_COLORS = [
    "#3b82f6", "#22c55e", "#f59e0b", "#ef4444",
    "#8b5cf6", "#06b6d4", "#ec4899", "#f97316",
]

DATE_EDIT_QSS = (
    "QDateEdit {"
    "  border: 1px solid #334155; border-radius: 4px;"
    "  background: #162032; color: #f1f5f9;"
    "  padding: 3px 6px; font-size: 11px;"
    "}"
    "QDateEdit:focus { border-color: #3b82f6; }"
    "QDateEdit::drop-down { border: none; width: 18px; }"
    "QDateEdit::calendar-popup { background: #1e293b; }"
)

BTN_QSS = (
    "QPushButton { background: #1e3a5f; color: #94a3b8; border: 1px solid #334155;"
    " border-radius: 4px; padding: 4px 12px; font-size: 11px; }"
    "QPushButton:hover { background: #2a4f80; color: #f1f5f9; }"
    "QPushButton:pressed { background: #16294a; }"
)


def truncate(text: str, max_len: int) -> str:
    """Tronque un texte à max_len caractères avec ellipse."""
    return text if len(text) <= max_len else text[: max_len - 1] + "\u2026"
