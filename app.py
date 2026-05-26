import streamlit as st
import pandas as pd
import numpy as np
import fundamentus

# Configuração de interface adaptável para computadores e celulares
st.set_page_config(page_title="Diagrama do Cerrado + Fundamentus", layout="wide")

st.title("🌱 Sistema Diagrama do Cerrado & Monitor de Carteira")
st.write("Dados extraídos com segurança utilizando a biblioteca oficial do Fundamentus.")

# 1. CAPTURA DOS DADOS UTILIZANDO A BIBLIOTECA OFICIAL
@st.cache_data(ttl=3600) # Mantém na memória por 1 hora para carregar instantaneamente
def carregar_dados_fundamentus_oficial():
    # Coleta a tabela completa diretamente do portal Fundamentus
    df = fundamentus.get_resultado()
    
    # MAPEAMENTO CORRETO DAS COLUNAS (Conforme documentação oficial da biblioteca)
    df['Div.Yield'] = df['dy'] * 100
    df['Marg. Líq.'] = df['mrgliq'] * 100
    df['ROE'] = df['roe'] * 100
    df['ROIC'] = df['roic'] * 100
    df['P/L'] = df['pl']
    df['P/VP'] = df['pvp']
    df['Cotação'] = df['cotacao']
    df['Dív.Brut/ Patrim.'] = df['divbpatr']
    df['Liq.2meses'] = df['liq2m']
    df['CAGR Lucro Proj (%)'] = df['c5y'] * 100  # Crescimento de receita/lucro dos últimos 5 anos
    
    return df

try:
    df_processado = carregar_dados_fundamentus_oficial()
except Exception as e:
    st.error(f"Erro ao processar dados da API Fundamentus: {e}")
    st.stop()

# 2. CONFIGURAÇÕES DA BARRA LATERAL (PAINEL DO INVESTIDOR)
st.sidebar.header("🎛️ Critérios de Rendimento")
dy_slider = st.sidebar.slider("Dividend Yield (DY) Desejado (%)", min_value=0.0, max_value=15.0, value=6.0, step=0.5)
dy_esperado = dy_slider / 100 if dy_slider > 0 else 0.001

aporte_disponivel = st.sidebar.number_input("Valor do Aporte Mensal (R$)", min_value=0.0, value=2000.0)

# 3. CRITÉRIOS DO DIAGRAMA DO CERRADO (0 a 10 PONTOS)
df_processado['Nota Cerrado'] = 0.0

# Pergunta 1: O negócio apresenta lucro recorrente estável e ROE forte (> 11%)?
df_processado['Nota Cerrado'] += np.where(df_processado['ROE'] >= 11.0, 2.5, 0.5)
# Pergunta 2: A Margem Líquida protege as operações contra crises operacionais (> 10%)?
df_processado['Nota Cerrado'] += np.where(df_processado['Marg. Líq.'] >= 10.0, 2.5, 0.5)
# Pergunta 3: A dívida está sob rédea curta e balanceada (Dívida/Patrimônio <= 1.5)?
df_processado['Nota Cerrado'] += np.where(df_processado['Dív.Brut/ Patrim.'] <= 1.5, 2.5, 0.5)
# Pergunta 4: O preço de mercado está descontado e dentro do aceitável (P/VP <= 2.2)?
df_processado['Nota Cerrado'] += np.where(df_processado['P/VP'] <= 2.2, 2.5, 0.5)

# Punição Financeira: Se a empresa opera no prejuízo (P/L negativo), a nota despenca para zero na hora
df_processado['Nota Cerrado'] = np.where(df_processado['P/L'] <= 0, 0.0, df_processado['Nota Cerrado'])

