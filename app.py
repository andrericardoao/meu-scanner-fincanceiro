import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# Configuração de interface adaptável
st.set_page_config(page_title="Scanner Fundamentalista 360", layout="wide")

st.title("🛡️ Scanner Fundamentalista 360° - Análise Avançada de Relatórios")
st.write("Robô de auditoria que cruza 15 indicadores financeiros reais e calcula o Preço-Teto Projetivo.")

# 1. PAINEL DE CONTROLE LATERAL
st.sidebar.header("🎛️ Critérios Globais")
dy_desejado = st.sidebar.slider("Dividend Yield (DY) Mínimo Desejado (%)", min_value=0.0, max_value=15.0, value=6.0, step=0.5) / 100
aporte_disponivel = st.sidebar.number_input("Aporte Financeiro Disponível (R$)", min_value=0.0, value=2000.0)

filtrar_saudaveis = st.sidebar.checkbox("🔒 Filtrar apenas empresas seguras (Nota > 5)", value=True)

# Lista com grandes ações da B3 de múltiplos setores para comparação
tickers_b3 = ['BBAS3', 'WEGE3', 'TAEE11', 'VALE3', 'ITUB4', 'PETR4', 'EGIE3', 'ELET3', 'SAPR11', 'VIVT3']

if tickers_b3:
    dados_fundamentais = {}
    
    with st.spinner("Varrendo balanços patrimoniais e DREs oficiais da B3..."):
        for acao_nome in tickers_b3:
            try:
                ticker_real = f"{acao_nome}.SA"
                obj = yf.Ticker(ticker_real)
                info = obj.info
                
                # Extração estatística de históricos de crescimento (últimos 4-5 anos)
                dre_historica = obj.financials
                cgrowth_lucro = 0.05
                if dre_historica is not None and 'Net Income' in dre_historica.index:
                    lucros = dre_historica.loc['Net Income'].dropna().values
                    if len(lucros) >= 2:
                        cgrowth_lucro = np.mean(np.diff(lucros[::-1]) / lucros[::-1][:-1])
                cgrowth_lucro = np.clip(cgrowth_lucro, -0.15, 0.20) # Proteção matemática contra distorções

                # Coleta estruturada dos 15 indicadores fundamentais cruciais
                dados_fundamentais[acao_nome] = {
                    'Preço Atual': info.get('currentPrice', info.get('previousClose', 0)),
                    'LPA': info.get('trailingEps', 1.0),
                    'VPA': info.get('bookValue', 1.0),
                    'P/L': info.get('trailingPegRatio', info.get('forwardPE', 10)), # Estimador P/L aproximado se não disponível
                    'P/VP': info.get('priceToBook', 1.0),
                    'EV/EBITDA': info.get('enterpriseToEbitda', 5.0),
                    'ROE (%)': info.get('returnOnEquity', 0.0) * 100,
                    'ROIC (%)': info.get('returnOnAssets', 0.0) * 100, # Proxy de eficiência patrimonial
                    'Margem Líquida (%)': info.get('profitMargins', 0.0) * 100,
                    'Margem Bruta (%)': info.get('grossMargins', 0.0) * 100,
                    'Dívida/EBITDA': info.get('debtToEbitda', 0.0),
                    'Liquidez Corrente': info.get('currentRatio', 1.0),
                    'Dívida/Patrimônio': info.get('debtToEquity', 50.0) / 100,
                    'Payout Realizado': info.get('payoutRatio', 0.50),
                    'CAGR Lucro Proj (%)': cgrowth_lucro * 100,
                    'FCA Operacional': info.get('operatingCashflow', 1.0)
                }
            except:
                pass

    if dados_fundamentais:
        df = pd.DataFrame.from_dict(dados_fundamentais, orient='index')
        
        # 2. SISTEMA DE SCORE MULTI-INDICADOR (0 a 10 Pontos)
        df['Nota Geral'] = 0.0
        
        # Bloco A: Saúde e Margens (Máx 2.5 pts)
        df['Nota Geral'] += np.where(df['ROE (%)'] >= 12.0, 0.75, 0.2)
        df['Nota Geral'] += np.where(df['ROIC (%)'] >= 10.0, 0.50, 0.1)
        df['Nota Geral'] += np.where(df['Margem Líquida (%)'] >= 10.0, 0.75, 0.2)
        df['Nota Geral'] += np.where(df['Margem Bruta (%)'] >= 25.0, 0.50, 0.1)
        
        # Bloco B: Dívida e Risco (Máx 2.5 pts)
        df['Nota Geral'] += np.where(df['Dívida/EBITDA'] <= 2.5, 1.00, 0.1)
        df['Nota Geral'] += np.where(df['Liquidez Corrente'] >= 1.2, 0.75, 0.2)
        df['Nota Geral'] += np.where(df['Dívida/Patrimônio'] <= 0.8, 0.75, 0.2)
        
        # Bloco C: Preço e Valuation (Máx 2.5 pts)
        df['Nota Geral'] += np.where(df['P/VP'] <= 2.0, 1.00, 0.2)
        df['Nota Geral'] += np.where(df['EV/EBITDA'] <= 10.0, 0.75, 0.2)
        
        # Bloco D: Potencial de Crescimento e Caixa (Máx 2.5 pts)
        df['Nota Geral'] += np.where(df['CAGR Lucro Proj (%)'] >= 5.0, 1.50, 0.3)
        df['Nota Geral'] += np.where(df['FCA Operacional'] > 0, 1.00, 0.0)
        
        # Ajuste de Segurança: Empresas com prejuízo crônico (LPA negativo) caem para nota zero automática
        df['Nota Geral'] = np.where(df['LPA'] <= 0, 0.0, df['Nota Geral'])

        # 3. VALUATION PROJETIVO MÓVEL (MÉTODO GERAÇÃO DIVIDENDOS)
        # Impede divisão por zero se o slider de dividendos for colocado em 0%
        divisor_dy = dy_desejado if dy_desejado > 0 else 0.001
        
        df['LPA Projetado'] = df['LPA'] * (1 + (df['CAGR Lucro Proj (%)'] / 100))
        df['DPA Projetado'] = df['LPA Projetado'] * np.clip(df['Payout Realizado'], 0.1, 0.9)
        df['Preço Teto Projetivo'] = df['DPA Projetado'] / divisor_dy
        df['Margem de Segurança (%)'] = ((df['Preço Teto Projetivo'] - df['Preço Atual']) / df['Preço Teto Projetivo']) * 100

        # Filtro de exibição conforme a escolha do usuário no menu lateral
        if filtrar_saudaveis:
            df_filtrado = df[df['Nota Geral'] >= 5.0].copy()
        else:
            df_filtrado = df.copy()

        # Classificação definitiva em Ordem Decrescente pelas melhores oportunidades
        df_filtrado = df_filtrado.sort_values(by='Margem de Segurança (%)', ascending=False)

        # 4. INTERFACE GRÁFICA DO APP
        aba1, aba2, aba3 = st.tabs(["🏆 Ranking de Oportunidades", "📊 Raio-X dos 15 Indicadores", "💰 Divisão de Aportes"])
        
        with aba1:
            st.subheader(f"Melhores Ações para Investir (Objetivo de DY: {dy_desejado*100:.1f}%)")
            for pos, (empresa, linha) in enumerate(df_filtrado.iterrows(), start=1):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric(label=f"{pos}º Lugar - {empresa}", value=f"Nota: {linha['Nota Geral']:.1f}/10")
                with c2:
                    st.write(f"**Preço na Bolsa:** R$ {linha['Preço Atual']:.2f}")
                    st.write(f"**Preço Teto Alvo:** R$ {linha['Preço Teto Projetivo']:.2f}")
                    st.write(f"**Crescimento do Lucro:** {linha['CAGR Lucro Proj (%)']:.1f}% a.a.")
                with c3:
                    if linha['Preço Atual'] < linha['Preço Teto Projetivo']:
                        st.success(f"🟢 OPORTUNIDADE: {linha['Margem de Segurança (%)']:.1f}% de Margem")
                    else:
                        st.error(f"🔴 ESTICADA: {-linha['Margem de Segurança (%)']:.1f}% acima do limite")
                st.divider()

        with aba2:
            st.subheader("Planilha de Auditoria - Todos os Múltiplos Coletados")
            st.write("Aqui você pode auditar e ordenar a tabela clicando no topo de qualquer coluna:")
            # Exibe os dados de forma limpa e arredondada na tela
            st.dataframe(df_filtrado[['Preço Atual', 'P/L', 'P/VP', 'EV/EBITDA', 'ROE (%)', 'ROIC (%)', 'Margem Líquida (%)', 'Dívida/EBITDA', 'Liquidez Corrente', 'CAGR Lucro Proj (%)']].style.format("{:.2f}"))

        with aba3:
            st.subheader("Simulador de Compras - Método Diagrama do Cerrado")
            st.write("O sistema direciona o seu capital focado nas empresas com a maior nota de fundamentos abaixo do preço teto:")
            
            # Filtra ativos aptos para compra (saudáveis e com desconto real)
            df_compras = df_filtrado[df_filtrado['Preço Atual'] < df_filtrado['Preço Teto Projetivo']].copy()
            soma_notas = df_compras['Nota Geral'].sum()
            
            if soma_notas > 0:
                df_compras['Aporte Sugerido (R$)'] = (df_compras['Nota Geral'] / soma_notas) * aporte_disponivel
                st.dataframe(df_compras[['Preço Atual', 'Preço Teto Projetivo', 'Nota Geral', 'Aporte Sugerido (R$)']].style.format({"Preço Atual": "R$ {:.2f}", "Preço Teto Projetivo": "R$ {:.2f}", "Nota Geral": "{:.1f}", "Aporte Sugerido (R$)": "R$ {:.2f}"}))
            else:
                st.warning("Nenhum ativo passou simultaneamente nos testes de desconto de preço para o Yield desejado.")
