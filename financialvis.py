# Gerekli kütüphaneleri içeri aktarıyoruz
from dash import Dash, dcc, html, Input, Output, callback, ctx
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd
import traceback
import numpy as np

# Takip edilecek varlıklar (Hisse Senetleri ve Kripto Paralar)
TICKERS = {
    'NVIDIA': 'NVDA',
    'Tesla': 'TSLA',
    'Netflix': 'NFLX',
    'Apple': 'AAPL',
    'Google': 'GOOGL',
    'Microsoft': 'MSFT',
    'Bitcoin (BTC)': 'BTC-USD',
    'Ethereum (ETH)': 'ETH-USD'
}

# Kullanıcı arayüzünde gösterilecek zaman aralıkları
INTERVAL_OPTIONS = {
    '1 Dakika': '1m',
    '5 Dakika': '5m',
    '15 Dakika': '15m',
    '30 Dakika': '30m',
    '1 Saat': '1h',
    '1 Gün': '1d',
}

# --- Dash Web Uygulamasını Başlatma ---
app = Dash(__name__)
app.title = "Rarty Canlı Finans Grafiği"

# --- Uygulamanın Arayüzünü Tanımlama ---
app.layout = html.Div(
    style={'backgroundColor': '#1e2125', 'color': '#FFFFFF', 'fontFamily': 'Arial, sans-serif'},
    children=[
        html.H1('Rarty Canlı Finans Grafiği', style={'textAlign': 'center', 'padding': '20px 0'}),
        html.Div(
            style={'display': 'flex', 'justifyContent': 'center', 'gap': '20px', 'paddingBottom': '20px'},
            children=[
                dcc.Dropdown(
                    id='stock-ticker-dropdown',
                    options=[{'label': key, 'value': value} for key, value in TICKERS.items()],
                    value='NVDA', clearable=False, style={'width': '200px', 'color': 'black'}
                ),
                dcc.Dropdown(
                    id='interval-dropdown',
                    options=[{'label': key, 'value': value} for key, value in INTERVAL_OPTIONS.items()],
                    value='5m', clearable=False, style={'width': '200px', 'color': 'black'}
                )
            ]
        ),
        html.Div(style={'display': 'flex', 'flexDirection': 'row'}, children=[
            html.Div(
                style={'width': '10%', 'padding': '20px', 'display': 'flex', 'flexDirection': 'column', 'alignItems': 'center'},
                children=[
                    html.Label('Fiyat Aralığı', style={'marginBottom': '10px'}),
                    dcc.RangeSlider(
                        id='price-range-slider', min=0, max=100, step=0.1, value=[0, 100],
                        vertical=True, verticalHeight=500, marks=None,
                        tooltip={"placement": "right", "always_visible": True}
                    )
                ]
            ),
            html.Div(
                style={'width': '90%', 'flexGrow': 1},
                children=[
                    dcc.Graph(id='live-graph', style={'height': '80vh'}, config={'scrollZoom': True})
                ]
            ),
        ]),
        dcc.Interval(id='interval-component', interval=60 * 1000, n_intervals=0)
    ]
)

