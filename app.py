import streamlit as st
import pandas as pd
import requests
import math
from datetime import datetime, timedelta
import json

st.set_page_config(page_title="Sistema EV+ - Brasileirão 2025", page_icon="⚽", layout="wide")

# ==================== FUNÇÕES MATEMÁTICAS ====================

def poisson_probability(k, lambda_value):
    if lambda_value <= 0:
        lambda_value = 0.5
    return (lambda_value ** k * math.exp(-lambda_value)) / math.factorial(k)

def calculate_match_probabilities(home_expected_goals, away_expected_goals, max_goals=7):
    probability_matrix = []
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            probability = poisson_probability(home_goals, home_expected_goals) * poisson_probability(away_goals, away_expected_goals)
            probability_matrix.append({
                'home_goals': home_goals,
                'away_goals': away_goals,
                'probability': probability
            })
    return probability_matrix

def calculate_markets(probability_matrix):
    markets = {}
    markets['home_win'] = sum(p['probability'] for p in probability_matrix if p['home_goals'] > p['away_goals'])
    markets['draw'] = sum(p['probability'] for p in probability_matrix if p['home_goals'] == p['away_goals'])
    markets['away_win'] = sum(p['probability'] for p in probability_matrix if p['home_goals'] < p['away_goals'])
    markets['over_2.5'] = sum(p['probability'] for p in probability_matrix if (p['home_goals'] + p['away_goals']) > 2.5)
    markets['under_2.5'] = 1 - markets['over_2.5']
    markets['btts_yes'] = sum(p['probability'] for p in probability_matrix if p['home_goals'] > 0 and p['away_goals'] > 0)
    markets['btts_no'] = 1 - markets['btts_yes']
    return markets

def calculate_ev(probability, odd):
    return (probability * odd) - 1 if odd > 0 else 0

def calculate_kelly_criterion(probability, odd):
    if odd <= 1:
        return 0
    kelly = (probability * odd - 1) / (odd - 1)
    return max(0, min(kelly, 0.25))

def classify_bet(probability, odd, ev):
    if ev >= 0.10 and probability >= 0.40 and 1.50 <= odd <= 4.00:
        return "simple_high"
    elif ev >= 0.15 and odd >= 5.00:
        return "high_risk"
    elif 0.05 <= ev <= 0.15 and probability >= 0.30:
        return "multiple"
    elif ev > 0:
        return "simple_low"
    else:
        return "no_value"

def calculate_bankroll_distribution(total_bankroll, bets, risk_profile="balanced"):
    simple_high_bets = [bet for bet in bets if classify_bet(bet['prob'], bet['odd'], bet['ev']) == "simple_high"]
    multiple_bets = [bet for bet in bets if classify_bet(bet['prob'], bet['odd'], bet['ev']) == "multiple"]
    high_risk_bets = [bet for bet in bets if classify_bet(bet['prob'], bet['odd'], bet['ev']) == "high_risk"]
    simple_low_bets = [bet for bet in bets if classify_bet(bet['prob'], bet['odd'], bet['ev']) == "simple_low"]
    
    profiles = {
        "conservative": {"simple": 0.60, "multiple": 0.30, "high_risk": 0.10},
        "balanced": {"simple": 0.50, "multiple": 0.35, "high_risk": 0.15},
        "aggressive": {"simple": 0.40, "multiple": 0.40, "high_risk": 0.20}
    }
    
    profile = profiles[risk_profile]
    
    simple_budget = total_bankroll * profile["simple"]
    multiple_budget = total_bankroll * profile["multiple"]
    high_risk_budget = total_bankroll * profile["high_risk"]
    
    recommendations = {
        "simple_high": simple_high_bets,
        "simple_low": simple_low_bets,
        "multiple": multiple_bets,
        "high_risk": high_risk_bets,
        "budgets": {
            "simple_total": simple_budget,
            "multiple_total": multiple_budget,
            "high_risk_total": high_risk_budget
        }
    }
    
    return recommendations

# ==================== FUNÇÕES DA API ====================

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
                games.append({
                    'scored': int(event['intHomeScore']),
                    'conceded': int(event['intAwayScore']),
                    'date': event.get('dateEvent')
                })
            elif venue == 'away' and event.get('strAwayTeam') == team_name:
                games.append({
                    'scored': int(event['intAwayScore']),
                    'conceded': int(event['intHomeScore']),
                    'date': event.get('dateEvent')
                })
        except:
            continue
    
    if not games:
        return None
    
    games.sort(key=lambda x: x['date'], reverse=True)
    
    return {
        'games': len(games),
        'scored_average': sum(game['scored'] for game in games) / len(games),
        'conceded_average': sum(game['conceded'] for game in games) / len(games),
        'last_5': games[:5] if len(games) >= 5 else games
    }

