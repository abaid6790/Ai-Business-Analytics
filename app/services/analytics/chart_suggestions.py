"""
Picks sensible default charts for a dataset based on its column types,
so the EDA page has something meaningful to show immediately without the
user configuring anything (spec section 6: "Automatically select suitable
charts based on column types").
"""

MAX_AUTO_CHARTS = 8
MAX_CATEGORIES_FOR_BAR = 15


def suggest_charts(stats: dict) -> list:
    """
    `stats` is the dict returned by compute_descriptive_stats(). Returns a
    list of chart specs: {title, chart_type, x, y, reason}.
    """
    suggestions = []

    numeric_cols = stats["numeric_columns"]
    categorical_cols = stats["categorical_columns"]
    datetime_cols = stats["datetime_columns"]

    # Histograms for numeric columns (distribution shape)
    for col in numeric_cols[:4]:
        suggestions.append({
            "title": f"Distribution of {col}",
            "chart_type": "histogram",
            "x": col,
            "y": None,
            "reason": "Numeric column — shows the distribution of values.",
        })

    # Bar charts for categorical columns with a manageable number of categories
    for col in categorical_cols:
        unique_count = stats["categorical"].get(col, {}).get("unique_count", 0)
        if 0 < unique_count <= MAX_CATEGORIES_FOR_BAR:
            suggestions.append({
                "title": f"Count by {col}",
                "chart_type": "bar",
                "x": col,
                "y": None,
                "reason": "Categorical column with a manageable number of categories.",
            })
        if len(suggestions) >= MAX_AUTO_CHARTS:
            break

    # Line chart for date + numeric combination (trend over time)
    if datetime_cols and numeric_cols:
        suggestions.append({
            "title": f"{numeric_cols[0]} over {datetime_cols[0]}",
            "chart_type": "line",
            "x": datetime_cols[0],
            "y": numeric_cols[0],
            "reason": "Date column paired with a numeric column — shows trend over time.",
        })

    # Scatter plot for two numeric columns (relationship)
    if len(numeric_cols) >= 2:
        suggestions.append({
            "title": f"{numeric_cols[0]} vs {numeric_cols[1]}",
            "chart_type": "scatter",
            "x": numeric_cols[0],
            "y": numeric_cols[1],
            "reason": "Two numeric columns — shows their relationship.",
        })

    return suggestions[:MAX_AUTO_CHARTS]
