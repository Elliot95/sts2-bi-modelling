-- Grain: one row per choice made in an event or Ancient room
-- (run / player / floor / choice_index). Joined to what happened next, to
-- answer "do runs die soon after this choice?":
--   floors_survived_after  floors the run lasted beyond this one
--   died_within_3_floors   lost (not abandoned) within 3 floors of the choice
--   died_before_next_act   lost in the same act the choice was made in
-- plus the HP / gold change recorded on that floor. Abandoned runs are not
-- counted as deaths.

with choices as (
    select * from {{ ref('stg_sts2__event_choices') }}
),

runs as (
    select run_id, outcome, win, floors_reached, acts_reached
    from {{ ref('dim_run') }}
),

floor as (
    select run_id, player_id, floor_number, current_hp, max_hp, damage_taken, hp_healed,
           max_hp_gained, max_hp_lost, gold_gained, gold_lost, gold_spent
    from {{ ref('fct_floor_state') }}
),

-- The option's display title: event options from the event option catalog,
-- Ancient relic choices from the relic catalog.
labelled as (
    select
        c.*,
        coalesce(
            o.option_title,
            rel.relic_name,
            initcap(replace(coalesce(c.option_code, split(c.choice_key, '.')[offset(0)]), '_', ' '))
        ) as option_name,
        o.option_description
    from choices c
    left join {{ ref('event_option_catalog') }} o on o.option_key = c.choice_key
    left join {{ ref('relic_catalog') }} rel on rel.relic_id = c.relic_id
)

select
    l.run_id,
    l.player_id,
    l.floor_number,
    l.act_index + 1                                         as act,
    l.choice_index,
    -- the last choice on a floor is the decision that "stuck" for multi-step events
    l.choice_index = max(l.choice_index) over (partition by l.run_id, l.player_id, l.floor_number)
                                                            as is_final_choice,
    l.event_id,
    l.choice_table,
    l.choice_key,
    l.option_page,
    l.option_code,
    l.relic_id,
    l.option_name,
    l.option_description,
    l.variables_json,
    r.outcome,
    r.win,
    r.floors_reached - l.floor_number                       as floors_survived_after,
    r.outcome = 'Lost' and r.floors_reached - l.floor_number <= 3   as died_within_3_floors,
    r.outcome = 'Lost' and r.acts_reached = l.act_index + 1         as died_before_next_act,
    f.current_hp                                            as hp_after,
    f.max_hp                                                as max_hp_after,
    coalesce(f.hp_healed, 0) - coalesce(f.damage_taken, 0)  as hp_change,
    coalesce(f.max_hp_gained, 0) - coalesce(f.max_hp_lost, 0) as max_hp_change,
    coalesce(f.gold_gained, 0) - coalesce(f.gold_lost, 0) - coalesce(f.gold_spent, 0) as gold_change
from labelled l
join runs r using (run_id)
left join floor f
    on f.run_id = l.run_id and f.player_id = l.player_id and f.floor_number = l.floor_number
