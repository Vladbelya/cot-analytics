import json
import pandas as pd
from src.config import MARKETS

def render_tv_gex_chart(df_hist, levels_data, spot_price, zones_data=None):
    if df_hist.empty:
        return "<div style='color: white; text-align: center; padding: 20px;'>Нет исторических данных для графика</div>"
    
    # Format data
    chart_data = []
    for _, row in df_hist.iterrows():
        # Timestamp is in seconds
        timestamp = int(row['datetime'].timestamp())
        chart_data.append({
            'time': timestamp,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
        })
    
    chart_data_json = json.dumps(chart_data)
    
    # Only keep levels within 15% range of spot to avoid squishing
    filtered_levels = []
    for lvl in levels_data:
        if spot_price * 0.85 <= lvl['price'] <= spot_price * 1.15:
            filtered_levels.append(lvl)
            
    levels_json = json.dumps(filtered_levels)

    # Process zones
    if zones_data is None:
        zones_data = []
    filtered_zones = []
    for zone in zones_data:
        low = spot_price * 0.85
        high = spot_price * 1.15
        if not (zone['max_price'] < low or zone['min_price'] > high):
            filtered_zones.append(zone)
    zones_json = json.dumps(filtered_zones)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: #0b0f19;
                overflow: hidden;
            }}
            #chart-container {{
                width: 100%;
                height: 580px;
                position: relative;
            }}
            #legend {{
                position: absolute;
                left: 15px;
                top: 15px;
                z-index: 10;
                font-family: 'Inter', -apple-system, sans-serif;
                font-size: 11px;
                line-height: 18px;
                color: #e2e8f0;
                background: rgba(15, 23, 42, 0.7);
                backdrop-filter: blur(4px);
                border: 1px solid rgba(255,255,255,0.05);
                padding: 10px 14px;
                border-radius: 8px;
                pointer-events: none;
            }}
            .legend-title {{
                font-size: 14px;
                font-weight: 700;
                color: #ffffff;
                margin-bottom: 4px;
                letter-spacing: -0.01em;
            }}
            .legend-item {{
                margin-right: 12px;
                display: inline-block;
            }}
            .legend-value {{
                font-weight: 600;
                font-family: monospace;
            }}
        </style>
        <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    </head>
    <body>
        <div id="legend">
            <div class="legend-title">BTC/USDT (GEX Tracker)</div>
            <div id="legend-details">Загрузка данных...</div>
        </div>
        <div id="chart-container"></div>
        <script>
            // Custom Primitive to draw horizontal zones/bands
            class HorizontalZonePrimitive {{
                constructor(minPrice, maxPrice, color) {{
                    this.minPrice = minPrice;
                    this.maxPrice = maxPrice;
                    this.color = color;
                    this.y1 = null;
                    this.y2 = null;
                    this._paneViews = [{{
                        renderer: () => {{
                            return {{
                                draw: (target) => {{
                                    if (this.y1 === null || this.y2 === null) return;
                                    target.useBitmapCoordinateSpace(scope => {{
                                        const ctx = scope.context;
                                        const yTop = Math.min(this.y1, this.y2) * scope.verticalPixelRatio;
                                        const yBottom = Math.max(this.y1, this.y2) * scope.verticalPixelRatio;
                                        const width = scope.bitmapSize.width;
                                        ctx.fillStyle = this.color;
                                        ctx.fillRect(0, yTop, width, yBottom - yTop);
                                    }});
                                }}
                            }};
                        }}
                    }}];
                }}
                attached(params) {{
                    this.series = params.series;
                }}
                paneViews() {{
                    return this._paneViews;
                }}
                updateAllViews() {{
                    if (!this.series) return;
                    this.y1 = this.series.priceToCoordinate(this.minPrice);
                    this.y2 = this.series.priceToCoordinate(this.maxPrice);
                }}
            }}

            const chartData = {chart_data_json};
            const levels = {levels_json};
            const zones = {zones_json};
            
            const container = document.getElementById('chart-container');
            const chart = LightweightCharts.createChart(container, {{
                width: container.clientWidth,
                height: 580,
                layout: {{
                    background: {{ type: 'solid', color: '#0b0f19' }},
                    textColor: '#94a3b8',
                    fontSize: 11,
                    fontFamily: 'Inter, sans-serif',
                }},
                grid: {{
                    vertLines: {{ color: 'rgba(255, 255, 255, 0.02)' }},
                    horzLines: {{ color: 'rgba(255, 255, 255, 0.02)' }},
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: {{
                        color: 'rgba(148, 163, 184, 0.4)',
                        width: 1,
                        style: 3, // dashed
                        labelBackgroundColor: '#1e293b',
                    }},
                    horzLine: {{
                        color: 'rgba(148, 163, 184, 0.4)',
                        width: 1,
                        style: 3, // dashed
                        labelBackgroundColor: '#1e293b',
                    }},
                }},
                rightPriceScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.07)',
                    textColor: '#94a3b8',
                    autoScale: true,
                }},
                timeScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.07)',
                    textColor: '#94a3b8',
                    timeVisible: true,
                    secondsVisible: false,
                }},
            }});
            
            const candleSeries = chart.addCandlestickSeries({{
                upColor: '#10b981',
                downColor: '#ef4444',
                borderDownColor: '#ef4444',
                borderUpColor: '#10b981',
                wickDownColor: '#ef4444',
                wickUpColor: '#10b981',
            }});
            
            candleSeries.setData(chartData);
            
            // Draw zones
            zones.forEach(zone => {{
                const zonePrimitive = new HorizontalZonePrimitive(zone.min_price, zone.max_price, zone.color);
                candleSeries.attachPrimitive(zonePrimitive);
            }});
            
            // Draw levels
            levels.forEach(level => {{
                candleSeries.createPriceLine({{
                    price: level.price,
                    color: level.color,
                    lineWidth: 1.5,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: level.title,
                }});
            }});
            
            // Fit content
            chart.timeScale().fitContent();
            
            // Legend details
            const legendDetails = document.getElementById('legend-details');
            
            function updateLegend(candle) {{
                if (!candle) return;
                const isGreen = candle.close >= candle.open;
                const color = isGreen ? '#10b981' : '#ef4444';
                const dateStr = new Date(candle.time * 1000).toLocaleString('ru-RU', {{
                    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                }});
                
                legendDetails.innerHTML = `
                    <span class="legend-item">Время: <span style="color: #cbd5e1">${{dateStr}}</span></span>
                    <span class="legend-item">О: <span style="color: ${{color}}" class="legend-value">${{candle.open.toFixed(2)}}</span></span>
                    <span class="legend-item">В: <span style="color: ${{color}}" class="legend-value">${{candle.high.toFixed(2)}}</span></span>
                    <span class="legend-item">Н: <span style="color: ${{color}}" class="legend-value">${{candle.low.toFixed(2)}}</span></span>
                    <span class="legend-item">С: <span style="color: ${{color}}" class="legend-value">${{candle.close.toFixed(2)}}</span></span>
                `;
            }}
            
            // Show last candle initially
            if (chartData.length > 0) {{
                updateLegend(chartData[chartData.length - 1]);
            }}
            
            chart.subscribeCrosshairMove(param => {{
                if (param.time) {{
                    const candle = param.seriesData.get(candleSeries);
                    if (candle) {{
                        updateLegend(candle);
                    }}
                }} else if (chartData.length > 0) {{
                    updateLegend(chartData[chartData.length - 1]);
                }}
            }});
            
            function resizeChart() {{
                const w = container.clientWidth || window.innerWidth;
                const h = container.clientHeight || 600;
                chart.resize(w, h);
            }}
            window.addEventListener('resize', resizeChart);
            setTimeout(resizeChart, 100);
            setTimeout(resizeChart, 500);
        </script>
    </body>
    </html>
    """
    return html

def render_tv_cot_chart(df_plot, market_name, participant_name, z_up, z_low, pct_up, pct_low, color_up, color_low):
    if df_plot.empty:
        return "<div style='color: white; text-align: center; padding: 20px;'>Нет данных COT для графика</div>"
    
    # Format data
    chart_data = []
    for _, row in df_plot.iterrows():
        date_str = row['report_date'].strftime('%Y-%m-%d')
        chart_data.append({
            'time': date_str,
            'close': float(row['close']),
            'net_pct_oi': float(row['net_pct_oi']) if not pd.isna(row['net_pct_oi']) else 0.0,
            'percentile': float(row['cot_index_net_pct_oi_52w']) if not pd.isna(row['cot_index_net_pct_oi_52w']) else 50.0,
        })
    
    chart_data_json = json.dumps(chart_data)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: #0b0f19;
                color: #cbd5e1;
                font-family: 'Inter', -apple-system, sans-serif;
                overflow: hidden;
            }}
            .charts-container {{
                display: flex;
                flex-direction: column;
                gap: 8px;
                height: 630px;
                width: 100%;
            }}
            .chart-wrapper {{
                width: 100%;
                position: relative;
                border: 1px solid rgba(255, 255, 255, 0.03);
                border-radius: 6px;
                overflow: hidden;
            }}
            #wrapper-price {{
                flex: 2.2;
                min-height: 280px;
            }}
            #wrapper-percentile {{
                flex: 1.8;
                min-height: 220px;
            }}
            .chart-legend {{
                position: absolute;
                left: 12px;
                top: 8px;
                z-index: 10;
                font-size: 11px;
                background: rgba(15, 23, 42, 0.7);
                backdrop-filter: blur(4px);
                padding: 4px 10px;
                border-radius: 4px;
                border: 1px solid rgba(255,255,255,0.03);
                pointer-events: none;
            }}
            .legend-title {{
                font-weight: 700;
                color: #ffffff;
                display: inline-block;
                margin-right: 8px;
            }}
        </style>
        <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    </head>
    <body>
        <div class="charts-container">
            <div id="wrapper-price" class="chart-wrapper">
                <div class="chart-legend">
                    <span class="legend-title">{market_name.upper()} ({participant_name})</span>
                    <span id="legend-price">Ожидание...</span>
                </div>
                <div id="chart-price" style="width:100%; height:100%;"></div>
            </div>

            <div id="wrapper-percentile" class="chart-wrapper">
                <div class="chart-legend">
                    <span class="legend-title" style="color: #3498db">Перцентиль позиций (52н)</span>
                    <span id="legend-percentile">Ожидание...</span>
                </div>
                <div id="chart-percentile" style="width:100%; height:100%;"></div>
            </div>
        </div>
        
        <script>
            const data = {chart_data_json};
            const marketColor = "{MARKETS.get(market_name, {}).get("color", "#3498db")}";
            
            // Shared options
            const getOptions = (bgColor) => ({{
                layout: {{
                    background: {{ type: 'solid', color: bgColor }},
                    textColor: '#94a3b8',
                    fontSize: 10,
                    fontFamily: 'Inter, sans-serif',
                }},
                grid: {{
                    vertLines: {{ color: 'rgba(255, 255, 255, 0.02)' }},
                    horzLines: {{ color: 'rgba(255, 255, 255, 0.02)' }},
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: {{
                        color: 'rgba(148, 163, 184, 0.3)',
                        width: 1,
                        style: 3,
                    }},
                    horzLine: {{
                        color: 'rgba(148, 163, 184, 0.3)',
                        width: 1,
                        style: 3,
                    }},
                }},
                rightPriceScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.05)',
                    textColor: '#94a3b8',
                }},
                timeScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.05)',
                    textColor: '#94a3b8',
                    visible: false,
                }},
            }});
            
            // 1. Create Price Chart
            const priceWrapper = document.getElementById('wrapper-price');
            const priceChart = LightweightCharts.createChart(document.getElementById('chart-price'), getOptions('#0b0f19'));
            const priceSeries = priceChart.addAreaSeries({{
                lineColor: marketColor,
                topColor: marketColor + '1a',
                bottomColor: marketColor + '03',
                lineWidth: 2,
            }});
            
            const priceData = data.map(d => ({{ time: d.time, value: d.close }}));
            priceSeries.setData(priceData);
            

            
            // 3. Create Percentile Chart
            const pctWrapper = document.getElementById('wrapper-percentile');
            const pctOptions = getOptions('#0b0f19');
            pctOptions.timeScale.visible = true;
            const pctChart = LightweightCharts.createChart(document.getElementById('chart-percentile'), pctOptions);
            const pctSeries = pctChart.addLineSeries({{
                color: '#3498db',
                lineWidth: 2,
            }});
            
            const pctData = data.map(d => ({{ time: d.time, value: d.percentile }}));
            pctSeries.setData(pctData);
            
            // Percentile thresholds
            pctSeries.createPriceLine({{
                price: {pct_up},
                color: '{color_up}',
                lineWidth: 1.5,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: 'Pct-Up ({pct_up}%)',
            }});
            pctSeries.createPriceLine({{
                price: 50.0,
                color: 'rgba(255,255,255,0.2)',
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: true,
            }});
            pctSeries.createPriceLine({{
                price: {pct_low},
                color: '{color_low}',
                lineWidth: 1.5,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: 'Pct-Down ({pct_low}%)',
            }});
            
            // Fit timescale on all
            priceChart.timeScale().fitContent();
            
            // Synchronize visible ranges
            let isSyncing = false;
            const syncTimescales = (srcChart, destCharts) => {{
                srcChart.timeScale().subscribeVisibleLogicalRangeChange(range => {{
                    if (isSyncing || !range) return;
                    isSyncing = true;
                    destCharts.forEach(dest => {{
                        dest.timeScale().setVisibleLogicalRange(range);
                    }});
                    isSyncing = false;
                }});
            }};
            
            syncTimescales(priceChart, [pctChart]);
            syncTimescales(pctChart, [priceChart]);
            
            // Synchronize crosshairs
            const syncCrosshair = (srcChart, destCharts) => {{
                srcChart.subscribeCrosshairMove(param => {{
                    if (isSyncing) return;
                    isSyncing = true;
                    
                    if (!param.time || !param.point) {{
                        destCharts.forEach(dest => dest.setCrosshairPosition(null, null, null));
                        isSyncing = false;
                        updateLegends(param.time);
                        return;
                    }}
                    
                    destCharts.forEach(dest => {{
                        dest.setCrosshairPosition(null, param.point.x, null);
                    }});
                    
                    isSyncing = false;
                    updateLegends(param.time);
                }});
            }};
            
            syncCrosshair(priceChart, [pctChart]);
            syncCrosshair(pctChart, [priceChart]);
            
            // Legends
            const legPrice = document.getElementById('legend-price');
            const legPercentile = document.getElementById('legend-percentile');
            
            function updateLegends(time) {{
                let target = data[data.length - 1];
                if (time) {{
                    const match = data.find(d => d.time === time);
                    if (match) target = match;
                }}
                
                if (!target) return;
                
                legPrice.innerHTML = `<span style="color:#ffffff">$${{target.close.toLocaleString('en-US', {{minimumFractionDigits:2, maximumFractionDigits:4}})}}</span> <span style="color:#64748b">(${{target.time}})</span>`;
                legPercentile.innerHTML = `<span style="color:#3498db">${{target.percentile.toFixed(1)}}%</span>`;
            }}
            
            updateLegends(null);
            
            function resizeAll() {{
                priceChart.resize(priceWrapper.clientWidth, priceWrapper.clientHeight);
                pctChart.resize(pctWrapper.clientWidth, pctWrapper.clientHeight);
            }}
            
            window.addEventListener('resize', resizeAll);
            setTimeout(resizeAll, 100);
        </script>
    </body>
    </html>
    """
    return html

