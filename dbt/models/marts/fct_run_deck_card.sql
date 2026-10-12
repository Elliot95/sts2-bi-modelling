-- Grain: one row per card copy in the final deck (run / player / card copy;
-- duplicates of the same card_id are legitimate).
select
    run_id,
    player_id,
    card_id,
    floor_added_to_deck
from {{ ref('stg_sts2__run_deck_cards') }}
