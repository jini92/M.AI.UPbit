# app.py
import os
import json
import logging
import requests
from dotenv import load_dotenv
import pyupbit
import pandas as pd
import pandas_ta as ta
from openai import OpenAI
import streamlit as st
import plotly.graph_objects as go
import pyupbit
import numpy as np
from dotenv import dotenv_values
from dotenv import load_dotenv, find_dotenv
import uuid
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
from keras.models import Sequential
from keras.layers import Dense, LSTM
import plotly.graph_objects as go


# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# debugging fuction
def is_valid_json(json_string):
    try:
        json.loads(json_string)
        return True
    except ValueError:
        return False

def get_current_status(upbit, symbol):
    orderbook = pyupbit.get_orderbook(ticker=symbol)
    current_time = orderbook['timestamp']
    balance = upbit.get_balance(ticker=symbol)
    avg_buy_price = upbit.get_avg_buy_price(ticker=symbol)

    return json.dumps({
        'current_time': current_time,
        'orderbook': orderbook,
        'balance': balance,
        'krw_balance': upbit.get_balance(ticker='KRW'),
        'coin_avg_buy_price': avg_buy_price
    })

def fetch_data(symbol, start_date=None, end_date=None):
    """
    Fetches historical price data for the specified symbol and date range.
    start_date: default is 30 days ago from the current date
    end_date: default is the current date
    
    Args:
        symbol (str): The trading symbol (e.g., "KRW-BTC", "BTC-ETH", etc.).
        start_date (datetime.date, optional): The start date of the data range.
                                              Defaults to 30 days ago from the current date if not provided.
        end_date (datetime.date, optional): The end date of the data range. 
                                            Defaults to the current date if not provided.
    
    Returns:
        tuple: A tuple containing the daily and hourly price data as pandas DataFrames.
               Returns (None, None) if an error occurs.
    
    Raises:
        Exception: If an error occurs while fetching the data.
    
    """
    if end_date is None:
        end_date = datetime.now().date()
    
    if start_date is None:
        start_date = end_date - timedelta(days=30)
    
    try:
        count_daily = (end_date - start_date).days + 1
        count_hourly = count_daily * 24
        
        daily_data = pyupbit.get_ohlcv(symbol, "day", to=end_date.strftime("%Y-%m-%d"), count=count_daily)
        hourly_data = pyupbit.get_ohlcv(symbol, interval="minute60", to=end_date.strftime("%Y-%m-%d"), count=count_hourly)
        return daily_data, hourly_data
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        return None, None

def add_indicators(df):
    """
    Adds technical indicators to the given DataFrame.

    Parameters:
    - df (pandas.DataFrame): The DataFrame to which the indicators will be added.

    Returns:
    - pandas.DataFrame: The DataFrame with the added indicators.
    """
    df['SMA_10'] = ta.sma(df['close'], length=10)
    df['EMA_10'] = ta.ema(df['close'], length=10)
    df['RSI_14'] = ta.rsi(df['close'], length=14)
    stoch = ta.stoch(df['high'], df['low'], df['close'], k=14, d=3, smooth_k=3)
    df['STOCHk_14_3_3'] = stoch['STOCHk_14_3_3']
    df['STOCHd_14_3_3'] = stoch['STOCHd_14_3_3']
    ema_fast = df['close'].ewm(span=12, adjust=False).mean()
    ema_slow = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_fast - ema_slow
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Histogram'] = df['MACD'] - df['Signal_Line']
    df['Middle_Band'] = df['close'].rolling(window=20).mean()
    std_dev = df['close'].rolling(window=20).std()
    df['Upper_Band'] = df['Middle_Band'] + (std_dev * 2)
    df['Lower_Band'] = df['Middle_Band'] - (std_dev * 2)
    return df

def prepare_data(df_daily, df_hourly):
    df_daily = add_indicators(df_daily)
    df_hourly = add_indicators(df_hourly)
    df_daily = add_signals(df_daily)
    df_hourly = add_signals(df_hourly)
    combined_df = pd.concat([df_daily, df_hourly], keys=['daily', 'hourly'])
    return json.dumps(combined_df.to_json(orient='split'))

