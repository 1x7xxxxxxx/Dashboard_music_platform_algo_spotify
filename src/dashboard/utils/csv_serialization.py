"""Comment on décide de l'encodage et du séparateur d'un CSV déposé.

Type: Utility
Uses: csv (stdlib)
Triggers: importé par la vue d'import CSV
Persists in: nothing

Sorti de `views/upload_csv.py` le 2026-09-11. Le fichier était à son plafond de
longueur gelé, et le cliquet demande de faire sortir « un sujet entier » plutôt
que de raboter des lignes. Celui-ci en est un : quatre fonctions, deux
constantes, une seule question — avec quel encodage et quel séparateur lire ce
fichier. Il devient testable sans Streamlit ni base par la même occasion.
"""
from __future__ import annotations

_ENCODINGS = ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252')
_SEPARATORS = ('\t', ';', ',')


def _resolve_serialization(file) -> tuple[str, str, str]:
    """(encodage retenu, séparateur retenu, ligne d'en-tête). `('', ',', '')` si illisible.

    `utf-8-sig` AVANT `utf-8`, et c'est tout le défaut du 2026-09-06 : un fichier
    UTF-8 portant un BOM décode SANS ERREUR en `utf-8`, donc la boucle s'arrêtait au
    premier essai et le BOM survivait, collé au premier en-tête (`\ufeffdate`).
    `utf-8-sig` lit les deux cas à l'identique et retire le BOM quand il est là.

    Le séparateur est le plus fréquent de la LIGNE D'EN-TÊTE. Le point-virgule y
    figure parce que c'est ce que produit Excel en configuration française : un
    artiste qui ouvre puis réenregistre son export obtenait un fichier lu comme UNE
    colonne géante, donc « type non reconnu », sans que rien ne nomme la cause.
    """
    raw = file.read()
    file.seek(0)
    for enc in _ENCODINGS:
        try:
            first_line = raw.decode(enc).split('\n', 1)[0]
            break
        except (UnicodeDecodeError, ValueError):
            continue
    else:
        return '', ',', ''
    counts = {sep: first_line.count(sep) for sep in _SEPARATORS}
    sep = max(counts, key=counts.get) if max(counts.values()) else ','
    return enc, sep, first_line


def _serialization_label(file) -> str:
    """« utf-8-sig | , » — ce qu'on a DEVINÉ, pour le journal.

    Sans cette trace, un refus reste indiagnosticable après coup : les colonnes vues
    disent ce qu'on a lu, jamais avec quel encodage ni quel séparateur on l'a lu.
    """
    # Un classeur Excel n'a ni encodage de texte ni séparateur : `latin-1` décode
    # n'importe quels octets sans jamais lever, donc la résolution rendrait
    # « latin-1 | , » sur un binaire — une trace fausse, pire qu'aucune trace.
    if getattr(file, 'name', '').lower().endswith(('.xlsx', '.xls')):
        return 'xlsx (binaire — ni encodage ni séparateur)'
    enc, sep, _ = _resolve_serialization(file)
    printable = {'\t': 'TAB', ';': ';', ',': ','}.get(sep, sep)
    return f"{enc or 'illisible'} | {printable}"


def _read_headers(file) -> list[str]:
    """Header row of an uploaded file — encoding fallback + delimiter sniffing.

    pd.read_csv(nrows=0) assumed utf-8 + comma, which broke on DistroKid
    exports (tab-delimited, latin-1). Works for every supported platform.
    """
    import csv as _csv
    _enc, sep, first_line = _resolve_serialization(file)
    if not first_line:
        return []
    return next(_csv.reader([first_line], delimiter=sep), [])


def _sniff_sep(file) -> str:
    """Le séparateur de la ligne d'en-tête — la MÊME résolution que `_read_headers`.

    `_parse_file` relisait le fichier avec `pd.read_csv(file)` nu, donc virgule et
    utf-8. Un fichier tabulé ou point-virgulé pouvait donc être DÉTECTÉ correctement
    puis exploser à la lecture, et le message rendu était l'exception brute de pandas.
    """
    return _resolve_serialization(file)[1]
