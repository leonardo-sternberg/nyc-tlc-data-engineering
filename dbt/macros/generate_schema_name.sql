{#
    Overrides dbt's built-in macro that decides the BigQuery dataset of each model, seed and test.

    Built-in behaviour: <profile dataset>_<custom schema>, e.g. staging_marts.
    That prefix keeps developers apart when each one has their own profile dataset (dbt_ana_marts),
    but this project has a single developer, so custom schemas are used exactly as written:

        no +schema configured  -> profile dataset (staging)
        +schema: marts         -> marts
#}
{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}