def get_instructions(file_path):
    """
    Read and return the contents of a file.

    Args:
        file_path (str): The path to the file.

    Returns:
        str: The contents of the file.

    Raises:
        FileNotFoundError: If the file is not found.
        IOError: If an error occurs while reading the file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
    except IOError as e:
        logging.error(f"An error occurred while reading the file: {e}")

# def analyze_data_with_gpt4(client, data_json, instructions, current_status):
#     try:
#         if not instructions:
#             logging.warning("No instructions found.")
#             return None, None, None
#         response = client.chat.completions.create(
#             model="gpt-4-turbo-preview",
#             messages=[
#                 {"role": "system", "content": instructions},
#                 {"role": "user", "content": data_json},
#                 {"role": "user", "content": current_status}
#             ],
#             response_format={"type":"json_object"}
#         )
#         response_data = response.choices[0].message.content
#         advice_and_indicators = json.loads(response_data)
#         logging.info(f"Advice and indicators: {advice_and_indicators}")

#         # Extracting recommendation, reason, and technical_indicators
#         recommendation = advice_and_indicators.get('decision')
#         reason = advice_and_indicators.get('reason')
#         technical_indicators = advice_and_indicators.get('technical_indicators')

#         logging.info(f"Decision: {recommendation}")
#         logging.info(f"Reason: {reason}")
#         logging.info(f"Technical indicators: {technical_indicators}")

#         return recommendation, reason, technical_indicators
#     except Exception as e:
#         logging.error(f"Error in analyzing data with GPT-4: {e}")
#         return None, None, None
        
def analyze_data_with_gpt4(client, 
                           data_json, 
                           instructions, 
                           current_status, 
                           macd_signals, 
                           technical_indicators, 
                           lstm_predictions):
    try:
        if not instructions:
            logging.warning("No instructions found.")
            return None, None, None
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": data_json},
                {"role": "user", "content": current_status},
                {"role": "user", "content": f"MACD Signals: {macd_signals}"},
                {"role": "user", "content": f"Technical Indicators: {technical_indicators}"},
                {"role": "user", "content": f"LSTM Predictions: {lstm_predictions}"}
            ],
            response_format={"type":"json_object"}
        )
        response_data = response.choices[0].message.content
        advice_and_indicators = json.loads(response_data)
        logging.info(f"Advice and indicators: {advice_and_indicators}")

        # Extracting recommendation, reason, and technical_indicators
        recommendation = advice_and_indicators.get('decision')
        reason = advice_and_indicators.get('reason')
        technical_indicators = advice_and_indicators.get('technical_indicators')

        logging.info(f"Decision: {recommendation}")
        logging.info(f"Reason: {reason}")
        logging.info(f"Technical indicators: {technical_indicators}")

        return recommendation, reason, technical_indicators
    except Exception as e:
        logging.error(f"Error in analyzing data with GPT-4: {e}")
        return None, None, None

def execute_buy(upbit, symbol, order_amount):
    """
    Executes a buy order for the specified symbol and amount using the specified Upbit instance.

    Args:
        upbit (Upbit): An instance of the Upbit class.
        symbol (str): The trading symbol (e.g., "KRW-BTC", "BTC-ETH", etc.).
        order_amount (float): The amount to buy.

    Returns:
        None

    Raises:
        Exception: If there is an error executing the buy order.

    """
    logging.info(f"Attempting to buy {order_amount} {symbol}...")
    try:
        result = upbit.buy_market_order(symbol, order_amount)
        logging.info(f"Buy order successful: {result}")
    except Exception as e:
        logging.error(f"Failed to execute buy order: {e}")

def execute_sell(upbit, symbol, order_amount):
    """
    Executes a sell order for the specified symbol and amount using the specified Upbit instance.

    Args:
        upbit (Upbit): An instance of the Upbit class.
        symbol (str): The trading symbol (e.g., "KRW-BTC", "BTC-ETH", etc.).
        order_amount (float): The amount to sell.

    Returns:
        None

    Raises:
        Exception: If there is an error executing the sell order.

    """
    logging.info(f"Attempting to sell {order_amount} {symbol}...")
    try:
        result = upbit.sell_market_order(symbol, order_amount)
        logging.info(f"Sell order successful: {result}")
    except Exception as e:
        logging.error(f"Failed to execute sell order: {e}")

def execute_trade(upbit, symbol, recommendation, order_amount):
    if recommendation == "buy":
        execute_buy(upbit, symbol, order_amount)
    elif recommendation == "sell":
        execute_sell(upbit, symbol, order_amount)
    else:
        logging.info("No trade executed. Recommendation: hold.")

def make_decision_and_execute(upbit, symbol, advice, order_amount):
    logging.info("Making decision and executing...")
    if advice:
        try:
            execute_trade(upbit, symbol, advice, order_amount)
        except Exception as e:
            logging.error(f"Failed to execute trade: {e}")
    else:
        logging.warning("No advice generated. Skipping trade execution.")

def get_market_info():
    url = "https://api.upbit.com/v1/market/all"
    response = requests.get(url)
    markets_info = response.json()
    return {market['korean_name']: market['market'] for market in markets_info if 'BTC-' in market['market'] or 'KRW-' in market['market']}

def generate_macd_signal(df):
    """
    Generates buy/sell signals based on MACD crossovers.

    Args:
        df (pd.DataFrame): DataFrame with MACD data.

    Returns:
        pd.Series: Series with buy/sell signals.
    """
    signal = pd.Series(index=df.index, data=np.zeros(len(df)))
    signal[df['MACD'] > df['Signal_Line']] = 1
    signal[df['MACD'] < df['Signal_Line']] = -1
    return signal

def add_signals(df):
    """
    Adds buy/sell signals to the DataFrame.

    Args:
        df (pd.DataFrame): DataFrame with technical indicators.

    Returns:
        pd.DataFrame: DataFrame with buy/sell signals.
    """
    df['MACD_Signal'] = generate_macd_signal(df)
    return df

def update_env_file(env_vars):
    with open(".env", "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

def mask_value(value):
    return "*" * len(value)

def load_env_variables():
    openai_key = ""
    upbit_access_key = ""
    upbit_secret_key = ""
    instructions_path = "./instructions.md"

    # # 현재 스크립트 파일의 디렉토리 경로 가져오기
    # current_dir = os.path.dirname(os.path.abspath(__file__))
    # instructions_path = os.path.join(current_dir, "instructions.md")

    if find_dotenv():
        load_dotenv()
        openai_key = os.getenv("OPENAI_API_KEY", "")
        upbit_access_key = os.getenv("UPBIT_ACCESS_KEY", "")
        upbit_secret_key = os.getenv("UPBIT_SECRET_KEY", "")
        instructions_path = os.getenv("INSTRUCTIONS_PATH", "")

    if os.path.exists(".streamlit/secrets.toml"):
        try:
            if not openai_key:
                openai_key = st.secrets["OPENAI_API_KEY"]
            if not upbit_access_key:
                upbit_access_key = st.secrets["UPBIT_ACCESS_KEY"]
            if not upbit_secret_key:
                upbit_secret_key = st.secrets["UPBIT_SECRET_KEY"]
            if not instructions_path:
                instructions_path = st.secrets["INSTRUCTIONS_PATH"]
        except KeyError:
            pass

    return openai_key, upbit_access_key, upbit_secret_key, instructions_path

def set_environment_variables():
    st.sidebar.subheader("Environment Variables")

    openai_key, upbit_access_key, upbit_secret_key, instructions_path = load_env_variables()

    if "openai_key" not in st.session_state:
        st.session_state.openai_key = openai_key
    if "upbit_access_key" not in st.session_state:
        st.session_state.upbit_access_key = upbit_access_key
    if "upbit_secret_key" not in st.session_state:
        st.session_state.upbit_secret_key = upbit_secret_key
    if "instructions_path" not in st.session_state:
        st.session_state.instructions_path = instructions_path

    # st.session_state.openai_key = st.sidebar.text_input("OpenAI API Key", value=mask_value(st.session_state.openai_key), type="password", key="openai_key_input_sidebar")
    # st.session_state.upbit_access_key = st.sidebar.text_input("Upbit Access Key", value=mask_value(st.session_state.upbit_access_key), type="password", key="upbit_access_key_input_sidebar")
    # st.session_state.upbit_secret_key = st.sidebar.text_input("Upbit Secret Key", value=mask_value(st.session_state.upbit_secret_key), type="password", key="upbit_secret_key_input_sidebar")
    # st.session_state.instructions_path = st.sidebar.text_input("Instructions Path", value=mask_value(st.session_state.instructions_path), key="instructions_path_input_sidebar")

    st.session_state.openai_key = st.sidebar.text_input("OpenAI API Key", value=st.session_state.openai_key, type="password", key="openai_key_input_sidebar")
    st.session_state.upbit_access_key = st.sidebar.text_input("Upbit Access Key", value=st.session_state.upbit_access_key, type="password", key="upbit_access_key_input_sidebar")
    st.session_state.upbit_secret_key = st.sidebar.text_input("Upbit Secret Key", value=st.session_state.upbit_secret_key, type="password", key="upbit_secret_key_input_sidebar")
    st.session_state.instructions_path = st.sidebar.text_input("Instructions Path", value=st.session_state.instructions_path, key="instructions_path_input_sidebar")

  
    if st.sidebar.button("Update Environment Variables"):
        if find_dotenv():
            env_vars = {
                "export OPENAI_API_KEY": st.session_state.openai_key,
                "export UPBIT_ACCESS_KEY": st.session_state.upbit_access_key,
                "export UPBIT_SECRET_KEY": st.session_state.upbit_secret_key,
                "export INSTRUCTIONS_PATH": st.session_state.instructions_path
            }
            update_env_file(env_vars)
        else:
            logging.warning("No .env file found.")

        st.sidebar.success("Environment variables updated successfully!")

    # Return the updated environment variables and data information
    logging.info("\n")
    logging.info("set_environment_variables()-return:")
    logging.info(f"openai_key: {st.session_state.openai_key}")
    logging.info(f"upbit_access_key: {st.session_state.upbit_access_key}")
    logging.info(f"upbit_secret_key: {st.session_state.upbit_secret_key}")
    logging.info(f"instructions_path: {st.session_state.instructions_path}")

    # # 사이드바에 토스 QR 코드 추가
    # st.sidebar.subheader("토스로 펀드 받기")
    # st.sidebar.image("toss_funding.jpeg", use_column_width=True)

    # 사이드바에 kakao QR 코드 추가
    st.sidebar.subheader("카카오페이로 펀드 받기")
    kakaopay_funding_link = "https://qr.kakaopay.com/Ej797GOPG1c205798"
    st.sidebar.markdown(f"[[개발펀딩]]({kakaopay_funding_link})")
    st.sidebar.image("kakao_funding.jpeg", use_column_width=True)
    

    return st.session_state.openai_key, st.session_state.upbit_access_key, st.session_state.upbit_secret_key, st.session_state.instructions_path

def select_symbols():
    st.title("AI Trader")
    st.subheader("Market Search")
    market_info = get_market_info()
    coin_name = st.text_input("Enter Cryptocurrency Name (e.g., 비트코인, 레이븐):")
    filtered_tickers = [ticker for name, ticker in market_info.items() if coin_name in name]
    selected_symbol = st.selectbox("Select Ticker:", filtered_tickers)

    order_amount = st.number_input(f"Enter order amount ({selected_symbol.split('-')[0]})", min_value=0.0, format="%.8f")

    # Add date range input controls
    today = datetime.now().date()
    one_month_ago = today - timedelta(days=30)
    start_date = st.date_input("Start Date", value=one_month_ago, max_value=today)
    # one_year_ago = today - timedelta(days=365)
    # start_date = st.date_input("Start Date", value=one_year_ago, max_value=today)
    end_date = st.date_input("End Date", value=today, max_value=today, min_value=start_date)


    enable_trading = st.checkbox("Enable Trading")
    auto_trade = st.checkbox("Enable Auto Trading")

    # 스케줄 주기 선택
    schedule_interval = None
    schedule_value = None
    if auto_trade:
        schedule_interval = st.selectbox("스케줄 주기", ("분", "시간", "일", "주", "월", "년"))

        # 주기 값 입력
        if schedule_interval == "분":
            schedule_value = st.number_input("분 간격", min_value=1, value=1, step=1)
        elif schedule_interval == "시간":
            schedule_value = st.number_input("시간 간격", min_value=1, value=1, step=1)
        elif schedule_interval == "일":
            schedule_value = st.number_input("일 간격", min_value=1, value=1, step=1)
        elif schedule_interval == "주":
            schedule_value = st.number_input("주 간격", min_value=1, value=1, step=1)
        elif schedule_interval == "월":
            schedule_value = st.number_input("월 간격", min_value=1, value=1, step=1)
        elif schedule_interval == "년":
            schedule_value = st.number_input("년 간격", min_value=1, value=1, step=1)

    return selected_symbol, order_amount, enable_trading, auto_trade, schedule_interval, schedule_value, start_date, end_date

def prepare_lstm_data(data, lookback):
    X, Y = [], []
    for i in range(len(data) - lookback):
        X.append(data[i:i + lookback])
        Y.append(data[i + lookback])
    return np.array(X), np.array(Y)

def train_lstm(data, lookback):
    scaler = MinMaxScaler(feature_range=(0, 1))
    data = scaler.fit_transform(data)

    X, Y = prepare_lstm_data(data, lookback)
    X = X.reshape((X.shape[0], X.shape[1], 1))

    model = Sequential()
    model.add(LSTM(50, return_sequences=True, input_shape=(X.shape[1], 1)))
    model.add(LSTM(50))
    model.add(Dense(1))

    model.compile(loss='mean_squared_error', optimizer='adam')
    model.fit(X, Y, epochs=100, batch_size=16, verbose=0)

    return scaler, model

def predict_prices(scaler, model, data, lookback, num_predictions):
    X_test = data[-lookback:]
    X_test = scaler.transform(X_test.reshape(-1, 1))
    X_test = X_test.reshape((1, lookback, 1))

    predictions = []
    for _ in range(num_predictions):
        prediction = model.predict(X_test)
        predictions.append(scaler.inverse_transform(prediction)[0][0])
        X_test = np.append(X_test[:, 1:, :], prediction.reshape((1, 1, 1)), axis=1)

    return predictions

def visualize_predictions(data, predictions):
    actual_fig = go.Figure()
    actual_fig.add_trace(go.Scatter(x=data.index, y=data['close'], mode='lines', name='Actual Price'))

    last_timestamp = data.index[-1]
    prediction_timestamps = pd.date_range(start=last_timestamp, periods=len(predictions) + 1, freq='H')[1:]
    actual_fig.add_trace(go.Scatter(x=prediction_timestamps, y=predictions, mode='lines', name='Predicted Price'))

    st.plotly_chart(actual_fig)

def predict_and_visualize(data):
    """
    Predicts future prices using LSTM model and visualizes the predictions.

    Args:
        data (pandas.DataFrame): The input data containing historical prices.

    Returns:
        numpy.ndarray: An array of predicted prices.

    """
    lookback = 24*30            # Number of previous hours to consider, (hours * days)
    num_predictions = 24*2      # Number of hours to predict, (hours * days)

    close_data = data['close'].values.reshape(-1, 1)
    scaler, model = train_lstm(close_data, lookback)
    predictions = predict_prices(scaler, model, close_data, lookback, num_predictions)
    visualize_predictions(data, predictions)

    return predictions

# def main(openai_key, 
#          upbit_access_key, 
#          upbit_secret_key, 
#          instructions_path, 
#          symbol, 
#          order_amount, 
#          enable_trading, 
#          auto_trade,
#          start_date=None,
#          end_date=None
#         ):
    
#     st.title(f"AI Trader - {symbol}")
    
#     # 사용자 정의 CSS 추가
#     st.markdown("""
#         <style>
#             /* 기본 스타일 */
#             .sidebar .sidebar-content {
#                 width: 300px;
#             }
            
