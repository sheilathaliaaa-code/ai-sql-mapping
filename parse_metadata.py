from pathlib import Path
from collections import Counter
import json
import re

import sqlglot
from sqlglot import exp


# ============================================================
# CONFIG
# ============================================================

SQL_FILE = Path("output/sample_view.sql")
OUTPUT_FILE = Path("output/metadata_clean.json")

DIALECT = "tsql"


# ============================================================
# HELPERS
# ============================================================

def clean_identifier(value: str) -> str:
    """
    Bersihkan identifier SQL dari bracket dan whitespace.
    """
    if not value:
        return value

    value = value.strip()

    # [abc] -> abc
    value = value.replace("[", "").replace("]", "")

    return value


def clean_table_name(table: exp.Table) -> str:
    """
    Ambil nama table tanpa alias/comment.
    """
    parts = []

    catalog = table.args.get("catalog")
    db = table.args.get("db")
    name = table.args.get("this")

    if catalog:
        parts.append(clean_identifier(catalog.name))

    if db:
        parts.append(clean_identifier(db.name))

    if name:
        parts.append(clean_identifier(name.name))

    return ".".join(parts)


def get_alias(table: exp.Table) -> str | None:
    """
    Ambil alias table.
    """
    alias = table.alias

    if alias:
        return clean_identifier(alias)

    return None


def extract_sql_comment(line: str) -> str | None:
    """
    Ambil isi comment SQL '-- ...'
    """
    if "--" not in line:
        return None

    comment = line.split("--", 1)[1].strip()

    return comment if comment else None


# ============================================================
# READ SQL
# ============================================================

if not SQL_FILE.exists():
    raise FileNotFoundError(
        f"SQL file tidak ditemukan: {SQL_FILE}"
    )

sql = SQL_FILE.read_text(
    encoding="utf-8"
)


# ============================================================
# PARSE SQL
# ============================================================

try:
    tree = sqlglot.parse_one(
        sql,
        read=DIALECT
    )
except Exception as exc:
    print("❌ SQL gagal diparse")
    print(exc)
    raise SystemExit(1)


# ============================================================
# VIEW INFORMATION
# ============================================================

create = tree.find(exp.Create)

if not create:
    raise RuntimeError(
        "CREATE VIEW tidak ditemukan."
    )

target = create.this

view_name = None
schema_name = None
database_name = None

if isinstance(target, exp.Schema):
    table = target.this

    if isinstance(table, exp.Table):
        view_name = clean_identifier(table.name)

        if table.args.get("db"):
            schema_name = clean_identifier(
                table.args["db"].name
            )

        if table.args.get("catalog"):
            database_name = clean_identifier(
                table.args["catalog"].name
            )

elif isinstance(target, exp.Table):
    view_name = clean_identifier(target.name)

    if target.args.get("db"):
        schema_name = clean_identifier(
            target.args["db"].name
        )

    if target.args.get("catalog"):
        database_name = clean_identifier(
            target.args["catalog"].name
        )


# ============================================================
# CTE NAMES
# ============================================================

cte_names = set()

for cte in tree.find_all(exp.CTE):
    alias = cte.alias

    if alias:
        cte_names.add(
            clean_identifier(alias)
        )


# ============================================================
# TABLE / SOURCE EXTRACTION
# ============================================================

alias_map = {}
source_objects = {}

for table in tree.find_all(exp.Table):

    table_name = clean_table_name(table)

    if not table_name:
        continue

    alias = get_alias(table)

    if alias:
        alias_map[alias] = table_name

    # Jangan masukkan CTE sebagai physical source
    if table_name.lower() in {
        c.lower() for c in cte_names
    }:
        continue

    # Jangan masukkan target view sebagai source
    if view_name and table_name.lower().endswith(
        view_name.lower()
    ):
        continue

    source_objects[table_name] = {
        "name": table_name,
        "alias": alias,
        "database": None,
        "schema": None,
        "table": table_name,
    }


# ============================================================
# PARSE DATABASE / SCHEMA / TABLE
# ============================================================

for item in source_objects.values():

    parts = item["name"].split(".")

    if len(parts) == 3:
        item["database"] = parts[0]
        item["schema"] = parts[1]
        item["table"] = parts[2]

    elif len(parts) == 2:
        item["schema"] = parts[0]
        item["table"] = parts[1]

    elif len(parts) == 1:
        item["table"] = parts[0]


# ============================================================
# CTE METADATA
# ============================================================

ctes = []

for cte in tree.find_all(exp.CTE):

    alias = cte.alias

    if not alias:
        continue

    cte_sql = cte.this.sql(
        dialect=DIALECT
    )

    cte_sources = []

    for table in cte.find_all(exp.Table):

        name = clean_table_name(table)

        if name and name.lower() not in {
            c.lower() for c in cte_names
        }:
            if name not in cte_sources:
                cte_sources.append(name)

    ctes.append(
        {
            "name": clean_identifier(alias),
            "sources": cte_sources,
            "sql": cte_sql[:1000],
        }
    )


# ============================================================
# FINAL SELECT / OUTPUT COLUMNS
# ============================================================

# Ambil SELECT yang bukan berasal dari CTE.
cte_select_ids = set()

for cte in tree.find_all(exp.CTE):
    for select in cte.this.find_all(exp.Select):
        cte_select_ids.add(id(select))


output_columns = []
seen_columns = set()

