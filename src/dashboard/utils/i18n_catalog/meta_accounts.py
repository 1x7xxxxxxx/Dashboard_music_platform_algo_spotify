"""EN catalog for the shared Meta ad-account selector (R53 / ADR-013).

Type: Sub
Uses: nothing (pure data module)
Triggers: src/dashboard/utils/meta_accounts.py, rendered by the 5 Meta views
    and the PDF export form.

Ces deux clés vivent dans leur propre fichier plutôt que dans l'un des cinq
catalogues `meta_*.py` : le sélecteur est UN composant partagé, et le poser dans
le catalogue d'une vue le rendrait invisible depuis les quatre autres au moment
où quelqu'un cherche à le traduire.
"""

EN = {
    "meta.account_filter": "🏦 Ad account",
    "meta.account_all": "All accounts (combined)",
}