#             .reportview-container .main .block-container {
#                 padding-top: 2rem;
#                 padding-right: 2rem;
#                 padding-left: 2rem;
#                 padding-bottom: 2rem;
#             }
            
#             /* 화면 너비가 600px 이하일 때 적용되는 스타일 */
#             @media screen and (max-width: 600px) {
#                 .sidebar .sidebar-content {
#                     width: 100%;
#                 }
                
#                 .reportview-container .main .block-container {
#                     padding: 1rem;
#                 }
#             }
#         </style>
#     """, unsafe_allow_html=True)

#     if not openai_key or not upbit_access_key or not upbit_secret_key:
#         st.warning("openai_key: " + openai_key)
#         st.warning("upbit_access_key: " + upbit_access_key)
#         st.warning("upbit_secret_key: " + upbit_secret_key)
#         st.warning("Not all required environment variables are set. Please enter them in the sidebar.")
#         return
    

#     # 이동된 부분 제거
#     # openai = OpenAI(api_key=openai_key)
#     # upbit = pyupbit.Upbit(upbit_access_key, upbit_secret_key)
#     # instructions = get_instructions(instructions_path)

#     with st.container():
#         st.markdown("""
#             *This is a simple AI trader that uses OpenAI's GPT-4 to analyze market data and make trading decisions.*
#             *The application uses the Upbit API to fetch market data and execute buy/sell orders.*
#             *The GPT-4 model is used to analyze the market data and provide trading advice.*
#         """)
#         st.markdown("---")

