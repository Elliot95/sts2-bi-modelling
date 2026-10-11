-- Grain: one row per run. The hub dimension every fct_* joins to, carrying the
-- run's attributes plus run-level derived metrics. Replaces the old pattern of
-- other facts relating to fact_run (a fact-to-fact relationship in Power BI).

with runs as (
    select * from {{ ref('stg_sts2__runs') }}
),

floor_states as (
    select * from {{ ref('stg_sts2__floor_states') }}
),

-- Single-player focus: the primary player is the lowest player_id per run.
primary_player as (
    select run_id, min(player_id) as player_id
    from floor_states
    group by run_id
),

player_floors as (
    select fs.*
    from floor_states fs
    join primary_player pp using (run_id, player_id)
),

run_floor_stats as (
    select
        run_id,
        max(floor_number)   as floors_reached,
        max(act_index) + 1  as acts_reached,
        sum(damage_taken)   as total_damage_taken,
        array_agg(current_hp order by floor_number desc limit 1)[offset(0)] as final_hp
    from player_floors
    group by run_id
)

select
    r.run_id,
    r.run_date,
    r.character,
    r.ascension,
    r.game_mode,
    r.build_id,
    r.platform_type,
    r.seed,
    r.win,
    r.was_abandoned,
    r.killed_by_encounter,
    r.killed_by_event,
    r.acts_completed,
    r.run_time_seconds,
    s.acts_reached,
    s.floors_reached,
    case
        when not r.win and not coalesce(r.was_abandoned, false) then s.floors_reached
    end                                         as death_floor,
    s.final_hp,
    s.total_damage_taken
from runs r
left join run_floor_stats s using (run_id)
