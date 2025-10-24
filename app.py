import streamlit as st
import pandas as pd
import requests
import math

st.set_page_config(page_title="Sistema EV+ - Brasileirão 2025", page_icon="⚽", layout="wide")
st.title('⚽ Sistema de Análise de Valor (EV+) - Brasileirão 2025')

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
API_BASE = "https://www.thesportsdb.com/api/v1/json/3"
LEAGUE_ID = "4351"

@st.cache_data(ttl=3600)
def get_season_results():
    season_formats = ["2025", "2024-2025"]
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
    return None, "Erro ao carregar dados", None

def process_team_stats(events, team_name, venue='home'):
    games = []
    for event in events:
        if not event.get('intHomeScore') or not event.get('intAwayScore'):
            continue
        try:
            if venue == 'home' and event.get('strHomeTeam') == team_name:
                games.append({'scored': int(event['intHomeScore']), 'conceded': int(event['intAwayScore'])})
            elif venue == 'away' and event.get('strAwayTeam') == team_name:
                games.append({'scored': int(event['intAwayScore']), 'conceded': int(event['intHomeScore'])})
        except:
            continue
    if not games:
        return None
    return {
        'games': len(games),
        'scored_avg': sum(g['scored'] for g in games) / len(games),
        'conceded_avg': sum(g['conceded'] for g in games) / len(games)
    }

# --- INICIALIZAR ESTADO ---
if 'multiple_bets' not in st.session_state:
    st.session_state.multiple_bets = []
if 'show_analysis' not in st.session_state:
    st.session_state.show_analysis = False

# --- CARREGAR DADOS ---
with st.spinner("🔄 Carregando dados..."):
    events, error, season_used = get_season_results()

if error or not events:
    st.error(f"❌ {error}")
    st.stop()

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

# --- SEÇÃO 1: ANÁLISE DE JOGO ---
st.header("⚽ Análise de Jogo")
st.caption(f"✅ {completed_games} jogos | {len(team_list)} times | Temporada {season_used}")

col1, col2 = st.columns(2)
with col1:
    home_team = st.selectbox('🏠 Time da Casa', team_list, index=0)
with col2:
    away_team = st.selectbox('✈️ Time Visitante', team_list, index=1)

if home_team != away_team:
    if st.button("🔍 ANALISAR JOGO", type="primary", use_container_width=True):
        st.session_state.show_analysis = True
    
    if st.session_state.show_analysis:
        home_stats = process_team_stats(events, home_team, 'home')
        away_stats = process_team_stats(events, away_team, 'away')
        
        if home_stats and away_stats:
            exp_home = (home_stats['scored_avg'] + away_stats['conceded_avg']) / 2
            exp_away = (away_stats['scored_avg'] + home_stats['conceded_avg']) / 2
            
            st.success(f"**{home_team}** vs **{away_team}**")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(home_team, f"{exp_home:.2f} gols")
            with col2:
                st.metric(away_team, f"{exp_away:.2f} gols")
            with col3:
                st.metric("Total", f"{exp_home + exp_away:.2f} gols")
            
            prob_matrix = calculate_match_probabilities(exp_home, exp_away)
            markets = calculate_markets(prob_matrix)
            
            st.subheader("🎯 Mercados com EV+")
            
            # Container para cada mercado
            markets_data = []
            
            # Resultado
            st.write("**Resultado do Jogo:**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write(f"**{home_team}**")
                st.write(f"Prob: {markets['home_win']*100:.1f}%")
                odd_h = st.number_input("Odd:", 1.01, value=2.00, step=0.01, key=f"h_{home_team}_{away_team}")
                ev_h = calculate_ev(markets['home_win'], odd_h)
                st.metric("EV", f"{ev_h*100:.1f}%", delta="✅" if ev_h > 0 else "")
                
                if ev_h > 0:
                    markets_data.append({
                        'jogo': f"{home_team} vs {away_team}",
                        'mercado': f'Vitória {home_team}',
                        'prob': markets['home_win'],
                        'odd': odd_h,
                        'ev': ev_h,
                        'key': 'h'
                    })
            
            with col2:
                st.write("**Empate**")
                st.write(f"Prob: {markets['draw']*100:.1f}%")
                odd_d = st.number_input("Odd:", 1.01, value=3.00, step=0.01, key=f"d_{home_team}_{away_team}")
                ev_d = calculate_ev(markets['draw'], odd_d)
                st.metric("EV", f"{ev_d*100:.1f}%", delta="✅" if ev_d > 0 else "")
                
                if ev_d > 0:
                    markets_data.append({
                        'jogo': f"{home_team} vs {away_team}",
                        'mercado': 'Empate',
                        'prob': markets['draw'],
                        'odd': odd_d,
                        'ev': ev_d,
                        'key': 'd'
                    })
            
            with col3:
                st.write(f"**{away_team}**")
                st.write(f"Prob: {markets['away_win']*100:.1f}%")
                odd_a = st.number_input("Odd:", 1.01, value=4.00, step=0.01, key=f"a_{home_team}_{away_team}")
                ev_a = calculate_ev(markets['away_win'], odd_a)
                st.metric("EV", f"{ev_a*100:.1f}%", delta="✅" if ev_a > 0 else "")
                
                if ev_a > 0:
                    markets_data.append({
                        'jogo': f"{home_team} vs {away_team}",
                        'mercado': f'Vitória {away_team}',
                        'prob': markets['away_win'],
                        'odd': odd_a,
                        'ev': ev_a,
                        'key': 'a'
                    })
            
            # Over/Under
            st.write("**Over/Under 2.5 Gols:**")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Mais de 2.5**")
                st.write(f"Prob: {markets['over_2.5']*100:.1f}%")
                odd_o = st.number_input("Odd:", 1.01, value=2.50, step=0.01, key=f"o_{home_team}_{away_team}")
                ev_o = calculate_ev(markets['over_2.5'], odd_o)
                st.metric("EV", f"{ev_o*100:.1f}%", delta="✅" if ev_o > 0 else "")
                
                if ev_o > 0:
                    markets_data.append({
                        'jogo': f"{home_team} vs {away_team}",
                        'mercado': 'Mais de 2.5',
                        'prob': markets['over_2.5'],
                        'odd': odd_o,
                        'ev': ev_o,
                        'key': 'o'
                    })
            
            with col2:
                st.write("**Menos de 2.5**")
                st.write(f"Prob: {markets['under_2.5']*100:.1f}%")
                odd_u = st.number_input("Odd:", 1.01, value=1.80, step=0.01, key=f"u_{home_team}_{away_team}")
                ev_u = calculate_ev(markets['under_2.5'], odd_u)
                st.metric("EV", f"{ev_u*100:.1f}%", delta="✅" if ev_u > 0 else "")
                
                if ev_u > 0:
                    markets_data.append({
                        'jogo': f"{home_team} vs {away_team}",
                        'mercado': 'Menos de 2.5',
                        'prob': markets['under_2.5'],
                        'odd': odd_u,
                        'ev': ev_u,
                        'key': 'u'
                    })
            
            # Botões de adicionar
            if markets_data:
                st.divider()
                st.write("**➕ Adicionar à Múltipla:**")
                
                for market in markets_data:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"{market['mercado']} - Odd {market['odd']:.2f} - EV {market['ev']*100:.1f}%")
                    with col2:
                        if st.button("Adicionar", key=f"add_{market['key']}_{home_team}_{away_team}"):
                            st.session_state.multiple_bets.append(market)
                            st.success("✅")

