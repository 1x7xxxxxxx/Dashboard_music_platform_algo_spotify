"""EN catalog for the setup status matrix (src/dashboard/utils/status_matrix.py).

One renderer, four surfaces (credentials, onboarding, home, 🚦 Santé onboarding), so
one namespace. FR is the inline default at each call site; only EN lives here.
"""

EN = {
    # Column headers — three boxes: identity entered, platform answered, rows landed.
    "matrix.col_platform": "**Platform**",
    "matrix.col_set": "**Set up**",
    "matrix.col_responds": "**Responds**",
    "matrix.col_data": "**Data**",
    "matrix.col_action": "**Next step**",

    # Tooltips. Each says what the box MEANS, not what colour it is.
    "matrix.tip_set": "Identifier entered.",
    "matrix.tip_unset": "No identifier entered.",
    "matrix.tip_not_set": "Nothing to check until the identifier is entered.",
    "matrix.tip_data_proves":
        "Data is arriving — the connection works, no check needed.",
    "matrix.tip_never_probed":
        "Never checked. Press “Check now” to ask the platform.",
    "matrix.tip_ok_no_data":
        "The platform answers ({age}) but no data has arrived yet — the first "
        "collection may not have run.",

    # The button. Nothing is called until it is pressed; that is the whole design.
    "matrix.check_now": "🔌 Check now",
    "matrix.check_help":
        "Asks each configured platform and remembers its answer. Nothing is called "
        "until you click.",
    "matrix.checking": "Checking…",
    "matrix.checked": "{n} platform(s) checked",

    # Age of a remembered verdict.
    "matrix.age_now": "just now",
    "matrix.age_hours": "{n} h ago",
    "matrix.age_days": "{n} d ago",
    "matrix.tip_data_proved_then_stopped": "The connection worked — data did arrive, but not recently. Nothing to reconfigure: see the « Data » column.",
    "matrix.tip_connected_nothing_to_send": "The connection works; this source simply has nothing to send right now. This is not a failure.",

    # ── Colonne « Format » + légende intégrée (2026-09-04) ──
    "matrix.col_shape": "**Shape**",
    "matrix.legend_inline": (
        "**Entered**: you typed an identifier · **Shape**: it looks the way the "
        "platform expects · **Responds**: the platform answered when we asked · "
        "**Data**: rows actually reached us. Four ✅ per line is the goal."
    ),
    "matrix.help_set": "An identifier is stored for this platform.",
    "matrix.help_shape": (
        "This identifier has the shape the platform expects. It can be well-formed "
        "and still wrong — « Responds » is what settles that."
    ),
    "matrix.help_responds": (
        "The platform answered correctly the last time we asked. Fresh data counts "
        "as an answer: nothing is called in that case."
    ),
    "matrix.help_data": (
        "Rows reached our database for you. It is the only proof that matters for "
        "your charts."
    ),
    "matrix.tip_shape_na": "Nothing to check until an identifier is entered.",
    "matrix.tip_shape_unknown": "Shape cannot be checked for this platform.",
    "matrix.tip_shape_ok": (
        "The identifier has the expected shape. That does not prove it is the right "
        "one — the « Responds » column says that."
    ),
    "matrix.tip_shape_bad": (
        "This identifier does not have the expected shape: it was probably pasted "
        "with text around it. Enter it again."
    ),
}