#     with st.container():
#         st.subheader("Market Analysis and Trading")
#         # openai, upbit, instructions_path = load_env()
#         # instructions = get_instructions(instructions_path)
#         # daily_data, hourly_data = fetch_data(symbol)
#         daily_data, hourly_data = fetch_data(symbol, start_date=start_date, end_date=end_date)
#         data_json = prepare_data(daily_data, hourly_data)
#         current_status = get_current_status(upbit, symbol)
#         recommendation, reason, technical_indicators = analyze_data_with_gpt4(openai, data_json, instructions, current_status)
        
#         # recommendation = "hold" # 임시
#         # reason = "hold" # 임시
#         # technical_indicators = "hold" # 임시


#         if enable_trading:
#             if auto_trade:
#                 st.write("Auto Trading Enabled. Executed trading decision.")
#             else:
#                 st.write("Trading Enabled. Please review the analysis and execute trades manually.")
            
#             # GPT-4 분석 결과에 따라 매매 결정
#             make_decision_and_execute(upbit, symbol, recommendation, order_amount)
#         else:
#             st.write("Trading Disabled. Analysis only.")

#         st.write("Trading Advice:", recommendation)
#         st.write("Reasoning:", reason)
#         st.write("Technical Indicators:", technical_indicators)
#         st.markdown("---")
    
