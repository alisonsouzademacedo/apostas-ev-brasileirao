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

# IDs para Brasileirão Série A
LEAGUE_ID = 71  # Brasil Série A
SEASON = 2024

# --- FUNÇÕES DE CÁLCULO ---
def poisson_probability(k, lambda_value):
    """Calcula a probabilidade de Poisson"""
    if lambda_value <= 0:
        return 0
    return (lambda_value ** k * math.exp(-lambda_value)) / math.factorial(k)

def calculate_match_probabilities(home_expected_goals, away_expected_goals, max_goals=7):
    """Calcula probabilidades usando Poisson"""
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
    """Calcula EV"""
    if bookmaker_odd > 0:
        return (probability * bookmaker_odd) - 1
    return 0

# --- FUNÇÕES DA API ---
@st.cache_data(ttl=3600)
def get_brasileirao_teams():
    """Busca times do Brasileirão"""
    url = f"{API_BASE_URL}/teams"
    params = {
        "league": LEAGUE_ID,
        "season": SEASON
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('response'):
                teams = []
                for item in data['response']:
                    teams.append({
                        'id': item['team']['id'],
                        'name': item['team']['name']
                    })
                return teams, None
            else:
                return [], "Nenhum time encontrado na resposta da API"
        else:
            return [], f"Erro HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return [], f"Erro na requisição: {str(e)}"

@st.cache_data(ttl=3600)
def get_team_statistics(team_id):
    """Busca estatísticas de um time"""
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
                return None, "Sem dados na resposta"
        else:
            return None, f"Erro HTTP {response.status_code}"
    except Exception as e:
        return None, f"Erro: {str(e)}"

# --- INTERFACE ---
st.header("📊 Análise com API-Football")

# Verificar API Key
if not API_KEY or API_KEY == "COLE_SUA_API_KEY_AQUI":
    st.error("⚠️ API Key não configurada!")
    st.stop()

# Buscar times
with st.spinner("Carregando times..."):
    teams, error = get_brasileirao_teams()

if error:
    st.error(f"❌ Erro: {error}")
    st.info("💡 Verifique se sua API Key está correta e se você ainda tem requests disponíveis (100/dia no plano gratuito)")
    st.stop()

if not teams:
    st.error("Nenhum time encontrado")
    st.stop()

st.success(f"✅ {len(teams)} times carregados!")

# --- SELEÇÃO DE TIMES ---
st.header("Selecione os Times")

team_dict = {team['name']: team['id'] for team in teams}
team_names = sorted(team_dict.keys())

col1, col2 = st.columns(2)

with col1:
    home_team_name = st.selectbox('Time da Casa', team_names, index=0)
    home_team_id = team_dict[home_team_name]

with col2:
    away_team_name = st.selectbox('Time Visitante', team_names, index=1 if len(team_names) > 1 else 0)
    away_team_id = team_dict[away_team_name]

if home_team_name == away_team_name:
    st.error("Times devem ser diferentes")
    st.stop()

st.success(f"**{home_team_name}** (Casa) vs **{away_team_name}** (Visitante)")

# --- BUSCAR ESTATÍSTICAS ---
with st.spinner("Buscando estatísticas..."):
    home_stats, home_error = get_team_statistics(home_team_id)
    away_stats, away_error = get_team_statistics(away_team_id)

if home_error or away_error:
    st.error("Erro ao buscar estatísticas")
    if home_error:
        st.write(f"Casa: {home_error}")
    if away_error:
        st.write(f"Visitante: {away_error}")
    st.stop()

# --- EXTRAIR DADOS ---
try:
    # Dados do time da casa (jogando em casa)
    home_goals_for = float(home_stats['goals']['for']['average']['home'] or 0)
    home_goals_against = float(home_stats['goals']['against']['average']['home'] or 0)
    
    # Dados do time visitante (jogando fora)
    away_goals_for = float(away_stats['goals']['for']['average']['away'] or 0)
    away_goals_against = float(away_stats['goals']['against']['average']['away'] or 0)
    
    # Gols esperados
    expected_home = (home_goals_for + away_goals_against) / 2 if (home_goals_for + away_goals_against) > 0 else 1.0
    expected_away = (away_goals_for + home_goals_against) / 2 if (away_goals_for + home_goals_against) > 0 else 1.0
    
except Exception as e:
    st.error(f"Erro ao processar dados: {str(e)}")
    st.stop()

# --- EXIBIR ESTATÍSTICAS ---
st.header("📊 Estatísticas Temporada 2024")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(f"Gols Esperados - {home_team_name}", f"{expected_home:.2f}")
with col2:
    st.metric(f"Gols Esperados - {away_team_name}", f"{expected_away:.2f}")
with col3:
    st.metric("Total Esperado", f"{expected_home + expected_away:.2f}")

# --- CALCULAR PROBABILIDADES ---
prob_matrix = calculate_match_probabilities(expected_home, expected_away)
markets = calculate_market_probabilities(prob_matrix)

# --- ANÁLISE DE VALOR ---
st.header("🎯 Análise de Valor (EV+)")

positive_ev_bets = []

# Resultado
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

# Over/Under
st.subheader("Over/Under Gols")
over_markets = [
    ('over_2.5', 'Mais de 2.5', 2.50),
    ('under_2.5', 'Menos de 2.5', 1.80),
]

cols = st.columns(2)
for idx, (key, name, default_odd) in enumerate(over_markets):
    with cols[idx]:
        st.write(f"**{name}**")
        st.write(f"Prob: **{markets[key]*100:.1f}%**")
        odd = st.number_input("Odd:", min_value=1.01, value=default_odd, step=0.01, key=key)
        ev = calculate_ev(markets[key], odd)
        st.metric("EV", f"{ev*100:.1f}%", delta="✅" if ev > 0 else "❌")
        if ev > 0:
            positive_ev_bets.append({'Mercado': name, 'Prob': f"{markets[key]*100:.1f}%", 'Odd': odd, 'EV': f"{ev*100:.1f}%"})

# BTTS
st.subheader("Ambos Marcam")
col1, col2 = st.columns(2)

with col1:
    st.write("**BTTS - SIM**")
    st.write(f"Prob: **{markets['btts_yes']*100:.1f}%**")
    odd_btts_yes = st.number_input("Odd:", min_value=1.01, value=2.00, step=0.01, key="btts_yes")
    ev_btts_yes = calculate_ev(markets['btts_yes'], odd_btts_yes)
    st.metric("EV", f"{ev_btts_yes*100:.1f}%", delta="✅" if ev_btts_yes > 0 else "❌")
    if ev_btts_yes > 0:
        positive_ev_bets.append({'Mercado': 'BTTS SIM', 'Prob': f"{markets['btts_yes']*100:.1f}%", 'Odd': odd_btts_yes, 'EV': f"{ev_btts_yes*100:.1f}%"})

with col2:
    st.write("**BTTS - NÃO**")
    st.write(f"Prob: **{markets['btts_no']*100:.1f}%**")
    odd_btts_no = st.number_input("Odd:", min_value=1.01, value=1.80, step=0.01, key="btts_no")
    ev_btts_no = calculate_ev(markets['btts_no'], odd_btts_no)
    st.metric("EV", f"{ev_btts_no*100:.1f}%", delta="✅" if ev_btts_no > 0 else "❌")
    if ev_btts_no > 0:
        positive_ev_bets.append({'Mercado': 'BTTS NÃO', 'Prob': f"{markets['btts_no']*100:.1f}%", 'Odd': odd_btts_no, 'EV': f"{ev_btts_no*100:.1f}%"})

# --- RESULTADO ---
st.header("🏆 Melhores Apostas EV+")

if positive_ev_bets:
    sorted_bets = sorted(positive_ev_bets, key=lambda x: float(x['EV'].replace('%', '')), reverse=True)
    df_bets = pd.DataFrame(sorted_bets)
    st.success(f"✅ {len(positive_ev_bets)} apostas com EV+")
    st.dataframe(df_bets, use_container_width=True, hide_index=True)
else:
    st.warning("⚠️ Nenhuma aposta com EV+ encontrada")