# --- SEÇÃO 2: MÚLTIPLA ---
st.divider()
st.header("🎰 Sua Múltipla")

if len(st.session_state.multiple_bets) > 0:
    st.success(f"✅ {len(st.session_state.multiple_bets)} apostas")
    
    # Mostrar apostas
    for idx, bet in enumerate(st.session_state.multiple_bets):
        col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 1])
        with col1:
            st.write(f"**{bet['jogo']}**")
        with col2:
            st.write(bet['mercado'])
        with col3:
            st.write(f"{bet['odd']:.2f}")
        with col4:
            st.write(f"{bet['ev']*100:.1f}%")
        with col5:
            if st.button("🗑️", key=f"del_{idx}"):
                st.session_state.multiple_bets.pop(idx)
                st.rerun()
    
    st.divider()
    
    # Calcular múltipla
    odd_total = 1
    prob_total = 1
    for bet in st.session_state.multiple_bets:
        odd_total *= bet['odd']
        prob_total *= bet['prob']
    
    ev_multiple = calculate_ev(prob_total, odd_total)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Odd Total", f"{odd_total:.2f}")
    with col2:
        st.metric("Prob. Combinada", f"{prob_total*100:.2f}%")
    with col3:
        st.metric("EV Múltipla", f"{ev_multiple*100:.1f}%", delta="✅" if ev_multiple > 0 else "❌")
    
    # Gerenciamento
    st.subheader("💰 Gestão de Banca")
    stake = st.number_input("Valor (R$):", min_value=1.0, value=100.0, step=10.0)
    
    retorno = stake * odd_total
    lucro = retorno - stake
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Investimento", f"R$ {stake:.2f}")
    with col2:
        st.metric("Retorno se Ganhar", f"R$ {retorno:.2f}")
    with col3:
        st.metric("Lucro", f"R$ {lucro:.2f}", delta=f"+{lucro:.2f}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Limpar Tudo", use_container_width=True):
            st.session_state.multiple_bets = []
            st.rerun()
    with col2:
        df = pd.DataFrame(st.session_state.multiple_bets)
        csv = df.to_csv(index=False)
        st.download_button("💾 Baixar CSV", csv, "multipla.csv", "text/csv", use_container_width=True)

else:
    st.info("👆 Analise jogos e adicione apostas EV+")
