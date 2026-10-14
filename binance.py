import time
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

# 1. Configuração da Página
st.set_page_config(
    page_title="Crypto Futures - Painel de Sinais Institucional",
    page_icon="🚀",
    layout="wide",
)

# Estilo CSS rigoroso para sumir com o badge/ícone flutuante do celular e limpar o topo
hide_streamlit_style = """
    <style>
    header {visibility: hidden !important;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .viewerBadge_container__1QSob {display: none !important; visibility: hidden !important;}
    .stAppDeployButton {display: none !important; visibility: hidden !important;}
    iframe[title="streamlitAppBadge"] {display: none !important;}
    .stPlotlyChart {
        margin-top: -10px !important;
        margin-bottom: 25px !important;
    }
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Título Fixo e Definitivo
st.title("🚀 Crypto Futures - Painel de Sinais Institucional")

# 2. Painel de Configuração Limpo (Com 3 Perfis)
st.markdown("### ⚙️ Painel de Configuração do Robô")
col_cfg1, col_cfg2 = st.columns([3, 3])

with col_cfg1:
  modo_operacao = st.selectbox(
      "📊 Perfil de Estratégia:",
      [
          "Agressivo / Scalp (Alvo: 0.8% | Stop: 0.3% | 5x)",
          "Moderado / Day Trade (Alvo: 1.2% | Stop: 0.4% | 3x)",
          "Conservador / Swing (Alvo: 1.8% | Stop: 0.5% | 2x)",
      ],
  )

with col_cfg2:
  timeframe_escolhido = st.selectbox(
      "⏱️ Timeframe das Velas:",
      ["15m", "1h", "4h"],
      index=0,
  )

CUSTO_TAXA_ESTIMADO_PCT = 0.25

if "Agressivo" in modo_operacao:
  TAKE_PROFIT_PCT = 0.8
  STOP_LOSS_PCT = 0.3
  ALAVANCAGEM = "5x"
  MULT_LEV = 5
  RSI_COMPRA_MAX = 52
  RSI_VENDA_MIN = 48
elif "Conservador" in modo_operacao:
  TAKE_PROFIT_PCT = 1.8
  STOP_LOSS_PCT = 0.5
  ALAVANCAGEM = "2x"
  MULT_LEV = 2
  RSI_COMPRA_MAX = 45
  RSI_VENDA_MIN = 55
else:  # Moderado
  TAKE_PROFIT_PCT = 1.2
  STOP_LOSS_PCT = 0.4
  ALAVANCAGEM = "3x"
  MULT_LEV = 3
  RSI_COMPRA_MAX = 48
  RSI_VENDA_MIN = 52

st.markdown("---")

# 6 Ativos consolidados com os pares oficiais da Binance Futures
COINS = {
    "Bitcoin (BTC)": "BTCUSDT",
    "Ethereum (ETH)": "ETHUSDT",
    "Solana (SOL)": "SOLUSDT",
    "Ripple (XRP)": "XRPUSDT",
    "Cardano (ADA)": "ADAUSDT",
    "Litecoin (LTC)": "LTCUSDT",
}

if "historico_global" not in st.session_state:
  st.session_state.historico_global = []

if "cooldown_ativos" not in st.session_state:
  st.session_state.cooldown_ativos = {}


@st.cache_data(ttl=30)
def get_binance_futures_data(symbol, interval):
  url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit=100"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }
  try:
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
      return None
    data = response.json()
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
    return df
  except Exception as e:
    return None


def analisar_mercado_multi_timeframe(df_tf, df_1h, rsi_c_max, rsi_v_min):
  ema20_1h = EMAIndicator(close=df_1h["close"], window=20).ema_indicator()
  ema50_1h = EMAIndicator(close=df_1h["close"], window=50).ema_indicator()
  tendencia_macro_alta = (
      ema20_1h.iloc[-1] > ema50_1h.iloc[-1]
      and df_1h["close"].iloc[-1] > ema50_1h.iloc[-1]
  )
  tendencia_macro_baixa = (
      ema20_1h.iloc[-1] < ema50_1h.iloc[-1]
      and df_1h["close"].iloc[-1] < ema50_1h.iloc[-1]
  )

  rsi_calc = RSIIndicator(close=df_tf["close"], window=14)
  df_tf["rsi"] = rsi_calc.rsi()

  ema9_calc = EMAIndicator(close=df_tf["close"], window=9)
  df_tf["ema9"] = ema9_calc.ema_indicator()

  ema21_calc = EMAIndicator(close=df_tf["close"], window=21)
  df_tf["ema21"] = ema21_calc.ema_indicator()

  ultimo_rsi = df_tf["rsi"].iloc[-1]
  preco_atual = df_tf["close"].iloc[-1]
  ema9 = df_tf["ema9"].iloc[-1]
  ema21 = df_tf["ema21"].iloc[-1]

  vol_atual = df_tf["volume"].iloc[-1]
  vol_medio = df_tf["volume"].tail(15).mean()

  sinal = "AGUARDAR"
  cor = "gray"

  if (
      tendencia_macro_alta
      and ema9 > ema21
      and ultimo_rsi < rsi_c_max
      and vol_atual > (vol_medio * 0.7)
  ):
    sinal = "🟢 COMPRA"
    cor = "green"

  elif (
      tendencia_macro_baixa
      and ema9 < ema21
      and ultimo_rsi > rsi_v_min
      and vol_atual > (vol_medio * 0.7)
  ):
    sinal = "🔴 VENDA"
    cor = "red"

  return preco_atual, ultimo_rsi, sinal, cor


tempo_atual_epoch = time.time()
precos_atuais_mercado = {}
moedas_lista = list(COINS.items())

# Organizando em 2 linhas de 3 colunas cada
linhas_ativos = [moedas_lista[:3], moedas_lista[3:]]

for idx_linha, linha in enumerate(linhas_ativos):
  colunas_ui = st.columns(3)
  for i, (nome_amigavel, symbol) in enumerate(linha):
    with colunas_ui[i]:
      df_tf = get_binance_futures_data(symbol, timeframe_escolhido)
      df_1h = get_binance_futures_data(symbol, "1h")

      if (
          df_tf is not None
          and not df_tf.empty
          and df_1h is not None
          and not df_1h.empty
      ):
        preco, rsi, sinal, cor = analisar_mercado_multi_timeframe(
            df_tf, df_1h, RSI_COMPRA_MAX, RSI_VENDA_MIN
        )
        precos_atuais_mercado[nome_amigavel] = preco

        # Cores base do gráfico
        if cor == "green":
          cor_hex = "#00ffcc"
          fill_color = "rgba(0, 255, 204, 0.15)"
        elif cor == "red":
          cor_hex = "#ff4d4d"
          fill_color = "rgba(255, 77, 77, 0.15)"
        else:
          cor_hex = (
              "#29b6f6"
              if "SOL" in symbol or "XRP" in symbol or "ADA" in symbol
              else "#ab47bc"
          )
          fill_color = "rgba(41, 182, 246, 0.12)"

        # Indicador Badge do RSI
        if rsi < 30:
          rsi_badge = (
              f"<span style='background-color: #2e1a0f; color: #ffb74d; border:"
              " 1px solid #ffb74d; padding: 2px 6px; border-radius: 10px;"
              f" font-weight: bold; font-size: 11px;'>RSI: {rsi:.1f}"
              " (Oversold)</span>"
          )
        elif rsi < 45:
          rsi_badge = (
              f"<span style='background-color: #1a2332; color: #64b5f6; border:"
              " 1px solid #64b5f6; padding: 2px 6px; border-radius: 10px;"
              f" font-weight: bold; font-size: 11px;'>RSI: {rsi:.1f}"
              " (Baixo)</span>"
          )
        elif rsi > 70:
          rsi_badge = (
              f"<span style='background-color: #3b0d0d; color: #ff4d4d; border:"
              " 1px solid #ff4d4d; padding: 2px 6px; border-radius: 10px;"
              f" font-weight: bold; font-size: 11px;'>RSI: {rsi:.1f}"
              " (Overbought)</span>"
          )
        elif rsi > 55:
          rsi_badge = (
              f"<span style='background-color: #311818; color: #ff8a80; border:"
              " 1px solid #ff8a80; padding: 2px 6px; border-radius: 10px;"
              f" font-weight: bold; font-size: 11px;'>RSI: {rsi:.1f}"
              " (Alto)</span>"
          )
        else:
          rsi_badge = (
              f"<span style='background-color: #21252d; color: #b2b5be; border:"
              " 1px solid #363c4e; padding: 2px 6px; border-radius: 10px;"
              f" font-weight: bold; font-size: 11px;'>RSI: {rsi:.1f}"
              " (Neutro)</span>"
          )

        sinal_badge = (
            f"<span style='font-size: 12px; color: {cor_hex}; font-weight:"
            f" bold;'>{sinal}</span>"
            if sinal != "AGUARDAR"
            else f"<span style='font-size: 11px; color: #666;'>AGUARDAR</span>"
        )

        # Cabeçalho do Card unificado com borda superior
        st.markdown(
            f"""
                <div style="background-color: #131722; padding: 12px 14px; border-radius: 8px 8px 0px 0px; border: 1px solid #2a2e39; border-bottom: none;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: bold; font-size: 15px; color: #ffffff;">{nome_amigavel}</span>
                        <span style="color: {cor_hex}; font-weight: bold; font-size: 15px;">$ {preco:,.2f}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px;">
                        <div>{rsi_badge}</div>
                        <div>{sinal_badge}</div>
                    </div>
                </div>
                """,
            unsafe_allow_html=True,
        )

        # Preparar dados do gráfico
        df_plot = df_tf.tail(30).copy()
        min_p = df_plot["close"].min()
        max_p = df_plot["close"].max()
        padding = (max_p - min_p) * 0.1 if max_p != min_p else 1

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df_plot["data_formatada"],
                y=df_plot["close"],
                mode="lines",
                line=dict(color=cor_hex, width=2.5),
                fill="tonexty",
                fillcolor=fill_color,
                hovertemplate="<b>Preço</b>: $%{y:,.2f}<br><b>Data/Hora</b>: %{x}<extra></extra>",
            )
        )

        fig.update_layout(
            height=120,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(
                showticklabels=False,
                showgrid=False,
                zeroline=False,
                visible=False,
                fixedrange=True,
            ),
            yaxis=dict(
                range=[min_p - padding, max_p + padding],
                showticklabels=False,
                showgrid=True,
                gridcolor="rgba(255,255,255,0.03)",
                zeroline=False,
                fixedrange=True,
            ),
            paper_bgcolor="#131722",
            plot_bgcolor="#131722",
            showlegend=False,
            hovermode="x unified",
        )

        # Gráfico estático (sem zoom/duplo clique, apenas tooltip de preço e horário)
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "staticPlot": False,
                "displayModeBar": False,
                "scrollZoom": False,
                "doubleClick": False,
                "showTips": False,
            },
        )

        ja_tem_posicao_aberta = any(
            item["Ativo"] == nome_amigavel
            and "EM ANDAMENTO" in item["Status / Simulação"]
            for item in st.session_state.historico_global
        )

        em_cooldown = (
            nome_amigavel in st.session_state.cooldown_ativos
            and tempo_atual_epoch < st.session_state.cooldown_ativos[nome_amigavel]
        )

        if (
            "AGUARDAR" not in sinal
            and not ja_tem_posicao_aberta
            and not em_cooldown
        ):
          st.session_state.historico_global.insert(
              0,
              {
                  "Horário": pd.Timestamp.now().strftime("%H:%M:%S"),
                  "Ativo": nome_amigavel,
                  "Timeframe": timeframe_escolhido,
                  "Tipo": sinal,
                  "Preço Entrada": preco,
                  "Alavancagem": ALAVANCAGEM,
                  "Alvo Config": f"+{TAKE_PROFIT_PCT}% / -{STOP_LOSS_PCT}%",
                  "Status / Simulação": "🟢 EM ANDAMENTO",
              },
          )

      else:
        st.error(f"Erro ao carregar dados de {nome_amigavel}")

  if idx_linha == 0:
    st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

# Atualização de Posições
for item in st.session_state.historico_global:
  if "EM ANDAMENTO" in item["Status / Simulação"]:
    ativo = item["Ativo"]
    if ativo in precos_atuais_mercado:
      preco_entrada = item["Preço Entrada"]
      preco_atual = precos_atuais_mercado[ativo]
      tipo = item["Tipo"]
      lev_num = MULT_LEV

      if "COMPRA" in tipo:
        variacao_ativo_pct = (preco_atual - preco_entrada) / preco_entrada * 100
      else:
        variacao_ativo_pct = (preco_entrada - preco_atual) / preco_entrada * 100

      lucro_bruto_alavancado = variacao_ativo_pct * lev_num
      resultado_liquido_pct = lucro_bruto_alavancado - CUSTO_TAXA_ESTIMADO_PCT

      if variacao_ativo_pct >= TAKE_PROFIT_PCT:
        item["Status / Simulação"] = (
            f"🎯 ALVO ATINGIDO (+{resultado_liquido_pct:.2f}% Líquido)"
        )
        st.session_state.cooldown_ativos[ativo] = time.time() + 1800

      elif variacao_ativo_pct <= -STOP_LOSS_PCT:
        perda_total_liquida = (STOP_LOSS_PCT * lev_num) + CUSTO_TAXA_ESTIMADO_PCT
        item["Status / Simulação"] = (
            f"🛑 STOP LOSS (-{perda_total_liquida:.2f}% Líquido)"
        )
        st.session_state.cooldown_ativos[ativo] = time.time() + 1800

st.markdown("---")

# Seção de Histórico com os parâmetros de Alvo/Stop ao lado do título
col_hist_titulo, col_hist_info = st.columns([3, 3])
with col_hist_titulo:
  st.subheader("📜 Histórico e Acompanhamento de Sinais")
with col_hist_info:
  st.markdown(
      f"<div style='text-align: right; padding-top: 10px; font-size: 14px; color:"
      f" #b2b5be;'>🎯 Alvo: <b>+{TAKE_PROFIT_PCT}%</b> | 🛑 Stop:"
      f" <b>-{STOP_LOSS_PCT}%</b> | ⚡ Alav.: <b>{ALAVANCAGEM}</b></div>",
      unsafe_allow_html=True,
  )

if st.session_state.historico_global:
  total_trades = len(
      [
          x
          for x in st.session_state.historico_global
          if "EM ANDAMENTO" not in x["Status / Simulação"]
      ]
  )
  vitorias = len(
      [
          x
          for x in st.session_state.historico_global
          if "ALVO ATINGIDO" in x["Status / Simulação"]
      ]
  )
  derrotas = len(
      [
          x
          for x in st.session_state.historico_global
          if "STOP LOSS" in x["Status / Simulação"]
      ]
  )

  col_m1, col_m2, col_m3 = st.columns(3)
  col_m1.metric("Total de Operações Finalizadas", total_trades)
  col_m2.metric("Vitórias vs Derrotas", f"{vitorias} / {derrotas}")
  taxa_acerto = (vitorias / total_trades * 100) if total_trades > 0 else 0
  col_m3.metric("Taxa de Assertividade", f"{taxa_acerto:.1f}%")

  df_hist = pd.DataFrame(st.session_state.historico_global)

  csv_data = df_hist.to_csv(index=False).encode("utf-8")
  st.download_button(
      label="📥 Baixar Histórico em CSV",
      data=csv_data,
      file_name=f"historico_sinais_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
      mime="text/csv",
  )

  df_para_exibir = []
  for item in st.session_state.historico_global:
    item_copia = item.copy()
    item_copia["Preço Entrada"] = f"$ {item_copia['Preço Entrada']:,.2f}"
    df_para_exibir.append(item_copia)

  st.dataframe(pd.DataFrame(df_para_exibir), use_container_width=True)
else:
  st.info(
      "Painel ativo. Aguardando confluência de tendência para emitir o próximo"
      " sinal..."
  )

time.sleep(30)
st.rerun()
