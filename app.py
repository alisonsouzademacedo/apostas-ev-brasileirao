import streamlit as st
import pandas as pd
import requests
import math

# Configuração da página
st.set_page_config(
    page_title="Sistema de Análise de Valor (EV+) - Brasileirão 2025",
    page_icon="⚽",
    layout="wide"
)

st.title('Sistema de Análise de Valor (EV+) - Brasileirão 2025 ⚽')

# --- CONFIGURAÇÃO DA API ---
API_KEY = st.secrets["api"]["football_api_key"]
API_BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

LEAGUE_ID = 71  # Brasileirão Série A
SEASON = 2025  # ✅ ATUALIZADO PARA 2025

# --- TIMES DO BRASILEIRÃO 2025 ---
BRASILEIRAO_TEAMS = {
    "Athletico-PR": 1050,
    "Atlético-GO": 1062,
    "Atlético-MG": 127,
    "Bahia": 132,
    "Botafogo": 124,
    "Ceará": 134,
    "Corinthians": 131,
    "Criciúma": 1065,
    "Cruzeiro": 128,
    "Flamengo": 123,
    "Fluminense": 125,
    "Fortaleza": 142,
    "Grêmio": 130,
    "Internacional": 129,
    "Juventude": 1071,
    "Mirassol": 2282,
    "Palmeiras": 126,
    "Red Bull Bragantino": 1064,
    "Santos": 121,
    "São Paulo": 119,
    "Sport": 139,
    "Vasco da Gama": 122,
    "Vitória": 135
}

# --- FUNÇÕES ---
def poisson_probability(k, lambda_value):
    if lambda_value <= 0:
        lambda_value = 0.5
    return (lambda_value ** k * math.exp(-lambda_value)) / math.factorial(k)

def calculate_match_probabilities(home_expected_goals, away_expected_goals, max_goals=7):
    prob_matrix = []
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            prob_home = poisson_probability(home_goals, home_expected_goals)
            prob_away = poisson_probability(away_goals, away_expected_goals)
            prob_score = prob_home * prob_away
            prob_matrix.append({'home_goals': home_goals, 'away_goals': away_goals, 'probability': prob_score})
    return prob_matrix

def calculate_market_probabilities(prob_matrix):
    markets = {}
    markets['home_win'] = sum(p['probability'] for p in prob_matrix if p['home_goals'] > p['away_goals'])
    markets['draw'] = sum(p['probability'] for p in prob_matrix if p['home_goals'] == p['away_goals'])
    markets['away_win'] = sum(p['probability'] for p in prob_matrix if p['home_goals'] < p['away_goals'])
    markets['over_2.5'] = sum(p['probability'] for p in prob_matrix if (p['home_goals'] + p['away_goals']) > 2.5)
    markets['under_2.5'] = 1 - markets['over_2.5']
    markets['btts_yes'] = sum(p['probability'] for p in prob_matrix if p['home_goals'] > 0 and p['away_goals'] > 0)
    markets['btts_no'] = 1 - markets['btts_yes']
    return markets

def calculate_ev(probability, bookmaker_odd):
    if bookmaker_odd > 0:
        return (probability * bookmaker_odd) - 1
    return 0

def get_team_statistics(team_id, team_name):
    """Busca estatísticas com mensagens detalhadas"""
    url = f"{API_BASE_URL}/teams/statistics"
    params = {"team": team_id, "season": SEASON, "league": LEAGUE_ID}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'response' in data and data['response']:
                return data['response'], None
            else:
                return None, f"Sem dados disponíveis para {team_name} na temporada 2025"
                
        elif response.status_code == 401:
            return None, "❌ **API Key inválida**"
        elif response.status_code == 429:
            return None, "❌ **Limite de 100 requests/dia atingido**"
        else:
            return None, f"Erro HTTP {response.status_code}"
                
    except requests.exceptions.Timeout:
        return None, "⏱️ **Timeout da API**"
    except Exception as e:
        return None, f"❌ Erro: {str(e)}"

# --- INTERFACE ---
st.header("⚽ Selecione o Confronto")
st.caption(f"Dados atualizados - Temporada 2025 | Rodada ~31/38")

team_names = sorted(BRASILEIRAO_TEAMS.keys())

col1, col2 = st.columns(2)

with col1:
    home_team_name = st.selectbox(
        '🏠 Time da Casa', 
        team_names, 
        index=team_names.index("Fluminense") if "Fluminense" in team_names else 0
    )

with col2:
    away_team_name = st.selectbox(
        '✈️ Time Visitante', 
        team_names, 
        index=team_names.index("Internacional") if "Internacional" in team_names else 1
    )

