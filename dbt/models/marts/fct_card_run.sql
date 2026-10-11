-- Grain: one row per run / player / card that was OFFERED to that player at a
-- card-choice screen. Rolls fct_card_choice (one row per individual offer) up
-- to the run level, because "do I win more when I take this card?" is a
-- run-level question: compare runs where the card was offered and picked
-- against runs where it was offered and skipped. Both groups reached the
-- offer, which removes most of the survivorship bias of comparing picked
-- runs against the overall win rate.

with offers as (
    select * from {{ ref('fct_card_choice') }}
),

floors as (
    select run_id, player_id, floor_number, act_index
    from {{ ref('fct_floor_state') }}
),

final_deck as (
    select run_id, player_id, card_id, count(*) as final_deck_copies
    from {{ ref('fct_run_deck_card') }}
    group by run_id, player_id, card_id
),

rolled as (
    select
        o.run_id,
        o.player_id,
        o.card_id,
        count(*)                                        as times_offered,
        countif(o.was_picked)                           as times_picked,
        logical_or(o.was_picked)                        as was_picked,
        min(o.floor_number)                             as first_offered_floor,
        min(if(o.was_picked, o.floor_number, null))     as first_picked_floor
    from offers o
    group by o.run_id, o.player_id, o.card_id
)

select
    r.run_id,
    r.player_id,
    r.card_id,
    r.times_offered,
    r.times_picked,
    r.was_picked,
    r.first_offered_floor,
    f.act_index + 1                                     as first_offered_act,
    r.first_picked_floor,
    coalesce(d.final_deck_copies, 0) > 0                as in_final_deck,
    coalesce(d.final_deck_copies, 0)                    as final_deck_copies
from rolled r
left join floors f
    on  f.run_id = r.run_id
    and f.player_id = r.player_id
    and f.floor_number = r.first_offered_floor
left join final_deck d
    on  d.run_id = r.run_id
    and d.player_id = r.player_id
    and d.card_id = r.card_id
