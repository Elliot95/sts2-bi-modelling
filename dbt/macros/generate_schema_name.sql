{#
  Use the configured +schema verbatim (e.g. sts2_marts) instead of dbt's
  default "<target_dataset>_<custom_schema>" concatenation, so dataset names
  are stable and readable from Power BI.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
