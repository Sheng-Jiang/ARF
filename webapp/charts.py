"""Pyecharts Chart Generators for stock prices and backtesting results."""
import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Bar, Grid, Kline, Line


def split_data(df: pd.DataFrame) -> tuple[list[str], list[list[float]], pd.Series, list[list[float]]]:
    """Helper to split pandas DataFrame into pyecharts-compatible formats."""
    # Standardise column names from English or Chinese
    date_col = "日期" if "日期" in df.columns else "date"
    open_col = "开盘" if "开盘" in df.columns else "open"
    close_col = "收盘" if "收盘" in df.columns else "close"
    low_col = "最低" if "最低" in df.columns else "low"
    high_col = "最高" if "最高" in df.columns else "high"
    vol_col = "成交量" if "成交量" in df.columns else "volume"
    
    # Format date as YYYY-MM-DD string
    df_temp = df.copy()
    df_temp[date_col] = pd.to_datetime(df_temp[date_col]).dt.strftime("%Y-%m-%d")
    
    x_data = df_temp[date_col].values.tolist()
    y_data = df_temp[[open_col, close_col, low_col, high_col]].values.tolist()
    df_close = df_temp[close_col]

    df_temp["index"] = df_temp.index
    df_temp["rise"] = df_temp[[open_col, close_col]].apply(lambda x: 1 if x.iloc[0] > x.iloc[1] else -1, axis=1)
    y_vol = df_temp[["index", vol_col, "rise"]].values.tolist()
    return x_data, y_data, df_close, y_vol

def calculate_ma(day_count: int, df_close: pd.Series) -> list[float]:
    """Calculate moving average as a list of rounded floats or '-' for NaNs."""
    df_ma = df_close.rolling(day_count).mean().round(2).fillna("-")
    return df_ma.values.tolist()

