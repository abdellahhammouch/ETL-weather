WITH dernieres_previsions AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (
            PARTITION BY p.ville_id, p.date_prevision
            ORDER BY p.retrieved_at DESC
        ) AS rang
    FROM previsions p
)
SELECT
    v.city,
    MAX(dp.temperature_max) AS temperature_max_observee
FROM dernieres_previsions dp
JOIN villes v ON v.id = dp.ville_id
WHERE dp.rang = 1
GROUP BY v.city
ORDER BY temperature_max_observee DESC
LIMIT 10;



WITH dernieres_previsions AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (
            PARTITION BY p.ville_id, p.date_prevision
            ORDER BY p.retrieved_at DESC
        ) AS rang
    FROM previsions p
)
SELECT
    v.city,
    MAX(dp.precipitation_sum) AS precipitation_max_observee
FROM dernieres_previsions dp
JOIN villes v ON v.id = dp.ville_id
WHERE dp.rang = 1
GROUP BY v.city
ORDER BY precipitation_max_observee DESC
LIMIT 10;




WITH dernieres_previsions AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (
            PARTITION BY p.ville_id, p.date_prevision
            ORDER BY p.retrieved_at DESC
        ) AS rang
    FROM previsions p
)
SELECT
    v.city,
    ROUND(AVG(dp.risk_score), 1) AS risque_moyen
FROM dernieres_previsions dp
JOIN villes v ON v.id = dp.ville_id
WHERE dp.rang = 1
GROUP BY v.city
ORDER BY risque_moyen DESC
LIMIT 10;



WITH dernieres_previsions AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (
            PARTITION BY p.ville_id, p.date_prevision
            ORDER BY p.retrieved_at DESC
        ) AS rang
    FROM previsions p
)
SELECT
    dp.date_prevision,
    ROUND(AVG(dp.risk_score), 1) AS risque_moyen_ce_jour,
    MAX(dp.risk_score) AS risque_maximal_observe_ce_jour
FROM dernieres_previsions dp
WHERE dp.rang = 1
GROUP BY dp.date_prevision
ORDER BY risque_moyen_ce_jour DESC;




WITH dernieres_previsions AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (
            PARTITION BY p.ville_id, p.date_prevision
            ORDER BY p.retrieved_at DESC
        ) AS rang
    FROM previsions p
),
pire_jour_par_ville AS (
    SELECT
        dp.*,
        ROW_NUMBER() OVER (
            PARTITION BY dp.ville_id
            ORDER BY dp.risk_score DESC
        ) AS rang_risque
    FROM dernieres_previsions dp
    WHERE dp.rang = 1
)
SELECT
    v.city,
    pj.date_prevision AS periode_la_plus_a_risque,
    pj.risk_score,
    pj.risk_level
FROM pire_jour_par_ville pj
JOIN villes v ON v.id = pj.ville_id
WHERE pj.rang_risque = 1
ORDER BY pj.risk_score DESC;



WITH dernieres_previsions AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (
            PARTITION BY p.ville_id, p.date_prevision
            ORDER BY p.retrieved_at DESC
        ) AS rang
    FROM previsions p
)
SELECT
    v.city,
    ROUND(AVG(dp.risk_score), 1) AS risque_moyen_ville
FROM dernieres_previsions dp
JOIN villes v ON v.id = dp.ville_id
WHERE dp.rang = 1
GROUP BY v.city
HAVING AVG(dp.risk_score) > (
    SELECT AVG(dp2.risk_score)
    FROM dernieres_previsions dp2
    WHERE dp2.rang = 1
)
ORDER BY risque_moyen_ville DESC;