def get_head_to_head(events, home_team, away_team):
    """Retorna confrontos diretos entre os dois times"""
    h2h = []
    for event in events:
        if not event.get('intHomeScore') or not event.get('intAwayScore'):
            continue
        
        home = event.get('strHomeTeam')
        away = event.get('strAwayTeam')
        
        if (home == home_team and away == away_team) or (home == away_team and away == home_team):
            try:
                h2h.append({
                    'date': event.get('dateEvent'),
                    'home': home,
                    'away': away,
                    'score_home': int(event['intHomeScore']),
                    'score_away': int(event['intAwayScore'])
                })
            except:
                continue
    
    h2h.sort(key=lambda x: x['date'], reverse=True)
    return h2h[:5]

# ==================== GERENCIAMENTO DE APOSTAS ====================

def load_bets_history():
    """Carrega histórico de apostas do session_state"""
    if 'bets_history' not in st.session_state:
        st.session_state.bets_history = []
    return st.session_state.bets_history

def save_bet_to_history(bet_data):
    """Salva aposta no histórico"""
    if 'bets_history' not in st.session_state:
        st.session_state.bets_history = []
    
    bet_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    st.session_state.bets_history.append(bet_data)

def calculate_roi():
    """Calcula ROI das apostas finalizadas"""
    history = load_bets_history()
    finalized = [b for b in history if b.get('status') in ['ganhou', 'perdeu']]
    
    if not finalized:
        return 0, 0, 0
    
    total_invested = sum(b.get('stake', 0) for b in finalized)
    total_returned = sum(b.get('stake', 0) * b.get('odd', 0) for b in finalized if b.get('status') == 'ganhou')
    profit = total_returned - total_invested
    roi = (profit / total_invested * 100) if total_invested > 0 else 0
    
    wins = len([b for b in finalized if b.get('status') == 'ganhou'])
    win_rate = (wins / len(finalized) * 100) if finalized else 0
    
    return roi, profit, win_rate

# ==================== INICIALIZAR ESTADO ====================

if 'multiple_bets' not in st.session_state:
    st.session_state.multiple_bets = []
if 'show_analysis' not in st.session_state:
    st.session_state.show_analysis = False
if 'selected_home' not in st.session_state:
    st.session_state.selected_home = None
if 'selected_away' not in st.session_state:
    st.session_state.selected_away = None
if 'bets_history' not in st.session_state:
    st.session_state.bets_history = []

# ==================== CARREGAR DADOS ====================

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

# ==================== NAVEGAÇÃO ====================

st.title('⚽ Sistema de Análise de Valor (EV+) - Brasileirão 2025')

tab1, tab2 = st.tabs(["📊 Análise & Apostas", "📈 Dashboard de Performance"])

# ==================== TAB 1: ANÁLISE ====================

