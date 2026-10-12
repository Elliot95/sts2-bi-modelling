-- Grain: one row per rest-site option taken (run / player / floor / choice).
-- HP going in (previous floor) and what happened next, for questions like
-- "do I rest when I should, and do I die when I smith at low HP?".
-- died_before_next_act uses the same definition as fct_event_choice.
with choices as (
    select * from {{ ref('stg_sts2__rest_choices') }}
),

floors as (
    select
        run_id, player_id, floor_number,
        lag(current_hp) over (partition by run_id, player_id order by floor_number) as prev_hp,
        lag(max_hp)     over (partition by run_id, player_id order by floor_number) as prev_max_hp
    from {{ ref('fct_floor_state') }}
),

runs as (
    select run_id, outcome, win, floors_reached, acts_reached
    from {{ ref('dim_run') }}
)

select
    c.run_id,
    c.player_id,
    c.floor_number,
    c.act_index + 1                                             as act,
    c.choice_index,
    c.rest_option,
    coalesce(o.option_name, initcap(c.rest_option))             as option_name,
    f.prev_hp                                                   as hp_before,
    f.prev_max_hp                                               as max_hp_before,
    safe_divide(f.prev_hp, f.prev_max_hp)                       as hp_pct_before,
    case
        when safe_divide(f.prev_hp, f.prev_max_hp) < 0.4 then 'Under 40%'
        when safe_divide(f.prev_hp, f.prev_max_hp) < 0.7 then '40-70%'
        when safe_divide(f.prev_hp, f.prev_max_hp) is not null then '70%+'
    end                                                         as hp_band,
    case
        when safe_divide(f.prev_hp, f.prev_max_hp) < 0.4 then 1
        when safe_divide(f.prev_hp, f.prev_max_hp) < 0.7 then 2
        when safe_divide(f.prev_hp, f.prev_max_hp) is not null then 3
    end                                                         as hp_band_order,
    runs.outcome,
    runs.win,
    runs.floors_reached - c.floor_number                        as floors_survived_after,
    runs.outcome = 'Lost' and runs.acts_reached = c.act_index + 1 as died_before_next_act
from choices c
left join floors f
    on f.run_id = c.run_id and f.player_id = c.player_id and f.floor_number = c.floor_number
left join {{ ref('rest_option_catalog') }} o on o.rest_option = c.rest_option
join runs on runs.run_id = c.run_id
