-- Grain: one row per fight per player (run / player / floor / room_index).
-- Joins the room (encounter, turns) to that player's floor state:
--   hp_before          HP going into the fight (previous floor's HP; max HP on floor 1)
--   damage_pct_of_max  damage taken as a share of max HP, comparable across runs
--   potions_used       potions drunk on that floor
--   died_here          the run was lost on this floor to this encounter
with rooms as (
    select * from {{ ref('stg_sts2__rooms') }}
    where room_type in ('monster', 'elite', 'boss')
),

floors as (
    select
        run_id, player_id, floor_number, current_hp, max_hp, damage_taken,
        lag(current_hp) over (partition by run_id, player_id order by floor_number) as prev_hp,
        lag(max_hp)     over (partition by run_id, player_id order by floor_number) as prev_max_hp
    from {{ ref('fct_floor_state') }}
),

potions as (
    select run_id, player_id, floor_number, count(*) as potions_used
    from {{ ref('stg_sts2__potion_events') }}
    where action = 'used'
    group by run_id, player_id, floor_number
),

runs as (
    select run_id, outcome, win, floors_reached, killed_by_encounter
    from {{ ref('dim_run') }}
)

select
    r.run_id,
    f.player_id,
    r.floor_number,
    r.act_index + 1                                             as act,
    r.room_index,
    r.model_id                                                  as encounter_id,
    case r.room_type when 'monster' then 'Normal' when 'elite' then 'Elite' else 'Boss' end as room_type,
    r.monster_count,
    r.turns_taken,
    coalesce(f.prev_hp, f.max_hp)                               as hp_before,
    coalesce(f.prev_max_hp, f.max_hp)                           as max_hp_before,
    safe_divide(coalesce(f.prev_hp, f.max_hp), coalesce(f.prev_max_hp, f.max_hp)) as hp_pct_before,
    case
        when safe_divide(coalesce(f.prev_hp, f.max_hp), coalesce(f.prev_max_hp, f.max_hp)) < 0.4 then 'Under 40%'
        when safe_divide(coalesce(f.prev_hp, f.max_hp), coalesce(f.prev_max_hp, f.max_hp)) < 0.7 then '40-70%'
        when safe_divide(coalesce(f.prev_hp, f.max_hp), coalesce(f.prev_max_hp, f.max_hp)) is not null then '70%+'
    end                                                         as hp_band,
    case
        when safe_divide(coalesce(f.prev_hp, f.max_hp), coalesce(f.prev_max_hp, f.max_hp)) < 0.4 then 1
        when safe_divide(coalesce(f.prev_hp, f.max_hp), coalesce(f.prev_max_hp, f.max_hp)) < 0.7 then 2
        when safe_divide(coalesce(f.prev_hp, f.max_hp), coalesce(f.prev_max_hp, f.max_hp)) is not null then 3
    end                                                         as hp_band_order,
    f.damage_taken,
    safe_divide(f.damage_taken, coalesce(f.prev_max_hp, f.max_hp)) as damage_pct_of_max,
    f.current_hp                                                as hp_after,
    coalesce(p.potions_used, 0)                                 as potions_used,
    runs.outcome = 'Lost'
        and r.floor_number = runs.floors_reached
        and r.model_id = runs.killed_by_encounter               as died_here,
    runs.outcome,
    runs.win
from rooms r
join floors f
    on f.run_id = r.run_id and f.floor_number = r.floor_number
left join potions p
    on p.run_id = r.run_id and p.player_id = f.player_id and p.floor_number = r.floor_number
join runs on runs.run_id = r.run_id