with tab1:
    st.header("⚽ Análise de Jogo")
    st.caption(f"✅ {completed_games} jogos completos | {len(team_list)} times | Temporada {season_used}")

    column_home, column_away = st.columns(2)

    with column_home:
        if st.session_state.selected_home and st.session_state.selected_home in team_list:
            home_team_index = team_list.index(st.session_state.selected_home)
        else:
            home_team_index = 0
        home_team = st.selectbox('🏠 Time da Casa', team_list, index=home_team_index, key='select_home')

    with column_away:
        if st.session_state.selected_away and st.session_state.selected_away in team_list:
            away_team_index = team_list.index(st.session_state.selected_away)
        else:
            away_team_index = 1
        away_team = st.selectbox('✈️ Time Visitante', team_list, index=away_team_index, key='select_away')

    if home_team != away_team:
        if st.button("🔍 ANALISAR JOGO", type="primary", use_container_width=True):
            st.session_state.show_analysis = True
        
        if st.session_state.show_analysis:
            home_statistics = process_team_stats(events, home_team, 'home')
            away_statistics = process_team_stats(events, away_team, 'away')
            
            if home_statistics and away_statistics:
                expected_home_goals = (home_statistics['scored_average'] + away_statistics['conceded_average']) / 2
                expected_away_goals = (away_statistics['scored_average'] + home_statistics['conceded_average']) / 2
                
                st.success(f"**{home_team}** vs **{away_team}**")
                
                column_home_metric, column_away_metric, column_total_metric = st.columns(3)
                with column_home_metric:
                    st.metric(home_team, f"{expected_home_goals:.2f} gols")
                with column_away_metric:
                    st.metric(away_team, f"{expected_away_goals:.2f} gols")
                with column_total_metric:
                    st.metric("Total", f"{expected_home_goals + expected_away_goals:.2f} gols")
                
                # ===== NOVA SEÇÃO: TENDÊNCIAS =====
                with st.expander("📊 Análise de Tendências", expanded=False):
                    col_h2h, col_form = st.columns(2)
                    
                    with col_h2h:
                        st.subheader("🔄 Confrontos Diretos")
                        h2h = get_head_to_head(events, home_team, away_team)
                        if h2h:
                            for match in h2h:
                                winner = ""
                                if match['score_home'] > match['score_away']:
                                    winner = f"✅ {match['home']}"
                                elif match['score_away'] > match['score_home']:
                                    winner = f"✅ {match['away']}"
                                else:
                                    winner = "🤝 Empate"
                                st.write(f"**{match['date']}** | {match['home']} {match['score_home']} x {match['score_away']} {match['away']} - {winner}")
                        else:
                            st.info("Sem confrontos diretos recentes")
                    
                    with col_form:
                        st.subheader("📈 Últimos 5 Jogos")
                        st.write(f"**{home_team} (Casa)**")
                        for game in home_statistics['last_5']:
                            result = "✅" if game['scored'] > game['conceded'] else "❌" if game['scored'] < game['conceded'] else "🤝"
                            st.write(f"{result} {game['scored']} x {game['conceded']} gols")
                        
                        st.divider()
                        
                        st.write(f"**{away_team} (Fora)**")
                        for game in away_statistics['last_5']:
                            result = "✅" if game['scored'] > game['conceded'] else "❌" if game['scored'] < game['conceded'] else "🤝"
                            st.write(f"{result} {game['scored']} x {game['conceded']} gols")
                
                probability_matrix = calculate_match_probabilities(expected_home_goals, expected_away_goals)
                markets = calculate_markets(probability_matrix)
                
                st.divider()
                st.subheader("💡 Insira as Odds")
                st.caption("Digite apenas números - Ex: 225 = 2,25 | 180 = 1,80 | 15 = 1,5")
                
                markets_data = []
                
                st.markdown("### 🏆 Resultado do Jogo")
                column_home_result, column_draw_result, column_away_result = st.columns(3)
                
                with column_home_result:
                    st.write(f"**{home_team}**")
                    st.write(f"Probabilidade: {markets['home_win']*100:.1f}%")
                    odd_input_home = st.text_input(
                        "Odd (ex: 225 = 2,25):", 
                        value="",
                        key=f"home_{home_team}_{away_team}",
                        placeholder="Ex: 225"
                    )
                    
                    if odd_input_home and odd_input_home.isdigit():
                        odd_home = float(odd_input_home) / 100
                        if odd_home >= 1.01:
                            st.info(f"Odd: **{odd_home:.2f}**")
                            ev_home = calculate_ev(markets['home_win'], odd_home)
                            classification = classify_bet(markets['home_win'], odd_home, ev_home)
                            
                            if classification == "simple_high":
                                st.success(f"EV: +{ev_home*100:.1f}% ⭐ APOSTA SIMPLES")
                            elif classification == "high_risk":
                                st.warning(f"EV: +{ev_home*100:.1f}% 🎲 HIGH-RISK")
                            elif classification == "multiple":
                                st.info(f"EV: +{ev_home*100:.1f}% 🔗 BOA PARA MÚLTIPLA")
                            elif ev_home > 0:
                                st.metric("EV", f"+{ev_home*100:.1f}%", delta="✅")
                            else:
                                st.metric("EV", f"{ev_home*100:.1f}%", delta="❌")
                            
                            if ev_home > 0:
                                markets_data.append({
                                    'jogo': f"{home_team} vs {away_team}",
                                    'mercado': f'Vitória {home_team}',
                                    'prob': markets['home_win'],
                                    'odd': odd_home,
                                    'ev': ev_home,
                                    'classification': classification,
                                    'key': 'home'
                                })
                
                with column_draw_result:
                    st.write("**Empate**")
                    st.write(f"Probabilidade: {markets['draw']*100:.1f}%")
                    odd_input_draw = st.text_input(
                        "Odd (ex: 300 = 3,00):", 
                        value="",
                        key=f"draw_{home_team}_{away_team}",
                        placeholder="Ex: 300"
                    )
                    
                    if odd_input_draw and odd_input_draw.isdigit():
                        odd_draw = float(odd_input_draw) / 100
                        if odd_draw >= 1.01:
                            st.info(f"Odd: **{odd_draw:.2f}**")
                            ev_draw = calculate_ev(markets['draw'], odd_draw)
                            classification = classify_bet(markets['draw'], odd_draw, ev_draw)
                            
                            if classification == "simple_high":
                                st.success(f"EV: +{ev_draw*100:.1f}% ⭐ APOSTA SIMPLES")
                            elif classification == "high_risk":
                                st.warning(f"EV: +{ev_draw*100:.1f}% 🎲 HIGH-RISK")
                            elif classification == "multiple":
                                st.info(f"EV: +{ev_draw*100:.1f}% 🔗 BOA PARA MÚLTIPLA")
                            elif ev_draw > 0:
                                st.metric("EV", f"+{ev_draw*100:.1f}%", delta="✅")
                            else:
                                st.metric("EV", f"{ev_draw*100:.1f}%", delta="❌")
                            
                            if ev_draw > 0:
                                markets_data.append({
                                    'jogo': f"{home_team} vs {away_team}",
                                    'mercado': 'Empate',
                                    'prob': markets['draw'],
                                    'odd': odd_draw,
                                    'ev': ev_draw,
                                    'classification': classification,
                                    'key': 'draw'
                                })
                
                with column_away_result:
                    st.write(f"**{away_team}**")
                    st.write(f"Probabilidade: {markets['away_win']*100:.1f}%")
                    odd_input_away = st.text_input(
                        "Odd (ex: 400 = 4,00):", 
                        value="",
                        key=f"away_{home_team}_{away_team}",
                        placeholder="Ex: 400"
                    )
                    
                    if odd_input_away and odd_input_away.isdigit():
                        odd_away = float(odd_input_away) / 100
                        if odd_away >= 1.01:
                            st.info(f"Odd: **{odd_away:.2f}**")
                            ev_away = calculate_ev(markets['away_win'], odd_away)
                            classification = classify_bet(markets['away_win'], odd_away, ev_away)
                            
                            if classification == "simple_high":
                                st.success(f"EV: +{ev_away*100:.1f}% ⭐ APOSTA SIMPLES")
                            elif classification == "high_risk":
                                st.warning(f"EV: +{ev_away*100:.1f}% 🎲 HIGH-RISK")
                            elif classification == "multiple":
                                st.info(f"EV: +{ev_away*100:.1f}% 🔗 BOA PARA MÚLTIPLA")
                            elif ev_away > 0:
                                st.metric("EV", f"+{ev_away*100:.1f}%", delta="✅")
                            else:
                                st.metric("EV", f"{ev_away*100:.1f}%", delta="❌")
                            
                            if ev_away > 0:
                                markets_data.append({
                                    'jogo': f"{home_team} vs {away_team}",
                                    'mercado': f'Vitória {away_team}',
                                    'prob': markets['away_win'],
                                    'odd': odd_away,
                                    'ev': ev_away,
                                    'classification': classification,
                                    'key': 'away'
                                })
                
                st.divider()
                st.markdown("### 📊 Over/Under 2.5 Gols")
                column_over, column_under = st.columns(2)
                
                with column_over:
                    st.write("**Mais de 2.5**")
                    st.write(f"Probabilidade: {markets['over_2.5']*100:.1f}%")
                    odd_input_over = st.text_input(
                        "Odd (ex: 250 = 2,50):", 
                        value="",
                        key=f"over_{home_team}_{away_team}",
                        placeholder="Ex: 250"
                    )
                    
                    if odd_input_over and odd_input_over.isdigit():
                        odd_over = float(odd_input_over) / 100
                        if odd_over >= 1.01:
                            st.info(f"Odd: **{odd_over:.2f}**")
                            ev_over = calculate_ev(markets['over_2.5'], odd_over)
                            classification = classify_bet(markets['over_2.5'], odd_over, ev_over)
                            
                            if classification == "simple_high":
                                st.success(f"EV: +{ev_over*100:.1f}% ⭐ APOSTA SIMPLES")
                            elif classification == "high_risk":
                                st.warning(f"EV: +{ev_over*100:.1f}% 🎲 HIGH-RISK")
                            elif classification == "multiple":
                                st.info(f"EV: +{ev_over*100:.1f}% 🔗 BOA PARA MÚLTIPLA")
                            elif ev_over > 0:
                                st.metric("EV", f"+{ev_over*100:.1f}%", delta="✅")
                            else:
                                st.metric("EV", f"{ev_over*100:.1f}%", delta="❌")
                            
                            if ev_over > 0:
                                markets_data.append({
                                    'jogo': f"{home_team} vs {away_team}",
                                    'mercado': 'Mais de 2.5',
                                    'prob': markets['over_2.5'],
                                    'odd': odd_over,
                                    'ev': ev_over,
                                    'classification': classification,
                                    'key': 'over'
                                })
                
                with column_under:
                    st.write("**Menos de 2.5**")
                    st.write(f"Probabilidade: {markets['under_2.5']*100:.1f}%")
                    odd_input_under = st.text_input(
                        "Odd (ex: 180 = 1,80):", 
                        value="",
                        key=f"under_{home_team}_{away_team}",
                        placeholder="Ex: 180"
                    )
                    
                    if odd_input_under and odd_input_under.isdigit():
                        odd_under = float(odd_input_under) / 100
                        if odd_under >= 1.01:
                            st.info(f"Odd: **{odd_under:.2f}**")
                            ev_under = calculate_ev(markets['under_2.5'], odd_under)
                            classification = classify_bet(markets['under_2.5'], odd_under, ev_under)
                            
                            if classification == "simple_high":
                                st.success(f"EV: +{ev_under*100:.1f}% ⭐ APOSTA SIMPLES")
                            elif classification == "high_risk":
                                st.warning(f"EV: +{ev_under*100:.1f}% 🎲 HIGH-RISK")
                            elif classification == "multiple":
                                st.info(f"EV: +{ev_under*100:.1f}% 🔗 BOA PARA MÚLTIPLA")
                            elif ev_under > 0:
                                st.metric("EV", f"+{ev_under*100:.1f}%", delta="✅")
                            else:
                                st.metric("EV", f"{ev_under*100:.1f}%", delta="❌")
                            
                            if ev_under > 0:
                                markets_data.append({
                                    'jogo': f"{home_team} vs {away_team}",
                                    'mercado': 'Menos de 2.5',
                                    'prob': markets['under_2.5'],
                                    'odd': odd_under,
                                    'ev': ev_under,
                                    'classification': classification,
                                    'key': 'under'
                                })
                
                # ===== NOVA SEÇÃO: BTTS =====
                st.divider()
                st.markdown("### ⚽ Ambas Marcam (BTTS)")
                column_btts_yes, column_btts_no = st.columns(2)
                
                with column_btts_yes:
                    st.write("**Sim (Ambas Marcam)**")
                    st.write(f"Probabilidade: {markets['btts_yes']*100:.1f}%")
                    odd_input_btts_yes = st.text_input(
                        "Odd (ex: 170 = 1,70):", 
                        value="",
                        key=f"btts_yes_{home_team}_{away_team}",
                        placeholder="Ex: 170"
                    )
                    
                    if odd_input_btts_yes and odd_input_btts_yes.isdigit():
                        odd_btts_yes = float(odd_input_btts_yes) / 100
                        if odd_btts_yes >= 1.01:
                            st.info(f"Odd: **{odd_btts_yes:.2f}**")
                            ev_btts_yes = calculate_ev(markets['btts_yes'], odd_btts_yes)
                            classification = classify_bet(markets['btts_yes'], odd_btts_yes, ev_btts_yes)
                            
                            if classification == "simple_high":
                                st.success(f"EV: +{ev_btts_yes*100:.1f}% ⭐ APOSTA SIMPLES")
                            elif classification == "high_risk":
                                st.warning(f"EV: +{ev_btts_yes*100:.1f}% 🎲 HIGH-RISK")
                            elif classification == "multiple":
                                st.info(f"EV: +{ev_btts_yes*100:.1f}% 🔗 BOA PARA MÚLTIPLA")
                            elif ev_btts_yes > 0:
                                st.metric("EV", f"+{ev_btts_yes*100:.1f}%", delta="✅")
                            else:
                                st.metric("EV", f"{ev_btts_yes*100:.1f}%", delta="❌")
                            
                            if ev_btts_yes > 0:
                                markets_data.append({
                                    'jogo': f"{home_team} vs {away_team}",
                                    'mercado': 'Ambas Marcam - Sim',
                                    'prob': markets['btts_yes'],
                                    'odd': odd_btts_yes,
                                    'ev': ev_btts_yes,
                                    'classification': classification,
                                    'key': 'btts_yes'
                                })
                
                with column_btts_no:
                    st.write("**Não (Pelo menos 1 não marca)**")
                    st.write(f"Probabilidade: {markets['btts_no']*100:.1f}%")
                    odd_input_btts_no = st.text_input(
                        "Odd (ex: 200 = 2,00):", 
                        value="",
                        key=f"btts_no_{home_team}_{away_team}",
                        placeholder="Ex: 200"
                    )
                    
                    if odd_input_btts_no and odd_input_btts_no.isdigit():
                        odd_btts_no = float(odd_input_btts_no) / 100
                        if odd_btts_no >= 1.01:
                            st.info(f"Odd: **{odd_btts_no:.2f}**")
                            ev_btts_no = calculate_ev(markets['btts_no'], odd_btts_no)
                            classification = classify_bet(markets['btts_no'], odd_btts_no, ev_btts_no)
                            
                            if classification == "simple_high":
                                st.success(f"EV: +{ev_btts_no*100:.1f}% ⭐ APOSTA SIMPLES")
                            elif classification == "high_risk":
                                st.warning(f"EV: +{ev_btts_no*100:.1f}% 🎲 HIGH-RISK")
                            elif classification == "multiple":
                                st.info(f"EV: +{ev_btts_no*100:.1f}% 🔗 BOA PARA MÚLTIPLA")
                            elif ev_btts_no > 0:
                                st.metric("EV", f"+{ev_btts_no*100:.1f}%", delta="✅")
                            else:
                                st.metric("EV", f"{ev_btts_no*100:.1f}%", delta="❌")
                            
                            if ev_btts_no > 0:
                                markets_data.append({
                                    'jogo': f"{home_team} vs {away_team}",
                                    'mercado': 'Ambas Marcam - Não',
                                    'prob': markets['btts_no'],
                                    'odd': odd_btts_no,
                                    'ev': ev_btts_no,
                                    'classification': classification,
                                    'key': 'btts_no'
                                })
                
                if markets_data:
                    st.divider()
                    st.success(f"🎯 {len(markets_data)} apostas com EV+ identificadas")
                    
                    for market in markets_data:
                        column_market, column_button = st.columns([4, 1])
                        with column_market:
                            classification_emoji = {
                                "simple_high": "⭐",
                                "high_risk": "🎲",
                                "multiple": "🔗",
                                "simple_low": "✅"
                            }
                            emoji = classification_emoji.get(market['classification'], "")
                            st.write(f"{emoji} **{market['mercado']}** - Odd {market['odd']:.2f} - EV +{market['ev']*100:.1f}%")
                        with column_button:
                            if st.button("➕", key=f"add_{market['key']}_{home_team}_{away_team}"):
                                st.session_state.multiple_bets.append(market)
                                st.success("✅")

    # ==================== GESTÃO DE BANCA ====================

    st.divider()
    st.header("💰 Gestão de Banca Inteligente")

    if len(st.session_state.multiple_bets) > 0:
        
        bankroll_input = st.text_input(
            "💵 Banca Total Disponível (em centavos - ex: 10000 = R$ 100,00):",
            value="",
            placeholder="Ex: 10000",
            help="Valor total que você tem disponível para investir"
        )
        
        if bankroll_input and bankroll_input.isdigit():
            total_bankroll = float(bankroll_input) / 100
            
            st.info(f"**Banca Total: R$ {total_bankroll:.2f}**")
            
            st.subheader("📈 Escolha seu Perfil de Risco")
            risk_profile = st.radio(
                "Perfil:",
                options=["conservative", "balanced", "aggressive"],
                format_func=lambda x: {
                    "conservative": "🛡️ Conservador (60% simples, 30% múltiplas, 10% high-risk)",
                    "balanced": "⚖️ Balanceado (50% simples, 35% múltiplas, 15% high-risk)",
                    "aggressive": "🔥 Agressivo (40% simples, 40% múltiplas, 20% high-risk)"
                }[x],
                horizontal=True
            )
            
            recommendations = calculate_bankroll_distribution(total_bankroll, st.session_state.multiple_bets, risk_profile)
            
            st.divider()
            
            st.markdown("### 🎯 Recomendação de Investimento")
            
            if recommendations['simple_high'] or recommendations['simple_low']:
                st.markdown("#### ⭐ Apostas Simples")
                simple_budget = recommendations['budgets']['simple_total']
                all_simple = recommendations['simple_high'] + recommendations['simple_low']
                
                if all_simple:
                    st.write(f"**Orçamento: R$ {simple_budget:.2f}**")
                    
                    for bet in all_simple:
                        kelly = calculate_kelly_criterion(bet['prob'], bet['odd'])
                        total_kelly = sum(calculate_kelly_criterion(b['prob'], b['odd']) for b in all_simple)
                        stake = simple_budget * (kelly / total_kelly) if total_kelly > 0 else simple_budget / len(all_simple)
                        
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.write(f"**{bet['mercado']}** ({bet['jogo']})")
                        with col2:
                            st.write(f"Odd: {bet['odd']:.2f}")
                        with col3:
                            st.write(f"**R$ {stake:.2f}**")
            
            if recommendations['multiple']:
                st.markdown("#### 🔗 Apostas para Múltipla")
                multiple_budget = recommendations['budgets']['multiple_total']
                
                st.write(f"**Orçamento: R$ {multiple_budget:.2f}**")
                st.caption("💡 Monte uma múltipla com 2-4 dessas apostas")
                
                for bet in recommendations['multiple']:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"**{bet['mercado']}** - Odd {bet['odd']:.2f} - EV +{bet['ev']*100:.1f}%")
                    with col2:
                        st.write(f"Prob: {bet['prob']*100:.1f}%")
                
                if len(recommendations['multiple']) >= 2:
                    example_multiple = recommendations['multiple'][:min(4, len(recommendations['multiple']))]
                    odd_multiple = 1
                    prob_multiple = 1
                    for bet in example_multiple:
                        odd_multiple *= bet['odd']
                        prob_multiple *= bet['prob']
                    
                    st.write(f"**Exemplo:** {len(example_multiple)} apostas → Odd {odd_multiple:.2f} → Investir R$ {multiple_budget:.2f}")
                    st.write(f"Retorno potencial: R$ {multiple_budget * odd_multiple:.2f}")
            
            if recommendations['high_risk']:
                st.markdown("#### 🎲 Apostas High-Risk (Tiro Alto)")
                high_risk_budget = recommendations['budgets']['high_risk_total']
                
                st.write(f"**Orçamento: R$ {high_risk_budget:.2f}**")
                st.caption("⚠️ Alto retorno, mas risco elevado")
                
                for bet in recommendations['high_risk']:
                    stake = high_risk_budget / len(recommendations['high_risk'])
                    
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"**{bet['mercado']}** ({bet['jogo']})")
                    with col2:
                        st.write(f"Odd: {bet['odd']:.2f}")
                    with col3:
                        st.write(f"**R$ {stake:.2f}**")
            
            st.divider()
            
            st.markdown("### 📊 Resumo da Estratégia")
            
            total_recommended = recommendations['budgets']['simple_total'] + recommendations['budgets']['multiple_total'] + recommendations['budgets']['high_risk_total']
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Apostas Simples", f"R$ {recommendations['budgets']['simple_total']:.2f}")
            with col2:
                st.metric("Múltiplas", f"R$ {recommendations['budgets']['multiple_total']:.2f}")
            with col3:
                st.metric("High-Risk", f"R$ {recommendations['budgets']['high_risk_total']:.2f}")
            with col4:
                st.metric("Total Investido", f"R$ {total_recommended:.2f}")
        
        else:
            st.info("💡 Insira sua banca total para receber recomendações personalizadas")
        
        st.divider()
        
        st.subheader("📋 Suas Apostas Selecionadas")
        
        for index, bet in enumerate(st.session_state.multiple_bets):
            column_game, column_market, column_odd, column_ev, column_class, column_delete = st.columns([2, 2, 1, 1, 1, 1])
            with column_game:
                st.write(f"**{bet['jogo']}**")
            with column_market:
                st.write(bet['mercado'])
            with column_odd:
                st.write(f"{bet['odd']:.2f}")
            with column_ev:
                st.write(f"+{bet['ev']*100:.1f}%")
            with column_class:
                classification_labels = {
                    "simple_high": "⭐ Simples",
                    "high_risk": "🎲 High-Risk",
                    "multiple": "🔗 Múltipla",
                    "simple_low": "✅ Simples"
                }
                st.write(classification_labels.get(bet.get('classification', 'simple_low'), ""))
            with column_delete:
                if st.button("🗑️", key=f"delete_{index}"):
                    st.session_state.multiple_bets.pop(index)
                    st.rerun()
        
        st.divider()
        
        column_clear, column_download = st.columns(2)
        with column_clear:
            if st.button("🗑️ Limpar Todas", use_container_width=True):
                st.session_state.multiple_bets = []
                st.rerun()
        with column_download:
            dataframe_bets = pd.DataFrame(st.session_state.multiple_bets)
            csv_data = dataframe_bets.to_csv(index=False)
            st.download_button("💾 Baixar CSV", csv_data, "apostas_ev.csv", "text/csv", use_container_width=True)

    else:
        st.info("👆 Analise jogos acima e adicione apostas com EV+ para receber recomendações de gestão de banca")
        st.caption("💡 O sistema classificará automaticamente cada aposta e sugerirá a melhor estratégia")

