import streamlit as st
import pandas as pd
import requests
import math

# Configuração da página
st.set_page_config(
    page_title="Sistema de Análise de Valor (EV+) - Brasileirão",
    page_icon="⚽",
    layout="wide"
)

st.title('Sistema de Análise de Valor (EV+) - Brasileirão ⚽')

# --- CONFIGURAÇÃO DA API ---
API_KEY = st.secrets["api"]["football_api_key"]
API_BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

LEAGUE_ID = 71  # Brasileirão Série A
SEASON = 2024

# --- TIMES DO BRASILEIRÃO 2024 (LISTA FIXA) ---
BRASILEIRAO_TEAMS = {
    "Athletico-PR": 1050,
    "Atlético-GO": 1062,
    "Atlético-MG": 127,
    "Bahia": 132,
    "Botafogo": 124,
    "Corinthians": 131,
    "Criciúma": 1065,
    "Cruzeiro": 128,
    "Cuiabá": 1074,
    "Flamengo": 123,
    "Fluminense": 125,
    "Fortaleza": 142,
    "Grêmio": 130,
    "Internacional": 129,
    "Juventude": 1071,
    "Palmeiras": 126,
    "Red Bull Bragantino": 1064,
    "São Paulo": 119,
    "Vasco da Gama": 122,
    "Vitória": 135
}

# --- FUNÇÕES DE CÁLCULO ---
def poisson_probability(k, lambda_value):
    """Calcula probabilidade de Poisson"""
    if lambda_value <= 0:
        lambda_value = 0.5
    return (lambda_value ** k * math.exp(-lambda_value)) / math.factorial(k)

def calculate_match_probabilities(home_expected_goals, away_expected_goals, max_goals=7):
    """Calcula probabilidades de placares"""
    prob_matrix = []
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            prob_home = poisson_probability(home_goals, home_expected_goals)
            prob_away = poisson_probability(away_goals, away_expected_goals)
            prob_score = prob_home * prob_away
            prob_matrix.append({
                'home_goals': home_goals,
                'away_goals': away_goals,
                'probability': prob_score
            })
    return prob_matrix

def calculate_market_probabilities(prob_matrix):
    """Calcula probabilidades de mercados"""
    markets = {}
    markets['home_win'] = sum(p['probability'] for p in prob_matrix if p['home_goals'] > p['away_goals'])
    markets['draw'] = sum(p['probability'] for p in prob_matrix if p['home_goals'] == p['away_goals'])
    markets['away_win'] = sum(p['probability'] for p in prob_matrix if p['home_goals'] < p['away_goals'])
    markets['over_1.5'] = sum(p['probability'] for p in prob_matrix if (p['home_goals'] + p['away_goals']) > 1.5)
    markets['over_2.5'] = sum(p['probability'] for p in prob_matrix if (p['home_goals'] + p['away_goals']) > 2.5)
    markets['over_3.5'] = sum(p['probability'] for p in prob_matrix if (p['home_goals'] + p['away_goals']) > 3.5)
    markets['under_1.5'] = 1 - markets['over_1.5']
    markets['under_2.5'] = 1 - markets['over_2.5']
    markets['under_3.5'] = 1 - markets['over_3.5']
    markets['btts_yes'] = sum(p['probability'] for p in prob_matrix if p['home_goals'] > 0 and p['away_goals'] > 0)
    markets['btts_no'] = 1 - markets['btts_yes']
    return markets

def calculate_ev(probability, bookmaker_odd):
    """Calcula Valor Esperado (EV)"""
    if bookmaker_odd > 0:
        return (probability * bookmaker_odd) - 1
    return 0

