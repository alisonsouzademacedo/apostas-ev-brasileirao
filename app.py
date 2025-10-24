import streamlit as st
import pandas as pd
import requests
import math
from datetime import datetime

st.set_page_config(
    page_title="Sistema EV+ - Brasileirão 2025",
    page_icon="⚽",
    layout="wide"
)

st.title('⚽ Sistema de Análise de Valor (EV+) - Brasileirão 2025')

# --- API TheSportsDB (GRATUITA) ---
API_BASE = "https://www.thesportsdb.com/api/v1/json/3"
LEAGUE_ID = "4351"  # Brasileirão Série A

# --- FUNÇÕES MATEMÁTICAS ---
def poisson_probability(k, lambda_value):
    if lambda_value <= 0:
        lambda_value = 0.5
    return (lambda_value ** k * math.exp(-lambda_value)) / math.factorial(k)

def calculate_match_probabilities(home_exp, away_exp, max_goals=7):
    prob_matrix = []
    for hg in range(max_goals + 1):
        for ag in range(max_goals + 1):
            p = poisson_probability(hg, home_exp) * poisson_probability(ag, away_exp)
            prob_matrix.append({'home_goals': hg, 'away_goals': ag, 'probability': p})
    return prob_matrix

def calculate_markets(prob_matrix):
    m = {}
    m['home_win'] = sum(p['probability'] for p in prob_matrix if p['home_goals'] > p['away_goals'])
    m['draw'] = sum(p['probability'] for p in prob_matrix if p['home_goals'] == p['away_goals'])
    m['away_win'] = sum(p['probability'] for p in prob_matrix if p['home_goals'] < p['away_goals'])
    m['over_2.5'] = sum(p['probability'] for p in prob_matrix if (p['home_goals'] + p['away_goals']) > 2.5)
    m['under_2.5'] = 1 - m['over_2.5']
    m['btts_yes'] = sum(p['probability'] for p in prob_matrix if p['home_goals'] > 0 and p['away_goals'] > 0)
    m['btts_no'] = 1 - m['btts_yes']
    return m

def calculate_ev(prob, odd):
    return (prob * odd) - 1 if odd > 0 else 0

# --- FUNÇÕES DA API ---
@st.cache_data(ttl=3600)
def get_season_results():
    """Busca TODOS os resultados da temporada 2025"""
    url = f"{API_BASE}/eventsseason.php?id={LEAGUE_ID}&s=2024-2025"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and data.get('events'):
                return data['events'], None
        return None, "Sem dados"
    except Exception as e:
        return None, str(e)

def process_team_stats(events, team_name, venue='home'):
    """Processa estatísticas de um time"""
    games = []
    
    for event in events:
        if event.get('intHomeScore') is None or event.get('intAwayScore') is None:
            continue
            
        if venue == 'home' and event['strHomeTeam'] == team_name:
            games.append({
                'scored': int(event['intHomeScore']),
                'conceded': int(event['intAwayScore'])
            })
        elif venue == 'away' and event['strAwayTeam'] == team_name:
            games.append({
                'scored': int(event['intAwayScore']),
                'conceded': int(event['intHomeScore'])
            })
    
    if not games:
        return None
    
    scored_avg = sum(g['scored'] for g in games) / len(games)
    conceded_avg = sum(g['conceded'] for g in games) / len(games)
    
    return {
        'games': len(games),
        'scored_avg': scored_avg,
        'conceded_avg': conceded_avg
    }

# --- INTERFACE ---
st.header("⚽ Selecione o Confronto")

# Carregar dados
with st.spinner("🔄 Carregando dados da temporada 2025..."):
    events, error = get_season_results()

if error or not events:
    st.error(f"❌ Erro ao carregar dados: {error}")
    st.stop()

# Extrair lista de times únicos
teams = set()
for event in events:
    if event.get('strHomeTeam'):
        teams.add(event['strHomeTeam'])
    if event.get('strAwayTeam'):
        teams.add(event['strAwayTeam'])

team_list = sorted(list(teams))

if not team_list:
    st.error("Nenhum time encontrado")
    st.stop()

st.success(f"✅ {len(events)} jogos carregados | {len(team_list)} times")

col1, col2 = st.columns(2)

with col1:
    home_team = st.selectbox('🏠 Time da Casa', team_list, index=team_list.index("Fluminense") if "Fluminense" in team_list else 0)

with col2:
    away_team = st.selectbox('✈️ Time Visitante', team_list, index=team_list.index("Internacional") if "Internacional" in team_list else 1)

if home_team == away_team:
    st.error("⚠️ Times devem ser diferentes")
    st.stop()

analyze_btn = st.button("🔍 ANALISAR CONFRONTO", type="primary", use_container_width=True)

