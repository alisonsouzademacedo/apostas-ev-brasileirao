import streamlit as st
import pandas as pd
import requests
import math
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Sistema de Análise de Valor (EV+) - Brasileirão",
    page_icon="⚽",
    layout="wide"
)

# Título do Dashboard
st.title('Sistema de Análise de Valor (EV+) - Brasileirão ⚽')

# --- CONFIGURAÇÃO DA API ---
API_KEY = st.secrets["api"]["football_api_key"]
API_BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

# --- FUNÇÕES DE CÁLCULO ---
def poisson_probability(k, lambda_value):
    """Calcula a probabilidade de Poisson para k eventos"""
    return (lambda_value ** k * math.exp(-lambda_value)) / math.factorial(k)

def calculate_match_probabilities(home_expected_goals, away_expected_goals, max_goals=7):
    """Calcula probabilidades de resultados usando distribuição de Poisson"""
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
    """Calcula probabilidades para diferentes mercados de apostas"""
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
    """Calcula o Valor Esperado (EV)"""
    if bookmaker_odd > 0:
        return (probability * bookmaker_odd) - 1
    return 0

# --- FUNÇÕES DA API ---
@st.cache_data(ttl=86400)  # Cache por 24 horas
def get_team_statistics(team_id, season=2024):
    """Busca estatísticas de um time específico"""
    url = f"{API_BASE_URL}/teams/statistics"
    params = {
        "team": team_id,
        "season": season,
        "league": 71  # ID do Brasileirão Série A
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Erro na API: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Erro ao buscar dados: {str(e)}")
        return None

@st.cache_data(ttl=86400)
def get_brasileirao_teams(season=2024):
    """Busca lista de times do Brasileirão"""
    url = f"{API_BASE_URL}/teams"
    params = {
        "league": 71,
        "season": season
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code == 200:
            data = response.json()
            teams = []
            for item in data['response']:
                teams.append({
                    'id': item['team']['id'],
                    'name': item['team']['name']
                })
            return teams
        else:
            st.error(f"Erro na API: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Erro ao buscar times: {str(e)}")
        return []

# --- INÍCIO DA APLICAÇÃO ---
st.header("📊 Dados via API-Football")

# Verificar se a API Key está configurada
if not API_KEY or API_KEY == "COLE_SUA_API_KEY_AQUI":
    st.error("⚠️ API Key não configurada! Configure o arquivo `.streamlit/secrets.toml`")
    st.stop()

# Buscar times do Brasileirão
with st.spinner("Carregando times do Brasileirão..."):
    teams = get_brasileirao_teams()

if not teams:
    st.error("Erro ao carregar times. Verifique sua conexão e API Key.")
    st.stop()

st.success(f"✅ {len(teams)} times carregados com sucesso!")

# --- UI: SELEÇÃO DE TIMES ---
st.header("Selecione os Times para a Análise")

# Criar dicionário de times
team_dict = {team['name']: team['id'] for team in teams}
team_names = sorted(team_dict.keys())

col1, col2 = st.columns(2)

with col1:
    home_team_name = st.selectbox(
        'Selecione o Time da Casa',
        options=team_names,
        index=0
    )
    home_team_id = team_dict[home_team_name]

with col2:
    away_team_name = st.selectbox(
        'Selecione o Time Visitante',
        options=team_names,
        index=1 if len(team_names) > 1 else 0
    )
    away_team_id = team_dict[away_team_name]

# --- ANÁLISE ---
if home_team_name == away_team_name:
    st.error("Erro: O time da casa e o time visitante não podem ser iguais.")
else:
    st.success(f"Análise para o jogo: **{home_team_name}** (Casa) vs **{away_team_name}** (Visitante)")
    
    # Buscar estatísticas dos times
    with st.spinner("Buscando dados da API..."):
        home_stats = get_team_statistics(home_team_id)
        away_stats = get_team_statistics(away_team_id)
    
    if home_stats and away_stats:
        # Extrair dados de gols
        home_goals_home = home_stats['response']['goals']['for']['average']['home']
        home_goals_against_home = home_stats['response']['goals']['against']['average']['home']
        
        away_goals_away = away_stats['response']['goals']['for']['average']['away']
        away_goals_against_away = away_stats['response']['goals']['against']['average']['away']
        
        # Calcular gols esperados
        expected_home_goals = (float(home_goals_home) + float(away_goals_against_away)) / 2
        expected_away_goals = (float(away_goals_away) + float(home_goals_against_home)) / 2
        
        # Exibir estatísticas
        st.header("📊 Estatísticas da Temporada 2024")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(f"Gols Esperados - {home_team_name}", f"{expected_home_goals:.2f}")
        with col2:
            st.metric(f"Gols Esperados - {away_team_name}", f"{expected_away_goals:.2f}")
        with col3:
            st.metric("Total de Gols Esperados", f"{expected_home_goals + expected_away_goals:.2f}")
        
        # Calcular probabilidades
        prob_matrix = calculate_match_probabilities(expected_home_goals, expected_away_goals)
        markets = calculate_market_probabilities(prob_matrix)
        
        # --- ANÁLISE DE VALOR ---
        st.header("🎯 Análise de Valor (EV+)")
        
        positive_ev_bets = []
        
        # Resultado do Jogo
        st.subheader("Resultado do Jogo")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write(f"**Vitória {home_team_name}**")
            st.write(f"Probabilidade: **{markets['home_win']*100:.2f}%**")
            odd_home = st.number_input("Odd:", min_value=1.01, value=2.00, step=0.01, key="home")
            ev_home = calculate_ev(markets['home_win'], odd_home)
            st.metric("EV", f"{ev_home*100:.2f}%", delta="✅ EV+" if ev_home > 0 else "❌ EV-")
            if ev_home > 0:
                positive_ev_bets.append({
                    'Mercado': f'Vitória {home_team_name}',
                    'Probabilidade': f"{markets['home_win']*100:.2f}%",
                    'Odd': odd_home,
                    'EV': f"{ev_home*100:.2f}%"
                })
        
        with col2:
            st.write("**Empate**")
            st.write(f"Probabilidade: **{markets['draw']*100:.2f}%**")
            odd_draw = st.number_input("Odd:", min_value=1.01, value=3.00, step=0.01, key="draw")
            ev_draw = calculate_ev(markets['draw'], odd_draw)
            st.metric("EV", f"{ev_draw*100:.2f}%", delta="✅ EV+" if ev_draw > 0 else "❌ EV-")
            if ev_draw > 0:
                positive_ev_bets.append({
                    'Mercado': 'Empate',
                    'Probabilidade': f"{markets['draw']*100:.2f}%",
                    'Odd': odd_draw,
                    'EV': f"{ev_draw*100:.2f}%"
                })
        
        with col3:
            st.write(f"**Vitória {away_team_name}**")
            st.write(f"Probabilidade: **{markets['away_win']*100:.2f}%**")
            odd_away = st.number_input("Odd:", min_value=1.01, value=4.00, step=0.01, key="away")
            ev_away = calculate_ev(markets['away_win'], odd_away)
            st.metric("EV", f"{ev_away*100:.2f}%", delta="✅ EV+" if ev_away > 0 else "❌ EV-")
            if ev_away > 0:
                positive_ev_bets.append({
                    'Mercado': f'Vitória {away_team_name}',
                    'Probabilidade': f"{markets['away_win']*100:.2f}%",
                    'Odd': odd_away,
                    'EV': f"{ev_away*100:.2f}%"
                })
        
        # Over/Under
        st.subheader("Over/Under - Total de Gols")
        over_markets = [
            ('over_2.5', 'Mais de 2.5 Gols', 2.50),
            ('under_2.5', 'Menos de 2.5 Gols', 1.80),
        ]
        
        cols = st.columns(2)
        for idx, (key, name, default_odd) in enumerate(over_markets):
            with cols[idx]:
                st.write(f"**{name}**")
                st.write(f"Probabilidade: **{markets[key]*100:.2f}%**")
                odd = st.number_input("Odd:", min_value=1.01, value=default_odd, step=0.01, key=key)
                ev = calculate_ev(markets[key], odd)
                st.metric("EV", f"{ev*100:.2f}%", delta="✅ EV+" if ev > 0 else "❌ EV-")
                if ev > 0:
                    positive_ev_bets.append({
                        'Mercado': name,
                        'Probabilidade': f"{markets[key]*100:.2f}%",
                        'Odd': odd,
                        'EV': f"{ev*100:.2f}%"
                    })
        
        # --- RESULTADO FINAL ---
        st.header("🏆 Melhores Apostas de Valor (EV+)")
        
        if len(positive_ev_bets) > 0:
            positive_ev_bets_sorted = sorted(positive_ev_bets, key=lambda x: float(x['EV'].replace('%', '')), reverse=True)
            df_bets = pd.DataFrame(positive_ev_bets_sorted)
            st.success(f"✅ **{len(positive_ev_bets)} apostas com Valor Positivo encontradas!**")
            st.dataframe(df_bets, use_container_width=True, hide_index=True)
        else:
            st.warning("⚠️ Nenhuma aposta com EV+ encontrada com as odds inseridas.")
    else:
        st.error("Erro ao buscar dados dos times.")
