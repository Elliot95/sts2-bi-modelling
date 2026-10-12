-- Grain: one line of dialogue (Ancient / character / conversation / line).
-- Reference data from the game's localization (ancient_dialogue seed), so the
-- report can show what an Ancient says to the character you are filtering on.
-- encounter labels the conversation ("Encounter 1" = first meeting; "Generic"
-- = lines any character can get); encounter_order sorts those labels.
-- Limited to Ancients seen in runs, so every row joins to dim_event.
select
    event_id,
    character,
    conversation,
    line,
    line + 1                                                    as step,
    case when character = 'Any' then concat('Generic ', cast(conversation + 1 as string))
         else concat('Encounter ', cast(conversation + 1 as string)) end as encounter,
    case when character = 'Any' then 100 + conversation else conversation end as encounter_order,
    speaker,
    text
from {{ ref('ancient_dialogue') }}
where event_id in (select event_id from {{ ref('dim_event') }})
