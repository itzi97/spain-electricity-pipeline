{# Fails for every row where the column falls outside [minimum, maximum]. #}
{% test values_between(model, column_name, minimum, maximum) %}
select *
from {{ model }}
where {{ column_name }} < {{ minimum }} or {{ column_name }} > {{ maximum }}
{% endtest %}

{# Fails for every row where the column is below minimum. #}
{% test values_at_least(model, column_name, minimum) %}
select *
from {{ model }}
where {{ column_name }} < {{ minimum }}
{% endtest %}
