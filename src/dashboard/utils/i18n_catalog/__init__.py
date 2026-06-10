"""EN translation catalogs — one module per view/domain, auto-merged by i18n.py.

Type: Sub
Uses: nothing (pure data modules)
Triggers: imported once by src.dashboard.utils.i18n._load_catalogs()

Each module exposes `EN: dict[str, str]` with keys namespaced `<view>.<slug>`.
FR source strings live inline at the call sites (`t(key, "FR …")`); only the EN
side lives here. Templates keep the same named {placeholders} as their FR source.
"""
