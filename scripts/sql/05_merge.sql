-- Fusion ERP / web via la table de liaison (714 lignes attendues).
CREATE OR REPLACE TABLE fusion AS
SELECT
    e.product_id,
    l.id_web            AS sku,
    w.post_title        AS nom_produit,
    w.post_name         AS slug,
    e.price             AS prix,
    w.total_sales       AS quantite_vendue,
    e.stock_quantity    AS stock,
    e.stock_status      AS statut_stock,
    e.onsale_web        AS en_vente_web
FROM erp_dedup      AS e
JOIN liaison_dedup  AS l ON l.product_id = e.product_id
JOIN web_dedup      AS w ON w.sku = l.id_web;
