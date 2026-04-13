import streamlit as st
import pandas as pd
import plotly.express as px
import random
import re

# Configuração da página
st.set_page_config(page_title="Dashboard SUS - Análise Completa", layout="wide")

@st.cache_data
def carregar_e_unificar_dados():
    # 1. Leitura das bases com tratamento de encoding
    try:
        df_qtd_raw = pd.read_csv('dados_datasus_quantidade_aih.csv', sep=';', encoding='utf-8-sig')
        df_val_raw = pd.read_csv('dados_datasus_valor_total.csv', sep=';', encoding='utf-8-sig')
    except:
        df_qtd_raw = pd.read_csv('dados_datasus_quantidade_aih.csv', sep=';', encoding='iso-8859-1')
        df_val_raw = pd.read_csv('dados_datasus_valor_total.csv', sep=';', encoding='iso-8859-1')

    # 2. Identificação automática de sufixos de data (_MMYY)
    colunas_texto = "".join(df_qtd_raw.columns)
    sufixos = sorted(list(set(re.findall(r'_(\d{4})', colunas_texto))), reverse=True)
    
    if not sufixos:
        st.error("Nenhuma coluna de data detectada no formato _MMYY.")
        st.stop()

    lista_final = []

    def limpar_colunas(df_input, padrao_data):
        cols = [c for c in df_input.columns if padrao_data in c]
        if not cols: return pd.Series(0, index=df_input.index)
        temp = df_input[cols].copy()
        for c in cols:
            temp[c] = temp[c].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            temp[c] = pd.to_numeric(temp[c], errors='coerce').fillna(0)
        return temp.sum(axis=1)

    # 3. Processamento mensal e merge
    for suf in sufixos:
        col_mun_q = df_qtd_raw.columns[0]
        col_mun_v = df_val_raw.columns[0]

        df_mes_q = pd.DataFrame({'MUNICIPIO': df_qtd_raw[col_mun_q], 'Quantidade': limpar_colunas(df_qtd_raw, suf)})
        df_mes_v = pd.DataFrame({'MUNICIPIO': df_val_raw[col_mun_v], 'Valor': limpar_colunas(df_val_raw, suf)})
        
        df_unido = pd.merge(df_mes_q, df_mes_v, on='MUNICIPIO', how='outer').fillna(0)
        df_unido = df_unido[~df_unido['MUNICIPIO'].str.contains('Total|TOTAL|Soma', na=False)]
        
        df_unido['Mes_Ano'] = f"{suf[:2]}/{suf[2:]}"
        df_unido['Data'] = pd.to_datetime(f"20{suf[2:]}-{suf[:2]}-01")
        lista_final.append(df_unido)

    return pd.concat(lista_final, ignore_index=True).sort_values('Data')

# --- CARREGAMENTO ---
try:
    df = carregar_e_unificar_dados()
except Exception as e:
    st.error(f"Erro crítico: {e}")
    st.stop()

# --- SIDEBAR (FILTROS) ---
st.sidebar.header("⚙️ Configurações")
todos_municipios = list(df['MUNICIPIO'].unique())

if st.sidebar.button("🎲 Sorteio Aleatório (10 cidades)"):
    selecao_padrao = random.sample(todos_municipios, min(len(todos_municipios), 10))
else:
    selecao_padrao = todos_municipios[:10]

municipios_selecionados = st.sidebar.multiselect("Selecione os Municípios:", options=todos_municipios, default=selecao_padrao)
df_filtrado = df[df['MUNICIPIO'].isin(municipios_selecionados)]

# --- LAYOUT PRINCIPAL ---
st.title("🏥 Dashboard de Produção Hospitalar SUS")

# --- KPIs GERAIS (Sempre mostram a base completa) ---
st.markdown("### 📊 Visão Geral da Base Completa")
c1, c2, c3, c4 = st.columns(4)

# Calculando sobre 'df' (Base Total) e não sobre 'df_filtrado'
total_geral_qtd = df['Quantidade'].sum()
total_geral_val = df['Valor'].sum()
media_geral_qtd = df['Quantidade'].mean()
media_geral_val = df['Valor'].mean()

with c1:
    st.metric("Qtd Total (Base)", f"{total_geral_qtd:,.0f}".replace(',', '.'))
    
with c2:
    st.metric("Valor Total (Base)", f"R$ {total_geral_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))

with c3:
    st.metric("Média Qtd (Geral)", f"{media_geral_qtd:,.2f}".replace('.', ','))

with c4:
    st.metric("Média Valor (Geral)", f"R$ {media_geral_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
st.markdown("---")

# ABAS DE ANÁLISE
tab_geral, tab_estatistica, tab_rankings = st.tabs(["📈 Evolução Temporal", "📊 Análise Estatística", "🏆 Rankings Top 10"])

with tab_geral:
    metrica_ev = st.selectbox("Métrica:", ["Quantidade", "Valor"], key="ev")
    fig_line = px.line(df_filtrado, x="Mes_Ano", y=metrica_ev, color="MUNICIPIO", markers=True, title=f"Tendência Mensal de {metrica_ev}")
    st.plotly_chart(fig_line, use_container_width=True)

with tab_estatistica:
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Distribuição e Outliers")
        met_dist = st.radio("Variável:", ["Quantidade", "Valor"], horizontal=True, key="dist")
        fig_box = px.box(df_filtrado, x="MUNICIPIO", y=met_dist, color="MUNICIPIO")
        st.plotly_chart(fig_box, use_container_width=True)
        
        st.subheader("Histograma")
        fig_hist = px.histogram(df_filtrado, x=met_dist, color="MUNICIPIO", nbins=20)
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_b:
        st.subheader("Correlação: Qtd vs Valor")
        fig_scatter = px.scatter(df_filtrado, x="Quantidade", y="Valor", color="MUNICIPIO", trendline="ols")
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        correl = df_filtrado[['Quantidade', 'Valor']].corr().iloc[0, 1]
        st.write(f"**Coeficiente de Correlação de Pearson:** {correl:.4f}")

with tab_rankings:
    # O Ranking ignora o filtro lateral para mostrar os top 10 de TODA a base
    df_rank_geral = df.groupby('MUNICIPIO')[['Quantidade', 'Valor']].sum().reset_index()
    
    col_q, col_v = st.columns(2)
    
    with col_q:
        st.subheader("Top 10 por Quantidade")
        top10_q = df_rank_geral.sort_values('Quantidade', ascending=False).head(10)
        st.plotly_chart(px.bar(top10_q, x='Quantidade', y='MUNICIPIO', orientation='h', color='Quantidade'), use_container_width=True)
        st.plotly_chart(px.pie(top10_q, values='Quantidade', names='MUNICIPIO', hole=0.4), use_container_width=True)

    with col_v:
        st.subheader("Top 10 por Valor")
        top10_v = df_rank_geral.sort_values('Valor', ascending=False).head(10)
        st.plotly_chart(px.bar(top10_v, x='Valor', y='MUNICIPIO', orientation='h', color='Valor', color_continuous_scale='Reds'), use_container_width=True)
        st.plotly_chart(px.pie(top10_v, values='Valor', names='MUNICIPIO', hole=0.4), use_container_width=True)

st.markdown("---")
st.subheader("🔍 Tabela de Dados Detalhada")
st.dataframe(df_filtrado.sort_values(['Data', 'MUNICIPIO']), use_container_width=True)