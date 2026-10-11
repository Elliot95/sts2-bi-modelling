-- Grain: one row per card offered at a card-choice screen
-- (run / floor / player / offered card). was_picked drives pick-rate analysis.
select
    run_id,
    floor_number,
    player_id,
    card_id,
    was_picked,
    floor_added_to_deck
from {{ ref('stg_sts2__card_choices') }}
