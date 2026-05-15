"""Vue Credentials — package (split from the former 893-line credentials.py).

Layout (audit refactor-audit-dashboard.md #3, as-built):
- _core            : Fernet crypto + DB load/save + Airflow-state + constants
- _platform_*      : per-platform connection-test + setup-guide pair
- _registry        : PLATFORMS dict + CONNECTION_TESTS + guide dispatch
- _render          : Streamlit render/form helpers + _handle_save
- router           : the slim show() entry point

Public surface is unchanged: `from views.credentials import show`.
"""
from .router import show

__all__ = ["show"]
