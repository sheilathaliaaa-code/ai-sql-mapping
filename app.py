import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Metadata Catalog POC",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
METADATA_FILE = BASE_DIR / "output" / "metadata_clean.json"


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>
        .main-title {
            font-size: 34px;
            font-weight: 700;
            margin-bottom: 4px;
        }

        .subtitle {
            color: #666;
            font-size: 15px;
            margin-bottom: 20px;
        }

        .asset-card {
            padding: 18px;
            border-radius: 12px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
            margin-bottom: 12px;
        }

        .small-label {
            color: #6b7280;
            font-size: 13px;
        }

        .small-value {
            font-size: 16px;
            font-weight: 600;
        }

        .lineage-box {
            padding: 14px 18px;
            border-radius: 10px;
            border: 1px solid #e5e7eb;
            background: #fafafa;
            margin: 6px 0;
        }

        .source-box {
            padding: 12px 16px;
            border-radius: 10px;
            background: #f7f8fa;
            border: 1px solid #e6e8eb;
            margin-bottom: 8px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# LOAD JSON
# ============================================================

@st.cache_data
def load_metadata() -> dict[str, Any]:
    if not METADATA_FILE.exists():
        raise FileNotFoundError(
            f"File metadata tidak ditemukan:\n{METADATA_FILE}"
        )

    with open(METADATA_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            "metadata_clean.json harus berupa JSON object/dictionary."
        )

    return data


try:
    metadata = load_metadata()
except Exception as error:
    st.error("Gagal membaca metadata_clean.json")
    st.code(str(error))
    st.stop()


# ============================================================
# GENERIC HELPERS
# ============================================================

def first_existing(data: dict[str, Any], keys: list[str], default: Any = None):
    """
    Ambil nilai pertama yang ditemukan dari beberapa kemungkinan key.
    """
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def as_list(value: Any) -> list[Any]:
    """
    Pastikan value menjadi list.
    """
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def text_value(value: Any, default: str = "") -> str:
    """
    Convert value apa pun menjadi string yang aman untuk UI.
    """
    if value is None:
        return default

    if isinstance(value, str):
        return value

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, dict):
        # Prioritaskan field umum
        for key in ["name", "displayName", "object", "value", "source", "target"]:
            if key in value and value[key] is not None:
                return text_value(value[key], default)

        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, list):
        return ", ".join(text_value(item) for item in value)

    return str(value)


def asset_name(metadata: dict[str, Any]) -> str:
    """
    Cari nama asset/view dari berbagai kemungkinan struktur JSON.
    """
    value = first_existing(
        metadata,
        [
            "view_name",
            "view",
            "asset_name",
            "asset",
            "name",
            "fully_qualified_name",
        ],
        "Unknown View",
    )

    if isinstance(value, dict):
        value = first_existing(
            value,
            ["name", "displayName", "fullyQualifiedName", "value"],
            "Unknown View",
        )

    return text_value(value, "Unknown View")


def extract_count(metadata: dict[str, Any], possible_keys: list[str], fallback: int) -> int:
    value = first_existing(metadata, possible_keys)

    if isinstance(value, int):
        return value

    if isinstance(value, list):
        return len(value)

    if value is not None:
        try:
            return int(value)
        except (ValueError, TypeError):
            pass

    return fallback


# ============================================================
# EXTRACT MAIN COLLECTIONS
# ============================================================

columns_raw = first_existing(
    metadata,
    [
        "columns",
        "output_columns",
        "column_expressions",
        "outputColumns",
    ],
    [],
)

sources_raw = first_existing(
    metadata,
    [
        "sources",
        "source_objects",
        "physical_sources",
        "sourceObjects",
    ],
    [],
)

relationships_raw = first_existing(
    metadata,
    [
        "relationships",
        "joins",
        "lineage",
        "relationship_list",
    ],
    [],
)


columns = as_list(columns_raw)
sources = as_list(sources_raw)
relationships = as_list(relationships_raw)


# ============================================================
# METADATA DETAILS
# ============================================================

VIEW_NAME = asset_name(metadata)

SCHEMA_NAME = text_value(
    first_existing(
        metadata,
        ["schema", "schema_name", "database_schema"],
        "Unknown",
    ),
    "Unknown",
)

DATABASE_NAME = text_value(
    first_existing(
        metadata,
        ["database", "database_name"],
        "Unknown",
    ),
    "Unknown",
)

VIEW_TYPE = text_value(
    first_existing(
        metadata,
        ["type", "object_type", "view_type"],
        "VIEW",
    ),
    "VIEW",
)

MAPPING_COUNT = extract_count(
    metadata,
    ["mapping_comments", "mapping_comment_count", "mappingComments"],
    0,
)

