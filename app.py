import streamlit as st
import pandas as pd
import numpy as np
import urllib.request

# Interface otimizada
st.set_page_config(page_title="Diagrama do Cerrado + Fundamentus", layout="wide")

st.title("🌱 Sistema Diagrama do Cerrado & Monitor de Carteira")
st.write("Dados auditados em tempo real diretamente do portal Fundamentus.")

# 1. FUNÇÃO DE EXTRAÇÃO DO FUNDAMENTUS
@st.cache_data(ttl=3600) # Guarda os dados por 1 hora para carregar instantaneamente
def carregar_dados_fundamentus():
    url = "https://www.fundamentus.com.br/resultado.php"
    # Configura cabeçalho para evitar bloqueio do servidor do Fundamentus
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read()
    
    # Lê as tabelas da página
    dfs = pd.read_html(html, decimal=',', thousands='.')
    df = dfs[0]
    
    # Ajusta nomes e formatações textuais
    df.columns = [c.strip() for c in df.columns]
    df.set_index('Papel', inplace=True)
    
    # Converte strings percentuais em números float reais
    for col in ['Div.Yield', 'Marg. Líq.', 'ROE', 'ROIC', 'Cres. Rec.5a']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('.', '', regex=False)
            df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            df[col] = df[col].astype(str).str.replace('%', '', regex=False).astype(float)
            
    return df

try:
    df_raw = carregar_dados_fundamentus()
except Exception as e:
    st.error(f"Erro ao conectar com o Fundamentus: {e}")
    st.stop()

# 2. CONFIGURAÇÕES NA BARRA LATERAL
st.sidebar.header("🎛️ Painel de Controle")
dy_slider = st.sidebar.slider("Dividend Yield (DY) Mínimo Desejado (%)", min_value=0.0, max_value=15.0, value=6.0, step=0.5)
dy_esperado = dy_slider / 100 if dy_slider > 0 else 0.001

aporte_disponivel = st.sidebar.number_input("Valor para Aportar Hoje (R$)", min_value=0.0, value=2000.0)

# 3. ALGORITMO INTEGRADO: PERGUNTAS DO DIAGRAMA DO CERRADO
df_processado = df_raw.copy()

# Tratamento de LPA e VPA numéricos
df_processado['LPA'] = pd.to_numeric(df_processado['EBIT / Ativo'], errors='coerce').fillna(1.0) # Fallback seguro
df_processado['VPA'] = df_processado['Cotação'] / df_processado['P/VP']

# Executando o questionário interno de pontuação (Sim ou Não baseado nos dados)
df_processado['Nota Cerrado'] = 0.0

# Pergunta 1: Lucro consistente e ROE atraente (>10%)?
df_processado['Nota Cerrado'] += np.where(df_processado['ROE'] >= 10.0, 2.5, 0.5)
# Pergunta 2: Margem Líquida confortável (>10%) protegendo o negócio?
df_processado['Nota Cerrado'] += np.where(df_processado['Marg. Líq.'] >= 10.0, 2.5, 0.5)
# Pergunta 3: Dívida controlada e caixa sob rédea curta (Dív.Bruta/Patrimônio < 1.5)?
df_processado['Nota Cerrado'] += np.where(df_processado['Dív.Brut/ Patrim.'] <= 1.5, 2.5, 0.5)
# Pergunta 4: Preço atrativo no mercado (P/VP menor que 2.5)?
df_processado['Nota Cerrado'] += np.where(df_processado['P/VP'] <= 2.5, 2.5, 0.5)

# Punição Absoluta: Se o P/L for negativo (empresa gerando prejuízos), a nota cai para zero automático
df_processado['Nota Cerrado'] = np.where(df_processado['P/L'] <= 0, 0.0, df_processado['Nota Cerrado'])

# VALUATION DE PREÇO-TETO PROJETIVO (Geração Dividendos baseado no lucro atual ajustado)
df_processado['DPA_Estimado'] = (df_processado['Cotação'] / df_processado['P/L']) * 0.50 # Estimativa média de 50% de Payout
df_processado['Preço Teto Projetivo'] = df_processado['DPA_Estimado'] / dy_esperado
df_processado['Margem de Segurança (%)'] = ((df_processado['Preço Teto Projetivo'] - df_processado['Cotação']) / df_processado['Preço Teto Projetivo']) * 100