#         with st.container():
#             st.subheader("Market Data Visualization")
#             st.write("Daily Data Chart")
#             daily_fig = go.Figure(data=[go.Candlestick(x=daily_data.index,
#                                                     open=daily_data['open'],
#                                                     high=daily_data['high'],
#                                                     low=daily_data['low'],
#                                                     close=daily_data['close'])])
#             st.plotly_chart(daily_fig)
#             st.markdown("---")

#             st.subheader("MACD Signal (Daily)")
#             macd_signal_fig = go.Figure()
#             macd_signal_fig.add_trace(go.Scatter(x=daily_data.index, y=daily_data['MACD'], mode='lines', name='MACD'))
#             macd_signal_fig.add_trace(go.Scatter(x=daily_data.index, y=daily_data['Signal_Line'], mode='lines', name='Signal Line'))
            
#             # Add buy/sell signals
#             buy_signals = daily_data[daily_data['MACD_Signal'] == 1]
#             sell_signals = daily_data[daily_data['MACD_Signal'] == -1]
#             macd_signal_fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['MACD'], mode='markers', marker=dict(size=10, color='green'), name='Buy Signal'))
#             macd_signal_fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['MACD'], mode='markers', marker=dict(size=10, color='red'), name='Sell Signal'))
            
#             st.plotly_chart(macd_signal_fig)
#             st.markdown("---")


