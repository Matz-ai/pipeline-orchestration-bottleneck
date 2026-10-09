-- ERP : suppression des doublons exacts et des lignes sans product_id (825 lignes attendues).
-- Deux lignes de même product_id mais de contenu différent ne sont pas arbitrées ici :
-- le test d'unicité les fera remonter.
CREATE OR REPLACE TABLE erp_dedup AS
SELECT DISTINCT
    product_id,
    onsale_web,
    price,
    stock_quantity,
    stock_status
FROM raw_erp
WHERE product_id IS NOT NULL;
