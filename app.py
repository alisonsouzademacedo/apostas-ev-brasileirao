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

def calculate_match_probabilities(home_expected_goals, away_expected_goals, max_goals=7):
    probability_matrix = []
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            probability = poisson_probability(home_goals, home_expected_goals) * poisson_probability(away_goals, away_expected_goals)
            probability_matrix.append({'home_goals': home_goals, 'away_goals': away_goals, 'probability': probability})
    return probability_matrix

def calculate_markets(probability_matrix):
    markets = {}
    markets['home_win'] = sum(probability['probability'] for probability in probability_matrix if probability['home_goals'] > probability['away_goals'])
    markets['draw'] = sum(probability['probability'] for probability in probability_matrix if probability['home_goals'] == probability['away_goals'])
    markets['away_win'] = sum(probability['probability'] for probability in probability_matrix if probability['home_goals'] < probability['away_goals'])
    markets['over_2.5'] = sum(probability['probability'] for probability in probability_matrix if (probability['home_goals'] + probability['away_goals']) > 2.5)
    markets['under_2.5'] = 1 - markets['over_2.5']
    markets['btts_yes'] = sum(probability['probability'] for probability in probability_matrix if probability['home_goals'] > 0 and probability['away_goals'] > 0)
    markets['btts_no'] = 1 - markets['btts_yes']
    return markets

def calculate_ev(probability, odd):
    return (probability * odd) - 1 if odd > 0 else 0

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
        'scored_average': sum(game['scored'] for game in games) / len(games),
        'conceded_average': sum(game['conceded'] for game in games) / len(games)
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

column_home, column_away = st.columns(2)
with column_home:
    home_team = st.selectbox('🏠 Time da Casa', team_list, index=0)
