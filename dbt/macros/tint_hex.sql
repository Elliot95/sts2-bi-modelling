{#
  Lighten a '#rrggbb' colour by mixing it with white. weight = share of white
  (0.8 -> a pale tint). Used for table backgrounds in the character's colour
  that stay readable under green/red conditional font colours.
#}
{% macro tint_hex(column, weight=0.8) -%}
    format('#%02x%02x%02x',
        cast(round(cast(concat('0x', substr({{ column }}, 2, 2)) as int64) * (1 - {{ weight }}) + 255 * {{ weight }}) as int64),
        cast(round(cast(concat('0x', substr({{ column }}, 4, 2)) as int64) * (1 - {{ weight }}) + 255 * {{ weight }}) as int64),
        cast(round(cast(concat('0x', substr({{ column }}, 6, 2)) as int64) * (1 - {{ weight }}) + 255 * {{ weight }}) as int64)
    )
{%- endmacro %}

{#
  Darken a '#rrggbb' colour by mixing it into the report's dark base
  (#0b1220). weight = share of the base (0.75 -> a deep shade). Used for
  table rows on the dark report theme, under light text.
#}
{% macro shade_hex(column, weight=0.75) -%}
    format('#%02x%02x%02x',
        cast(round(cast(concat('0x', substr({{ column }}, 2, 2)) as int64) * (1 - {{ weight }}) + 11 * {{ weight }}) as int64),
        cast(round(cast(concat('0x', substr({{ column }}, 4, 2)) as int64) * (1 - {{ weight }}) + 18 * {{ weight }}) as int64),
        cast(round(cast(concat('0x', substr({{ column }}, 6, 2)) as int64) * (1 - {{ weight }}) + 32 * {{ weight }}) as int64)
    )
{%- endmacro %}