# --- FUNÇÕES DA API ---
def get_team_statistics(team_id, team_name):
    """Busca estatísticas de um time na API"""
    url = f"{API_BASE_URL}/teams/statistics"
    params = {
        "team": team_id,
        "season": SEASON,
        "league": LEAGUE_ID
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('response'):
                return data['response'], None
            else:
                return None, f"Sem dados para {team_name}"
        elif response.status_code == 401:
            return None, "API Key inválida ou expirada"
        elif response.status_code == 429:
            return None, "Limite de requisições atingido (100/dia)"
        else:
            return None, f"Erro HTTP {response.status_code}"
    except Exception as e:
        return None, f"Erro: {str(e)}"

# --- INTERFACE ---
st.header("⚽ Selecione o Confronto")

# Lista de times ordenada
team_names = sorted(BRASILEIRAO_TEAMS.keys())

col1, col2 = st.columns(2)

with col1:
    home_team_name = st.selectbox(
        '🏠 Time da Casa',
        options=team_names,
        index=team_names.index("Flamengo") if "Flamengo" in team_names else 0
    )

with col2:
    away_team_name = st.selectbox(
        '✈️ Time Visitante',
        options=team_names,
        index=team_names.index("Palmeiras") if "Palmeiras" in team_names else 1
    )

# Validação
if home_team_name == away_team_name:
    st.error("⚠️ Os times devem ser diferentes!")
    st.stop()

# Botão de análise
analyze_button = st.button("🔍 ANALISAR CONFRONTO", type="primary", use_container_width=True)

if analyze_button:
    st.divider()
    st.success(f"Analisando: **{home_team_name}** (Casa) vs **{away_team_name}** (Visitante)")
    
    # Buscar dados dos times
    home_team_id = BRASILEIRAO_TEAMS[home_team_name]
    away_team_id = BRASILEIRAO_TEAMS[away_team_name]
    
    with st.spinner("🔄 Consultando API-Football..."):
        home_stats, home_error = get_team_statistics(home_team_id, home_team_name)
        away_stats, away_error = get_team_statistics(away_team_id, away_team_name)
    
    # Verificar erros
    if home_error or away_error:
        st.error("❌ Erro ao buscar dados")
        if home_error:
            st.write(f"**{home_team_name}:** {home_error}")
        if away_error:
            st.write(f"**{away_team_name}:** {away_error}")
        st.info("💡 **Dica:** Verifique se você ainda tem requests disponíveis (100/dia no plano gratuito)")
        st.stop()
    
    # Processar estatísticas
    try:
        # Time da casa (jogando em casa)
        home_goals_for = float(home_stats['goals']['for']['average']['home'] or 0)
        home_goals_against = float(home_stats['goals']['against']['average']['home'] or 0)
        
        # Time visitante (jogando fora)
        away_goals_for = float(away_stats['goals']['for']['average']['away'] or 0)
        away_goals_against = float(away_stats['goals']['against']['average']['away'] or 0)
        
        # Calcular gols esperados
        expected_home = (home_goals_for + away_goals_against) / 2 if (home_goals_for + away_goals_against) > 0 else 1.0
        expected_away = (away_goals_for + home_goals_against) / 2 if (away_goals_for + home_goals_against) > 0 else 1.0
        
    except Exception as e:
        st.error(f"❌ Erro ao processar dados: {str(e)}")
        st.stop()
    
    # --- EXIBIR ESTATÍSTICAS ---
    st.header("📊 Estatísticas da Temporada 2024")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label=f"Gols Esperados - {home_team_name}",
            value=f"{expected_home:.2f}",
            help="Baseado em gols marcados em casa e gols sofridos fora pelo adversário"
        )
    
    with col2:
        st.metric(
            label=f"Gols Esperados - {away_team_name}",
            value=f"{expected_away:.2f}",
            help="Baseado em gols marcados fora e gols sofridos em casa pelo adversário"
        )
    
    with col3:
        st.metric(
            label="Total de Gols Esperados",
            value=f"{expected_home + expected_away:.2f}",
            help="Soma dos gols esperados de ambos os times"
        )
    
    # --- CALCULAR PROBABILIDADES ---
    prob_matrix = calculate_match_probabilities(expected_home, expected_away)
    markets = calculate_market_probabilities(prob_matrix)
    
    # --- ANÁLISE DE VALOR ---
    st.header("🎯 Análise de Valor (EV+)")
    st.markdown("**Insira as odds da casa de apostas para calcular o Valor Esperado**")
    
    positive_ev_bets = []
    
    # RESULTADO DO JOGO
    st.subheader("Resultado do Jogo")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"**Vitória {home_team_name}**")
        st.write(f"Probabilidade: **{markets['home_win']*100:.1f}%**")
        odd_home = st.number_input("Odd da Casa:", min_value=1.01, value=2.00, step=0.01, key="home")
        ev_home = calculate_ev(markets['home_win'], odd_home)
        st.metric("EV", f"{ev_home*100:.1f}%", delta="✅ EV+" if ev_home > 0 else "❌ EV-")
        if ev_home > 0:
            positive_ev_bets.append({
                'Mercado': f'Vitória {home_team_name}',
                'Probabilidade': f"{markets['home_win']*100:.1f}%",
                'Odd': odd_home,
                'EV': f"{ev_home*100:.1f}%"
            })
    
    with col2:
        st.write("**Empate**")
        st.write(f"Probabilidade: **{markets['draw']*100:.1f}%**")
        odd_draw = st.number_input("Odd da Casa:", min_value=1.01, value=3.00, step=0.01, key="draw")
        ev_draw = calculate_ev(markets['draw'], odd_draw)
        st.metric("EV", f"{ev_draw*100:.1f}%", delta="✅ EV+" if ev_draw > 0 else "❌ EV-")
        if ev_draw > 0:
            positive_ev_bets.append({
                'Mercado': 'Empate',
                'Probabilidade': f"{markets['draw']*100:.1f}%",
                'Odd': odd_draw,
                'EV': f"{ev_draw*100:.1f}%"
            })
    
    with col3:
        st.write(f"**Vitória {away_team_name}**")
        st.write(f"Probabilidade: **{markets['away_win']*100:.1f}%**")
        odd_away = st.number_input("Odd da Casa:", min_value=1.01, value=4.00, step=0.01, key="away")
        ev_away = calculate_ev(markets['away_win'], odd_away)
        st.metric("EV", f"{ev_away*100:.1f}%", delta="✅ EV+" if ev_away > 0 else "❌ EV-")
        if ev_away > 0:
            positive_ev_bets.append({
                'Mercado': f'Vitória {away_team_name}',
                'Probabilidade': f"{markets['away_win']*100:.1f}%",
                'Odd': odd_away,
                'EV': f"{ev_away*100:.1f}%"
            })
    
    st.divider()
    
    # OVER/UNDER
    st.subheader("Over/Under - Total de Gols")
    over_markets = [
        ('over_2.5', 'Mais de 2.5 Gols', 2.50),
        ('under_2.5', 'Menos de 2.5 Gols', 1.80),
    ]
    
    cols = st.columns(2)
    for idx, (key, name, default_odd) in enumerate(over_markets):
        with cols[idx]:
            st.write(f"**{name}**")
            st.write(f"Probabilidade: **{markets[key]*100:.1f}%**")
            odd = st.number_input("Odd da Casa:", min_value=1.01, value=default_odd, step=0.01, key=key)
            ev = calculate_ev(markets[key], odd)
            st.metric("EV", f"{ev*100:.1f}%", delta="✅ EV+" if ev > 0 else "❌ EV-")
            if ev > 0:
                positive_ev_bets.append({
                    'Mercado': name,
                    'Probabilidade': f"{markets[key]*100:.1f}%",
                    'Odd': odd,
                    'EV': f"{ev*100:.1f}%"
                })
    
    st.divider()
    
    # AMBOS MARCAM
    st.subheader("Ambos Marcam (BTTS)")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Ambos Marcam - SIM**")
        st.write(f"Probabilidade: **{markets['btts_yes']*100:.1f}%**")
        odd_btts_yes = st.number_input("Odd da Casa:", min_value=1.01, value=2.00, step=0.01, key="btts_yes")
        ev_btts_yes = calculate_ev(markets['btts_yes'], odd_btts_yes)
        st.metric("EV", f"{ev_btts_yes*100:.1f}%", delta="✅ EV+" if ev_btts_yes > 0 else "❌ EV-")
        if ev_btts_yes > 0:
            positive_ev_bets.append({
                'Mercado': 'Ambos Marcam - SIM',
                'Probabilidade': f"{markets['btts_yes']*100:.1f}%",
                'Odd': odd_btts_yes,
                'EV': f"{ev_btts_yes*100:.1f}%"
            })
    
    with col2:
        st.write("**Ambos Marcam - NÃO**")
        st.write(f"Probabilidade: **{markets['btts_no']*100:.1f}%**")
        odd_btts_no = st.number_input("Odd da Casa:", min_value=1.01, value=1.80, step=0.01, key="btts_no")
        ev_btts_no = calculate_ev(markets['btts_no'], odd_btts_no)
        st.metric("EV", f"{ev_btts_no*100:.1f}%", delta="✅ EV+" if ev_btts_no > 0 else "❌ EV-")
        if ev_btts_no > 0:
            positive_ev_bets.append({
                'Mercado': 'Ambos Marcam - NÃO',
                'Probabilidade': f"{markets['btts_no']*100:.1f}%",
                'Odd': odd_btts_no,
                'EV': f"{ev_btts_no*100:.1f}%"
            })
    
    # --- RESULTADO FINAL ---
    st.header("🏆 Melhores Apostas de Valor (EV+)")
    
    if len(positive_ev_bets) > 0:
        sorted_bets = sorted(positive_ev_bets, key=lambda x: float(x['EV'].replace('%', '')), reverse=True)
        df_bets = pd.DataFrame(sorted_bets)
        st.success(f"✅ **{len(positive_ev_bets)} apostas com Valor Positivo encontradas!**")
        st.dataframe(df_bets, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Nenhuma aposta com EV+ encontrada com as odds inseridas.")

else:
    st.info("👆 Selecione os times e clique em **ANALISAR CONFRONTO** para começar")
