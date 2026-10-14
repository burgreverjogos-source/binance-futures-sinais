import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
import yfinance as yf

# 1. Configuração da Página
st.set_page_config(
    page_title="Crypto Futures - Painel de Sinais Institucional",
    page_icon="🚀",
    layout="wide",
)

# Título Fixo e Definitivo
st.title("🚀 Crypto Futures - Painel de Sinais Institucional")

# 2. Barra Lateral (Configurações do Robô)
st.sidebar.header("⚙️ Configurações do Robô")

modo_operacao = st.sidebar.selectbox(
    "📊 Perfil de Estratégia:",
    [
        "Moderado / Day Trade (Alvo: 1.2% | Stop: 0.4%)",
        "Conservador / Swing (Alvo: 1.8% | Stop: 0.5%)",
    ],
)

timeframe_escolhido = st.sidebar.selectbox(
    "⏱️ Timeframe das Velas:",
    ["15m", "1h", "4h"],
    index=0,
)

CUSTO_TAXA_ESTIMADO_PCT = 0.25

if "Conservador" in modo_operacao:
  TAKE_PROFIT_PCT = 1.8
  STOP_LOSS_PCT = 0.5
  ALAVANCAGEM = "2x"
  MULT_LEV = 2
else:
  TAKE_PROFIT_PCT = 1.2
  STOP_LOSS_PCT = 0.4
  ALAVANCAGEM = "3x"
  MULT_LEV = 3

st.sidebar.markdown("---")
st.sidebar.caption(
    f"Alvo: **+{TAKE_PROFIT_PCT}%** | Stop: **-{STOP_LOSS_PCT}%** |"
    f" Alavancagem: **{ALAVANCAGEM}**"
)

COINS = {
    "Bitcoin (BTC)": "BTC-USD",
    "Ethereum (ETH)": "ETH-USD",
    "Solana (SOL)": "SOL-USD",
    "Ripple (XRP)": "XRP-USD",
    "Cardano (ADA)": "ADA-USD",
    "Litecoin (LTC)": "LTC-USD",
}

if "historico_global" not in st.session_state:
  st.session_state.historico_global = []

if "cooldown_ativos" not in st.session_state:
  st.session_state.cooldown_ativos = {}


@st.cache_data(ttl=30)
def get_market_data(ticker, interval):
  yf_interval_map = {"15m": "15m", "1h": "60m", "4h": "60m"}
  period_map = {"15m": "5d", "1h": "1mo", "4h": "2mo"}

  intervalo = yf_interval_map.get(interval, "15m")
  periodo = period_map.get(interval, "5d")

  try:
    df = yf.download(
        ticker, period=periodo, interval=intervalo, progress=False
    )
    if df.empty:
      return None

    if isinstance(df.columns, pd.MultiIndex):
      df.columns = df.columns.get_level_values(0)

    df = df.reset_index()

    col_data = (
        "Datetime"
        if "Datetime" in df.columns
        else ("Date" if "Date" in df.columns else df.columns[0])
    )

    df["data_formatada"] = pd.to_datetime(df[col_data]).dt.strftime(
        "%d/%m %H:%M"
    )
    df["close"] = df["Close"].astype(float)
    df["high"] = df["High"].astype(float)
    df["low"] = df["Low"].astype(float)
    df["volume"] = df["Volume"].astype(float)

    df = df.tail(100).copy()
    return df
  except Exception as e:
    return None


def analisar_mercado_multi_timeframe(df_tf, df_1h):
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
      and ultimo_rsi < 48
      and vol_atual > (vol_medio * 0.8)
  ):
    sinal = "🟢 COMPRA"
    cor = "green"

  elif (
      tendencia_macro_baixa
      and ema9 < ema21
      and ultimo_rsi > 52
      and vol_atual > (vol_medio * 0.8)
  ):
    sinal = "🔴 VENDA"
    cor = "red"

  return preco_atual, ultimo_rsi, sinal, cor


tempo_atual_epoch = time.time()
precos_atuais_mercado = {}
moedas_lista = list(COINS.items())

linhas_ativos = [moedas_lista[:3], moedas_lista[3:]]