if home_team_name == away_team_name:
    st.error("⚠️ Os times devem ser diferentes!")
    st.stop()

analyze_button = st.button("🔍 ANALISAR CONFRONTO", type="primary", use_container_width=True)

if analyze_button:
    st.divider()
    st.success(f"Analisando: **{home_team_name}** vs **{away_team_name}**")
    
    home_team_id = BRASILEIRAO_TEAMS[home_team_name]
    away_team_id = BRASILEIRAO_TEAMS[away_team_name]
    
    with st.spinner("🔄 Consultando API-Football (temporada 2025)..."):
        home_stats, home_error = get_team_statistics(home_team_id, home_team_name)
        away_stats, away_error = get_team_statistics(away_team_id, away_team_name)
    
    if home_error or away_error:
        st.error("❌ **Erro ao buscar dados**")
        
        if home_error:
            st.error(f"**{home_team_name}:** {home_error}")
        if away_error:
            st.error(f"**{away_team_name}:** {away_error}")
        
        st.info("""
        **💡 Possíveis causas:**
        - **Limite de requests:** 100/dia no plano gratuito
        - **Temporada 2025:** Verifique se os dados já estão disponíveis na API
        - Aguarde alguns segundos e tente novamente
        """)
        st.stop()
    
    # Processar dados
    try:
        home_goals_for = float(home_stats['goals']['for']['average']['home'] or 0)
        home_goals_against = float(home_stats['goals']['against']['average']['home'] or 0)
        away_goals_for = float(away_stats['goals']['for']['average']['away'] or 0)
        away_goals_against = float(away_stats['goals']['against']['average']['away'] or 0)
        
        expected_home = (home_goals_for + away_goals_against) / 2 if (home_goals_for + away_goals_against) > 0 else 1.0
        expected_away = (away_goals_for + home_goals_against) / 2 if (away_goals_for + home_goals_against) > 0 else 1.0
        
    except Exception as e:
        st.error(f"❌ Erro ao processar: {str(e)}")
        st.stop()
    
    # --- ESTATÍSTICAS ---
    st.header("📊 Estatísticas Temporada 2025")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(f"Gols Esperados - {home_team_name}", f"{expected_home:.2f}")
    with col2:
        st.metric(f"Gols Esperados - {away_team_name}", f"{expected_away:.2f}")
    with col3:
        st.metric("Total Esperado", f"{expected_home + expected_away:.2f}")
    
    prob_matrix = calculate_match_probabilities(expected_home, expected_away)
    markets = calculate_market_probabilities(prob_matrix)
    
    # --- ANÁLISE DE VALOR ---
    st.header("🎯 Análise de Valor (EV+)")
    st.markdown("**Insira as odds para calcular o Valor Esperado**")
    
    positive_ev_bets = []
    
    st.subheader("Resultado do Jogo")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"**Vitória {home_team_name}**")
        st.write(f"Prob: **{markets['home_win']*100:.1f}%**")
        odd_home = st.number_input("Odd:", min_value=1.01, value=2.00, step=0.01, key="home")
        ev_home = calculate_ev(markets['home_win'], odd_home)
        st.metric("EV", f"{ev_home*100:.1f}%", delta="✅" if ev_home > 0 else "❌")
        if ev_home > 0:
            positive_ev_bets.append({'Mercado': f'Vitória {home_team_name}', 'Prob': f"{markets['home_win']*100:.1f}%", 'Odd': odd_home, 'EV': f"{ev_home*100:.1f}%"})
    
    with col2:
        st.write("**Empate**")
        st.write(f"Prob: **{markets['draw']*100:.1f}%**")
        odd_draw = st.number_input("Odd:", min_value=1.01, value=3.00, step=0.01, key="draw")
        ev_draw = calculate_ev(markets['draw'], odd_draw)
        st.metric("EV", f"{ev_draw*100:.1f}%", delta="✅" if ev_draw > 0 else "❌")
        if ev_draw > 0:
            positive_ev_bets.append({'Mercado': 'Empate', 'Prob': f"{markets['draw']*100:.1f}%", 'Odd': odd_draw, 'EV': f"{ev_draw*100:.1f}%"})
    
    with col3:
        st.write(f"**Vitória {away_team_name}**")
        st.write(f"Prob: **{markets['away_win']*100:.1f}%**")
        odd_away = st.number_input("Odd:", min_value=1.01, value=4.00, step=0.01, key="away")
        ev_away = calculate_ev(markets['away_win'], odd_away)
        st.metric("EV", f"{ev_away*100:.1f}%", delta="✅" if ev_away > 0 else "❌")
        if ev_away > 0:
            positive_ev_bets.append({'Mercado': f'Vitória {away_team_name}', 'Prob': f"{markets['away_win']*100:.1f}%", 'Odd': odd_away, 'EV': f"{ev_away*100:.1f}%"})
    
    st.divider()
    
    st.subheader("Over/Under 2.5 Gols")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Mais de 2.5**")
        st.write(f"Prob: **{markets['over_2.5']*100:.1f}%**")
        odd_over = st.number_input("Odd:", min_value=1.01, value=2.50, step=0.01, key="over")
        ev_over = calculate_ev(markets['over_2.5'], odd_over)
        st.metric("EV", f"{ev_over*100:.1f}%", delta="✅" if ev_over > 0 else "❌")
        if ev_over > 0:
            positive_ev_bets.append({'Mercado': 'Mais de 2.5', 'Prob': f"{markets['over_2.5']*100:.1f}%", 'Odd': odd_over, 'EV': f"{ev_over*100:.1f}%"})
    
    with col2:
        st.write("**Menos de 2.5**")
        st.write(f"Prob: **{markets['under_2.5']*100:.1f}%**")
        odd_under = st.number_input("Odd:", min_value=1.01, value=1.80, step=0.01, key="under")
        ev_under = calculate_ev(markets['under_2.5'], odd_under)
        st.metric("EV", f"{ev_under*100:.1f}%", delta="✅" if ev_under > 0 else "❌")
        if ev_under > 0:
            positive_ev_bets.append({'Mercado': 'Menos de 2.5', 'Prob': f"{markets['under_2.5']*100:.1f}%", 'Odd': odd_under, 'EV': f"{ev_under*100:.1f}%"})
    
    st.divider()
    
    st.subheader("Ambos Marcam (BTTS)")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**SIM**")
        st.write(f"Prob: **{markets['btts_yes']*100:.1f}%**")
        odd_btts_yes = st.number_input("Odd:", min_value=1.01, value=2.00, step=0.01, key="btts_yes")
        ev_btts_yes = calculate_ev(markets['btts_yes'], odd_btts_yes)
        st.metric("EV", f"{ev_btts_yes*100:.1f}%", delta="✅" if ev_btts_yes > 0 else "❌")
        if ev_btts_yes > 0:
            positive_ev_bets.append({'Mercado': 'BTTS SIM', 'Prob': f"{markets['btts_yes']*100:.1f}%", 'Odd': odd_btts_yes, 'EV': f"{ev_btts_yes*100:.1f}%"})
    
    with col2:
        st.write("**NÃO**")
        st.write(f"Prob: **{markets['btts_no']*100:.1f}%**")
        odd_btts_no = st.number_input("Odd:", min_value=1.01, value=1.80, step=0.01, key="btts_no")
        ev_btts_no = calculate_ev(markets['btts_no'], odd_btts_no)
        st.metric("EV", f"{ev_btts_no*100:.1f}%", delta="✅" if ev_btts_no > 0 else "❌")
        if ev_btts_no > 0:
            positive_ev_bets.append({'Mercado': 'BTTS NÃO', 'Prob': f"{markets['btts_no']*100:.1f}%", 'Odd': odd_btts_no, 'EV': f"{ev_btts_no*100:.1f}%"})
    
    # --- RESULTADO ---
    st.header("🏆 Apostas com Valor Positivo (EV+)")
    
    if positive_ev_bets:
        sorted_bets = sorted(positive_ev_bets, key=lambda x: float(x['EV'].replace('%', '')), reverse=True)
        df_bets = pd.DataFrame(sorted_bets)
        st.success(f"✅ {len(positive_ev_bets)} apostas com EV+")
        st.dataframe(df_bets, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Nenhuma aposta com EV+ encontrada")

else:
    st.info("👆 Selecione os times e clique em **ANALISAR CONFRONTO**")
    
    with st.expander("ℹ️ Próximos Jogos - 25-26 OUT 2025"):
        st.markdown("""
        **Sábado, 25 de outubro:**
        - Atlético-MG vs Ceará - 16h
        - Vitória vs Corinthians - 16h
        - **Fluminense vs Internacional - 17h30** ⚽
        - Fortaleza vs Flamengo - 19h30
        - São Paulo vs Bahia - 21h30
        
        **Domingo, 26 de outubro:**
        - Botafogo vs Santos - 16h
        - Grêmio vs Juventude - 16h
        - Palmeiras vs Cruzeiro - 20h30
        """)