CTE_COUNT = extract_count(
    metadata,
    ["ctes", "cte_count", "cteCount"],
    0,
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🗂️ Metadata Catalog POC</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">Automated Metadata Extraction from Azure DevOps SQL Repository</div>',
    unsafe_allow_html=True,
)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Metadata POC")

    st.write(f"**Asset**")
    st.write(VIEW_NAME)

    st.divider()

    st.write("**Metadata Source**")
    st.write("Azure DevOps")

    st.write("**Parser**")
    st.write("Python + SQLGlot")

    st.divider()

    st.caption("POC Architecture")

    st.code(
        "Azure DevOps\n"
        "      ↓\n"
        "REST API\n"
        "      ↓\n"
        "Python + SQLGlot\n"
        "      ↓\n"
        "Metadata JSON\n"
        "      ↓\n"
        "Metadata Catalog",
        language="text",
    )

    if st.button("🔄 Reload Metadata"):
        st.cache_data.clear()
        st.rerun()


# ============================================================
# TOP SUMMARY
# ============================================================

metric1, metric2, metric3, metric4 = st.columns(4)

with metric1:
    st.metric(
        "Data Asset",
        VIEW_NAME,
    )

with metric2:
    st.metric(
        "Source Objects",
        len(sources),
    )

with metric3:
    st.metric(
        "Columns",
        len(columns),
    )

with metric4:
    st.metric(
        "Relationships",
        len(relationships),
    )


st.divider()


# ============================================================
# TABS
# ============================================================

tab_overview, tab_columns, tab_sources, tab_lineage, tab_mapping = st.tabs(
    [
        "📋 Overview",
        "🧱 Columns",
        "📦 Source Objects",
        "🔗 Lineage",
        "📝 Mapping",
    ]
)


# ============================================================
# OVERVIEW
# ============================================================

