import streamlit as st
import pandas as pd
import requests
import math

st.set_page_config(page_title="Sistema EV+ - Brasileirão 2025", page_icon="⚽", layout="wide")
st.title('⚽ Sistema de Análise de Valor (EV+) - Brasileirão 2025')

# --- API TheSportsDB ---
API_BASE = "https://www.thesportsdb.com/api/v1/json/3"
LEAGUE_ID = "4351"

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
    """Busca resultados da temporada 2025"""
    # Tentar diferentes formatos de season
    season_formats = ["2025", "2024-2025", "2024/2025"]
    
    for season in season_formats:
        url = f"{API_BASE}/eventsseason.php?id={LEAGUE_ID}&s={season}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data and data.get('events') and len(data['events']) > 0:
                    return data['events'], None, season
        except:
            continue
    
    return None, "Nenhum formato de temporada funcionou", None

def process_team_stats(events, team_name, venue='home'):
    """Processa estatísticas de um time"""
    games = []
    
    for event in events:
        # Verificar se o jogo já aconteceu
        if not event.get('intHomeScore') or not event.get('intAwayScore'):
            continue
        
        try:
            if venue == 'home' and event.get('strHomeTeam') == team_name:
                games.append({
                    'scored': int(event['intHomeScore']),
                    'conceded': int(event['intAwayScore'])
                })
            elif venue == 'away' and event.get('strAwayTeam') == team_name:
                games.append({
                    'scored': int(event['intAwayScore']),
                    'conceded': int(event['intHomeScore'])
                })
        except:
            continue
    
    if not games:
        return None
    
    return {
        'games': len(games),
        'scored_avg': sum(g['scored'] for g in games) / len(games),
        'conceded_avg': sum(g['conceded'] for g in games) / len(games)
    }

# --- INTERFACE ---
st.header("⚽ Selecione o Confronto")

with st.spinner("🔄 Carregando dados..."):
    events, error, season_used = get_season_results()

if error or not events:
    st.error(f"❌ Erro: {error}")
    
    # DEBUG
    with st.expander("🔧 Informações de Debug"):
        st.write("Tentando buscar dados da API TheSportsDB...")
        st.write(f"League ID: {LEAGUE_ID}")
        st.write("Formatos de temporada tentados: 2025, 2024-2025, 2024/2025")
        
        # Teste manual
        test_url = f"{API_BASE}/eventsseason.php?id={LEAGUE_ID}&s=2024-2025"
        st.write(f"**URL de teste:** {test_url}")
        
        try:
            test_response = requests.get(test_url, timeout=10)
            st.write(f"**Status:** {test_response.status_code}")
            if test_response.status_code == 200:
                test_data = test_response.json()
                st.json(test_data)
        except Exception as e:
            st.write(f"Erro: {str(e)}")
    
    st.stop()

# Extrair times
teams = set()
completed_games = 0

for event in events:
    if event.get('intHomeScore') and event.get('intAwayScore'):
        completed_games += 1
    if event.get('strHomeTeam'):
        teams.add(event['strHomeTeam'])
    if event.get('strAwayTeam'):
        teams.add(event['strAwayTeam'])

team_list = sorted(list(teams))

if not team_list:
    st.error("Nenhum time encontrado")
    st.stop()

