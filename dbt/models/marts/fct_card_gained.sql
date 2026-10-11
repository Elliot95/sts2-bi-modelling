-- Grain: one row per card added outside a choice screen (run / floor / player / card).
select
    run_id,
    floor_number,
    player_id,
    card_id
from {{ ref('stg_sts2__cards_gained') }}
