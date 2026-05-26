import streamlit as st
import pandas as pd
import numpy as np
import requests

# Ajuste visual de tela adaptável para smartphones e computadores
st.set_page_config(page_title="Diagrama do Cerrado Real", layout="wide")

st.title("🌱 Diagrama do Cerrado Automatizado (Dados do Fundamentus)")
st.write("Dados fundamentalistas e cotações auditados em tempo real direto da base do Fundamentus.")

# 1. PAINEL DE CONTROLE DE ENTRADA (MENU LATERAL)
st.sidebar.header("🎛️ Configurações de Rendimento")
dy_slider = st.sidebar.slider("Dividend Yield (DY) Desejado (%)", min_value=0.0, max_value=15.0, value=6.0, step=0.5)
dy_esperado = dy_slider / 100 if dy_slider > 0 else 0.001

aporte_disponivel = st.sidebar.number_input("Valor do Aporte Mensal (R$)", min_value=0.0, value=2000.0)

# 2. CAPTURA PURA E DIRETA DE DADOS DO SITE FUNDAMENTUS
@st.cache_data(ttl=1800) # Atualiza a tabela a cada 30 minutos de forma ultra rápida
def puxar_base_fundamentus_pura():
    url = "https://www.fundamentus.com.br/resultado.php"
    # Cabeçalho que simula o Google Chrome para o site liberar o acesso sem travar
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    resposta = requests.get(url, headers=headers)
    # Lê as tabelas HTML de texto puras injetadas no site do Fundamentus
    tabelas = pd.read_html(resposta.text, decimal=',', thousands='.')
    df = tabelas[0]
    
    # Padronização e limpeza de textos das colunas
    df.columns = [c.strip() for c in df.columns]
    df.set_index('Papel', inplace=True)
    
    # Tratamento de dados numéricos (Removendo símbolos de % e corrigindo pontos flutuantes)
    colunas_ajustar = ['Div.Yield', 'Marg. Líq.', 'ROE', 'ROIC', 'Cres. Rec.5a']
    for col in colunas_ajustar:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('.', '', regex=False)
            df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            df[col] = df[col].astype(str).str.replace('%', '', regex=False).astype(float)
            
    return df

try:
    df_raw = puxar_base_fundamentus_pura()
except Exception as e:
    st.error(f"Não foi possível conectar à base de dados do Fundamentus. Erro técnico: {e}")
    st.stop()

# 3. CRUZAMENTO MATEMÁTICO: PERGUNTAS DO DIAGRAMA DO CERRADO
df_analise = df_raw.copy()

# Cálculo das Notas Fundamentalistas (0 a 10) baseadas nas regras do Raul Sena
df_analise['Nota Cerrado'] = 0.0
df_analise['Nota Cerrado'] += np.where(df_analise['ROE'] >= 11.0, 2.5, 0.5)         # Pergunta 1: Lucro consistente?
df_analise['Nota Cerrado'] += np.where(df_analise['Marg. Líq.'] >= 10.0, 2.5, 0.5)   # Pergunta 2: Margem segura?
df_analise['Nota Cerrado'] += np.where(df_analise['Dív.Brut/ Patrim.'] <= 1.5, 2.5, 0.5) # Pergunta 3: Dívida sob controle?
df_analise['Nota Cerrado'] += np.where(df_analise['P/VP'] <= 2.2, 2.5, 0.5)         # Pergunta 4: Preço aceitável?

# Punição severa do Raul Sena: Se a empresa opera no prejuízo (P/L negativo), a nota zera
df_analise['Nota Cerrado'] = np.where(df_analise['P/L'] <= 0, 0.0, df_analise['Nota Cerrado'])

# VALUATION PROJETIVO (GERAÇÃO DIVIDENDOS DO LÉO)
# Dividendo por Ação Projetado = (Cotação / P/L) * Payout Estimado Médio de 50%
df_analise['DPA_Projetado'] = (df_analise['Cotação'] / df_analise['P/L']) * 0.50
df_analise['Preço Teto Projetivo'] = df_analise['DPA_Projetado'] / dy_esperado
df_analise['Margem de Segurança (%)'] = ((df_analise['Preço Teto Projetivo'] - df_analise['Cotação']) / df_analise['Preço Teto Projetivo']) * 100

# 4. CRIAÇÃO DAS ABAS DE NAVEGAÇÃO DO USUÁRIO
tab1, tab2 = st.tabs(["🏆 Scanner Geral da B3", "💼 Minha Carteira Pessoal"])

