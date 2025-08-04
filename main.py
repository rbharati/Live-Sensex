import eventlet
eventlet.monkey_patch() 
from flask import Flask, jsonify, request # Added 'request' import
from flask_cors import CORS

import yfinance as yf
import pandas as pd
from flask_socketio import SocketIO, emit
import time # For time.sleep

# Patch standard library for async operations with eventlet

# --- Installation Instructions ---
# If you don't have these installed, run these commands in your terminal:
# pip install yfinance pandas Flask Flask-Cors Flask-SocketIO eventlet

app = Flask(__name__)
# Allow CORS for all origins and all routes for development purposes
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize Flask-SocketIO with eventlet as the async mode
# cors_allowed_origins="*" allows connections from any origin, essential for client-side apps
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# --- Global variable to control the background task loop ---
# This will be used to stop the background task if needed (e.g., on server shutdown)
thread_running = False

# --- Function to fetch and emit index data periodically ---
def fetch_and_emit_indices():
    """
    Fetches live Sensex and Nifty 50 index values and emits them via WebSocket.
    This function runs as a background task.
    """
    global thread_running
    thread_running = True
    
    index_symbols = {
        'Sensex': '^BSESN',  # BSE Sensex
        'Nifty 50': '^NSEI'  # NSE Nifty 50
    }

    while thread_running:
        indices_data = []
        print("--- Fetching Live Indian Index Data (Sensex, Nifty) for WebSocket ---")

        for name, symbol in index_symbols.items():
            try:
                ticker = yf.Ticker(symbol)
                # Use .info to get comprehensive current data
                info = ticker.info 

                # Yahoo Finance's 'regularMarketPrice' is generally the most up-to-date
                # price during market hours. 'currentPrice' can also work but 'regularMarketPrice'
                # is often more reliable for live data.
                current_price = info.get('regularMarketPrice') 
                previous_close = info.get('previousClose')

                change = 'N/A'
                change_percent = 'N/A'
                change_percent_formatted = 'N/A'

                if current_price is not None and previous_close is not None and previous_close != 0:
                    change = round(current_price - previous_close, 2)
                    change_percent = round((change / previous_close) * 100, 2)
                    change_percent_formatted = f"{'+' if change_percent > 0 else ''}{change_percent}%"
                elif current_price is not None:
                    # If previous_close is 0 or None, we can still show current price but no change
                    change = "N/A"
                    change_percent = "N/A"
                    change_percent_formatted = "N/A"

                indices_data.append({
                    'Name': name,
                    'Symbol': symbol,
                    'Price': current_price,
                    'Change': change,
                    'Change %': change_percent_formatted
                })
                print(f"Fetched data for index: {name} ({symbol})")
            except Exception as e:
                print(f"Error fetching data for index {name} ({symbol}): {e}")
                indices_data.append({
                    'Name': name,
                    'Symbol': symbol,
                    'Price': 'N/A',
                    'Change': 'N/A',
                    'Change %': 'N/A'
                })
        
        # Emit the data to all connected clients under the 'indices_update' event
        if indices_data:
            socketio.emit('indices_update', indices_data)
            print("Emitted indices_update to clients.")
        else:
            print("No index data to emit.")
            socketio.emit('indices_update', [{"message": "No index data could be retrieved."}])

        # Wait for 15 seconds before fetching again
        eventlet.sleep(15) # Use eventlet.sleep for non-blocking sleep

# --- Flask Routes ---

@app.route('/')
def home():
    """
    Returns a simple greeting message.
    """
    return "Hello, this is a simple Stock API!"

# Removed the duplicate /data route and the unused get_data function
# @app.route('/data')
# def get_data():
#     """
#     Returns a JSON object with some sample data.
#     """
#     sample_data = {
#         "name": "API Example",
#         "version": "1.0",
#         "message": "This is some data from your API!",
#         "items": ["item1", "item2", "item3"]
#     }
#     return jsonify(sample_data)