# VALUATION DE PREÇO-TETO PROJETIVO (Payout Médio Padrão de 50%)
df_processado['DPA_Estimado'] = (df_processado['Cotação'] / df_processado['P/L']) * 0.50
df_processado['Preço Teto Projetivo'] = df_processado['DPA_Estimado'] / dy_esperado
df_processado['Margem de Segurança (%)'] = ((df_processado['Preço Teto Projetivo'] - df_processado['Cotação']) / df_processado['Preço Teto Projetivo']) * 100

# 4. CRIAÇÃO REESTRUTURADA DAS ABAS
tab1, tab2 = st.tabs(["🏆 Scanner Geral da Bolsa", "💼 Minha Carteira Monitorada"])

with tab1:
    st.subheader(f"Top 15 Melhores Ações do Mercado Geral (Foco em DY de {dy_slider}%)")
    st.write("Filtro executado sobre as empresas mais negociadas da Bolsa (Liq. > 500k/dia) para evitar distorções.")
    
    # Filtra apenas empresas com volume real na bolsa
    df_liquidas = df_processado[df_processado['Liq.2meses'] > 500000].copy()
    df_ranking = df_liquidas.sort_values(by='Margem de Segurança (%)', ascending=False).head(15)
    
    for pos, (empresa, linha) in enumerate(df_ranking.iterrows(), start=1):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(label=f"{pos}º Lugar - {empresa}", value=f"Nota: {linha['Nota Cerrado']:.1f}/10")
        with c2:
            st.write(f"**Preço de Tela:** R$ {linha['Cotação']:.2f} | **Preço-Teto:** R$ {linha['Preço Teto Projetivo']:.2f}")
            st.write(f"**P/L:** {linha['P/L']:.2f} | **Margem Líquida:** {linha['Marg. Líq.']:.1f}%")
        with c3:
            if linha['Cotação'] < linha['Preço Teto Projetivo']:
                st.success(f"🟢 OPORTUNIDADE: {linha['Margem de Segurança (%)']:.1f}% de Desconto")
            else:
                st.error(f"🔴 EXCEDEU O TETO: Está {-linha['Margem de Segurança (%)']:.1f}% mais cara")
        st.divider()

with tab2:
    st.subheader("Gerenciador da Sua Carteira Pessoal")
    carteira_usuario = st.text_input("Códigos das ações em carteira (separe por vírgula):", value="BBAS3, WEGE3, TAEE11")
    lista_carteira = [t.strip().upper() for t in carteira_usuario.split(",") if t.strip() != ""]
    
    if lista_carteira:
        df_minha_carteira = df_processado[df_processado.index.isin(lista_carteira)].copy()
        
        if not df_minha_carteira.empty:
            st.write("### Seus Ativos Monitorados:")
            st.dataframe(df_minha_carteira[['Cotação', 'Preço Teto Projetivo', 'Margem de Segurança (%)', 'Nota Cerrado', 'ROE', 'Marg. Líq.']].style.format("{:.2f}"))
            
            st.write("### 💰 Onde Aportar Hoje na sua Carteira:")
            df_compras_carteira = df_minha_carteira[df_minha_carteira['Cotação'] < df_minha_carteira['Preço Teto Projetivo']].copy()
            soma_pesos = df_compras_carteira['Nota Cerrado'].sum()
            
            if soma_pesos > 0:
                df_compras_carteira['Sugestão de Aporte (R$)'] = (df_compras_carteira['Nota Cerrado'] / soma_pesos) * aporte_disponivel
                st.success("Cálculo de Rebalanceamento Concluído!")
                st.dataframe(df_compras_carteira[['Cotação', 'Preço Teto Projetivo', 'Nota Cerrado', 'Sugestão de Aporte (R$)']].style.format({"Cotação": "R$ {:.2f}", "Preço Teto Projetivo": "R$ {:.2f}", "Nota Cerrado": "{:.1f}", "Sugestão de Aporte (R$)": "R$ {:.2f}"}))
            else:
                st.warning("Nenhum ativo da sua carteira está abaixo do preço-teto calculado para o Yield selecionado.")
