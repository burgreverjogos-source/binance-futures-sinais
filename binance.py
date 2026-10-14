import time
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

st.set_page_config(
    page_title="Binance Futures - Painel de Sinais",
    page_icon="🚀",
    layout="wide",
)

st.title("🚀 Binance Futures - Painel de Sinais (Modo Diagnóstico)")

COINS = {
    "Bitcoin (BTC)": "BTCUSDT",
    "Ethereum (ETH)": "ETHUSDT",
    "Solana (SOL)": "SOLUSDT",
    "Ripple (XRP)": "XRPUSDT",
    "Cardano (ADA)": "ADAUSDT",
    "Litecoin (LTC)": "LTCUSDT",
}


@st.cache_data(ttl=10)
def get_binance_data(symbol, interval):
  url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit=100"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }
  try:
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
      return None, f"HTTP Status {response.status_code}: {response.text}"

    data = response.json()
    if not isinstance(data, list):
      return None, f"Retorno inválido da API: {data}"

    df = pd.DataFrame(
        data,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "qav",
            "num_trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )
    df["data_formatada"] = pd.to_datetime(df["timestamp"], unit="ms").dt.strftime(
        "%d/%m %H:%M"
    )
    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["volume"] = df["volume"].astype(float)
    return df, None
  except Exception as e:
    return None, str(e)


# Testando a exibição para ver qual erro exato aparece na tela
colunas_ui = st.columns(3)
moedas_lista = list(COINS.items())
linhas_ativos = [moedas_lista[:3], moedas_lista[3:]]

for linha in linhas_ativos:
  cols = st.columns(3)
  for i, (nome_amigavel, symbol) in enumerate(linha):
    with cols[i]:
      df_tf, erro = get_binance_data(symbol, "15m")
      if df_tf is not None and not df_tf.empty:
        st.success(
            f"Sucesso em {nome_amigavel}! Preço:"
            f" {df_tf['close'].iloc[-1]:,.2f}"
        )
      else:
        st.error(f"Erro em {nome_amigavel}:\n{erro}")
