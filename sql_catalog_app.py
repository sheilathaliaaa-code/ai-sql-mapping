
import json
import html

import pandas as pd
import streamlit as st
import sqlglot
from sqlglot import exp
import streamlit.components.v1 as components

from mapping_engine import extract_column_mapping


st.set_page_config(
    page_title="AI SQL Mapping & Data Catalog",
    page_icon="🔗",
    layout="wide",
)

st.title("🔗 AI SQL Mapping & Data Catalog")
st.caption("SQL Parser • Metadata • Mapping Automation • Column Lineage")


# ============================================================
# HELPERS
# ============================================================

def safe_text(value):
    """
    Convert sqlglot objects / lists / dicts into plain strings.
    This prevents Streamlit/PyArrow DataFrameConversionError.
    """
    if value is None:
        return ""

    if isinstance(value, (str, int, float, bool)):
        return str(value)

    if isinstance(value, (list, tuple, set)):
        return ", ".join(safe_text(v) for v in value)

    if isinstance(value, dict):
        return json.dumps(
            {str(k): safe_text(v) for k, v in value.items()},
            ensure_ascii=False,
        )

    try:
        return value.sql(dialect="tsql")
    except Exception:
        return str(value)


def normalize_mapping_result(result):
    """Accept several possible mapping_engine return shapes."""
    if result is None:
        return []

    if isinstance(result, list):
        return result

    if isinstance(result, dict):
        for key in (
            "mappings",
            "column_mappings",
            "mapping",
            "results",
            "data",
        ):
            value = result.get(key)
            if isinstance(value, list):
                return value

    return []


def normalize_source_columns(item):
    source_cols = item.get("source_columns", [])

    if isinstance(source_cols, dict):
        source_cols = [source_cols]

    if isinstance(source_cols, str):
        source_cols = [
            {
                "source_table": "",
                "source_column": source_cols,
            }
        ]

    return source_cols if isinstance(source_cols, list) else []


def build_source_table_rows(parsed):
    """
    Extract source tables from SQL and immediately convert every
    sqlglot Identifier/Table object to plain strings.
    """
    rows = []
    seen = set()

    for table in parsed.find_all(exp.Table):
        database = safe_text(table.args.get("catalog"))
        schema = safe_text(table.args.get("db"))
        name = safe_text(table.args.get("this"))

        alias_obj = table.args.get("alias")
        alias = safe_text(alias_obj)

        key = (database, schema, name, alias)

        if key in seen:
            continue

        seen.add(key)

        rows.append(
            {
                "Database": database or "-",
                "Schema": schema or "-",
                "Table": name or "-",
                "Alias": alias or "-",
            }
        )

    return rows


def build_mapping_rows(mappings):
    """
    Flatten mapping_engine output into Arrow-safe rows.
    """
    rows = []

    for item in mappings:
        if not isinstance(item, dict):
            continue

        target = safe_text(item.get("target_column", ""))
        transformation = safe_text(
            item.get("transformation", "DIRECT")
        )

        source_columns = normalize_source_columns(item)

        # Literal / derived column
        if not source_columns:
            rows.append(
                {
                    "Source Table": "LITERAL / DERIVED",
                    "Source Column": "",
                    "Target Column": target,
                    "Transformation": transformation,
                }
            )
            continue

        for source in source_columns:

            if isinstance(source, dict):
                rows.append(
                    {
                        "Source Table": safe_text(
                            source.get("source_table", "")
                        ),
                        "Source Column": safe_text(
                            source.get("source_column", "")
                        ),
                        "Target Column": target,
                        "Transformation": transformation,
                    }
                )

            else:
                rows.append(
                    {
                        "Source Table": "",
                        "Source Column": safe_text(source),
                        "Target Column": target,
                        "Transformation": transformation,
                    }
                )

    return rows


