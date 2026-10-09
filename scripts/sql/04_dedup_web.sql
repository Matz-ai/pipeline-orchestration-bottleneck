-- Web : dédoublonnage sur sku (714 lignes attendues).
-- Chaque produit apparaît deux fois (post_type 'product' et 'attachment' pour l'image).
-- On garde la ligne 'product' : pour 3 sku, total_sales diffère entre les deux.
CREATE OR REPLACE TABLE web_dedup AS
SELECT *
FROM web_nettoye
QUALIFY row_number() OVER (
    PARTITION BY sku
    ORDER BY (post_type = 'product') DESC, post_modified DESC
) = 1;