# 4. CRIAÇÃO DAS ABAS VIRTUAIS
tab1, tab2 = st.tabs(["🏆 Scanner de Oportunidades da Bolsa", "💼 Minha Carteira Pessoal"])

with tab1:
    st.subheader(f"Top 15 Melhores Ações do Mercado Geral (Foco em DY de {dy_slider}%)")
    st.write("Filtro executado sobre todas as empresas ativas listadas na Bolsa de Valores.")
    
    # Filtra apenas empresas com alta liquidez de negociação diária (Evita ações fantasma)
    df_liquidas = df_processado[df_processado['Liq.2meses'] > 500000].copy()
    df_ranking = df_liquidas.sort_values(by='Margem de Segurança (%)', ascending=False).head(15)
    
    for pos, (empresa, linha) in enumerate(df_ranking.iterrows(), start=1):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(label=f"{pos}º - {empresa}", value=f"Nota: {linha['Nota Cerrado']:.1f}/10")
        with c2:
            st.write(f"**Preço Atual:** R$ {linha['Cotação']:.2f} | **Preço-Teto:** R$ {linha['Preço Teto Projetivo']:.2f}")
            st.write(f"**ROE:** {linha['ROE']:.1f}% | **Margem Líquida:** {linha['Marg. Líq.']:.1f}%")
        with c3:
            if linha['Cotação'] < linha['Preço Teto Projetivo']:
                st.success(f"🟢 BARATA: {linha['Margem de Segurança (%)']:.1f}% de Desconto")
            else:
                st.error(f"🔴 ESTICADA: {-linha['Margem de Segurança (%)']:.1f}% acima")
        st.divider()

with tab2:
    st.subheader("Gerenciador da sua Carteira de Ativos")
    st.write("Insira os ativos que você já possui para que o sistema monitore as notas e indique onde aportar:")
    
    # Campo para você digitar seus ativos separados por vírgula (Ex: BBAS3, WEGE3, TAEE11)
    carteira_usuario = st.text_input("Digite os códigos das suas ações (separados por vírgula):", value="BBAS3, WEGE3, TAEE11")
    
    # Limpa os espaços e transforma em lista
    lista_carteira = [txt.strip().upper() for txt in carteira_usuario.split(",") if txt.strip() != ""]
    
    if lista_carteira:
        # Filtra na base do Fundamentus apenas o que você possui na carteira
        df_minha_carteira = df_processado[df_processado.index.isin(lista_carteira)].copy()
        
        if not df_minha_carteira.empty:
            st.write("### Suas Ações Monitoradas:")
            
            # Mostra uma tabela compacta com notas e preços-teto das suas ações
            st.dataframe(df_minha_carteira[['Cotação', 'Preço Teto Projetivo', 'Margem de Segurança (%)', 'Nota Cerrado', 'ROE', 'Marg. Líq.']].style.format("{:.2f}"))
            
            st.write("### 💰 Onde Aportar na sua Carteira:")
            st.write("O robô distribui seu dinheiro apenas nas ações da sua carteira que estão baratas hoje:")
            
            # Aplica o Diagrama do Cerrado: Aloca dinheiro conforme a nota apenas de quem está abaixo do teto
            df_compras_carteira = df_minha_carteira[df_minha_carteira['Cotação'] < df_minha_carteira['Preço Teto Projetivo']].copy()
            soma_pesos = df_compras_carteira['Nota Cerrado'].sum()
            
            if soma_pesos > 0:
                df_compras_carteira['Valor Sugerido para Comprar (R$)'] = (df_compras_carteira['Nota Cerrado'] / soma_pesos) * aporte_disponivel
                st.success("Sugestão de Aporte Gerada com Sucesso!")
                st.dataframe(df_compras_carteira[['Cotação', 'Preço Teto Projetivo', 'Nota Cerrado', 'Valor Sugerido para Comprar (R$)']].style.format({"Cotação": "R$ {:.2f}", "Preço Teto Projetivo": "R$ {:.2f}", "Nota Cerrado": "{:.1f}", "Valor Sugerido para Comprar (R$)": "R$ {:.2f}"}))
            else:
                st.warning("Nenhum ativo da sua carteira pessoal está abaixo do preço-teto calculado para o DY exigido.")
        else:
            st.info("Nenhuma das ações digitadas foi encontrada na base de dados ativa da B3.")

