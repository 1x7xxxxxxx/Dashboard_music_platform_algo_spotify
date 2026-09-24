"""The two sign-in buttons' look — Google's own button, and the shared fixed width.

Type: Utility
Uses: nothing
Triggers: src/dashboard/auth.py (login frame)
Persists in: nothing
"""
from __future__ import annotations

#: The Google button looks like Google's OWN button, as on every other site: white
#: background, thin grey border, dark text, the four-colour "G" on the left
#: (Google Identity branding guidelines — light theme: fill #FFFFFF, stroke #747775,
#: text #1F1F1F). Asked on 2026-09-23 after a gradient version: « de couleur comme sur
#: les autres sites internet avec le logo google ». The light button is also the one
#: the guidelines allow on a dark page, so there is no theme variant to keep in sync.
#: `.st-key-<key>` is the class Streamlit puts on any element given a `key`.
_GOOGLE_BUTTON_KEY = "google_signin"
_LOGIN_BUTTON_KEY = "login_submit"
_BUTTON_WIDTH_PX = 260
_GOOGLE_G_LOGO = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'"
    "%3E%3Cpath fill='%23EA4335' d='M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 "
    "2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 2"
    "4 9.5z'/%3E%3Cpath fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v"
    "9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
    "'/%3E%3Cpath fill='%23FBBC05' d='M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3."
    "14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19"
    "z'/%3E%3Cpath fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2"
    ".15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14"
    ".62 48 24 48z'/%3E%3C/svg%3E"
)
_GOOGLE_BUTTON_CSS = f"""<style>
.st-key-{_GOOGLE_BUTTON_KEY} button {{
    background: #FFFFFF !important; color: #1F1F1F !important;
    border: 1px solid #747775 !important; border-radius: 4px !important;
    min-height: 3rem; font-weight: 500;
}}
.st-key-{_GOOGLE_BUTTON_KEY} button:hover {{
    background: #F8F9FA !important; box-shadow: 0 1px 3px rgba(60, 64, 67, .30);
}}
.st-key-{_GOOGLE_BUTTON_KEY} button p {{ color: #1F1F1F !important; font-weight: 500; }}
.st-key-{_GOOGLE_BUTTON_KEY} button p::before {{
    content: ""; display: inline-block; width: 18px; height: 18px;
    margin-right: 12px; vertical-align: -3px;
    background: url("{_GOOGLE_G_LOGO}") no-repeat center / contain;
}}
.st-key-{_LOGIN_BUTTON_KEY} button {{ min-height: 3rem; }}
</style>"""