def build_graph_data(mapping_rows):
    """
    Build source-column -> target-column graph data.
    """
    nodes = {}
    edges = []

    for row in mapping_rows:

        source_table = row["Source Table"] or "LITERAL / DERIVED"
        source_column = row["Source Column"]
        target_column = row["Target Column"] or "UNKNOWN"
        transformation = row["Transformation"] or "DIRECT"

        source_id = (
            f"src::{source_table}::{source_column}"
        )

        target_id = (
            f"tgt::{target_column}"
        )

        if source_id not in nodes:
            nodes[source_id] = {
                "id": source_id,
                "label": (
                    f"{source_table}\n{source_column}"
                    if source_column
                    else source_table
                ),
                "group": "source",
                "title": (
                    f"<b>Source</b><br>"
                    f"{html.escape(source_table)}<br>"
                    f"{html.escape(source_column)}"
                ),
            }

        if target_id not in nodes:
            nodes[target_id] = {
                "id": target_id,
                "label": target_column,
                "group": "target",
                "title": (
                    f"<b>Target</b><br>"
                    f"{html.escape(target_column)}"
                ),
            }

        edges.append(
            {
                "from": source_id,
                "to": target_id,
                "label": transformation,
                "arrows": "to",
                "title": (
                    f"{html.escape(source_column)} → "
                    f"{html.escape(target_column)}"
                    f"<br>Transformation: "
                    f"{html.escape(transformation)}"
                ),
            }
        )

    return list(nodes.values()), edges


def render_interactive_lineage(mapping_rows):
    """
    Interactive lineage graph.

    - Click source/target node
    - See connected relations
    - Search source/target column
    - Zoom / pan
    """

    nodes, edges = build_graph_data(mapping_rows)

    payload = json.dumps(
        {
            "nodes": nodes,
            "edges": edges,
        },
        ensure_ascii=False,
    )

    page = f"""
<!doctype html>
<html>

<head>

<meta charset="utf-8">

<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>

<style>

html, body {{
    margin: 0;
    padding: 0;
    font-family: Arial, sans-serif;
    background: white;
}}

#toolbar {{
    padding: 10px 12px;
    border-bottom: 1px solid #ddd;
    display: flex;
    gap: 10px;
    align-items: center;
}}

#search {{
    width: 320px;
    padding: 8px 10px;
    border: 1px solid #ccc;
    border-radius: 6px;
}}

#graph {{
    height: 620px;
    border: 1px solid #ddd;
}}

#detail {{
    padding: 12px;
    border: 1px solid #ddd;
    border-top: 0;
    min-height: 55px;
    background: #fafafa;
}}

.badge {{
    display: inline-block;
    padding: 4px 8px;
    border-radius: 12px;
    background: #eee;
    font-size: 12px;
}}

</style>

</head>

<body>

<div id="toolbar">

<input
    id="search"
    placeholder="Search source / target column..."
>

<span class="badge">
    Click node → see its relations
</span>

</div>

<div id="graph"></div>

<div id="detail">
    <b>Lineage detail:</b>
    click a source or target node.
</div>


<script>

const raw = {payload};


const nodeData = new vis.DataSet(

    raw.nodes.map(n => {{

        n.shape = "box";

        n.margin = 10;

        n.font = {{
            multi: true
        }};

        n.borderWidth = 1;

        n.color =
            n.group === "source"
            ? {{
                background: "#eef5ff",
                border: "#5b8def"
            }}
            : {{
                background: "#fff1f1",
                border: "#ef5350"
            }};

        return n;

    }})

);


const edgeData = new vis.DataSet(raw.edges);


const container =
    document.getElementById("graph");


const network = new vis.Network(

    container,

    {{
        nodes: nodeData,
        edges: edgeData
    }},

    {{

        interaction: {{
            hover: true,
            navigationButtons: true,
            keyboard: true
        }},

        physics: {{
            enabled: true,
            stabilization: {{
                iterations: 250
            }}
        }},

        layout: {{
            improvedLayout: true
        }},

        nodes: {{
            font: {{
                size: 14
            }}
        }},

        edges: {{
            smooth: {{
                type: "cubicBezier",
                forceDirection: "horizontal"
            }},

            font: {{
                align: "middle",
                size: 10
            }}
        }}

    }}

);


network.on("click", function(params) {{

    if (!params.nodes.length) {{
        return;
    }}

    const id = params.nodes[0];

    const node =
        nodeData.get(id);

    const connectedEdges =
        network.getConnectedEdges(id)
        .map(e => edgeData.get(e));


    let detail =
        "<b>Selected:</b> "
        + (node.label || id)
        + "<br>";

    detail +=
        "<b>Relations:</b> "
        + connectedEdges.length
        + "<br>";


    connectedEdges.forEach(e => {{

        const from =
            nodeData.get(e.from);

        const to =
            nodeData.get(e.to);


        detail +=
            "• "
            + (from.label || e.from)
            + " → "
            + (to.label || e.to)
            + " ["
            + (e.label || "DIRECT")
            + "]<br>";

    }});


    document.getElementById("detail").innerHTML =
        detail;


    network.selectNodes([id]);

}});


document
    .getElementById("search")
    .addEventListener(
        "input",
        function() {{

            const q =
                this.value
                .toLowerCase()
                .trim();


            nodeData.forEach(n => {{

                if (!q) {{

                    nodeData.update({{
                        id: n.id,
                        hidden: false
                    }});

                    return;

                }}


                const match =
                    (n.label || "")
                    .toLowerCase()
                    .includes(q);


                nodeData.update({{
                    id: n.id,
                    hidden: !match
                }});

            }});

        }}
    );

</script>

</body>

</html>
"""

    components.html(
        page,
        height=710,
        scrolling=False,
    )