with column_away:
    away_team = st.selectbox('✈️ Time Visitante', team_list, index=1)

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
            
            # Resultado do Jogo
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
                        st.metric("EV", f"{ev_home*100:.1f}%", delta="✅ Valor!" if ev_home > 0 else "❌")
                        
                        if ev_home > 0:
                            markets_data.append({
                                'jogo': f"{home_team} vs {away_team}",
                                'mercado': f'Vitória {home_team}',
                                'prob': markets['home_win'],
                                'odd': odd_home,
                                'ev': ev_home,
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
                        st.metric("EV", f"{ev_draw*100:.1f}%", delta="✅ Valor!" if ev_draw > 0 else "❌")
                        
                        if ev_draw > 0:
                            markets_data.append({
                                'jogo': f"{home_team} vs {away_team}",
                                'mercado': 'Empate',
                                'prob': markets['draw'],
                                'odd': odd_draw,
                                'ev': ev_draw,
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
                        st.metric("EV", f"{ev_away*100:.1f}%", delta="✅ Valor!" if ev_away > 0 else "❌")
                        
                        if ev_away > 0:
                            markets_data.append({
                                'jogo': f"{home_team} vs {away_team}",
                                'mercado': f'Vitória {away_team}',
                                'prob': markets['away_win'],
                                'odd': odd_away,
                                'ev': ev_away,
                                'key': 'away'
                            })
            
            # Over/Under
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
                        st.metric("EV", f"{ev_over*100:.1f}%", delta="✅ Valor!" if ev_over > 0 else "❌")
                        
                        if ev_over > 0:
                            markets_data.append({
                                'jogo': f"{home_team} vs {away_team}",
                                'mercado': 'Mais de 2.5',
                                'prob': markets['over_2.5'],
                                'odd': odd_over,
                                'ev': ev_over,
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
                        st.metric("EV", f"{ev_under*100:.1f}%", delta="✅ Valor!" if ev_under > 0 else "❌")
                        
                        if ev_under > 0:
                            markets_data.append({
                                'jogo': f"{home_team} vs {away_team}",
                                'mercado': 'Menos de 2.5',
                                'prob': markets['under_2.5'],
                                'odd': odd_under,
                                'ev': ev_under,
                                'key': 'under'
                            })
            
            # Botões de adicionar
            if markets_data:
                st.divider()
                st.success(f"🎯 {len(markets_data)} apostas com EV+ identificadas")
                
                for market in markets_data:
                    column_market, column_button = st.columns([4, 1])
                    with column_market:
                        st.write(f"**{market['mercado']}** - Odd {market['odd']:.2f} - EV +{market['ev']*100:.1f}%")
                    with column_button:
                        if st.button("➕ Adicionar", key=f"add_{market['key']}_{home_team}_{away_team}"):
                            st.session_state.multiple_bets.append(market)
                            st.success("✅")

# --- SEÇÃO 2: MÚLTIPLA ---
st.divider()
st.header("🎰 Sua Múltipla")

if len(st.session_state.multiple_bets) > 0:
    st.success(f"✅ {len(st.session_state.multiple_bets)} apostas selecionadas")
    
    # Mostrar apostas
    for index, bet in enumerate(st.session_state.multiple_bets):
        column_game, column_market, column_odd, column_ev, column_delete = st.columns([3, 2, 1, 1, 1])
        with column_game:
            st.write(f"**{bet['jogo']}**")
        with column_market:
            st.write(bet['mercado'])
        with column_odd:
            st.write(f"Odd: {bet['odd']:.2f}")
        with column_ev:
            st.write(f"EV: +{bet['ev']*100:.1f}%")
        with column_delete:
            if st.button("🗑️", key=f"delete_{index}"):
                st.session_state.multiple_bets.pop(index)
                st.rerun()
    
    st.divider()
    
    # Calcular múltipla
    odd_total = 1
    probability_total = 1
    for bet in st.session_state.multiple_bets:
        odd_total *= bet['odd']
        probability_total *= bet['prob']
    
    ev_multiple = calculate_ev(probability_total, odd_total)
    
    column_odd_total, column_probability_total, column_ev_total = st.columns(3)
    with column_odd_total:
        st.metric("Odd Total da Múltipla", f"{odd_total:.2f}")
    with column_probability_total:
        st.metric("Probabilidade Combinada", f"{probability_total*100:.2f}%")
    with column_ev_total:
        st.metric("EV da Múltipla", f"{ev_multiple*100:+.1f}%", delta="✅ Valor!" if ev_multiple > 0 else "⚠️ Sem valor")
    
    # Gerenciamento
    st.subheader("💰 Gestão de Banca")
    
    stake_input = st.text_input(
        "💵 Valor a Apostar (em centavos - ex: 10000 = R$ 100,00):",
        value="",
        placeholder="Ex: 10000"
    )
    
    if stake_input and stake_input.isdigit():
        stake = float(stake_input) / 100
        
        st.info(f"**Investimento: R$ {stake:.2f}**")
        
        total_return = stake * odd_total
        profit = total_return - stake
        
        column_stake, column_return, column_profit = st.columns(3)
        with column_stake:
            st.metric("Investimento", f"R$ {stake:.2f}")
        with column_return:
            st.metric("Retorno se Ganhar", f"R$ {total_return:.2f}")
        with column_profit:
            st.metric("Lucro Potencial", f"R$ {profit:.2f}", delta=f"+{(profit/stake)*100:.1f}%")
    
    st.divider()
    
    column_clear, column_download = st.columns(2)
    with column_clear:
        if st.button("🗑️ Limpar Múltipla", use_container_width=True):
            st.session_state.multiple_bets = []
            st.rerun()
    with column_download:
        dataframe_bets = pd.DataFrame(st.session_state.multiple_bets)
        csv_data = dataframe_bets.to_csv(index=False)
        st.download_button("💾 Baixar CSV", csv_data, "multipla_ev.csv", "text/csv", use_container_width=True)

else:
    st.info("👆 Analise jogos acima e adicione apostas com EV+ à múltipla")
    st.caption("💡 Insira as odds digitando apenas números: 225 = 2,25 | 180 = 1,80")