# --- Callback Fonksiyonu: Grafiği ve Slider'ı Güncelleme ---
@callback(
    [Output('live-graph', 'figure'),
     Output('price-range-slider', 'min'),
     Output('price-range-slider', 'max'),
     Output('price-range-slider', 'value')],
    [Input('stock-ticker-dropdown', 'value'),
     Input('interval-dropdown', 'value'),
     Input('price-range-slider', 'value'),
     Input('interval-component', 'n_intervals')]
)
def update_graph_and_slider(selected_ticker, selected_interval, slider_range, n_intervals):
    try:
        # Seçilen varlığın kripto olup olmadığını kontrol et
        is_crypto = '-USD' in selected_ticker

        if is_crypto:
            period_val = '60d' # Kripto için daha uzun gün içi periyotları çekebiliriz
        else:
            if selected_interval == '1m': period_val = '7d'
            elif selected_interval in ['5m', '15m', '30m', '1h']: period_val = '1mo'
            else: period_val = '2y'

        data = yf.download(
            tickers=selected_ticker, period=period_val, interval=selected_interval,
            prepost=not is_crypto, # Sadece hisse senetleri için piyasa dışı saatleri çek
            progress=False
        )
        
        if data.empty: raise ValueError("Veri bulunamadı.")
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.droplevel(1)

        # İstatistiksel Filtreleme (IQR)
        upper_wick = data['High'] - np.maximum(data['Open'], data['Close'])
        lower_wick = np.minimum(data['Open'], data['Close']) - data['Low']
        q1_upper, q3_upper = upper_wick.quantile(0.25), upper_wick.quantile(0.75)
        iqr_upper = q3_upper - q1_upper
        upper_threshold = q3_upper + (1.5 * iqr_upper)
        q1_lower, q3_lower = lower_wick.quantile(0.25), lower_wick.quantile(0.75)
        iqr_lower = q3_lower - q1_lower
        lower_threshold = q3_lower + (1.5 * iqr_lower)
        outliers = (upper_wick > upper_threshold) | (lower_wick > lower_threshold)
        data = data[~outliers]

        data_min, data_max = data['Low'].min(), data['High'].max()
        padding = (data_max - data_min) * 0.1
        slider_min, slider_max = data_min - padding, data_max + padding
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name='Fiyat', increasing_line_color='#26A69A', decreasing_line_color='#EF5350'))
        if len(data) >= 20:
            data['SMA20'] = data['Close'].rolling(window=20).mean()
            fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], mode='lines', name='20-SMA', line={'color': '#FFC800', 'width': 1.5}))

        ticker_label = [key for key, value in TICKERS.items() if value == selected_ticker][0]
        interval_label = [key for key, value in INTERVAL_OPTIONS.items() if value == selected_interval][0]
        
        fig.update_layout(
            title=f"{ticker_label} - {interval_label}",
            title_x=0.5, yaxis_title=None, template='plotly_dark',
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            # === YENİ AYARLAR: Yatay Zoom ve Sabit Fiyat Ekseni ===
            dragmode='zoom', # Yatayda sürükleyerek zoom yapma
            xaxis={'fixedrange': False}, # X eksenini sürükleyerek zoom'a izin ver
            yaxis={'fixedrange': True},  # Y eksenini manuel slider ile kontrol et, sürükleyerek değişmesin
            margin=dict(l=20, r=20, b=20, t=80)
        )
        
        if is_crypto:
            fig.update_xaxes(rangebreaks=None)
        else:
            fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
            trading_hours_start_hour, trading_hours_start_minute = 16, 30
            trading_hours_end_hour = 23
            for day in data.index.normalize().unique():
                fig.add_vrect(
                    x0=day.replace(hour=0, minute=0), 
                    x1=day.replace(hour=trading_hours_start_hour, minute=trading_hours_start_minute),
                    fillcolor="#444", opacity=0.2, layer="below", line_width=0,
                )
                fig.add_vrect(
                    x0=day.replace(hour=trading_hours_end_hour, minute=0), 
                    x1=day.replace(hour=23, minute=59),
                    fillcolor="#444", opacity=0.2, layer="below", line_width=0,
                )

        trigger_id = ctx.triggered_id
        if trigger_id == 'price-range-slider':
            fig.update_yaxes(range=[slider_range[0], slider_range[1]])
            return fig, slider_min, slider_max, slider_range
        else:
            fig.update_yaxes(autorange=True)
            return fig, slider_min, slider_max, [slider_min, slider_max]

    except Exception as e:
        traceback.print_exc()
        error_fig = go.Figure().update_layout(title_text="Bir Hata Oluştu", template='plotly_dark', annotations=[{'text': f"Hata: {e}", 'showarrow': False}])
        return error_fig, 0, 100, [0, 100]

# --- Sunucuyu Başlatma ---
if __name__ == '__main__':
    app.run(debug=True)