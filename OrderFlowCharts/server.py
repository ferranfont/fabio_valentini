"""
OrderFlow Server - Receives tick data and displays real-time chart
Listens on HTTP port for incoming tick data and updates visualization
"""

from flask import Flask, request, jsonify
from OrderFlow import OrderFlowChart
import pandas as pd
import numpy as np
from datetime import datetime
from threading import Lock
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output
import json
import logging
import os

# Configuration
PORT = 8765
CANDLE_INTERVAL = '1min'
MAX_CANDLES = 500
INITIAL_WINDOW_MINUTES = 30

# Setup logging to file
LOG_DIR = 'logs'
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f'server_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Also print to console
    ]
)

logger = logging.getLogger(__name__)

# Thread-safe data storage
data_lock = Lock()
tick_buffer = []
ohlc_data = None
orderflow_data = None
y_axis_range = None  # Store fixed y-axis range

# Initialize Flask for receiving data
flask_app = Flask(__name__)

# Initialize Dash for visualization
dash_app = Dash(__name__, server=flask_app, url_base_pathname='/chart/')

# Define the Dash layout
dash_app.layout = html.Div([
    html.H1("OrderFlow Chart - Real-Time"),
    html.Div(id='stats', style={'padding': '10px', 'fontSize': '14px'}),
    dcc.Graph(id='orderflow-chart', style={'height': '90vh'}),
    dcc.Interval(
        id='interval-component',
        interval=500,  # Update every 500ms
        n_intervals=0
    )
])

def process_ticks_to_orderflow():
    """Process accumulated ticks into OHLC and orderflow data"""
    global ohlc_data, orderflow_data

    with data_lock:
        if len(tick_buffer) == 0:
            return None, None

        # Create DataFrame from tick buffer
        df = pd.DataFrame(tick_buffer)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='ISO8601')
        df.set_index('Timestamp', inplace=True)

        # Group by candle interval
        df['candle_id'] = df.index.floor(CANDLE_INTERVAL)

        # Limit to MAX_CANDLES most recent
        unique_candles = df['candle_id'].unique()
        if len(unique_candles) > MAX_CANDLES:
            selected_candles = unique_candles[-MAX_CANDLES:]
            df = df[df['candle_id'].isin(selected_candles)]

        # Create OHLC data
        ohlc_list = []
        for candle_time, group in df.groupby('candle_id'):
            ohlc_list.append({
                'timestamp': candle_time,
                'open': group['Precio'].iloc[0],
                'high': group['Precio'].max(),
                'low': group['Precio'].min(),
                'close': group['Precio'].iloc[-1],
                'identifier': candle_time.strftime('%Y-%m-%d %H:%M:%S')
            })

        ohlc_df = pd.DataFrame(ohlc_list)
        ohlc_df.set_index('timestamp', inplace=True)

        # Create Orderflow data
        orderflow_list = []
        for candle_time, group in df.groupby('candle_id'):
            identifier = candle_time.strftime('%Y-%m-%d %H:%M:%S')

            # Aggregate volume by price level and side
            volume_by_price = group.groupby(['Precio', 'Lado'])['Volumen'].sum().unstack(fill_value=0)

            # Ensure both BID and ASK columns exist
            if 'BID' not in volume_by_price.columns:
                volume_by_price['BID'] = 0
            if 'ASK' not in volume_by_price.columns:
                volume_by_price['ASK'] = 0

            # Get all price levels in this candle
            for price in volume_by_price.index:
                bid_vol = volume_by_price.loc[price, 'BID']
                ask_vol = volume_by_price.loc[price, 'ASK']

                orderflow_list.append({
                    'timestamp': candle_time,
                    'bid_size': int(bid_vol),
                    'price': float(price),
                    'ask_size': int(ask_vol),
                    'identifier': identifier
                })

        orderflow_df = pd.DataFrame(orderflow_list)
        orderflow_df.set_index('timestamp', inplace=True)

        return ohlc_df, orderflow_df

