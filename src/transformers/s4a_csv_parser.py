"""Parser S4A Intelligent (Supporte les CSV Timeline par fichier avec dates)."""
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging
import re  # Indispensable pour gérer les noms de fichiers changeants

logger = logging.getLogger(__name__)

_ARTIST_FILTER = '1x7xxxxxxx'


def _to_int(value, default: int = 0) -> int:
    """Convert a raw CSV value (may contain commas or spaces) to int."""
    try:
        return int(str(value).replace(',', '').replace(' ', '').split('.')[0])
    except Exception:
        return default


class S4ACSVParser:
    """Parse les CSV de Spotify for Artists."""

    def _extract_song_name_from_filename(self, filename: str) -> str:
        """
        Nettoie le nom du fichier pour extraire le titre.
        Transforme : "Mon Titre - Remix_20251129_180552.csv" -> "Mon Titre - Remix"
        """
        # 1. Enlève l'extension .csv
        name = Path(filename).stem

        # 2. REGEX : Supprime le pattern de date à la fin (_YYYYMMDD_HHMMSS)
        name = re.sub(r'_\d{8}_\d{6}$', '', name)

        # 3. Nettoyage des suffixes S4A classiques
        name = name.replace('-timeline', '').replace('_timeline', '')

        # 4. Nettoyage final
        return name.strip()

    def detect_csv_type(self, df: pd.DataFrame, filename: str = "") -> Optional[str]:
        """Détecte le type de CSV."""
        columns = set(df.columns.str.lower().str.strip())
        clean_name = self._extract_song_name_from_filename(filename)

        # Audience Globale
        if "audience" in clean_name.lower():
            return 'audience'

        # Timeline Chanson (Cas standard)
        if 'date' in columns:
            if any(col in columns for col in ['streams', 'ecoutes', 'écoutes']):
                return 'song_timeline_single'

        return None

    # ── Public parse methods (called from upload_csv.py) ─────────────────────

    def parse_timeline(self, df: pd.DataFrame, artist_id: int, filename: str = '') -> list:
        """Parse a per-song timeline CSV (headers: date, streams).

        The song name is extracted from the filename — required to identify the track.
        Returns an empty list if the filename is missing or unparseable.
        """
        df.columns = df.columns.str.strip().str.lower()
        song_name = self._extract_song_name_from_filename(filename) if filename else ''
        if not song_name:
            logger.warning("parse_timeline: filename missing — cannot determine song name")
            return []

        stream_col = next((c for c in df.columns if c in ['streams', 'ecoutes', 'écoutes']), None)
        if 'date' not in df.columns or not stream_col:
            return []

        data = []
        for _, row in df.iterrows():
            try:
                data.append({
                    'artist_id': artist_id,
                    'song': song_name,
                    'date': pd.to_datetime(row['date']).date(),
                    'streams': _to_int(row[stream_col]),
                })
            except Exception:
                continue
        return data

    def _detect_window(self, filename: str) -> str:
        """Return '28d' or '12m' from filename heuristic."""
        name = filename.lower()
        if any(t in name for t in ('28day', '28d', '28j')):
            return '28d'
        return '12m'

    def parse_songs_global(self, df: pd.DataFrame, artist_id: int, filename: str = '') -> list:
        """Parse a songs-all CSV (headers: song, listeners, streams, saves, release_date).

        Filters out the artist-level total row (1x7xxxxxxx).
        window is derived from the filename: '28d' if the name contains 28day/28d/28j, else '12m'.
        """
        df.columns = df.columns.str.strip().str.lower()
        window = self._detect_window(filename)

        data = []
        for _, row in df.iterrows():
            try:
                song = str(row.get('song', '')).strip()
                if not song or _ARTIST_FILTER.lower() in song.lower():
                    continue

                release_date = None
                try:
                    release_date = pd.to_datetime(row.get('release_date')).date()
                except Exception:
                    pass

                data.append({
                    'artist_id':    artist_id,
                    'song':         song,
                    'time_window':       window,
                    'listeners':    _to_int(row.get('listeners', 0)),
                    'streams':      _to_int(row.get('streams', 0)),
                    'saves':        _to_int(row.get('saves', 0)),
                    'release_date': release_date,
                })
            except Exception:
                continue
        return data

    def parse_audience(self, df: pd.DataFrame, artist_id: int) -> list:
        """Parse an audience-timeline CSV.

        Columns mapped to s4a_audience: date, listeners, streams, followers,
        playlist_adds (← 'playlist adds'), saves.
        """
        df.columns = df.columns.str.strip().str.lower()

        data = []
        for _, row in df.iterrows():
            try:
                data.append({
                    'artist_id':    artist_id,
                    'date':         pd.to_datetime(row['date']).date(),
                    'listeners':    _to_int(row.get('listeners', 0)),
                    'streams':      _to_int(row.get('streams', 0)),
                    'followers':    _to_int(row.get('followers', 0)),
                    'playlist_adds': _to_int(row.get('playlist adds', 0)),
                    'saves':        _to_int(row.get('saves', 0)),
                })
            except Exception:
                continue
        return data

    # ── Legacy method used by the Airflow DAG watcher ────────────────────────

    def parse_csv_file(self, file_path: Path) -> Dict:
        """Parse un fichier CSV."""
        try:
            # Lecture robuste (Header variable)
            try:
                df = pd.read_csv(file_path)
                if 'date' not in df.columns.str.lower() and len(df) > 0:
                     df = pd.read_csv(file_path, header=1)
            except:
                return {'type': None, 'data': []}

            df.columns = df.columns.str.strip().str.lower()

            # Identification
            csv_type = self.detect_csv_type(df, file_path.name)
            clean_song_name = self._extract_song_name_from_filename(file_path.name)

            data = []

            # Traitement Timeline Chanson
            if csv_type == 'song_timeline_single':
                # Trouver la colonne streams
                stream_col = next((c for c in df.columns if c in ['streams', 'ecoutes', 'écoutes']), None)

                if stream_col:
                    for _, row in df.iterrows():
                        try:
                            data.append({
                                'song': clean_song_name,
                                'date': pd.to_datetime(row['date']).date(),
                                'streams': _to_int(row[stream_col]),
                            })
                        except:
                            continue

                csv_type = 'song_timeline'

            return {
                'type': csv_type,
                'data': data,
                'source_file': file_path.name
            }

        except Exception as e:
            logger.error(f"❌ Erreur parsing {file_path.name}: {e}")
            return {'type': None, 'data': []}
