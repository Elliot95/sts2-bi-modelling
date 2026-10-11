-- Grain: one row per card. card_name is a readable label derived from the ID
-- (CARD.BATTLE_TRANCE -> Battle Trance). Real card metadata (rarity, cost,
-- character) is roadmap work: there is no external catalog to join yet.
select
    card_id,
    initcap(replace(regexp_replace(card_id, r'^CARD\.', ''), '_', ' ')) as card_name,
    first_seen_run_id,
    first_seen_date
from {{ ref('stg_sts2__cards') }}
