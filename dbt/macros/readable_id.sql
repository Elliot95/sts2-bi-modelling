{#
  Turn a game ID like CARD.BATTLE_TRANCE / CHARACTER.IRONCLAD into a display
  label ("Battle Trance", "Ironclad"): drop the TYPE. prefix, underscores ->
  spaces, title case. NONE.NONE (the game's "nothing") becomes null.
  strip_suffixes removes trailing tokens such as _ELITE / _BOSS from
  encounter IDs, which are modelled separately as an encounter type.
#}
{% macro readable_id(column, strip_suffixes=[]) -%}
    {%- set stripped -%}
        regexp_replace({{ column }}, r'^[A-Z_]+\.', '')
    {%- endset -%}
    {%- if strip_suffixes -%}
        {%- set stripped -%}
            regexp_replace({{ stripped }}, r'_({{ strip_suffixes | join("|") }})$', '')
        {%- endset -%}
    {%- endif -%}
    if({{ column }} = 'NONE.NONE', null, initcap(replace({{ stripped }}, '_', ' ')))
{%- endmacro %}