st.success(f"✅ {completed_games} jogos completos | {len(team_list)} times | Temporada: {season_used}")

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
    
    home_stats = process_team_stats(events, home_team, 'home')
    away_stats = process_team_stats(events, away_team, 'away')
    
    if not home_stats or not away_stats:
        st.error("❌ Dados insuficientes")
        st.info(f"Jogos de {home_team} em casa: {home_stats['games'] if home_stats else 0}")
        st.info(f"Jogos de {away_team} fora: {away_stats['games'] if away_stats else 0}")
        st.stop()
    
    exp_home = (home_stats['scored_avg'] + away_stats['conceded_avg']) / 2
    exp_away = (away_stats['scored_avg'] + home_stats['conceded_avg']) / 2
    
    st.header("📊 Estatísticas")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(f"{home_team}", f"{exp_home:.2f} gols", help=f"{home_stats['games']} jogos em casa")
    with col2:
        st.metric(f"{away_team}", f"{exp_away:.2f} gols", help=f"{away_stats['games']} jogos fora")
    with col3:
        st.metric("Total", f"{exp_home + exp_away:.2f} gols")
    
    prob_matrix = calculate_match_probabilities(exp_home, exp_away)
    markets = calculate_markets(prob_matrix)
    
    st.header("🎯 Análise de Valor")
    
    positive_bets = []
    
    st.subheader("Resultado")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"**{home_team}**")
        st.write(f"**{markets['home_win']*100:.1f}%**")
        odd_h = st.number_input("Odd:", 1.01, value=2.00, step=0.01, key="h")
        ev_h = calculate_ev(markets['home_win'], odd_h)
        st.metric("EV", f"{ev_h*100:.1f}%", delta="✅" if ev_h > 0 else "❌")
        if ev_h > 0:
            positive_bets.append({'Mercado': f'{home_team}', 'Prob': f"{markets['home_win']*100:.1f}%", 'Odd': odd_h, 'EV': f"{ev_h*100:.1f}%"})
    
    with col2:
        st.write("**Empate**")
        st.write(f"**{markets['draw']*100:.1f}%**")
        odd_d = st.number_input("Odd:", 1.01, value=3.00, step=0.01, key="d")
        ev_d = calculate_ev(markets['draw'], odd_d)
        st.metric("EV", f"{ev_d*100:.1f}%", delta="✅" if ev_d > 0 else "❌")
        if ev_d > 0:
            positive_bets.append({'Mercado': 'Empate', 'Prob': f"{markets['draw']*100:.1f}%", 'Odd': odd_d, 'EV': f"{ev_d*100:.1f}%"})
    
    with col3:
        st.write(f"**{away_team}**")
        st.write(f"**{markets['away_win']*100:.1f}%**")
        odd_a = st.number_input("Odd:", 1.01, value=4.00, step=0.01, key="a")
        ev_a = calculate_ev(markets['away_win'], odd_a)
        st.metric("EV", f"{ev_a*100:.1f}%", delta="✅" if ev_a > 0 else "❌")
        if ev_a > 0:
            positive_bets.append({'Mercado': f'{away_team}', 'Prob': f"{markets['away_win']*100:.1f}%", 'Odd': odd_a, 'EV': f"{ev_a*100:.1f}%"})
    
    st.subheader("Over/Under 2.5")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Mais de 2.5**")
        st.write(f"**{markets['over_2.5']*100:.1f}%**")
        odd_o = st.number_input("Odd:", 1.01, value=2.50, step=0.01, key="o")
        ev_o = calculate_ev(markets['over_2.5'], odd_o)
        st.metric("EV", f"{ev_o*100:.1f}%", delta="✅" if ev_o > 0 else "❌")
        if ev_o > 0:
            positive_bets.append({'Mercado': '+ 2.5', 'Prob': f"{markets['over_2.5']*100:.1f}%", 'Odd': odd_o, 'EV': f"{ev_o*100:.1f}%"})
    
    with col2:
        st.write("**Menos de 2.5**")
        st.write(f"**{markets['under_2.5']*100:.1f}%**")
        odd_u = st.number_input("Odd:", 1.01, value=1.80, step=0.01, key="u")
        ev_u = calculate_ev(markets['under_2.5'], odd_u)
        st.metric("EV", f"{ev_u*100:.1f}%", delta="✅" if ev_u > 0 else "❌")
        if ev_u > 0:
            positive_bets.append({'Mercado': '- 2.5', 'Prob': f"{markets['under_2.5']*100:.1f}%", 'Odd': odd_u, 'EV': f"{ev_u*100:.1f}%"})
    
    st.header("🏆 Apostas EV+")
    
    if positive_bets:
        sorted_bets = sorted(positive_bets, key=lambda x: float(x['EV'].replace('%', '')), reverse=True)
        df = pd.DataFrame(sorted_bets)
        st.success(f"✅ {len(positive_bets)} apostas")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Nenhuma aposta EV+")

else:
    st.info("👆 Selecione e clique em ANALISAR")
