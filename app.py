import streamlit as st
import pandas as pd
import requests
import math
from datetime import datetime, timedelta

st.set_page_config(page_title="Sistema EV+ - Brasileirão 2025", page_icon="⚽", layout="wide")
st.title('⚽ Sistema de Análise de Valor (EV+) - Brasileirão 2025')

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

@st.cache_data(ttl=1800)
def get_next_round_games_debug():
    """Busca próximos jogos com DEBUG detalhado"""
    debug_info = {
        'status': 'iniciado',
        'url': '',
        'status_code': 0,
        'response_preview': '',
        'error': None,
        'games_found': 0
    }
    
    try:
        url = "https://api.api-futebol.com.br/v1/campeonatos/10/rodadas"
        debug_info['url'] = url
        
        headers = {
            "Authorization": "Bearer test_a8c37778328495ac24c5d0d3c3923b"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        debug_info['status_code'] = response.status_code
        debug_info['response_preview'] = str(response.text)[:500]
        
        if response.status_code == 200:
            data = response.json()
            debug_info['status'] = 'sucesso'
            
            if not data:
                debug_info['status'] = 'vazio'
                return [], debug_info
            
            now = datetime.now()
            future_games = []
            
            for rodada in data:
                if rodada.get('partidas'):
                    for partida in rodada['partidas']:
                        if partida.get('data_realizacao'):
                            try:
                                game_datetime_str = partida['data_realizacao']
                                game_datetime = datetime.fromisoformat(game_datetime_str.replace('Z', '+00:00'))
                                
                                placar = partida.get('placar')
                                
                                if game_datetime > now and not placar:
                                    future_games.append({
                                        'datetime': game_datetime,
                                        'date': game_datetime.strftime('%Y-%m-%d'),
                                        'time': game_datetime.strftime('%H:%M'),
                                        'home': partida.get('time_mandante', {}).get('nome_popular', 'N/A'),
                                        'away': partida.get('time_visitante', {}).get('nome_popular', 'N/A'),
                                        'round': rodada.get('nome', 'Rodada')
                                    })
                            except Exception as e:
                                debug_info['error'] = f"Erro ao processar partida: {str(e)}"
                                continue
            
            debug_info['games_found'] = len(future_games)
            
            if not future_games:
                return [], debug_info
            
            future_games.sort(key=lambda x: x['datetime'])
            next_date = future_games[0]['date']
            next_day_games = [game for game in future_games if game['date'] == next_date]
            
            return next_day_games[:10], debug_info
        else:
            debug_info['status'] = f'erro_{response.status_code}'
            return [], debug_info
            
    except Exception as e:
        debug_info['status'] = 'exception'
        debug_info['error'] = str(e)
        return [], debug_info

def process_team_stats(events, team_name, venue='home'):
    games = []
    for event in events:
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
        'scored_average': sum(game['scored'] for game in games) / len(games),
        'conceded_average': sum(game['conceded'] for game in games) / len(games)
    }

# ==================== INICIALIZAR ESTADO ====================

if 'multiple_bets' not in st.session_state:
    st.session_state.multiple_bets = []
if 'show_analysis' not in st.session_state:
    st.session_state.show_analysis = False
if 'selected_home' not in st.session_state:
    st.session_state.selected_home = None
if 'selected_away' not in st.session_state:
    st.session_state.selected_away = None

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

# ==================== DEBUG: API FUTEBOL BR ====================

st.header("🔍 DEBUG - API Futebol BR")

next_round_games, debug_info = get_next_round_games_debug()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Status", debug_info['status'])
with col2:
    st.metric("Status Code", debug_info['status_code'])
with col3:
    st.metric("Jogos Encontrados", debug_info['games_found'])

with st.expander("📋 Detalhes da Requisição"):
    st.write(f"**URL:** {debug_info['url']}")
    st.write(f"**Erro:** {debug_info.get('error', 'Nenhum')}")
    st.write(f"**Preview da Resposta:**")
    st.code(debug_info['response_preview'])

st.divider()

# ==================== SEÇÃO 0: PRÓXIMOS JOGOS ====================

if next_round_games:
    match_date = datetime.strptime(next_round_games[0]['date'], "%Y-%m-%d")
    weekday_names = {
        0: "Segunda-feira",
        1: "Terça-feira",
        2: "Quarta-feira",
        3: "Quinta-feira",
        4: "Sexta-feira",
        5: "Sábado",
        6: "Domingo"
    }
    weekday = weekday_names[match_date.weekday()]
    
    st.header(f"📅 Próximos Jogos - {weekday}, {match_date.strftime('%d/%m/%Y')}")
    st.caption(f"⚽ {len(next_round_games)} jogos agendados | {next_round_games[0].get('round', 'Rodada')}")
    
    for game in next_round_games:
        column_time, column_match, column_button = st.columns([1, 4, 1])
        
        with column_time:
            st.write(f"**{game['time']}**")
        
        with column_match:
            st.write(f"🏠 **{game['home']}** vs ✈️ **{game['away']}**")
        
        with column_button:
            if st.button("🔍", key=f"analyze_{game['home']}_{game['away']}", help="Analisar confronto", use_container_width=True):
                st.session_state.selected_home = game['home']
                st.session_state.selected_away = game['away']
                st.session_state.show_analysis = True
                st.rerun()
    
    st.divider()

# ==================== SEÇÃO 1: ANÁLISE DE JOGO ====================

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

# ==================== SEÇÃO 2: GESTÃO DE BANCA ====================

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