with tab_overview:

    st.subheader(VIEW_NAME)

    col_a, col_b = st.columns(2)

    with col_a:

        st.markdown(
            """
            <div class="asset-card">
                <div class="small-label">Asset Type</div>
                <div class="small-value">VIEW</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="asset-card">
                <div class="small-label">Database</div>
                <div class="small-value">{DATABASE_NAME}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_b:

        st.markdown(
            f"""
            <div class="asset-card">
                <div class="small-label">Schema</div>
                <div class="small-value">{SCHEMA_NAME}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="asset-card">
                <div class="small-label">CTEs</div>
                <div class="small-value">{CTE_COUNT}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("Metadata Summary")

    summary_df = pd.DataFrame(
        {
            "Property": [
                "Asset Name",
                "Asset Type",
                "Database",
                "Schema",
                "Source System",
                "Parser",
                "Source Objects",
                "Output Columns",
                "Relationships",
                "CTEs",
                "Mapping Comments",
            ],
            "Value": [
                VIEW_NAME,
                VIEW_TYPE,
                DATABASE_NAME,
                SCHEMA_NAME,
                "Azure DevOps",
                "Python + SQLGlot",
                len(sources),
                len(columns),
                len(relationships),
                CTE_COUNT,
                MAPPING_COUNT,
            ],
        }
    )

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# COLUMNS
# ============================================================

with tab_columns:

    st.subheader("Output Columns")

    if not columns:

        st.info("Tidak ada column yang ditemukan di metadata.")

    else:

        rows = []

        for index, item in enumerate(columns, start=1):

            if isinstance(item, dict):

                name = first_existing(
                    item,
                    [
                        "name",
                        "column_name",
                        "column",
                        "alias",
                        "output_name",
                    ],
                    f"Column {index}",
                )

                expression = first_existing(
                    item,
                    [
                        "expression",
                        "source_expression",
                        "definition",
                        "source",
                        "sql",
                    ],
                    "",
                )

                rows.append(
                    {
                        "#": index,
                        "Column": text_value(name, f"Column {index}"),
                        "Expression": text_value(expression),
                    }
                )

            else:

                rows.append(
                    {
                        "#": index,
                        "Column": text_value(item),
                        "Expression": "",
                    }
                )

        df_columns = pd.DataFrame(rows)

        st.dataframe(
            df_columns,
            use_container_width=True,
            hide_index=True,
            column_config={
                "#": st.column_config.NumberColumn(
                    "#",
                    width="small",
                ),
                "Column": st.column_config.TextColumn(
                    "Column",
                    width="medium",
                ),
                "Expression": st.column_config.TextColumn(
                    "Source / Expression",
                    width="large",
                ),
            },
        )


# ============================================================
# SOURCES
# ============================================================

with tab_sources:

    st.subheader("Physical Source Objects")

    if not sources:

        st.info("Tidak ada source object yang ditemukan.")

    else:

        source_rows = []

        for index, item in enumerate(sources, start=1):

            if isinstance(item, dict):

                database = first_existing(
                    item,
                    ["database", "database_name", "db"],
                    "",
                )

                schema = first_existing(
                    item,
                    ["schema", "schema_name"],
                    "",
                )

                obj = first_existing(
                    item,
                    [
                        "name",
                        "object",
                        "object_name",
                        "table",
                        "table_name",
                    ],
                    "",
                )

                alias = first_existing(
                    item,
                    ["alias"],
                    "",
                )

                source_rows.append(
                    {
                        "#": index,
                        "Database": text_value(database),
                        "Schema": text_value(schema),
                        "Object": text_value(obj),
                        "Alias": text_value(alias),
                    }
                )

            else:

                source_rows.append(
                    {
                        "#": index,
                        "Database": "",
                        "Schema": "",
                        "Object": text_value(item),
                        "Alias": "",
                    }
                )

        df_sources = pd.DataFrame(source_rows)

        st.dataframe(
            df_sources,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# LINEAGE
# ============================================================

with tab_lineage:

    st.subheader("Lineage / Relationships")

    st.caption(
        "Relationship yang berhasil diekstrak dari SQL."
    )

    if not relationships:

        st.info(
            "Belum ditemukan relationship/lineage."
        )

    else:

        rows = []

        for index, item in enumerate(relationships, start=1):

            if isinstance(item, dict):

                source = first_existing(
                    item,
                    [
                        "source",
                        "from",
                        "left",
                        "source_object",
                        "upstream",
                    ],
                    "",
                )

                target = first_existing(
                    item,
                    [
                        "target",
                        "to",
                        "right",
                        "target_object",
                        "downstream",
                    ],
                    "",
                )

                relation_type = first_existing(
                    item,
                    [
                        "type",
                        "relationship",
                        "join_type",
                    ],
                    "RELATED",
                )

                condition = first_existing(
                    item,
                    [
                        "condition",
                        "on",
                        "join_condition",
                    ],
                    "",
                )

            else:

                source = item
                target = ""
                relation_type = "RELATED"
                condition = ""

            rows.append(
                {
                    "#": index,
                    "Source": text_value(source),
                    "Target": text_value(target),
                    "Relationship": text_value(relation_type, "RELATED"),
                    "Condition": text_value(condition),
                }
            )

        df_lineage = pd.DataFrame(rows)

        st.dataframe(
            df_lineage,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        st.subheader("Lineage Preview")

        for row in rows[:30]:

            source = row["Source"]
            target = row["Target"]

            if source and target:

                st.markdown(
                    f"""
                    <div class="lineage-box">
                        <b>{source}</b>
                        &nbsp;&nbsp; → &nbsp;&nbsp;
                        <b>{target}</b>
                        <br>
                        <span class="small-label">
                            {row["Relationship"]}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            elif source:

                st.markdown(
                    f"""
                    <div class="lineage-box">
                        <b>{source}</b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ============================================================
# MAPPING
# ============================================================

with tab_mapping:

    st.subheader("Migration / Mapping Documentation")

    # Coba beberapa kemungkinan field mapping
    mapping_raw = first_existing(
        metadata,
        [
            "mapping_comments",
            "mapping",
            "mappings",
            "mappingComments",
        ],
        [],
    )

    mappings = as_list(mapping_raw)

    if not mappings:

        st.info(
            f"Mapping comments terdeteksi: {MAPPING_COUNT}"
        )

        st.write(
            "Detail mapping tidak memiliki struktur list yang dapat ditampilkan."
        )

    else:

        mapping_rows = []

        for index, item in enumerate(mappings, start=1):

            if isinstance(item, dict):

                source = first_existing(
                    item,
                    [
                        "source",
                        "source_file",
                        "source_object",
                    ],
                    "",
                )

                target = first_existing(
                    item,
                    [
                        "target",
                        "target_column",
                        "column",
                    ],
                    "",
                )

                comment = first_existing(
                    item,
                    [
                        "comment",
                        "mapping",
                        "description",
                        "note",
                    ],
                    "",
                )

                mapping_rows.append(
                    {
                        "#": index,
                        "Source": text_value(source),
                        "Target": text_value(target),
                        "Comment": text_value(comment),
                    }
                )

            else:

                mapping_rows.append(
                    {
                        "#": index,
                        "Source": "",
                        "Target": "",
                        "Comment": text_value(item),
                    }
                )

        df_mapping = pd.DataFrame(mapping_rows)

        st.dataframe(
            df_mapping,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# RAW JSON
# ============================================================

with st.expander("🔎 Developer View — Raw Metadata JSON"):

    st.json(metadata)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "POC: Azure DevOps → REST API → Python + SQLGlot → Metadata Catalog"
)