@app.route('/stock')
def get_indian_stock_performance_route(): # Renamed for clarity from _1
    """
    Fetches current stock performance data for a predefined list of Indian stock symbols.
    Returns the data as a JSON array, sorted by percentage change (gainers first).
    """
    print("--- Fetching Current Stock Data for Selected Indian Companies (HTTP request) ---")

    all_stock_data = []
    symbols = [
        'RELIANCE.NS',   # Reliance Industries (NSE)
        'TCS.NS',        # Tata Consultancy Services (NSE)
        'HDFCBANK.NS',   # HDFC Bank (NSE)
        'ICICIBANK.NS',  # ICICI Bank (NSE)
        'INFY.NS',       # Infosys (NSE)
        'SBIN.NS',       # State Bank of India (NSE)
        'MARUTI.NS',     # Maruti Suzuki (NSE)
        'ASIANPAINT.BO', # Asian Paints (BSE) - Example of a BSE stock
        'TITAN.BO',      # Titan Company (BSE) - Example of a BSE stock
        'AMZN',          # Example of a US stock (will be fetched if available)
    ]

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            company_name = info.get('longName', 'N/A')
            current_price = info.get('currentPrice')
            previous_close = info.get('previousClose')

            change = 'N/A'
            change_percent = 'N/A'
            change_percent_formatted = 'N/A'
            change_numeric = -float('inf') # Default for sorting errors to bottom

            if current_price is not None and previous_close is not None and previous_close != 0:
                change = round(current_price - previous_close, 2)
                change_percent = round((change / previous_close) * 100, 2)
                change_percent_formatted = f"{'+' if change_percent > 0 else ''}{change_percent}%"
                change_numeric = change_percent # Use numeric for sorting
            elif current_price is not None:
                change = "N/A"
                change_percent = "N/A"
                change_percent_formatted = "N/A"
                change_numeric = 0 # Treat as no change for sorting if only current price is available
            else:
                company_name = "N/A (Data Unavailable)"
                change_percent_formatted = "N/A"

            all_stock_data.append({
                'Company': company_name,
                'Symbol': symbol,
                'Price': current_price,
                'Change': change,
                'ChangeP': change_percent_formatted,
                'Change_Numeric': change_numeric
            })
            print(f"Fetched data for {symbol}")
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            all_stock_data.append({
                'Company': 'Error',
                'Symbol': symbol,
                'Price': 'N/A',
                'Change': 'N/A',
                'Change %': 'N/A',
                'Change_Numeric': -float('inf')
            })

    if all_stock_data:
        df = pd.DataFrame(all_stock_data)
        df_sorted = df.sort_values(by='Change_Numeric', ascending=False).drop(columns=['Change_Numeric'])
        return jsonify(df_sorted.to_dict(orient='records'))
    else:
        return jsonify({"message": "No stock data could be retrieved."}), 500

# --- WebSocket Event Handlers ---

@socketio.on('connect')
def handle_connect():
    """
    Handles new WebSocket connections.
    Starts the background task to emit indices data if it's not already running.
    """
    global thread_running
    print('Client connected:', request.sid) # 'request' is now imported
    # Start the background task only if it's not already running
    if not thread_running:
        socketio.start_background_task(target=fetch_and_emit_indices)
        print("Started background task for indices updates.")

@socketio.on('disconnect')
def handle_disconnect():
    """
    Handles WebSocket disconnections.
    """
    print('Client disconnected:', request.sid)
    # You might want to add logic here to stop the background task if no clients are connected,
    # but for simplicity, we'll let it run. In a real app, you'd manage this more carefully.


# --- Run the Flask-SocketIO application ---
if __name__ == '__main__':
    # Use socketio.run() instead of app.run() when using Flask-SocketIO
    # Set debug=False and use_reloader=False to avoid issues with background tasks on some OS/environments
    print("Starting Flask-SocketIO server...")
    socketio.run(app, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
