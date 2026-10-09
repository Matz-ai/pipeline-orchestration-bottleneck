-- Web : suppression des lignes sans sku, clé de jointure avec la liaison (1 428 lignes attendues).
-- 83 lignes vides + 2 lignes sans sku : 1 513 - 85 = 1 428.
CREATE OR REPLACE TABLE web_nettoye AS
SELECT *
FROM raw_web
WHERE sku IS NOT NULL;
