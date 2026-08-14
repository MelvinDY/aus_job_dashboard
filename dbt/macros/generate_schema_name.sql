{#
    Use custom schemas verbatim.

    dbt's default is to prefix them with the profile's schema, which would build
    `dbo_mart.v_national_overview`. The Power BI model and the Excel workbook
    both address `mart.v_national_overview`, so the schema names configured in
    dbt_project.yml have to land exactly as written.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
