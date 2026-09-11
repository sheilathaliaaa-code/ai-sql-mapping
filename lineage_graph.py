import streamlit as st
import streamlit.components.v1 as components
import json
import html


def render_lineage_graph(mappings, target_table="Target View"):

    nodes = []
    edges = []

    node_ids = set()

    def add_node(node_id, label, node_type):
        if node_id not in node_ids:
            node_ids.add(node_id)

            nodes.append({
                "data": {
                    "id": node_id,
                    "label": label,
                    "type": node_type
                }
            })

    for idx, mapping in enumerate(mappings):

        target_column = mapping.get("target_column", "")
        transformation = mapping.get("transformation", "DIRECT")

        target_id = f"target_{target_column}"

        add_node(
            target_id,
            target_column,
            "target"
        )

        source_columns = mapping.get("source_columns", [])

        for source_idx, source in enumerate(source_columns):

            source_table = source.get("source_table", "")
            source_column = source.get("source_column", "")

            source_id = (
                f"source_{idx}_{source_idx}"
            )

            add_node(
                source_id,
                f"{source_table}.{source_column}",
                "source"
            )

            edges.append({
                "data": {
                    "id": f"edge_{idx}_{source_idx}",
                    "source": source_id,
                    "target": target_id,
                    "transformation": transformation
                }
            })

    graph_data = {
        "nodes": nodes,
        "edges": edges
    }

    graph_json = json.dumps(graph_data)

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>

    <script src="https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"></script>

    <style>

    body {{
        margin: 0;
        font-family: Arial, sans-serif;
        background: white;
    }}

    #cy {{
        width: 100%;
        height: 650px;
        border: 1px solid #ddd;
        border-radius: 12px;
    }}

    #details {{
        margin-top: 12px;
        padding: 15px;
        border-radius: 10px;
        background: #f7f7f7;
        border: 1px solid #ddd;
        font-family: Arial;
    }}

    .title {{
        font-weight: bold;
        font-size: 16px;
        margin-bottom: 8px;
    }}

    .item {{
        margin: 5px 0;
    }}

    </style>

    </head>

    <body>

    <div id="cy"></div>

    <div id="details">
        <div class="title">
            Click a column to view its lineage
        </div>

        <div class="item">
            Select a source or target column.
        </div>
    </div>

    <script>

    const graphData = {graph_json};

    const cy = cytoscape({{
        container: document.getElementById('cy'),

        elements: graphData,

        style: [

            {{
                selector: 'node',

                style: {{
                    'label': 'data(label)',
                    'text-wrap': 'wrap',
                    'text-max-width': '180px',

                    'width': '180px',
                    'height': '50px',

                    'background-color': '#ffffff',

                    'border-width': 2,
                    'border-color': '#888',

                    'font-size': 12,

                    'text-valign': 'center',
                    'text-halign': 'center'
                }}
            }},

            {{
                selector: 'node[type="source"]',

                style: {{
                    'background-color': '#eef5ff',
                    'border-color': '#4a90e2'
                }}
            }},

            {{
                selector: 'node[type="target"]',

                style: {{
                    'background-color': '#fff4e6',
                    'border-color': '#ff8a00'
                }}
            }},

            {{
                selector: 'edge',

                style: {{

                    'width': 2,

                    'line-color': '#999',

                    'target-arrow-color': '#999',

                    'target-arrow-shape': 'triangle',

                    'curve-style': 'bezier',

                    'label': 'data(transformation)',

                    'font-size': 9,

                    'text-background-color': '#ffffff',

                    'text-background-opacity': 1
                }}
            }},

            {{
                selector: '.highlight',

                style: {{
                    'border-width': 4,
                    'border-color': '#ff4b4b'
                }}
            }},

            {{
                selector: '.highlight-edge',

                style: {{
                    'width': 4,
                    'line-color': '#ff4b4b',
                    'target-arrow-color': '#ff4b4b'
                }}
            }}

        ],

        layout: {{
            name: 'breadthfirst',

            directed: true,

            padding: 40,

            spacingFactor: 1.5
        }}
    }});


    cy.on('tap', 'node', function(event) {{

        const node = event.target;

        cy.elements().removeClass('highlight highlight-edge');

        node.addClass('highlight');

        const connectedEdges = node.connectedEdges();

        connectedEdges.addClass('highlight-edge');

        connectedEdges.connectedNodes().addClass('highlight');

        let html = '';

        html += '<div class="title">';

        html += node.data('label');

        html += '</div>';

        html += '<div class="item">';

        html += '<b>Type:</b> ';

        html += node.data('type');

        html += '</div>';

        html += '<div class="item">';

        html += '<b>Relationships:</b> ';

        html += connectedEdges.length;

        html += '</div>';

        connectedEdges.forEach(function(edge) {{

            html += '<div class="item">';

            html += edge.data('source');

            html += ' → ';

            html += edge.data('target');

            html += ' | ';

            html += edge.data('transformation');

            html += '</div>';

        }});

        document.getElementById('details').innerHTML = html;

    }});

    </script>

    </body>
    </html>
    """

    components.html(
        html_code,
        height=750,
        scrolling=False
    )