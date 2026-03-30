"""Central Meta Graph API configuration.

Single source of truth for the API version used across all Meta collectors,
DAGs, and dashboard views. Update META_API_VERSION here when Meta deprecates
the current version — no other file needs to change.

Meta deprecation schedule: ~2 years per version.
Next version check: v24.0 → deprecated ~April 2027.
"""
META_API_VERSION = "v24.0"
META_GRAPH_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"