def render_tv_flows_chart(df_plot, market_name):
    if df_plot.empty:
        return "<div style='color: white; text-align: center; padding: 20px;'>Нет данных настроений для графика</div>"
    
    # Pre-calculate values in Python
    chart_data = []
    for _, row in df_plot.iterrows():
        date_str = row['report_date'].strftime('%Y-%m-%d')
        
        long_val = float(row['long_pct_oi']) if not pd.isna(row['long_pct_oi']) else 0.0
        short_val = float(row['short_pct_oi']) if not pd.isna(row['short_pct_oi']) else 0.0
        net_val = float(row['net']) if not pd.isna(row['net']) else 0.0
        
        chart_data.append({
            'time': date_str,
            'close': float(row['close']),
            'long_val': long_val,
            'short_val': short_val,
            'net_val': net_val
        })
        
    chart_data_json = json.dumps(chart_data)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: #0b0f19;
                color: #cbd5e1;
                font-family: 'Inter', -apple-system, sans-serif;
                overflow: hidden;
            }}
            .charts-container {{
                display: flex;
                flex-direction: column;
                gap: 8px;
                height: 730px;
                width: 100%;
            }}
            .chart-wrapper {{
                width: 100%;
                position: relative;
                border: 1px solid rgba(255, 255, 255, 0.03);
                border-radius: 6px;
                overflow: hidden;
            }}
            #wrapper-price {{
                flex: 2;
                min-height: 200px;
            }}
            #wrapper-long {{
                flex: 1.2;
                min-height: 130px;
            }}
            #wrapper-short {{
                flex: 1.2;
                min-height: 130px;
            }}
            #wrapper-net {{
                flex: 1.2;
                min-height: 130px;
            }}
            .chart-legend {{
                position: absolute;
                left: 12px;
                top: 8px;
                z-index: 10;
                font-size: 11px;
                background: rgba(15, 23, 42, 0.7);
                backdrop-filter: blur(4px);
                padding: 4px 10px;
                border-radius: 4px;
                border: 1px solid rgba(255,255,255,0.03);
                pointer-events: none;
            }}
            .legend-title {{
                font-weight: 700;
                color: #ffffff;
                display: inline-block;
                margin-right: 8px;
            }}
        </style>
        <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    </head>
    <body>
        <div class="charts-container">
            <div id="wrapper-price" class="chart-wrapper">
                <div class="chart-legend">
                    <span class="legend-title">{market_name.upper()} (Цена)</span>
                    <span id="legend-price">Ожидание...</span>
                </div>
                <div id="chart-price" style="width:100%; height:100%;"></div>
            </div>
            <div id="wrapper-long" class="chart-wrapper">
                <div class="chart-legend">
                    <span class="legend-title" style="color: #10b981">Long позиция (% от группы)</span>
                    <span id="legend-long">Ожидание...</span>
                </div>
                <div id="chart-long" style="width:100%; height:100%;"></div>
            </div>
            <div id="wrapper-short" class="chart-wrapper">
                <div class="chart-legend">
                    <span class="legend-title" style="color: #ef4444">Short позиция (% от группы)</span>
                    <span id="legend-short">Ожидание...</span>
                </div>
                <div id="chart-short" style="width:100%; height:100%;"></div>
            </div>
            <div id="wrapper-net" class="chart-wrapper">
                <div class="chart-legend">
                    <span class="legend-title" style="color: #f39c12">Чистая позиция (Net OI в контр.)</span>
                    <span id="legend-net">Ожидание...</span>
                </div>
                <div id="chart-net" style="width:100%; height:100%;"></div>
            </div>
        </div>
        
        <script>
            const data = {chart_data_json};
            const marketColor = "{MARKETS.get(market_name, {}).get("color", "#3498db")}";
            
            // Shared options
            const getOptions = (bgColor) => ({{
                layout: {{
                    background: {{ type: 'solid', color: bgColor }},
                    textColor: '#94a3b8',
                    fontSize: 10,
                    fontFamily: 'Inter, sans-serif',
                }},
                grid: {{
                    vertLines: {{ color: 'rgba(255, 255, 255, 0.02)' }},
                    horzLines: {{ color: 'rgba(255, 255, 255, 0.02)' }},
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: {{
                        color: 'rgba(148, 163, 184, 0.3)',
                        width: 1,
                        style: 3,
                    }},
                    horzLine: {{
                        color: 'rgba(148, 163, 184, 0.3)',
                        width: 1,
                        style: 3,
                    }},
                }},
                rightPriceScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.05)',
                    textColor: '#94a3b8',
                }},
                timeScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.05)',
                    textColor: '#94a3b8',
                    visible: false,
                }},
            }});
            
            // 1. Create Price Chart
            const priceWrapper = document.getElementById('wrapper-price');
            const priceChart = LightweightCharts.createChart(document.getElementById('chart-price'), getOptions('#0b0f19'));
            const priceSeries = priceChart.addAreaSeries({{
                lineColor: marketColor,
                topColor: marketColor + '1a',
                bottomColor: marketColor + '03',
                lineWidth: 2,
            }});
            
            const priceData = data.map(d => ({{ time: d.time, value: d.close }}));
            priceSeries.setData(priceData);
            
            // 2. Create Long % Chart (0-100%)
            const longWrapper = document.getElementById('wrapper-long');
            const longChart = LightweightCharts.createChart(document.getElementById('chart-long'), getOptions('#0b0f19'));
            const longSeries = longChart.addAreaSeries({{
                lineColor: '#10b981',
                topColor: 'rgba(16, 185, 129, 0.2)',
                bottomColor: 'rgba(16, 185, 129, 0.01)',
                lineWidth: 2,
            }});
            
            const longData = data.map(d => ({{ time: d.time, value: d.long_val }}));
            longSeries.setData(longData);
            
            // 3. Create Short % Chart (0-100%)
            const shortWrapper = document.getElementById('wrapper-short');
            const shortChart = LightweightCharts.createChart(document.getElementById('chart-short'), getOptions('#0b0f19'));
            const shortSeries = shortChart.addAreaSeries({{
                lineColor: '#ef4444',
                topColor: 'rgba(239, 68, 68, 0.2)',
                bottomColor: 'rgba(239, 68, 68, 0.01)',
                lineWidth: 2,
            }});
            
            const shortData = data.map(d => ({{ time: d.time, value: d.short_val }}));
            shortSeries.setData(shortData);
            
            // 4. Create Net % OI Chart (-100% to +100%)
            const netWrapper = document.getElementById('wrapper-net');
            const netOptions = getOptions('#0b0f19');
            netOptions.timeScale.visible = true;
            const netChart = LightweightCharts.createChart(document.getElementById('chart-net'), netOptions);
            const netSeries = netChart.addBaselineSeries({{
                baseValue: {{ type: 'price', price: 0.0 }},
                topLineColor: '#10b981',
                topFillColor1: 'rgba(16, 185, 129, 0.3)',
                topFillColor2: 'rgba(16, 185, 129, 0.05)',
                bottomLineColor: '#ef4444',
                bottomFillColor1: 'rgba(239, 68, 68, 0.05)',
                bottomFillColor2: 'rgba(239, 68, 68, 0.3)',
                lineWidth: 2,
                relativeGradient: true,
                priceFormat: {{ type: 'volume' }},
            }});
            
            const netData = data.map(d => ({{ time: d.time, value: d.net_val }}));
            netSeries.setData(netData);
            
            // Net zero reference line
            netSeries.createPriceLine({{
                price: 0.0,
                color: 'rgba(255, 255, 255, 0.3)',
                lineWidth: 1.5,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
            }});
            
            // Fit timescale or zoom to show last 30 bars by default
            const totalBars = data.length;
            if (totalBars > 30) {{
                priceChart.timeScale().setVisibleLogicalRange({{
                    from: totalBars - 30,
                    to: totalBars
                }});
            }} else {{
                priceChart.timeScale().fitContent();
            }}
            
            // Synchronize visible ranges
            let isSyncing = false;
            const syncTimescales = (srcChart, destCharts) => {{
                srcChart.timeScale().subscribeVisibleLogicalRangeChange(range => {{
                    if (isSyncing || !range) return;
                    isSyncing = true;
                    destCharts.forEach(dest => {{
                        dest.timeScale().setVisibleLogicalRange(range);
                    }});
                    isSyncing = false;
                }});
            }};
            
            syncTimescales(priceChart, [longChart, shortChart, netChart]);
            syncTimescales(longChart, [priceChart, shortChart, netChart]);
            syncTimescales(shortChart, [priceChart, longChart, netChart]);
            syncTimescales(netChart, [priceChart, longChart, shortChart]);
            
            // Synchronize crosshairs
            const syncCrosshair = (srcChart, destCharts) => {{
                srcChart.subscribeCrosshairMove(param => {{
                    if (isSyncing) return;
                    isSyncing = true;
                    
                    if (!param.time || !param.point) {{
                        destCharts.forEach(dest => dest.setCrosshairPosition(null, null, null));
                        isSyncing = false;
                        updateLegends(param.time);
                        return;
                    }}
                    
                    destCharts.forEach(dest => {{
                        dest.setCrosshairPosition(null, param.point.x, null);
                    }});
                    
                    isSyncing = false;
                    updateLegends(param.time);
                }});
            }};
            
            syncCrosshair(priceChart, [longChart, shortChart, netChart]);
            syncCrosshair(longChart, [priceChart, shortChart, netChart]);
            syncCrosshair(shortChart, [priceChart, longChart, netChart]);
            syncCrosshair(netChart, [priceChart, longChart, shortChart]);
            
            // Legends
            const legPrice = document.getElementById('legend-price');
            const legLong = document.getElementById('legend-long');
            const legShort = document.getElementById('legend-short');
            const legNet = document.getElementById('legend-net');
            
            function updateLegends(time) {{
                let target = data[data.length - 1];
                if (time) {{
                    const match = data.find(d => d.time === time);
                    if (match) target = match;
                }}
                
                if (!target) return;
                
                legPrice.innerHTML = `<span style="color:#ffffff">$${{target.close.toLocaleString('en-US', {{minimumFractionDigits:2, maximumFractionDigits:4}})}}</span> <span style="color:#64748b">(${{target.time}})</span>`;
                legLong.innerHTML = `<span style="color:#10b981">${{target.long_val.toFixed(2)}}%</span>`;
                legShort.innerHTML = `<span style="color:#ef4444">${{target.short_val.toFixed(2)}}%</span>`;
                legNet.innerHTML = `<span style="color:#f39c12">${{target.net_val >= 0 ? '+' : ''}}${{target.net_val.toLocaleString('en-US')}} контр.</span>`;
            }}
            
            updateLegends(null);
            
            function resizeAll() {{
                priceChart.resize(priceWrapper.clientWidth, priceWrapper.clientHeight);
                longChart.resize(longWrapper.clientWidth, longWrapper.clientHeight);
                shortChart.resize(shortWrapper.clientWidth, shortWrapper.clientHeight);
                netChart.resize(netWrapper.clientWidth, netWrapper.clientHeight);
            }}
            
            window.addEventListener('resize', resizeAll);
            setTimeout(resizeAll, 100);
        </script>
    </body>
    </html>
    """
    return html

def render_tv_macro_chart(df, date_col, value_col, color, title, height=300):
    if df.empty:
        return "<div style='color: white; text-align: center; padding: 20px;'>Нет данных для макро-графика</div>"
    
    # Format data
    chart_data = []
    for _, row in df.iterrows():
        if isinstance(row[date_col], pd.Timestamp) or hasattr(row[date_col], 'strftime'):
            date_str = row[date_col].strftime('%Y-%m-%d')
        else:
            date_str = str(row[date_col])
        
        if pd.isna(row[value_col]):
            continue
            
        chart_data.append({
            'time': date_str,
            'value': float(row[value_col])
        })
    
    chart_data_json = json.dumps(chart_data)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: #0b0f19;
                overflow: hidden;
            }}
            #chart-container {{
                width: 100%;
                height: {height - 20}px;
                position: relative;
                border: 1px solid rgba(255, 255, 255, 0.03);
                border-radius: 6px;
                overflow: hidden;
            }}
            #legend {{
                position: absolute;
                left: 12px;
                top: 8px;
                z-index: 10;
                font-family: 'Inter', -apple-system, sans-serif;
                font-size: 11px;
                color: #e2e8f0;
                background: rgba(15, 23, 42, 0.7);
                backdrop-filter: blur(4px);
                padding: 4px 10px;
                border-radius: 4px;
                pointer-events: none;
            }}
            .legend-title {{
                font-weight: 700;
                color: #ffffff;
                margin-right: 8px;
                display: inline-block;
            }}
        </style>
        <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    </head>
    <body>
        <div id="legend">
            <span class="legend-title">{title}</span>
            <span id="legend-val">Ожидание...</span>
        </div>
        <div id="chart-container"></div>
        <script>
            const chartData = {chart_data_json};
            const strokeColor = "{color}";
            
            const container = document.getElementById('chart-container');
            const chart = LightweightCharts.createChart(container, {{
                width: container.clientWidth,
                height: {height - 20},
                layout: {{
                    background: {{ type: 'solid', color: '#0b0f19' }},
                    textColor: '#94a3b8',
                    fontSize: 10,
                    fontFamily: 'Inter, sans-serif',
                }},
                grid: {{
                    vertLines: {{ color: 'rgba(255, 255, 255, 0.02)' }},
                    horzLines: {{ color: 'rgba(255, 255, 255, 0.02)' }},
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                }},
                rightPriceScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.05)',
                    textColor: '#94a3b8',
                    autoScale: true,
                }},
                timeScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.05)',
                    textColor: '#94a3b8',
                    timeVisible: false,
                }},
            }});
            
            const areaSeries = chart.addAreaSeries({{
                lineColor: strokeColor,
                topColor: strokeColor + '20',
                bottomColor: strokeColor + '01',
                lineWidth: 2,
            }});
            
            areaSeries.setData(chartData);
            chart.timeScale().fitContent();
            
            const legendVal = document.getElementById('legend-val');
            
            function updateLegend(point) {{
                if (!point) return;
                legendVal.innerHTML = `<span style="color:#ffffff; font-weight: 600;">${{point.value.toLocaleString('en-US', {{maximumFractionDigits:4}})}}</span> <span style="color:#64748b">(${{point.time}})</span>`;
            }}
            
            if (chartData.length > 0) {{
                updateLegend(chartData[chartData.length - 1]);
            }}
            
            chart.subscribeCrosshairMove(param => {{
                if (param.time) {{
                    const point = param.seriesData.get(areaSeries);
                    if (point) {{
                        updateLegend({{ time: param.time, value: point.value }});
                    }}
                }} else if (chartData.length > 0) {{
                    updateLegend(chartData[chartData.length - 1]);
                }}
            }});
            
            function resizeChart() {{
                const w = container.clientWidth || window.innerWidth;
                const h = {height - 20};
                chart.resize(w, h);
            }}
            window.addEventListener('resize', resizeChart);
            setTimeout(resizeChart, 100);
            setTimeout(resizeChart, 500);
        </script>
    </body>
    </html>
    """
    return html
