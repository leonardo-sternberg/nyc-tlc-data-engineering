{#
    Generic test: fails for rows where the column is outside [min_value, max_value].
    Either bound can be omitted. Nulls are not checked (use not_null for that).

    Usage in a YAML file:
        data_tests:
          - accepted_range:
              arguments:
                min_value: 0
                extra_columns: [partition_year, partition_month]   # optional

    extra_columns: columns returned next to the tested one, useful with store_failures
    to know WHERE the failing rows are. Careful: on BigQuery each extra column is read
    in full (all rows), so it adds cost. Partition columns are free.

    Like every dbt test, it is a query that returns the rows that BREAK the rule:
    0 rows = pass.
#}
{% test accepted_range(model, column_name, min_value=none, max_value=none, extra_columns=none) %}

select
    {%- for col in extra_columns or [] %}
    {{ col }},
    {%- endfor %}
    {{ column_name }}
from {{ model }}
where
    {%- if min_value is not none %}
    {{ column_name }} < {{ min_value }}
    {%- endif %}
    {%- if min_value is not none and max_value is not none %}
    or
    {%- endif %}
    {%- if max_value is not none %}
    {{ column_name }} > {{ max_value }}
    {%- endif %}

{% endtest %}
