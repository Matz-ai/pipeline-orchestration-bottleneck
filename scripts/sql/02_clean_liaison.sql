-- Liaison : suppression des doublons exacts (825 lignes attendues).
-- Les 91 produits sans id_web sont gardés : ils sortent à la fusion.
CREATE OR REPLACE TABLE liaison_dedup AS
SELECT DISTINCT
    product_id,
    id_web
FROM raw_liaison
WHERE product_id IS NOT NULL;