def draw_pro_kline(df: pd.DataFrame, static: bool = False) -> Grid:
    """Draw a professional candlestick chart with volume and MA lines.

    When ``static`` (used on phones), the chart becomes a fixed graphic: it shows
    only the most recent ~90 bars and drops the inside data-zoom, tooltip and
    axis-pointer so it cannot capture touch gestures and hijack page scrolling.
    """
    if static:
        df = df.tail(90)
    x_data, y_data, df_close, y_vol = split_data(df)

    # Touch-capturing interactions are stripped on mobile so the page scrolls past
    # the chart instead of panning it.
    if static:
        datazoom_opts: list = []
        tooltip_opts = opts.TooltipOpts(is_show=False)
    else:
        datazoom_opts = [
            opts.DataZoomOpts(
                is_show=False,
                type_="inside",
                xaxis_index=[0, 1],
                range_start=80,
                range_end=100,
            ),
            opts.DataZoomOpts(
                is_show=True,
                xaxis_index=[0, 1],
                type_="slider",
                pos_top="85%",
                range_start=80,
                range_end=100,
            ),
        ]
        tooltip_opts = opts.TooltipOpts(
            trigger="axis",
            axis_pointer_type="cross",
            background_color="rgba(245, 245, 245, 0.8)",
            border_width=1,
            border_color="#ccc",
            textstyle_opts=opts.TextStyleOpts(color="#000"),
        )

    kline_global_opts = dict(
        legend_opts=opts.LegendOpts(is_show=False, pos_bottom=10, pos_left="center"),
        datazoom_opts=datazoom_opts,
        yaxis_opts=opts.AxisOpts(
            is_scale=True,
            splitarea_opts=opts.SplitAreaOpts(is_show=True, areastyle_opts=opts.AreaStyleOpts(opacity=1)),
        ),
        tooltip_opts=tooltip_opts,
        visualmap_opts=opts.VisualMapOpts(
            is_show=False,
            dimension=2,
            series_index=5,
            is_piecewise=True,
            pieces=[
                {"value": 1, "color": "#00da3c"},
                {"value": -1, "color": "#ec0000"},
            ],
        ),
        axispointer_opts=opts.AxisPointerOpts(
            is_show=not static,
            link=[{"xAxisIndex": "all"}],
            label=opts.LabelOpts(background_color="#777"),
        ),
    )
    if not static:
        kline_global_opts["brush_opts"] = opts.BrushOpts(
            x_axis_index="all",
            brush_link="all",
            out_of_brush={"colorAlpha": 0.1},
            brush_type="lineX",
        )

    kline = (
        Kline()
        .add_xaxis(xaxis_data=x_data)
        .add_yaxis(
            series_name="日K",
            y_axis=y_data,
            itemstyle_opts=opts.ItemStyleOpts(color="#ec0000", color0="#00da3c"),
        )
        .set_global_opts(**kline_global_opts)
    )

    line = (
        Line()
        .add_xaxis(xaxis_data=x_data)
        .add_yaxis(
            series_name="MA5",
            y_axis=calculate_ma(5, df_close),
            is_smooth=True,
            is_hover_animation=False,
            linestyle_opts=opts.LineStyleOpts(width=2, opacity=0.7),
            label_opts=opts.LabelOpts(is_show=False),
        )
        .add_yaxis(
            series_name="MA10",
            y_axis=calculate_ma(10, df_close),
            is_smooth=True,
            is_hover_animation=False,
            linestyle_opts=opts.LineStyleOpts(width=2, opacity=0.7),
            label_opts=opts.LabelOpts(is_show=False),
        )
        .add_yaxis(
            series_name="MA20",
            y_axis=calculate_ma(20, df_close),
            is_smooth=True,
            is_hover_animation=False,
            linestyle_opts=opts.LineStyleOpts(width=2, opacity=0.7),
            label_opts=opts.LabelOpts(is_show=False),
        )
        .add_yaxis(
            series_name="MA30",
            y_axis=calculate_ma(30, df_close),
            is_smooth=True,
            is_hover_animation=False,
            linestyle_opts=opts.LineStyleOpts(width=2, opacity=0.7),
            label_opts=opts.LabelOpts(is_show=False),
        )
        .set_global_opts(xaxis_opts=opts.AxisOpts(type_="category"))
    )

    bar = (
        Bar()
        .add_xaxis(xaxis_data=x_data)
        .add_yaxis(
            series_name="成交量",
            y_axis=y_vol,
            xaxis_index=1,
            yaxis_index=1,
            label_opts=opts.LabelOpts(is_show=False),
        )
        .set_global_opts(
            xaxis_opts=opts.AxisOpts(
                type_="category",
                is_scale=True,
                grid_index=1,
                boundary_gap=True,
                axisline_opts=opts.AxisLineOpts(is_on_zero=False),
                axistick_opts=opts.AxisTickOpts(is_show=False),
                splitline_opts=opts.SplitLineOpts(is_show=False),
                axislabel_opts=opts.LabelOpts(is_show=False),
                split_number=20,
                min_="dataMin",
                max_="dataMax",
            ),
            yaxis_opts=opts.AxisOpts(
                grid_index=1,
                is_scale=True,
                split_number=2,
                axislabel_opts=opts.LabelOpts(is_show=False),
                axisline_opts=opts.AxisLineOpts(is_show=False),
                axistick_opts=opts.AxisTickOpts(is_show=False),
                splitline_opts=opts.SplitLineOpts(is_show=False),
            ),
            legend_opts=opts.LegendOpts(is_show=False),
        )
    )

    # Overlap Kline and Line
    overlap_kline_line = kline.overlap(line)

    # Grid layout combining price chart and volume chart
    grid_chart = Grid(
        init_opts=opts.InitOpts(
            animation_opts=opts.AnimationOpts(animation=False),
            width="100%",
        )
    )
    grid_chart.add(
        overlap_kline_line,
        grid_opts=opts.GridOpts(pos_left="5%", pos_right="5%", height="55%"),
    )
    grid_chart.add(
        bar,
        grid_opts=opts.GridOpts(pos_left="5%", pos_right="5%", pos_top="68%", height="15%"),
    )

    return grid_chart

def draw_result_bar(df: pd.DataFrame, n_scores: int = 3) -> Bar:
    """Draw a bar chart comparing performance metrics for different backtest parameters."""
    params_columns = df.columns[:-n_scores]
    scores_columns = df.columns[-n_scores:]
    
    # Custom x-axis labels describing the parameter combinations
    x_data = (
        df[params_columns]
        .apply(
            lambda x: "\n".join([f"{name}: {value}" for name, value in zip(params_columns, x, strict=False)]),
            axis=1,
        )
        .values.tolist()
    )
    
    bar = (
        Bar()
        .add_xaxis(x_data)
        .set_global_opts(
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
            legend_opts=opts.LegendOpts(selected_mode="single"),
        )
    )
    for col in scores_columns:
        bar.add_yaxis(col, df[col].values.tolist())
        
    bar.set_series_opts(
        label_opts=opts.LabelOpts(is_show=False),
        markpoint_opts=opts.MarkPointOpts(
            data=[
                opts.MarkPointItem(type_="max", name="最大值"),
                opts.MarkPointItem(type_="min", name="最小值"),
            ]
        ),
    )

    return bar
