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
