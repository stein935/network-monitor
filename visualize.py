#!/usr/bin/env python3

import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path


def visualize_network_data(csv_file):
    """
    Visualize network monitoring data from CSV file.
    Shows response time and connection success rate over time.
    """
    # Read CSV
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()  # Remove any whitespace from column names

    # Convert timestamp to datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Convert response_time to numeric (null becomes NaN)
    df["response_time"] = pd.to_numeric(df["response_time"], errors="coerce")

    # Calculate success rate percentage
    df["success_rate"] = (df["success_count"] / df["total_count"]) * 100

    # Create figure with secondary y-axis
    fig = go.Figure()

    # Plot 1: Response Time (primary y-axis, left) - Gruvbox blue
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["response_time"],
            mode="lines+markers",
            name="Response Time (ms)",
            line=dict(color="#83a598", width=2),
            marker=dict(size=4),
            hovertemplate="<b>%{x}</b><br>Response: %{y:.2f}ms<extra></extra>",
            yaxis="y",
        )
    )

    # Plot 2: Success Rate (secondary y-axis, right) - Gruvbox colors
    colors = df["success_rate"].apply(
        lambda x: "#b8bb26" if x == 100 else "#fb4934" if x == 0 else "#fe8019"
    )

    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["success_rate"],
            mode="lines+markers",
            name="Success Rate (%)",
            line=dict(color="#8ec07c", width=2),
            marker=dict(size=6, color=colors),
            fill="tozeroy",
            fillcolor="rgba(142, 192, 124, 0.2)",
            hovertemplate="<b>%{x}</b><br>Success: %{y:.1f}%<extra></extra>",
            yaxis="y2",
        )
    )

    # Update layout with dual y-axes - Gruvbox dark theme
    fig.update_layout(
        title=dict(
            text=f"Network Monitoring Dashboard<br><sub>{csv_file.name}</sub>",
            x=0.5,
            xanchor="center",
            pad=dict(b=20),
            font=dict(color="#fe8019", size=20),
        ),
        xaxis=dict(
            title="Time",
            gridcolor="#504945",
            color="#ebdbb2",
        ),
        yaxis=dict(
            title="Response Time (ms)",
            side="left",
            showgrid=True,
            gridcolor="#504945",
            color="#ebdbb2",
        ),
        yaxis2=dict(
            title="Success Rate (%)",
            overlaying="y",
            side="right",
            range=[0, 105],
            showgrid=False,
            color="#ebdbb2",
        ),
        height=600,
        hovermode="x unified",
        paper_bgcolor="#1d2021",
        plot_bgcolor="#282828",
        font=dict(color="#ebdbb2", family="monospace"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5,
            bgcolor="#3c3836",
            bordercolor="#665c54",
            borderwidth=1,
            font=dict(color="#ebdbb2"),
        ),
        margin=dict(b=120),
    )

    # Calculate statistics
    stats = {
        "avg_response": df["response_time"].mean(),
        "min_response": df["response_time"].min(),
        "max_response": df["response_time"].max(),
        "avg_success_rate": df["success_rate"].mean(),
        "total_samples": len(df),
        "disconnections": len(df[df["success_rate"] == 0]),
    }

    print("\n📊 Network Statistics:")
    print(f"   Average Response Time: {stats['avg_response']:.2f}ms")
    print(
        f"   Min/Max Response Time: {stats['min_response']:.2f}ms / {stats['max_response']:.2f}ms"
    )
    print(f"   Average Success Rate: {stats['avg_success_rate']:.1f}%")
    print(f"   Total Samples: {stats['total_samples']}")
    print(f"   Complete Disconnections: {stats['disconnections']}")
    print()

    # Save visualization
    # Create html directory in the date folder (parent of parent of csv file)
    html_dir = csv_file.parent.parent / "html"
    html_dir.mkdir(exist_ok=True)
    output_file = html_dir / f"{csv_file.stem}_visualization.html"
    fig.write_html(str(output_file))
    print(f"✅ Visualization saved to: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python visualize.py <path_to_csv>")
        print("\nExample:")
        print("  python visualize.py logs/2025-10-30/monitor_20251030_161404.csv")
        sys.exit(1)

    csv_path = Path(sys.argv[1])

    if not csv_path.exists():
        print(f"❌ Error: File not found: {csv_path}")
        sys.exit(1)

    visualize_network_data(csv_path)
