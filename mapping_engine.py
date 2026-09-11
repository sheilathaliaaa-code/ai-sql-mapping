import sqlglot
from sqlglot import exp


def extract_column_mapping(sql: str):
    """
    Extract source-to-output column relationships
    from a SQL query.
    """

    mappings = []

    try:
        tree = sqlglot.parse_one(sql, read="tsql")

        # Collect table aliases
        table_aliases = {}

        for table in tree.find_all(exp.Table):
            table_name = table.name
            alias = table.alias

            if alias:
                table_aliases[alias] = table_name
            else:
                table_aliases[table_name] = table_name

        # Find SELECT expressions
        for select in tree.find_all(exp.Select):

            for expression in select.expressions:

                target_column = expression.alias_or_name

                source_columns = []

                for column in expression.find_all(exp.Column):

                    source_table = column.table
                    source_column = column.name

                    if source_table in table_aliases:
                        source_table = table_aliases[source_table]

                    source_columns.append({
                        "source_table": source_table,
                        "source_column": source_column
                    })

                # Determine transformation
                transformation = "DIRECT"

                if isinstance(expression, exp.Alias):
                    inner = expression.this

                    if isinstance(inner, exp.Column):
                        transformation = "DIRECT"
                    else:
                        transformation = inner.key.upper()

                elif isinstance(expression, exp.Column):
                    transformation = "DIRECT"

                else:
                    transformation = expression.key.upper()

                mappings.append({
                    "target_column": target_column,
                    "source_columns": source_columns,
                    "transformation": transformation
                })

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
            "mappings": []
        }

    return {
        "success": True,
        "mappings": mappings
    }