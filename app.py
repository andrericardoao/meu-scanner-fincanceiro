import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup

# Configuração de interface adaptável para computadores e celulares
st.set_page_config(page_title="Diagrama do Cerrado + Fundamentus", layout="wide")

st.title("🌱 Sistema Diagrama do Cerrado & Monitor de Carteira")
st.write("Dados extraídos de forma segura e imediata diretamente do portal Fundamentus.")

# 1. CAPTURA BLINDADA DE DADOS DO FUNDAMENTUS
@st.cache_data(ttl=3600) # Mantém na memória por 1 hora para carregar instantaneamente
def carregar_dados_fundamentus_seguro():
    url = "https://www.fundamentus.com.br/resultado.php"
    
    # Cabeçalho de simulação de navegador real (Evita o bloqueio e o erro de conexão)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    resposta = requests.get(url, headers=headers)
    soup = BeautifulSoup(resposta.text, 'html.parser')
    tabela = soup.find('table', {'id': 'resultado'})
    
    # Converte o HTML da tabela diretamente em um painel estruturado do Pandas
    df = pd.read_html(str(tabela), decimal=',', thousands='.')[0]
    
    # Ajusta os nomes das colunas limpando espaços
    df.columns = [c.strip() for c in df.columns]
    df.set_index('Papel', inplace=True)
    
    # Processa e limpa os símbolos de porcentagem transformando em números puros
    colunas_percentuais = ['Div.Yield', 'Marg. Líq.', 'ROE', 'ROIC', 'Cres. Rec.5a']
    for col in colunas_percentuais:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('.', '', regex=False)
            df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            df[col] = df[col].astype(str).str.replace('%', '', regex=False).astype(float)
            
    return df

try:
    df_raw = carregar_dados_fundamentus_seguro()
except Exception as e:
    st.error(f"Erro na comunicação dos servidores: {e}")
    st.stop()

# 2. CONFIGURAÇÕES DA BARRA LATERAL (PAINEL DO INVESTIDOR)
st.sidebar.header("🎛️ Critérios de Rendimento")
dy_slider = st.sidebar.slider("Dividend Yield (DY) Desejado (%)", min_value=0.0, max_value=15.0, value=6.0, step=0.5)
dy_esperado = dy_slider / 100 if dy_slider > 0 else 0.001

aporte_disponivel = st.sidebar.number_input("Valor do Aporte Mensal (R$)", min_value=0.0, value=2000.0)

# 3. TRATAMENTO MATEMÁTICO INTEGRANDO O DIAGRAMA DO CERRADO
df_processado = df_raw.copy()

# Ajuste técnico para converter cotação e múltiplos em formatos numéricos limpos
df_processado['Cotação'] = pd.to_numeric(df_processado['Cotação'], errors='coerce')
df_processado['P/L'] = pd.to_numeric(df_processado['P/L'], errors='coerce')
df_processado['P/VP'] = pd.to_numeric(df_processado['P/VP'], errors='coerce')

# Gerando as Notas do Cerrado baseadas estritamente nas regras fundamentalistas (0 a 10)
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

# VALUATION PROJETIVO MÓVEL DE VALOR INTRÍNSECO
# DPA Estimado = (Cotação / P/L) * Payout Médio Padrão do Mercado de 50%
df_processado['DPA_Estimado'] = (df_processado['Cotação'] / df_processado['P/L']) * 0.50
df_processado['Preço Teto Projetivo'] = df_processado['DPA_Estimado'] / dy_esperado
df_processado['Margem de Segurança (%)'] = ((df_processado['Preço Teto Projetivo'] - df_processado['Cotação']) / df_processado['Preço Teto Projetivo']) * 100

# 4. CRIAÇÃO DAS ABAS DE NAVEGAÇÃO DO APLICATIVO
tab1, tab2 = st.tabs(["🏆 Scanner Geral da Bolsa", "💼 Minha Carteira Monitorada"])

