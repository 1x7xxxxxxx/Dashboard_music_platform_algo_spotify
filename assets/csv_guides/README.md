# CSV onboarding-guide screenshots

These PNGs illustrate the download steps shown in the Import-CSV view and the
static onboarding PDF. They are referenced **by filename only** from
`src/dashboard/content/csv_guides.py` (field `GuideStep.screenshot`) and resolved
here via `screenshot_path()`.

## Contract
- Files may live **flat here or in a platform subfolder** (`s4a/`, `apple_music/`,
  `imusician/`). `screenshot_path()` resolves by filename anywhere under this dir.
- **Drop a PNG in with the exact name below → it appears automatically** in both
  the Streamlit view (`st.image`) and the PDF (base64-embedded). No code change.
- **Missing file = graceful**: the Streamlit step shows its text only; the PDF
  shows a `[capture à venir : <file>]` placeholder. Nothing breaks.
- Recommended width ~1200px, PNG, cropped to the relevant UI area.
- Naming convention: `{platform_key}_step{N}_{slug}.png`.

## Expected filenames

| File | Step it illustrates | Status |
|---|---|---|
| `s4a_music_pannel.png` | Sidebar → Musique tab | ✅ provided |
| `s4a_music_titre_pannel.png` | Musique → Titres sub-tab | ✅ provided |
| `s4a_music_titre_12monthFilter.png` | Période filter → 12 mois | ✅ provided |
| `s4a_music_titre_filter12month_DOWNLOAD_csv.png` | Download résumé (songs-1year) | ✅ provided |
| `s4a_music_select1Track.png` | Titres list → open one track | ✅ provided |
| `s4a_music_titreselect_12month_Download.png` | Track page → 12 mois → download timeline | ✅ provided |
| `s4a_public.png` | Sidebar → Public tab | ✅ provided |
| `s4a_public_12monthfilter_download.png` | Public → Vue d'ensemble → download audience | ✅ provided |
| `apple_music/apple_music_aperçu_filtre_depuisledébut.png` | Aperçu → période → Depuis le début | ✅ provided |
| `apple_music/apple_music_ongletmusique.png` | Onglet Musique | ✅ provided |
| `apple_music/apple_music_tout_afficher_button.png` | Morceaux → Tout afficher | ✅ provided |
| `apple_music/apple_music_tout_télécharger.png` | Télécharger le CSV | ✅ provided |
| `imusician/imusician_dl_rapport.png` | Revenus → Rapports → Télécharger le rapport | ✅ provided |
| `imusician/imusician_annuel_résumé_par_sortie.png` | An → année → Résumé par sortie → Demander | ✅ provided |
| `imusician/imusician_annuel_rapportdevente.png` | An → année → Rapport de ventes → Demander | ✅ provided |
| `imusician/imusician_compte_téléchargements_download.png` | Compte → Téléchargements → tout télécharger | ✅ provided |

To add or rename a step's screenshot, edit `GuideStep(..., screenshot="…")` in
`src/dashboard/content/csv_guides.py` and drop the matching PNG here.
