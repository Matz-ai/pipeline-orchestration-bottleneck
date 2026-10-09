-- CA par produit = prix x quantité vendue, puis CA total (70 568,60 € attendus).
-- Calcul en DECIMAL pour tomber juste au centime.
CREATE OR REPLACE TABLE ca_par_produit AS
SELECT
    product_id,
    sku,
    nom_produit,
    CAST(prix AS DECIMAL(10, 2))                                    AS prix,
    CAST(quantite_vendue AS INTEGER)                                AS quantite_vendue,
    CAST(prix AS DECIMAL(10, 2)) * CAST(quantite_vendue AS INTEGER) AS ca
FROM fusion
ORDER BY ca DESC, product_id;

CREATE OR REPLACE TABLE ca_total AS
SELECT
    SUM(ca)                              AS ca_total,
    COUNT(*)                             AS nb_produits,
    COUNT(*) FILTER (WHERE ca > 0)       AS nb_produits_vendus
FROM ca_par_produit;