# ============================================================
# UPLOAD
# ============================================================

uploaded_file = st.file_uploader(
    "Upload SQL Query",
    type=["sql", "txt"],
)


if uploaded_file:

    sql = uploaded_file.read().decode(
        "utf-8",
        errors="replace",
    )

    with st.expander("View SQL Query"):

        st.code(
            sql,
            language="sql",
        )


    if st.button(
        "🔍 Analyze SQL",
        type="primary",
    ):

        try:

            # ==================================================
            # LEVEL 1 — SQL PARSER
            # ==================================================

            parsed = sqlglot.parse_one(
                sql,
                read="tsql",
            )


            # ==================================================
            # LEVEL 2 — MAPPING AUTOMATION
            # ==================================================

            mapping_result = extract_column_mapping(sql)

            mappings = normalize_mapping_result(mapping_result)


            source_rows = build_source_table_rows(parsed)

            mapping_rows = build_mapping_rows(mappings)


            # Store only normal Python objects
            # in session_state.

            st.session_state["source_rows"] = source_rows

            st.session_state["mapping_rows"] = mapping_rows

            st.session_state["sql"] = sql


            st.success(
                "SQL successfully analyzed!"
            )


        except Exception as e:

            st.error(
                "Unable to analyze SQL."
            )

            st.exception(e)


# ============================================================
# RESULTS
# ============================================================

if "source_rows" in st.session_state:

    source_rows = st.session_state["source_rows"]

    mapping_rows = st.session_state["mapping_rows"]


    # ========================================================
    # SUMMARY
    # ========================================================

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Source Tables",
        len(source_rows),
    )

    c2.metric(
        "Column Mappings",
        len(mapping_rows),
    )

    c3.metric(
        "SQL Statements",
        len(
            sqlglot.parse(
                st.session_state["sql"],
                read="tsql",
            )
        ),
    )


    # ========================================================
    # TABS
    # ========================================================

    tab_metadata, tab_mapping, tab_lineage = st.tabs(
        [
            "📋 Metadata",
            "🔗 Column Mapping",
            "🌳 Interactive Lineage",
        ]
    )


    # ========================================================
    # METADATA
    # ========================================================

    with tab_metadata:

        st.subheader(
            "Source Tables"
        )


        metadata_df = (
            pd.DataFrame(source_rows)
            .fillna("")
            .astype(str)
        )


        if metadata_df.empty:

            st.info(
                "No source tables detected."
            )

        else:

            st.dataframe(
                metadata_df,
                use_container_width=True,
                hide_index=True,
            )


    # ========================================================
    # COLUMN MAPPING
    # ========================================================

    with tab_mapping:

        st.subheader(
            "Column Mapping"
        )


        mapping_df = (
            pd.DataFrame(mapping_rows)
            .fillna("")
            .astype(str)
        )


        if mapping_df.empty:

            st.info(
                "No column mappings detected."
            )

        else:

            st.dataframe(
                mapping_df,
                use_container_width=True,
                hide_index=True,
            )


            st.download_button(
                "⬇️ Download Mapping CSV",

                data=
                    mapping_df
                    .to_csv(index=False)
                    .encode("utf-8"),

                file_name=
                    "column_mapping.csv",

                mime=
                    "text/csv",
            )


    # ========================================================
    # INTERACTIVE LINEAGE
    # ========================================================

    with tab_lineage:

        st.subheader(
            "Column Lineage"
        )

        st.caption(
            "Klik node untuk melihat relasi. "
            "Gunakan search untuk mencari "
            "source/target column."
        )


        if mapping_rows:

            render_interactive_lineage(
                mapping_rows
            )

        else:

            st.info(
                "No lineage available. "
                "Analyze SQL with column mappings first."
            )
