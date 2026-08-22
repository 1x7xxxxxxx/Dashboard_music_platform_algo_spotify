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
}
