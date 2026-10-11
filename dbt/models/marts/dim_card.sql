-- Grain: one row per card. card_name is a readable label derived from the ID
-- (CARD.BATTLE_TRANCE -> Battle Trance). Real card metadata (character,
-- rarity, cost) is roadmap work: there is no external catalog to join yet.
select
    card_id,
    {{ readable_id('card_id') }} as card_name,
    first_seen_run_id,
    first_seen_date
from {{ ref('stg_sts2__cards') }}