#             st.write("Hourly Data Chart")
#             hourly_fig = go.Figure(data=[go.Candlestick(x=hourly_data.index,
#                                                         open=hourly_data['open'],
#                                                         high=hourly_data['high'],
#                                                         low=hourly_data['low'],
#                                                         close=hourly_data['close'])])
#             st.plotly_chart(hourly_fig)
#             st.markdown("---")

#             st.subheader("MACD Signal (Hourly)")
#             macd_signal_hourly_fig = go.Figure()
#             macd_signal_hourly_fig.add_trace(go.Scatter(x=hourly_data.index, y=hourly_data['MACD'], mode='lines', name='MACD'))
#             macd_signal_hourly_fig.add_trace(go.Scatter(x=hourly_data.index, y=hourly_data['Signal_Line'], mode='lines', name='Signal Line'))
            
#             # Add buy/sell signals
#             buy_signals_hourly = hourly_data[hourly_data['MACD_Signal'] == 1]
#             sell_signals_hourly = hourly_data[hourly_data['MACD_Signal'] == -1]
#             macd_signal_hourly_fig.add_trace(go.Scatter(x=buy_signals_hourly.index, y=buy_signals_hourly['MACD'], mode='markers', marker=dict(size=10, color='green'), name='Buy Signal'))
#             macd_signal_hourly_fig.add_trace(go.Scatter(x=sell_signals_hourly.index, y=sell_signals_hourly['MACD'], mode='markers', marker=dict(size=10, color='red'), name='Sell Signal'))
            
#             st.plotly_chart(macd_signal_hourly_fig)
#             st.markdown("---")

            
#             st.write("Technical Indicators Chart")
#             tech_indicators_fig = go.Figure()
#             tech_indicators_fig.add_trace(go.Scatter(x=daily_data.index, y=daily_data['SMA_10'], mode='lines', name='SMA 10'))
#             # ... other technical indicators ...
#             tech_indicators_fig.add_trace(go.Scatter(x=daily_data.index, y=daily_data['Lower_Band'], mode='lines', name='Lower Band'))
#             st.plotly_chart(tech_indicators_fig)
#             st.markdown("---")

#             # 추가: LSTM 모델을 사용한 가격 예측 및 시각화
#             st.subheader("Price Prediction (LSTM)")
#             predict_and_visualize(hourly_data)
#             st.markdown("---")