with tab1:
    st.subheader(f"Top 15 Melhores Ações do Mercado Geral (Foco em DY de {dy_slider}%)")
    st.write("Filtro inteligente focado apenas em ações com volume relevante de negociação diária.")
    
    # Filtra e elimina ações sem volume de negociação (Ações fantasmas)
    df_liquidas = df_processado[df_processado['Liq.2meses'] > 500000].copy()
    df_ranking = df_liquidas.sort_values(by='Margem de Segurança (%)', ascending=False).head(15)
    
    for pos, (empresa, linha) in enumerate(df_ranking.iterrows(), start=1):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(label=f"{pos}º Lugar - {empresa}", value=f"Nota: {linha['Nota Cerrado']:.1f}/10")
        with c2:
            st.write(f"**Preço de Tela:** R$ {linha['Cotação']:.2f} | **Preço-Teto:** R$ {linha['Preço Teto Projetivo']:.2f}")
            st.write(f"**P/L Real:** {linha['P/L']:.2f} | **Margem Líquida:** {linha['Marg. Líq.']:.1f}%")
        with c3:
            if linha['Cotação'] < linha['Preço Teto Projetivo']:
                st.success(f"🟢 OPORTUNIDADE: {linha['Margem de Segurança (%)']:.1f}% de Desconto")
            else:
                st.error(f"🔴 EXCEDEU O TETO: Está {-linha['Margem de Segurança (%)']:.1f}% mais cara")
        st.divider()

with tab2:
    st.subheader("Gerenciador da Sua Carteira Pessoal")
    st.write("Digite os códigos das ações que você possui. O sistema irá rastrear os múltiplos de cada uma delas de forma dedicada.")
    
    # Campo interativo onde você digita seus ativos
    carteira_usuario = st.text_input("Códigos das ações em carteira (separe por vírgula):", value="BBAS3, WEGE3, TAEE11")
    
    # Limpa caracteres invisíveis e padroniza as letras maiúsculas
    lista_carteira = [t.strip().upper() for t in carteira_usuario.split(",") if t.strip() != ""]
    
    if lista_carteira:
        df_minha_carteira = df_processado[df_processado.index.isin(lista_carteira)].copy()
        
        if not df_minha_carteira.empty:
            st.write("### Seus Ativos Monitorados:")
            st.dataframe(df_minha_carteira[['Cotação', 'Preço Teto Projetivo', 'Margem de Segurança (%)', 'Nota Cerrado', 'ROE', 'Marg. Líq.']].style.format("{:.2f}"))
            
            st.write("### 💰 Onde Aportar Hoje na sua Carteira:")
            st.write("Seguindo à risca a lógica do Raul Sena, seu capital do mês será pulverizado apenas nos papéis da sua carteira que estão abaixo do preço-teto:")
            
            # Filtra apenas o que está com preço atrativo na carteira do usuário
            df_compras_carteira = df_minha_carteira[df_minha_carteira['Cotação'] < df_minha_carteira['Preço Teto Projetivo']].copy()
            soma_pesos = df_compras_carteira['Nota Cerrado'].sum()
            
            if soma_pesos > 0:
                df_compras_carteira['Sugestão de Aporte (R$)'] = (df_compras_carteira['Nota Cerrado'] / soma_pesos) * aporte_disponivel
                st.success("Cálculo de Rebalanceamento Concluído!")
                st.dataframe(df_compras_carteira[['Cotação', 'Preço Teto Projetivo', 'Nota Cerrado', 'Sugestão de Aporte (R$)']].style.format({"Cotação": "R$ {:.2f}", "Preço Teto Projetivo": "R$ {:.2f}", "Nota Cerrado": "{:.1f}", "Sugestão de Aporte (R$)": "R$ {:.2f}"}))
            else:
                st.warning("Nenhum ativo da sua carteira está em preço de barganha para o Yield selecionado neste momento.")