for select in tree.find_all(exp.Select):

    if id(select) in cte_select_ids:
        continue

    for expression in select.expressions:

        alias = None
        expression_sql = expression.sql(
            dialect=DIALECT
        )

        if isinstance(expression, exp.Alias):

            alias = clean_identifier(
                expression.alias
            )

            base_expression = expression.this

            expression_sql = base_expression.sql(
                dialect=DIALECT
            )

        else:
            alias = clean_identifier(
                expression.name
            )

        if not alias:
            alias = expression_sql

        # Source columns
        dependencies = []

        for col in expression.find_all(exp.Column):

            col_name = clean_identifier(col.name)
            table_alias = clean_identifier(col.table)

            if table_alias and table_alias in alias_map:

                source = alias_map[table_alias]

                dependency = {
                    "source_object": source,
                    "source_alias": table_alias,
                    "source_column": col_name,
                }

            else:

                dependency = {
                    "source_object": None,
                    "source_alias": table_alias or None,
                    "source_column": col_name,
                }

            if dependency not in dependencies:
                dependencies.append(
                    dependency
                )

        key = (
            alias.lower(),
            expression_sql.lower(),
        )

        if key in seen_columns:
            continue

        seen_columns.add(key)

        output_columns.append(
            {
                "name": alias,
                "expression": expression_sql,
                "dependencies": dependencies,
            }
        )


# ============================================================
# JOIN RELATIONSHIPS
# ============================================================

relationships = []

seen_relationships = set()

for join in tree.find_all(exp.Join):

    join_type = join.args.get("kind")

    join_table = join.this

    if not isinstance(join_table, exp.Table):
        continue

    target_table = clean_table_name(
        join_table
    )

    target_alias = get_alias(
        join_table
    )

    on_expression = join.args.get("on")

    on_sql = None

    if on_expression:
        on_sql = on_expression.sql(
            dialect=DIALECT
        )

    # Column pairs
    column_pairs = []

    if on_expression:

        for eq in on_expression.find_all(exp.EQ):

            left = eq.left
            right = eq.right

            if isinstance(left, exp.Column) and isinstance(
                right, exp.Column
            ):

                left_alias = clean_identifier(left.table)
                right_alias = clean_identifier(right.table)

                column_pairs.append(
                    {
                        "left": {
                            "alias": left_alias or None,
                            "column": clean_identifier(left.name),
                            "object": alias_map.get(left_alias),
                        },
                        "right": {
                            "alias": right_alias or None,
                            "column": clean_identifier(right.name),
                            "object": alias_map.get(right_alias),
                        },
                    }
                )

    relationship_key = (
        str(join_type),
        target_table,
        on_sql,
    )

    if relationship_key in seen_relationships:
        continue

    seen_relationships.add(
        relationship_key
    )

    relationships.append(
        {
            "join_type": join_type or "JOIN",
            "target_object": target_table,
            "target_alias": target_alias,
            "condition": on_sql,
            "column_pairs": column_pairs,
        }
    )


# ============================================================
# MAPPING / SQL COMMENTS
# ============================================================

all_comments = []

for line in sql.splitlines():

    comment = extract_sql_comment(line)

    if comment:
        all_comments.append(comment)


# Mapping-related comments
mapping_comments = []

for comment in all_comments:

    lower = comment.lower()

    if (
        "map:" in lower
        or "mapping" in lower
        or "tidak di temukan" in lower
    ):
        mapping_comments.append(comment)


# Unique comments + count
comment_counter = Counter(mapping_comments)

mapping_summary = [
    {
        "comment": comment,
        "count": count,
    }
    for comment, count
    in comment_counter.most_common()
]


# ============================================================
# SUMMARY STATISTICS
# ============================================================

physical_source_count = len(
    source_objects
)

cte_count = len(
    ctes
)

column_count = len(
    output_columns
)

relationship_count = len(
    relationships
)


# ============================================================
# CLEAN METADATA
# ============================================================

metadata = {

    "asset_type": "view",

    "view": {
        "name": view_name,
        "database": database_name,
        "schema": schema_name,
        "fully_qualified_name": ".".join(
            [
                x
                for x in [
                    database_name,
                    schema_name,
                    view_name,
                ]
                if x
            ]
        ),
    },

    "ctes": ctes,

    "source_objects": list(
        source_objects.values()
    ),

    "columns": output_columns,

    "relationships": relationships,

    "mapping": {
        "comments": mapping_comments,
        "summary": mapping_summary,
    },

    "statistics": {
        "physical_sources": physical_source_count,
        "ctes": cte_count,
        "output_columns": column_count,
        "join_relationships": relationship_count,
        "mapping_comments": len(
            mapping_comments
        ),
    },
}


# ============================================================
# SAVE
# ============================================================

OUTPUT_FILE.write_text(
    json.dumps(
        metadata,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


# ============================================================
# CONSOLE OUTPUT
# ============================================================

print("✅ Clean metadata berhasil dibuat")

print("\n=== VIEW ===")
print(
    metadata["view"]["fully_qualified_name"]
)

print("\n=== SOURCES ===")

for source in metadata["source_objects"]:
    print(
        f"- {source['name']}"
        f"  [alias={source['alias']}]"
    )

print("\n=== CTE ===")

for cte in metadata["ctes"]:
    print(
        f"- {cte['name']}"
    )

print("\n=== COUNTS ===")

print(
    "Physical Sources:",
    physical_source_count
)

print(
    "CTEs:",
    cte_count
)

print(
    "Output Columns:",
    column_count
)

print(
    "Relationships:",
    relationship_count
)

print(
    "Mapping Comments:",
    len(mapping_comments)
)

print("\n=== OUTPUT ===")
print(OUTPUT_FILE)