-- Grain: one row per run / player / potion that player came across (offered,
-- used, discarded, bought or held at the end). The run-level roll-up powers:
--   * picked vs skipped win rate (both groups were offered it, like cards)
--   * use rate (used / obtained)
--   * held_at_end: for a lost run, the player died still holding it
with events as (
    select
        run_id, player_id, potion_id,
        countif(action = 'offered')                     as times_offered,
        countif(action = 'offered' and was_picked)      as times_picked,
        countif(action = 'used')                        as times_used,
        countif(action = 'discarded')                   as times_discarded,
        countif(action = 'bought')                      as times_bought,
        min(if(action = 'offered', floor_number, null)) as first_offered_floor
    from {{ ref('stg_sts2__potion_events') }}
    group by run_id, player_id, potion_id
),

held as (
    select run_id, player_id, potion_id, count(*) as held_at_end_count
    from {{ ref('stg_sts2__run_potions') }}
    group by run_id, player_id, potion_id
)

select
    coalesce(e.run_id, h.run_id)                        as run_id,
    coalesce(e.player_id, h.player_id)                  as player_id,
    coalesce(e.potion_id, h.potion_id)                  as potion_id,
    coalesce(e.times_offered, 0)                        as times_offered,
    coalesce(e.times_picked, 0)                         as times_picked,
    coalesce(e.times_offered, 0) > 0                    as was_offered,
    coalesce(e.times_picked, 0) > 0                     as was_picked,
    coalesce(e.times_used, 0)                           as times_used,
    coalesce(e.times_discarded, 0)                      as times_discarded,
    coalesce(e.times_bought, 0)                         as times_bought,
    e.first_offered_floor,
    coalesce(h.held_at_end_count, 0)                    as held_at_end_count,
    coalesce(h.held_at_end_count, 0) > 0                as held_at_end
from events e
full outer join held h
    on h.run_id = e.run_id and h.player_id = e.player_id and h.potion_id = e.potion_id