@flask_app.route('/tick', methods=['POST'])
def receive_tick():
    """Receive a single tick from client"""
    try:
        tick_data = request.json

        # Convert price to float
        tick_data['Precio'] = float(tick_data['Precio'])
        tick_data['Volumen'] = int(tick_data['Volumen'])

        with data_lock:
            tick_buffer.append(tick_data)

        return jsonify({'status': 'ok', 'ticks_received': len(tick_buffer)}), 200
    except Exception as e:
        logger.error(f"Error receiving tick: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

@flask_app.route('/reset', methods=['POST'])
def reset_data():
    """Reset all data"""
    global tick_buffer, ohlc_data, orderflow_data, y_axis_range
    with data_lock:
        tick_buffer = []
        ohlc_data = None
        orderflow_data = None
        y_axis_range = None
    logger.info("Server data reset")
    return jsonify({'status': 'ok', 'message': 'Data reset'}), 200

@flask_app.route('/stats', methods=['GET'])
def get_stats():
    """Get current statistics"""
    with data_lock:
        return jsonify({
            'ticks_received': len(tick_buffer),
            'candles': len(ohlc_data) if ohlc_data is not None else 0
        }), 200

@dash_app.callback(
    [Output('orderflow-chart', 'figure'),
     Output('stats', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_chart(n):
    """Update the chart with latest data"""
    global ohlc_data, orderflow_data, y_axis_range

    try:
        # Process ticks into orderflow data
        ohlc_df, orderflow_df = process_ticks_to_orderflow()

        if ohlc_df is None or len(ohlc_df) == 0:
            # Return empty figure
            fig = go.Figure()
            fig.update_layout(
                title="Waiting for data...",
                template='plotly_dark',
                height=800
            )
            stats_text = "No data received yet. Waiting for client to send ticks..."
            return fig, stats_text

        # Update global variables
        ohlc_data = ohlc_df
        orderflow_data = orderflow_df

        # Calculate and store y-axis range on first data arrival
        if y_axis_range is None:
            tick_size = 0.25  # NQ tick size
            ymin = orderflow_df['price'].min() - tick_size * 10
            ymax = orderflow_df['price'].max() + tick_size * 10
            y_axis_range = [ymax, ymin]  # Reversed for plotly (top to bottom)
            logger.info(f"Y-axis range set: {y_axis_range}")

        # Create OrderFlowChart
        orderflowchart = OrderFlowChart(
            orderflow_data,
            ohlc_data,
            identifier_col='identifier'
        )

        # Get the figure
        fig = orderflowchart.plot(return_figure=True)

        # Set initial x-axis range to show only last 30 minutes
        if len(ohlc_data) > 0:
            last_time = ohlc_data.index[-1]
            first_time = last_time - pd.Timedelta(minutes=INITIAL_WINDOW_MINUTES)
            fig.update_xaxes(range=[first_time, last_time])

        # Disable range slider
        fig.update_xaxes(rangeslider_visible=False)

        # Update layout for dark theme and override y-axis range
        fig.update_layout(
            template='plotly_dark',
            height=800,
            yaxis=dict(range=y_axis_range, fixedrange=True)
        )

        # Statistics
        with data_lock:
            total_ticks = len(tick_buffer)

        stats_text = f"Total Ticks: {total_ticks:,} | Candles: {len(ohlc_data)} | " \
                     f"Orderflow Records: {len(orderflow_data)} | " \
                     f"Price Range: {orderflow_data['price'].min():.2f} - {orderflow_data['price'].max():.2f}"

        return fig, stats_text

    except Exception as e:
        logger.error(f"ERROR in update_chart: {e}")
        import traceback
        logger.error(traceback.format_exc())

        # Return error figure
        fig = go.Figure()
        fig.update_layout(
            title="Error rendering chart",
            template='plotly_dark',
            height=800
        )
        stats_text = f"Error: {str(e)}"
        return fig, stats_text

@flask_app.route('/')
def index():
    """Redirect to chart"""
    return """
    <html>
        <head><title>OrderFlow Server</title></head>
        <body style="background: #111; color: #fff; font-family: monospace; padding: 20px;">
            <h1>OrderFlow Server Running</h1>
            <p>Server is listening on port {}</p>
            <p>Endpoints:</p>
            <ul>
                <li><a href="/chart/" style="color: #4af">View Chart</a> - Real-time OrderFlow visualization</li>
                <li>POST /tick - Send tick data</li>
                <li>POST /reset - Reset all data</li>
                <li>GET /stats - Get statistics</li>
            </ul>
            <p>Ticks received: <span id="ticks">0</span></p>
            <script>
                setInterval(function() {{
                    fetch('/stats')
                        .then(r => r.json())
                        .then(data => {{
                            document.getElementById('ticks').textContent = data.ticks_received;
                        }});
                }}, 1000);
            </script>
        </body>
    </html>
    """.format(PORT)

if __name__ == '__main__':
    # Disable Flask/Werkzeug request logging
    werkzeug_log = logging.getLogger('werkzeug')
    werkzeug_log.setLevel(logging.ERROR)

    logger.info(f"OrderFlow Server starting on port {PORT}...")
    logger.info(f"Logging to file: {log_file}")
    logger.info(f"Chart will be available at: http://localhost:{PORT}/chart/")
    logger.info(f"Send ticks to: http://localhost:{PORT}/tick")

    flask_app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
