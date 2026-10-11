-- Grain: one row per run. The hub dimension every fct_* joins to, carrying the
-- run's attributes plus run-level derived metrics. Replaces the old pattern of
-- other facts relating to fact_run (a fact-to-fact relationship in Power BI).

with runs as (
    select * from {{ ref('stg_sts2__runs') }}
),

floor_states as (
    select * from {{ ref('stg_sts2__floor_states') }}
),

-- Floors/acts are shared by every player in a run, so they come from all rows.
-- Per-player metrics (HP, damage) are only filled for single-player runs:
-- in multiplayer runs player_id is a Steam64 ID and the loader doesn't record
-- which player is the host (players[0], whose character is on the run), so
-- attributing one player's HP to the run would be a guess.
run_floor_stats as (
    select
        run_id,
        count(distinct player_id)   as player_count,
        max(floor_number)           as floors_reached,
        max(act_index) + 1          as acts_reached,
        if(count(distinct player_id) = 1, sum(damage_taken), null) as total_damage_taken,
        if(
            count(distinct player_id) = 1,
            array_agg(current_hp order by floor_number desc limit 1)[offset(0)],
            null
        )                           as final_hp
    from floor_states
    group by run_id
),

-- Each character's card-frame colour from the card catalog, so run-level
-- visuals use the same palette as card-level ones.
character_colors as (
    select card_character, any_value(card_color) as character_color
    from {{ ref('card_catalog') }}
    where card_character in ('Ironclad', 'Silent', 'Defect', 'Necrobinder', 'Regent')
    group by card_character
)

select
    r.run_id,
    r.run_date,
    r.character,
    {{ readable_id('r.character') }}            as character_name,
    coalesce(cc.character_color, '#9ca3af')     as character_color,
    {{ tint_hex("coalesce(cc.character_color, '#9ca3af')") }} as character_color_tint,
    r.ascension,
    r.game_mode,
    r.build_id,
    r.platform_type,
    r.seed,
    r.win,
    r.was_abandoned,
    case
        when r.win then 'Won'
        when coalesce(r.was_abandoned, false) then 'Abandoned'
        else 'Lost'
    end                                         as outcome,
    r.killed_by_encounter,
    {{ readable_id('r.killed_by_encounter', ['ELITE', 'BOSS', 'NORMAL', 'WEAK']) }} as killed_by_encounter_name,
    case
        when r.killed_by_encounter is null or r.killed_by_encounter = 'NONE.NONE' then null
        when ends_with(r.killed_by_encounter, '_BOSS') then 'Boss'
        when ends_with(r.killed_by_encounter, '_ELITE') then 'Elite'
        else 'Normal'
    end                                         as killed_by_encounter_type,
    r.killed_by_event,
    {{ readable_id('r.killed_by_event') }}      as killed_by_event_name,
    -- What ended a lost run, whether a fight or an event (a few runs die in
    -- events, which left a blank "encounter").
    case when not r.win and not coalesce(r.was_abandoned, false) then
        coalesce({{ readable_id('r.killed_by_encounter', ['ELITE', 'BOSS', 'NORMAL', 'WEAK']) }},
                 {{ readable_id('r.killed_by_event') }}, 'Unknown')
    end                                         as ended_by,
    case when not r.win and not coalesce(r.was_abandoned, false) then
        case
            when ends_with(r.killed_by_encounter, '_BOSS') then 'Boss'
            when ends_with(r.killed_by_encounter, '_ELITE') then 'Elite'
            when r.killed_by_encounter is not null and r.killed_by_encounter != 'NONE.NONE' then 'Normal'
            when r.killed_by_event is not null and r.killed_by_event != 'NONE.NONE' then 'Event'
            else 'Unknown'
        end
    end                                         as ended_by_type,
    r.acts_completed,
    r.run_time_seconds,
    round(r.run_time_seconds / 60, 1)           as run_time_minutes,
    s.player_count,
    coalesce(s.player_count, 1) > 1             as is_multiplayer,
    if(coalesce(s.player_count, 1) > 1, 'Multiplayer', 'Solo') as play_mode,
    case
        when coalesce(s.player_count, 1) <= 1 then 'Solo'
        else concat(cast(s.player_count as string), ' players')
    end                                         as party_size,
    s.acts_reached,
    s.floors_reached,
    case
        when not r.win and not coalesce(r.was_abandoned, false) then s.floors_reached
    end                                         as death_floor,
    s.final_hp,
    s.total_damage_taken
from runs r
left join run_floor_stats s using (run_id)
left join character_colors cc
    on cc.card_character = {{ readable_id('r.character') }}
