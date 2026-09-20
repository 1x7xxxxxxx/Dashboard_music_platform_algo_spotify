"""La définition du MRR — une seule, composée depuis `tenant_kind`.

Type: Utility
Uses: src/utils/tenant_kind
Depends on: artist_subscriptions, subscription_plans, saas_artists
Persists in: nothing

Pourquoi ce module existe
-------------------------
Mesuré le 2026-09-18 : « MRR total » était calculé à **TROIS endroits**, avec **deux
réponses différentes** sous le même libellé.

    admin.py:544-546        WHERE a.status = 'active'                  SQL
    billing.py:322-331      WHERE asub.status = 'active'               SQL
    revenue_forecast.py     status ∈ {'active','trialing'} ET price>0  pandas

Dès qu'un abonnement est `trialing` — et `admin.py:524` parle explicitement d'« essai de
bienvenue » — la page Admin et la page Facturation affichaient deux nombres différents
sous le même mot, et « Artistes payants » aussi.

**La décision, prise le 2026-09-20 : un essai COMPTE dans le MRR.** Les deux réponses se
défendaient (prévisionnel contre encaissé) ; ce qui ne se défendait pas, c'est que deux
pages répondent différemment. Le prévisionnel est retenu parce que c'est la question que
les trois surfaces posent en pratique — « combien ce parc vaut-il par mois » — et parce
qu'un essai qui se convertit ne change alors aucun chiffre.

⚠️ **ET LES LOCATAIRES TECHNIQUES SONT EXCLUS**, ce qu'aucune des trois ne faisait —
alors que le compteur d'artistes juste au-dessus (`admin.py:536`) les excluait déjà. Deux
nombres de la MÊME page se contredisaient : « 10 artistes » et un MRR calculé sur les
canaris et le bac à sable.

⚠️ **Pourquoi du SQL composé en Python, et pas une vue.** Le prédicat « ce locataire n'est
pas réel » vit une seule fois, dans `src/utils/tenant_kind.py`, et
`tests/test_a_tenant_flag_is_applied_everywhere.py` le garde — mais ce garde balaie
`src/`, `airflow/` et `tools/`, **pas `migrations/`**. Une vue SQL qui recopierait
`COALESCE(is_canary, FALSE) OR …` échapperait donc au seul garde qui empêche ce prédicat
de diverger. Le composer ici le laisse sous surveillance.
"""
from __future__ import annotations

from src.utils.tenant_kind import human_tenants

#: Les statuts d'abonnement qui comptent dans le MRR. Un essai est du revenu PRÉVU :
#: il entre, et sa conversion ne change alors aucun chiffre.
MRR_STATUSES = ("active", "trialing")

#: Le libellé que les surfaces doivent afficher. Il dit ce que le nombre CONTIENT —
#: « MRR total » seul laissait croire à de l'encaissé.
MRR_LABEL = "MRR (abonnements actifs + essais)"


def mrr_by_plan_sql() -> str:
    """Le MRR par plan : une ligne par plan, avec son compte d'artistes.

    `price_monthly > 0` écarte le palier gratuit : il n'est pas du revenu, et le compter
    dans « artistes payants » en ferait un synonyme d'« artistes ».
    """
    return f"""
        SELECT sp.name              AS plan,
               sp.price_monthly     AS price_monthly,
               COUNT(*)             AS artists,
               SUM(sp.price_monthly) AS mrr
          FROM artist_subscriptions asub
          JOIN subscription_plans sp ON sp.id = asub.plan_id
          JOIN saas_artists        sa ON sa.id = asub.artist_id
         WHERE asub.status = ANY(%s)
           AND sp.price_monthly > 0
           AND {human_tenants("sa")}
         GROUP BY sp.name, sp.price_monthly
         ORDER BY sp.price_monthly DESC
    """


def mrr_params() -> tuple:
    """Les paramètres de `mrr_by_plan_sql()` — jamais interpolés (règle transverse #8)."""
    return (list(MRR_STATUSES),)