if analyze_btn:
    st.divider()
    st.success(f"Analisando: **{home_team}** vs **{away_team}**")
    
    # Processar estatísticas
    home_stats = process_team_stats(events, home_team, 'home')
    away_stats = process_team_stats(events, away_team, 'away')
    
    if not home_stats or not away_stats:
        st.error("❌ Dados insuficientes para análise")
        st.stop()
    
    # Calcular gols esperados
    exp_home = (home_stats['scored_avg'] + away_stats['conceded_avg']) / 2
    exp_away = (away_stats['scored_avg'] + home_stats['conceded_avg']) / 2
    
    # --- ESTATÍSTICAS ---
    st.header("📊 Estatísticas Temporada 2025")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(f"Gols Esperados - {home_team}", f"{exp_home:.2f}", help=f"Baseado em {home_stats['games']} jogos em casa")
    with col2:
        st.metric(f"Gols Esperados - {away_team}", f"{exp_away:.2f}", help=f"Baseado em {away_stats['games']} jogos fora")
    with col3:
        st.metric("Total Esperado", f"{exp_home + exp_away:.2f}")
    
    # Calcular probabilidades
    prob_matrix = calculate_match_probabilities(exp_home, exp_away)
    markets = calculate_markets(prob_matrix)
    
    # --- ANÁLISE DE VALOR ---
    st.header("🎯 Análise de Valor (EV+)")
    
    positive_bets = []
    
    st.subheader("Resultado")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"**{home_team}**")
        st.write(f"Prob: **{markets['home_win']*100:.1f}%**")
        odd_h = st.number_input("Odd:", min_value=1.01, value=2.00, step=0.01, key="h")
        ev_h = calculate_ev(markets['home_win'], odd_h)
        st.metric("EV", f"{ev_h*100:.1f}%", delta="✅" if ev_h > 0 else "❌")
        if ev_h > 0:
            positive_bets.append({'Mercado': f'Vitória {home_team}', 'Prob': f"{markets['home_win']*100:.1f}%", 'Odd': odd_h, 'EV': f"{ev_h*100:.1f}%"})
    
    with col2:
        st.write("**Empate**")
        st.write(f"Prob: **{markets['draw']*100:.1f}%**")
        odd_d = st.number_input("Odd:", min_value=1.01, value=3.00, step=0.01, key="d")
        ev_d = calculate_ev(markets['draw'], odd_d)
        st.metric("EV", f"{ev_d*100:.1f}%", delta="✅" if ev_d > 0 else "❌")
        if ev_d > 0:
            positive_bets.append({'Mercado': 'Empate', 'Prob': f"{markets['draw']*100:.1f}%", 'Odd': odd_d, 'EV': f"{ev_d*100:.1f}%"})
    
    with col3:
        st.write(f"**{away_team}**")
        st.write(f"Prob: **{markets['away_win']*100:.1f}%**")
        odd_a = st.number_input("Odd:", min_value=1.01, value=4.00, step=0.01, key="a")
        ev_a = calculate_ev(markets['away_win'], odd_a)
        st.metric("EV", f"{ev_a*100:.1f}%", delta="✅" if ev_a > 0 else "❌")
        if ev_a > 0:
            positive_bets.append({'Mercado': f'Vitória {away_team}', 'Prob': f"{markets['away_win']*100:.1f}%", 'Odd': odd_a, 'EV': f"{ev_a*100:.1f}%"})
    
    st.divider()
    
    st.subheader("Over/Under 2.5")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Mais de 2.5**")
        st.write(f"Prob: **{markets['over_2.5']*100:.1f}%**")
        odd_o = st.number_input("Odd:", min_value=1.01, value=2.50, step=0.01, key="o")
        ev_o = calculate_ev(markets['over_2.5'], odd_o)
        st.metric("EV", f"{ev_o*100:.1f}%", delta="✅" if ev_o > 0 else "❌")
        if ev_o > 0:
            positive_bets.append({'Mercado': 'Mais de 2.5', 'Prob': f"{markets['over_2.5']*100:.1f}%", 'Odd': odd_o, 'EV': f"{ev_o*100:.1f}%"})
    
    with col2:
        st.write("**Menos de 2.5**")
        st.write(f"Prob: **{markets['under_2.5']*100:.1f}%**")
        odd_u = st.number_input("Odd:", min_value=1.01, value=1.80, step=0.01, key="u")
        ev_u = calculate_ev(markets['under_2.5'], odd_u)
        st.metric("EV", f"{ev_u*100:.1f}%", delta="✅" if ev_u > 0 else "❌")
        if ev_u > 0:
            positive_bets.append({'Mercado': 'Menos de 2.5', 'Prob': f"{markets['under_2.5']*100:.1f}%", 'Odd': odd_u, 'EV': f"{ev_u*100:.1f}%"})
    
    # --- RESULTADO ---
    st.header("🏆 Apostas com EV+")
    
    if positive_bets:
        sorted_bets = sorted(positive_bets, key=lambda x: float(x['EV'].replace('%', '')), reverse=True)
        df = pd.DataFrame(sorted_bets)
        st.success(f"✅ {len(positive_bets)} apostas com valor positivo")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Nenhuma aposta com EV+")

else:
    st.info("👆 Selecione os times e clique em ANALISAR")
