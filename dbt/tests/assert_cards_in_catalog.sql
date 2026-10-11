{{ config(severity='warn') }}
-- Coverage monitor for the second data source: cards that appear in runs but
-- not in the card_catalog seed. Expected causes are cards added by a game
-- patch (re-run scripts/fetch_card_catalog.py) or cards retired from the
-- current version that still exist in older runs. Warn, not fail: these runs
-- are valid, the reference data is just incomplete.
select card_id, card_name, first_seen_date
from {{ ref('dim_card') }}
where not in_catalog