# ==================== TAB 2: DASHBOARD ====================

with tab2:
    st.header("📈 Dashboard de Performance")
    
    roi, profit, win_rate = calculate_roi()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("ROI", f"{roi:.1f}%", delta="Positivo" if roi > 0 else "Negativo")
    with col2:
        st.metric("Lucro/Prejuízo", f"R$ {profit:.2f}")
    with col3:
        st.metric("Taxa de Acerto", f"{win_rate:.1f}%")
    with col4:
        st.metric("Total de Apostas", len(st.session_state.bets_history))
    
    st.divider()
    
    st.subheader("➕ Registrar Nova Aposta")
    
    with st.form("new_bet_form"):
        col1, col2 = st.columns(2)
        with col1:
            bet_game = st.text_input("Jogo", placeholder="Ex: Flamengo vs Palmeiras")
            bet_market = st.text_input("Mercado", placeholder="Ex: Vitória Flamengo")
            bet_odd = st.number_input("Odd", min_value=1.01, value=2.00, step=0.01)
        with col2:
            bet_stake = st.number_input("Valor Apostado (R$)", min_value=0.01, value=10.00, step=0.01)
            bet_status = st.selectbox("Status", ["pendente", "ganhou", "perdeu"])
        
        submit = st.form_submit_button("💾 Salvar Aposta", use_container_width=True)
        
        if submit:
            if bet_game and bet_market:
                save_bet_to_history({
                    'jogo': bet_game,
                    'mercado': bet_market,
                    'odd': bet_odd,
                    'stake': bet_stake,
                    'status': bet_status
                })
                st.success("✅ Aposta registrada!")
                st.rerun()
            else:
                st.error("Preencha todos os campos!")
    
    st.divider()
    
    st.subheader("📋 Histórico de Apostas")
    
    if st.session_state.bets_history:
        df_history = pd.DataFrame(st.session_state.bets_history)
        
        for index, bet in enumerate(st.session_state.bets_history):
            with st.expander(f"{bet['timestamp']} | {bet['jogo']} - {bet['mercado']}"):
                col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
                with col1:
                    st.write(f"**Jogo:** {bet['jogo']}")
                    st.write(f"**Mercado:** {bet['mercado']}")
                with col2:
                    st.write(f"**Odd:** {bet['odd']:.2f}")
                with col3:
                    st.write(f"**Stake:** R$ {bet['stake']:.2f}")
                with col4:
                    status_emoji = {"pendente": "⏳", "ganhou": "✅", "perdeu": "❌"}
                    st.write(f"**Status:** {status_emoji.get(bet['status'])} {bet['status'].capitalize()}")
                with col5:
                    if st.button("🗑️", key=f"delete_history_{index}"):
                        st.session_state.bets_history.pop(index)
                        st.rerun()
        
        if st.button("🗑️ Limpar Histórico Completo", type="secondary"):
            st.session_state.bets_history = []
            st.rerun()
    else:
        st.info("Nenhuma aposta registrada ainda. Comece registrando suas apostas acima!")
