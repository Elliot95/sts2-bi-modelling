-- Grain: one line of dialogue (Ancient / character / conversation / line).
-- Reference data from the game's localization (ancient_dialogue seed), so the
-- report can show what an Ancient says to the character you are filtering on.
select
    event_id,
    character,
    conversation,
    line,
    speaker,
    text
from {{ ref('ancient_dialogue') }}