def main(openai_key, 
         upbit_access_key, 
         upbit_secret_key, 
         instructions_path, 
         symbol, 
         order_amount, 
         enable_trading, 
         auto_trade,
         start_date=None,
         end_date=None
        ):
    
    st.title(f"AI Trader - {symbol}")
    
    # 사용자 정의 CSS 추가
    st.markdown("""
        <style>
            /* 기본 스타일 */
            .sidebar .sidebar-content {
                width: 300px;
            }
            
            .reportview-container .main .block-container {
                padding-top: 2rem;
                padding-right: 2rem;
                padding-left: 2rem;
                padding-bottom: 2rem;
            }
            
            /* 화면 너비가 600px 이하일 때 적용되는 스타일 */
            @media screen and (max-width: 600px) {
                .sidebar .sidebar-content {
                    width: 100%;
                }
                
                .reportview-container .main .block-container {
                    padding: 1rem;
                }
            }
        </style>
    """, unsafe_allow_html=True)

    if not openai_key or not upbit_access_key or not upbit_secret_key:
        st.warning("openai_key: " + openai_key)
        st.warning("upbit_access_key: " + upbit_access_key)
        st.warning("upbit_secret_key: " + upbit_secret_key)
        st.warning("Not all required environment variables are set. Please enter them in the sidebar.")
        return
    
    with st.container():
        st.markdown("""
            *This is a simple AI trader that uses OpenAI's GPT-4 to analyze market data and make trading decisions.*
            *The application uses the Upbit API to fetch market data and execute buy/sell orders.*
            *The GPT-4 model is used to analyze the market data and provide trading advice.*
        """)
        st.markdown("---")

    with st.container():
        st.subheader("Market Analysis and Trading")
        daily_data, hourly_data = fetch_data(symbol, start_date=start_date, end_date=end_date)
        data_json = prepare_data(daily_data, hourly_data)
        current_status = get_current_status(upbit, symbol)
        
        # MACD signals, technical indicators, LSTM predictions 추출
        macd_signals = daily_data['MACD_Signal'].tolist()
        technical_indicators = {
            'SMA_10': daily_data['SMA_10'].tolist(),
            'Upper_Band': daily_data['Upper_Band'].tolist(),
            'Lower_Band': daily_data['Lower_Band'].tolist()
        }
        close_data = hourly_data['close'].values.reshape(-1, 1)


        # lookback = 24
        # num_predictions = 24
        # scaler, model = train_lstm(close_data, lookback)
        # lstm_predictions = predict_prices(scaler, model, close_data, lookback, num_predictions)

         # 추가: LSTM 모델을 사용한 가격 예측 및 시각화
        st.subheader("Price Prediction (LSTM)")
        lstm_predictions = predict_and_visualize(hourly_data)
        st.markdown("---")
        
        # recommendation, reason, technical_indicators = analyze_data_with_gpt4(openai, data_json, instructions, current_status, macd_signals, technical_indicators, lstm_predictions)
        recommendation, reason, technical_indicators = analyze_data_with_gpt4(openai, 
                                                                              data_json, 
                                                                              instructions, 
                                                                              current_status, 
                                                                              macd_signals, 
                                                                              technical_indicators, 
                                                                              lstm_predictions)
        
        if enable_trading:
            if auto_trade:
                st.write("Auto Trading Enabled. Executed trading decision.")
            else:
                st.write("Trading Enabled. Please review the analysis and execute trades manually.")
            
            make_decision_and_execute(upbit, symbol, recommendation, order_amount)
        else:
            st.write("Trading Disabled. Analysis only.")

        st.write("Trading Advice:", recommendation)
        st.write("Reasoning:", reason)
        st.write("Technical Indicators:", technical_indicators)
        st.markdown("---")
    
        with st.container():
            st.subheader("Market Data Visualization")
            st.write("Daily Data Chart")
            daily_fig = go.Figure(data=[go.Candlestick(x=daily_data.index,
                                                    open=daily_data['open'],
                                                    high=daily_data['high'],
                                                    low=daily_data['low'],
                                                    close=daily_data['close'])])
            st.plotly_chart(daily_fig)
            st.markdown("---")

            st.subheader("MACD Signal (Daily)")
            macd_signal_fig = go.Figure()
            macd_signal_fig.add_trace(go.Scatter(x=daily_data.index, y=daily_data['MACD'], mode='lines', name='MACD'))
            macd_signal_fig.add_trace(go.Scatter(x=daily_data.index, y=daily_data['Signal_Line'], mode='lines', name='Signal Line'))
            
            buy_signals = daily_data[daily_data['MACD_Signal'] == 1]
            sell_signals = daily_data[daily_data['MACD_Signal'] == -1]
            macd_signal_fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['MACD'], mode='markers', marker=dict(size=10, color='green'), name='Buy Signal'))
            macd_signal_fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['MACD'], mode='markers', marker=dict(size=10, color='red'), name='Sell Signal'))
            
            st.plotly_chart(macd_signal_fig)
            st.markdown("---")

            st.write("Hourly Data Chart")
            hourly_fig = go.Figure(data=[go.Candlestick(x=hourly_data.index,
                                                        open=hourly_data['open'],
                                                        high=hourly_data['high'],
                                                        low=hourly_data['low'],
                                                        close=hourly_data['close'])])
            st.plotly_chart(hourly_fig)
            st.markdown("---")

            st.subheader("MACD Signal (Hourly)")
            macd_signal_hourly_fig = go.Figure()
            macd_signal_hourly_fig.add_trace(go.Scatter(x=hourly_data.index, y=hourly_data['MACD'], mode='lines', name='MACD'))
            macd_signal_hourly_fig.add_trace(go.Scatter(x=hourly_data.index, y=hourly_data['Signal_Line'], mode='lines', name='Signal Line'))
            
            buy_signals_hourly = hourly_data[hourly_data['MACD_Signal'] == 1]
            sell_signals_hourly = hourly_data[hourly_data['MACD_Signal'] == -1]
            macd_signal_hourly_fig.add_trace(go.Scatter(x=buy_signals_hourly.index, y=buy_signals_hourly['MACD'], mode='markers', marker=dict(size=10, color='green'), name='Buy Signal'))
            macd_signal_hourly_fig.add_trace(go.Scatter(x=sell_signals_hourly.index, y=sell_signals_hourly['MACD'], mode='markers', marker=dict(size=10, color='red'), name='Sell Signal'))
            
            st.plotly_chart(macd_signal_hourly_fig)
            st.markdown("---")
            
            st.write("Technical Indicators Chart")
            tech_indicators_fig = go.Figure()
            tech_indicators_fig.add_trace(go.Scatter(x=daily_data.index, y=daily_data['SMA_10'], mode='lines', name='SMA 10'))
            # ... other technical indicators ...
            tech_indicators_fig.add_trace(go.Scatter(x=daily_data.index, y=daily_data['Lower_Band'], mode='lines', name='Lower Band'))
            st.plotly_chart(tech_indicators_fig)
            st.markdown("---")

            # st.subheader("Price Prediction (LSTM)")
            # visualize_predictions(hourly_data, lstm_predictions)
            # st.markdown("---")