for idx_linha, linha in enumerate(linhas_ativos):
  colunas_ui = st.columns(3)
  for i, (nome_amigavel, ticker) in enumerate(linha):
    with colunas_ui[i]:
      df_tf = get_market_data(ticker, timeframe_escolhido)
      df_1h = get_market_data(ticker, "1h")

      if (
          df_tf is not None
          and not df_tf.empty
          and df_1h is not None
          and not df_1h.empty
      ):
        preco, rsi, sinal, cor = analisar_mercado_multi_timeframe(df_tf, df_1h)
        precos_atuais_mercado[nome_amigavel] = preco

        if cor == "green":
          cor_hex = "#00b0ff" if st.get_option("theme.base") == "light" else "#00ffcc"
          fill_color = (
              "rgba(0, 176, 255, 0.15)"
              if st.get_option("theme.base") == "light"
              else "rgba(0, 255, 204, 0.15)"
          )
        elif cor == "red":
          cor_hex = "#ff1744" if st.get_option("theme.base") == "light" else "#ff4d4d"
          fill_color = (
              "rgba(255, 23, 68, 0.15)"
              if st.get_option("theme.base") == "light"
              else "rgba(255, 77, 77, 0.15)"
          )
        else:
          cor_hex = (
              "#0288d1"
              if st.get_option("theme.base") == "light"
              else "#29b6f6"
          )
          fill_color = (
              "rgba(2, 136, 209, 0.12)"
              if st.get_option("theme.base") == "light"
              else "rgba(41, 182, 246, 0.12)"
          )

        is_light = st.get_option("theme.base") == "light"
        bg_card = "#ffffff" if is_light else "#131722"
        borda_card = "#d1d4dc" if is_light else "#2a2e39"
        cor_titulo = "#131722" if is_light else "#ffffff"
        cor_preco = "#000000" if is_light else "#ffffff"

        if rsi < 30:
          rsi_badge = (
              f"<span style='background-color: {'#ffe0b2' if is_light else '#2e1a0f'}; color: {'#e65100' if is_light else '#ffb74d'}; border:"
              f" 1px solid {'#ffb74d'}; padding: 2px 6px; border-radius: 10px;"
              f" font-weight: bold; font-size: 11px;'>RSI: {rsi:.1f}"
              " (Oversold)</span>"
          )
        elif rsi < 45:
          rsi_badge = (
              f"<span style='background-color: {'#e3f2fd' if is_light else '#1a2332'}; color: {'#1565c0' if is_light else '#64b5f6'}; border:"
              f" 1px solid {'#64b5f6'}; padding: 2px 6px; border-radius: 10px;"
              f" font-weight: bold; font-size: 11px;'>RSI: {rsi:.1f}"
              " (Baixo)</span>"
          )
        elif rsi > 70:
          rsi_badge = (
              f"<span style='background-color: {'#ffebee' if is_light else '#3b0d0d'}; color: {'#c62828' if is_light else '#ff4d4d'}; border:"
              f" 1px solid {'#ff4d4d'}; padding: 2px 6px; border-radius: 10px;"
              f" font-weight: bold; font-size: 11px;'>RSI: {rsi:.1f}"
              " (Overbought)</span>"
          )
        elif rsi > 55:
          rsi_badge = (
              f"<span style='background-color: {'#fce4ec' if is_light else '#311818'}; color: {'#ad1457' if is_light else '#ff8a80'}; border:"
              f" 1px solid {'#ff8a80'}; padding: 2px 6px; border-radius: 10px;"
              f" font-weight: bold; font-size: 11px;'>RSI: {rsi:.1f}"
              " (Alto)</span>"
          )
        else:
          rsi_badge = (
              f"<span style='background-color: {'#f1f3f6' if is_light else '#21252d'}; color: {'#59606d' if is_light else '#b2b5be'}; border:"
              f" 1px solid {'#363c4e'}; padding: 2px 6px; border-radius: 10px;"
              f" font-weight: bold; font-size: 11px;'>RSI: {rsi:.1f}"
              " (Neutro)</span>"
          )

        sinal_badge = (
            f"<span style='font-size: 12px; color: {cor_hex}; font-weight:"
            f" bold;'>{sinal}</span>"
            if sinal != "AGUARDAR"
            else f"<span style='font-size: 11px; color: {'#888' if is_light else '#666'};'>AGUARDAR</span>"
        )

        # Card superior unificado
        st.markdown(
            f"""
                <div style="background-color: {bg_card}; padding: 12px 14px 4px 14px; border-radius: 8px 8px 0px 0px; border: 1px solid {borda_card}; border-bottom: none;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: bold; font-size: 15px; color: {cor_titulo};">{nome_amigavel}</span>
                        <span style="color: {cor_preco}; font-weight: bold; font-size: 15px;">$ {preco:,.2f}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px;">
                        <div>{rsi_badge}</div>
                        <div>{sinal_badge}</div>
                    </div>
                </div>
                """,
            unsafe_allow_html=True,
        )

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
                hovertemplate=(
                    "<b>Data/Hora</b>: %{x}<br><b>Preço</b>:"
                    " $%{y:,.2f}<extra></extra>"
                ),
            )
        )

        bg_plot = "#ffffff" if is_light else "#131722"
        grid_color = "rgba(0,0,0,0.05)" if is_light else "rgba(255,255,255,0.03)"

        fig.update_layout(
            height=110,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(
                showticklabels=False,
                showgrid=False,
                zeroline=False,
                visible=False,
            ),
            yaxis=dict(
                range=[min_p - padding, max_p + padding],
                showticklabels=False,
                showgrid=True,
                gridcolor=grid_color,
                zeroline=False,
            ),
            paper_bgcolor=bg_plot,
            plot_bgcolor=bg_plot,
            showlegend=False,
            hovermode="closest",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displayModeBar": False},
        )

        # Rodapé do card perfeitamente fechado e sem barras extras
        st.markdown(
            f"""
                <div style="background-color: {bg_card}; padding: 0px 0px 10px 0px; border-radius: 0px 0px 8px 8px; border: 1px solid {borda_card}; border-top: none; margin-bottom: 20px;"></div>
                """,
            unsafe_allow_html=True,
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
      lev_num = 2 if "2x" in item["Alavancagem"] else 3

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
st.subheader("📜 Histórico e Acompanhamento de Sinais")

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

# Atualização automática contínua
time.sleep(30)
st.rerun()