with tab1:
    st.subheader(f"Top 15 Ações com Maior Margem de Desconto (Alvo de DY: {dy_slider}%)")
    st.write("Exibindo apenas empresas com volume de negociação diária real acima de R$ 500 mil para afastar riscos.")
    
    # Filtro de liquidez de mercado para afastar ações sem movimentação
    df_liquidas = df_analise[df_analise['Liq.2meses'] > 500000].copy()
    df_ranking = df_liquidas.sort_values(by='Margem de Segurança (%)', ascending=False).head(15)
    
    for pos, (empresa, linha) in enumerate(df_ranking.iterrows(), start=1):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(label=f"{pos}º Lugar - {empresa}", value=f"Nota: {linha['Nota Cerrado']:.1f}/10")
        with c2:
            st.write(f"**Preço Atual:** R$ {linha['Cotação']:.2f} | **Preço-Teto:** R$ {linha['Preço Teto Projetivo']:.2f}")
            st.write(f"**P/L Real:** {linha['P/L']:.2f} | **ROE Real:** {linha['ROE']:.1f}%")
        with c3:
            if linha['Cotação'] < linha['Preço Teto Projetivo']:
                st.success(f"🟢 OPORTUNIDADE: {linha['Margem de Segurança (%)']:.1f}% de Desconto")
            else:
                st.error(f"🔴 ESTICADA: {-linha['Margem de Segurança (%)']:.1f}% acima do teto")
        st.divider()

with tab2:
    st.subheader("Painel Exclusivo da Sua Carteira")
    st.write("Preencha o campo de texto com as suas ações. O aplicativo puxará os indicadores reais do Fundamentus de forma dedicada:")
    
    # Campo de texto interativo em branco para você digitar
    carteira_usuario = st.text_input("Digite os códigos das suas ações (Ex: BBAS3, PETR4, VALE3):", value="")
    
    if carteira_usuario:
        # Organiza os códigos removendo espaços invisíveis e forçando letras maiúsculas
        lista_usuario = [ativo.strip().upper() for ativo in carteira_usuario.split(",") if ativo.strip() != ""]
        
        # Filtra a base do Fundamentus trazendo unicamente o que você escreveu
        df_minha_carteira = df_analise[df_analise.index.isin(lista_usuario)].copy()
        
        if not df_minha_carteira.empty:
            st.write("### 🗂️ Indicadores Fundamentais das Suas Ações:")
            st.dataframe(df_minha_carteira[['Cotação', 'Preço Teto Projetivo', 'Margem de Segurança (%)', 'Nota Cerrado', 'P/L', 'ROE', 'Marg. Líq.']].style.format("{:.2f}"))
            
            st.write("### 💰 Onde Aportar o Dinheiro do Mês:")
            st.write("Abaixo, o algoritmo do Diagrama do Cerrado cruza as notas e direciona seu capital proporcionalmente apenas para os ativos que estão abaixo do preço-teto:")
            
            # Filtra na sua carteira o que está barato e recomendado para compra
            df_oportunidades_carteira = df_minha_carteira[df_minha_carteira['Cotação'] < df_minha_carteira['Preço Teto Projetivo']].copy()
            soma_pesos = df_oportunidades_carteira['Nota Cerrado'].sum()
            
            if soma_pesos > 0:
                df_oportunidades_carteira['Sugestão de Aporte (R$)'] = (df_oportunidades_carteira['Nota Cerrado'] / soma_pesos) * aporte_disponivel
                st.success("Cálculo de Rebalanceamento Concluído!")
                st.dataframe(df_oportunidades_carteira[['Cotação', 'Preço Teto Projetivo', 'Nota Cerrado', 'Sugestão de Aporte (R$)']].style.format({"Cotação": "R$ {:.2f}", "Preço Teto Projetivo": "R$ {:.2f}", "Nota Cerrado": "{:.1f}", "Sugestão de Aporte (R$)": "R$ {:.2f}"}))
            else:
                st.warning("Nenhum ativo digitado da sua carteira está abaixo do preço-teto com este nível de Dividend Yield desejado.")
        else:
            st.info("Nenhum dos códigos digitados foi encontrado nos relatórios ativos da Bolsa.")
    else:
        st.info("💡 Digite os códigos das suas ações acima para ativar o monitoramento da sua carteira pessoal.")
