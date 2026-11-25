"""Reusable Plotly charts."""
import plotly.graph_objects as go


def gauge(value: float, title: str = "", height: int = 220) -> go.Figure:
    color = "#e74c3c" if value < 40 else "#f39c12" if value < 60 else "#2ecc71" if value < 80 else "#6C5CE7"
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value, title={"text": title},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": color},
               "steps": [{"range": [0, 40], "color": "rgba(231,76,60,.15)"},
                         {"range": [40, 60], "color": "rgba(243,156,18,.15)"},
                         {"range": [60, 80], "color": "rgba(46,204,113,.15)"},
                         {"range": [80, 100], "color": "rgba(108,92,231,.15)"}]}))
    fig.update_layout(height=height, margin=dict(t=40, b=10, l=20, r=20))
    return fig


def radar(labels: list[str], values: list[float], max_value: float = 100, height: int = 360,
          name: str = "Score") -> go.Figure:
    fig = go.Figure(go.Scatterpolar(r=list(values) + [values[0]], theta=list(labels) + [labels[0]],
                                    fill="toself", name=name, line_color="#6C5CE7"))
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, max_value])), showlegend=False,
                      height=height, margin=dict(t=30, b=30, l=50, r=50))
    return fig