if __name__ == "__main__":
    import schedule
    import time

    openai_key, upbit_access_key, upbit_secret_key, instructions_path = set_environment_variables()
    selected_symbol, order_amount, enable_trading, auto_trade, schedule_interval, schedule_value, start_date, end_date = select_symbols()

    # main() 에서 이동된 부분
    instructions = get_instructions(instructions_path)
    openai = OpenAI(api_key=openai_key)
    upbit = pyupbit.Upbit(upbit_access_key, upbit_secret_key)

    # debugging set_environment_variables and select_symbols
    logging.info("\n")
    logging.info("Environment variables: __main__")
    logging.info(f"openai_key: {openai_key}")
    logging.info(f"upbit_access_key: {upbit_access_key}")
    logging.info(f"upbit_secret_key: {upbit_secret_key}")
    logging.info(f"instructions_path: {instructions_path}")
    logging.info(f"selected_symbol: {selected_symbol}")
    logging.info(f"order_amount: {order_amount}")
    logging.info(f"enable_trading: {enable_trading}")
    logging.info(f"auto_trade: {auto_trade}")
    logging.info(f"schedule_interval: {schedule_interval}")
    logging.info(f"schedule_value: {schedule_value}")

    if selected_symbol:
        start_trading_button = st.button("Start Trading")
        stop_trading_button = st.button("Stop Trading")

        if start_trading_button:
            if auto_trade and schedule_interval and schedule_value:
                if schedule_interval == "분":
                    schedule.every(schedule_value).minutes.do(main, 
                                                              openai_key=openai_key,
                                                              upbit_access_key=upbit_access_key,
                                                              upbit_secret_key=upbit_secret_key,
                                                              instructions_path=instructions_path,
                                                              symbol=selected_symbol,
                                                              order_amount=order_amount,
                                                              enable_trading=enable_trading,
                                                              auto_trade=auto_trade,
                                                              start_date=start_date,
                                                              end_date=end_date)
                elif schedule_interval == "시간":
                    schedule.every(schedule_value).hours.do(main, 
                                                            openai_key=openai_key,
                                                            upbit_access_key=upbit_access_key,
                                                            upbit_secret_key=upbit_secret_key,
                                                            instructions_path=instructions_path,
                                                            symbol=selected_symbol,
                                                            order_amount=order_amount,
                                                            enable_trading=enable_trading,
                                                            auto_trade=auto_trade,
                                                            start_date=start_date,
                                                            end_date=end_date)
                elif schedule_interval == "일":
                    schedule.every(schedule_value).days.do(main, 
                                                           openai_key=openai_key,
                                                           upbit_access_key=upbit_access_key,
                                                           upbit_secret_key=upbit_secret_key,
                                                           instructions_path=instructions_path,
                                                           symbol=selected_symbol,
                                                           order_amount=order_amount,
                                                           enable_trading=enable_trading,
                                                           auto_trade=auto_trade,
                                                           start_date=start_date,
                                                           end_date=end_date)
                elif schedule_interval == "주":
                    schedule.every(schedule_value).weeks.do(main, 
                                                            openai_key=openai_key,
                                                            upbit_access_key=upbit_access_key,
                                                            upbit_secret_key=upbit_secret_key,
                                                            instructions_path=instructions_path,
                                                            symbol=selected_symbol,
                                                            order_amount=order_amount,
                                                            enable_trading=enable_trading,
                                                            auto_trade=auto_trade,
                                                            start_date=start_date,
                                                            end_date=end_date)
                elif schedule_interval == "월":
                    schedule.every(schedule_value).months.do(main, 
                                                             openai_key=openai_key,
                                                             upbit_access_key=upbit_access_key,
                                                             upbit_secret_key=upbit_secret_key,
                                                             instructions_path=instructions_path,
                                                             symbol=selected_symbol,
                                                             order_amount=order_amount,
                                                             enable_trading=enable_trading,
                                                             auto_trade=auto_trade,
                                                             start_date=start_date,
                                                             end_date=end_date)
                elif schedule_interval == "년":
                    schedule.every(schedule_value).years.do(main, 
                                                            openai_key=openai_key,
                                                            upbit_access_key=upbit_access_key,
                                                            upbit_secret_key=upbit_secret_key,
                                                            instructions_path=instructions_path,
                                                            symbol=selected_symbol,
                                                            order_amount=order_amount,
                                                            enable_trading=enable_trading,
                                                            auto_trade=auto_trade,
                                                            start_date=start_date,
                                                            end_date=end_date)
            
            # Run the Streamlit app for the selected symbol
            main(openai_key=openai_key,
                 upbit_access_key=upbit_access_key,
                 upbit_secret_key=upbit_secret_key,
                 instructions_path=instructions_path,
                 symbol=selected_symbol,
                 order_amount=order_amount,
                 enable_trading=enable_trading,
                 auto_trade=auto_trade,
                 start_date=start_date,
                 end_date=end_date)
            
            # Run the scheduled tasks if auto_trade is enabled
            while auto_trade:
                if stop_trading_button:
                    auto_trade = False
                    break
                schedule.run_pending()
                time.sleep(1)
        else:
            st.warning("No Trading Button Checked. Just Anaysis only!!.")
            st.warning("Please Check to start trading!!!!!")
    else:
        st.warning("No symbols selected. Please select at least one symbol to start trading.")