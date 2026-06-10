"""Minimal stub of the facebook_business SDK surface used by MetaAdsApiCollector.

Type: Sub (test fake)
Uses: nothing (pure in-memory)
Depends on: matches the SDK methods MetaAdsApiCollector actually calls.

SDK surface covered (only what the collector touches)
-----------------------------------------------------
AdAccount-level edge calls (all accept ``fields=`` / ``params=`` kwargs, all
return an *iterable* of dict-like nodes — the collector wraps each in
``list(...)`` via ``_meta_list``):

  * ``get_campaigns(fields=, params=)``  → campaign nodes
        node keys read: id, name, status, objective, daily_budget,
        lifetime_budget, start_time, stop_time, created_time, updated_time
  * ``get_ad_sets(fields=, params=)``    → adset nodes
        keys: id, name, campaign_id, status, optimization_goal, billing_event,
        daily_budget, lifetime_budget, start_time, end_time, targeting
        (``targeting`` is a plain dict; the collector calls ``.get(...)`` on it
        and checks ``hasattr(tgt, 'export_all_data')`` — a plain dict has none,
        so it is used directly.)
  * ``get_ads(fields=, params=)``        → ad nodes
        keys: id, name, adset_id, campaign_id, status, creative, created_time,
        updated_time  (``creative`` is a dict-like with an ``id`` key)
  * ``get_insights(fields=, params=)``   → insight nodes, ROUTED by
        ``params['level']`` ('campaign' | 'ad' | 'adset') and
        ``params['breakdowns']``. Each call is recorded in ``.insight_calls``
        and the returned rows are filtered by ``params['time_range']`` against
        each node's ``date_start`` (mirrors the API's own date filtering, which
        the collector relies on for monthly chunking / smart-incremental).

Per-creative content fetch (``AdCreative(cid).api_get(fields=)``) is NOT modeled
here — it is a *module-level* import inside ``_fetch_creatives``; tests that need
it monkeypatch ``facebook_business.adobjects.adcreative.AdCreative``. See
``tests/test_meta_ads_run.py::_patch_creatives``.

Insight nodes are dict-like (``node['k']``, ``node.get('k')``). ``FakeNode``
subclasses ``dict`` so both styles and the SDK's attribute reads work.
"""
from __future__ import annotations


class FakeNode(dict):
    """A facebook_business object stand-in: dict-like with attribute access.

    The real SDK objects support ``obj['key']``, ``obj.get('key')`` and the
    ``export_all_data()`` method on nested targeting. A plain dict already covers
    the first two; the collector only calls ``export_all_data`` when it is
    present (``hasattr`` guard), so we deliberately do NOT add it for the common
    case (targeting passed as a plain dict goes through the ``else`` branch).
    """

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(name) from exc


def _breakdown_key(params: dict):
    """Normalise the routing key for an insights call: (level, breakdown-tuple)."""
    level = params.get('level')
    bd = params.get('breakdowns')
    if bd is None:
        return (level, None)
    return (level, tuple(bd))


def _in_range(node, time_range):
    """True if the node's date_start falls inside [since, until] (inclusive).

    Mirrors the real Graph API, which filters insights server-side by
    time_range. The collector trusts this filtering for its monthly chunking
    and smart-incremental window — so the fake must honour it. A node with no
    date_start (aggregate breakdown rows) is always kept.
    """
    if not time_range:
        return True
    ds = node.get('date_start')
    if not ds:
        return True
    return time_range['since'] <= ds <= time_range['until']


class FakeAdAccount:
    """In-memory AdAccount. Returns preloaded dict-like nodes; records calls.

    Parameters
    ----------
    campaigns, adsets, ads : list[dict]
        Returned verbatim (wrapped in FakeNode) by the matching edge method.
    insights : dict | None
        Routing table ``{(level, breakdown_tuple): [insight dicts]}``. Keys:
          ('campaign', None)                                  -> daily/global campaign rows
          ('campaign', ('age',))                              -> age breakdown
          ('campaign', ('country',))                          -> country breakdown
          ('campaign', ('publisher_platform','platform_position')) -> placement
          ('ad', None)                                        -> ad-level daily rows
          ('ad'|'adset', ('country',) | ('age',) | (...placement)) -> entity breakdowns
        Missing keys yield an empty result (a real account with no such data).
    """

    def __init__(self, campaigns=None, adsets=None, ads=None, insights=None):
        self._campaigns = [FakeNode(c) for c in (campaigns or [])]
        self._adsets = [FakeNode(a) for a in (adsets or [])]
        self._ads = [FakeNode(a) for a in (ads or [])]
        self._insights = {k: [FakeNode(r) for r in v]
                          for k, v in (insights or {}).items()}
        # Recorded calls — assertion surface for the characterization tests.
        self.calls = []           # [(method_name, fields, params)]
        self.insight_calls = []   # [params] for every get_insights call

    # ── edge methods (names match the real SDK) ───────────────────────────────

    def get_campaigns(self, fields=None, params=None):
        self.calls.append(('get_campaigns', fields, params))
        return list(self._campaigns)

    def get_ad_sets(self, fields=None, params=None):
        self.calls.append(('get_ad_sets', fields, params))
        return list(self._adsets)

    def get_ads(self, fields=None, params=None):
        self.calls.append(('get_ads', fields, params))
        return list(self._ads)

    def get_insights(self, fields=None, params=None):
        params = params or {}
        self.calls.append(('get_insights', fields, params))
        self.insight_calls.append(params)
        rows = self._insights.get(_breakdown_key(params), [])
        tr = params.get('time_range')
        return [r for r in rows if _in_range(r, tr)]
