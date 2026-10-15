# FastAPI REST backend — Brick 14

# R621 — the ONE version literal of the API. `pyproject.toml` repeats it (PEP 621 wants a
# literal there, and the API image never installs the project, so importlib.metadata
# would raise); tests/test_one_version.py holds the two equal. 0.1.x: no external
# consumer yet, so no stability contract is claimed — reopen trigger in the R621 archive.
__version__ = "0.1.0"
