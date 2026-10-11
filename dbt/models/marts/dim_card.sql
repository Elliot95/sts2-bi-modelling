-- Grain: one row per card seen in the run data. Run-data IDs are enriched
-- with the card_catalog seed (second source: the installed game files). Cards in the
-- runs but missing from the catalog (retired from the current game version)
-- keep their derived name and get 'Unknown' attributes; the
-- assert_cards_in_catalog test reports them.
select
    c.card_id,
    coalesce(cat.card_name, {{ readable_id('c.card_id') }})    as card_name,
    coalesce(cat.card_character, 'Unknown')                     as card_character,
    coalesce(cat.rarity, 'Unknown')                             as rarity,
    coalesce(nullif(cat.card_type, ''), 'Unknown')              as card_type,
    nullif(cat.energy_cost, '')                                 as energy_cost,
    coalesce(cat.card_color, '#9ca3af')                         as card_color,
    {{ tint_hex("coalesce(cat.card_color, '#9ca3af')") }}       as card_color_tint,
    cat.card_id is not null                                     as in_catalog,
    c.first_seen_run_id,
    c.first_seen_date
from {{ ref('stg_sts2__cards') }} c
left join {{ ref('card_catalog') }} cat using (card_id)
