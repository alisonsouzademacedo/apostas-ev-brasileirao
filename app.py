import streamlit as st
import requests
import json

st.set_page_config(page_title="DEBUG API-Football", page_icon="🔍", layout="wide")
st.title("🔍 DEBUG: API-Football - Brasileirão 2025")

# Configuração
API_KEY = st.secrets["api"]["football_api_key"]
API_BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

st.header("Teste 1: Verificar Ligas Disponíveis no Brasil")

if st.button("🔍 Buscar Ligas do Brasil"):
    url = f"{API_BASE_URL}/leagues"
    params = {"country": "Brazil"}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        st.write(f"**Status:** {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            st.success("✅ Dados recebidos!")
            
            # Filtrar apenas Série A
            serie_a_leagues = [
                item for item in data.get('response', []) 
                if 'Serie A' in item['league']['name']
            ]
            
            st.subheader("Ligas Série A encontradas:")
            for item in serie_a_leagues:
                league = item['league']
                seasons = item['seasons']
                
                st.write(f"**{league['name']}** (ID: {league['id']})")
                st.write(f"Temporadas disponíveis:")
                
                for season in seasons:
                    if season['year'] >= 2024:
                        st.write(f"- {season['year']}: {season['start']} a {season['end']}")
        else:
            st.error(f"Erro: {response.status_code}")
            st.write(response.text)
    except Exception as e:
        st.error(f"Erro: {str(e)}")

st.divider()

st.header("Teste 2: Buscar Times do Brasileirão 2025")

if st.button("🔍 Buscar Times da Temporada 2025"):
    url = f"{API_BASE_URL}/teams"
    params = {
        "league": 71,
        "season": 2025
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        st.write(f"**Status:** {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            st.success("✅ Dados recebidos!")
            
            if data.get('response'):
                st.write(f"**Total de times:** {len(data['response'])}")
                
                teams_data = []
                for item in data['response']:
                    team = item['team']
                    teams_data.append({
                        'Nome': team['name'],
                        'ID': team['id'],
                        'Código': team.get('code', 'N/A')
                    })
                
                import pandas as pd
                df_teams = pd.DataFrame(teams_data)
                st.dataframe(df_teams, use_container_width=True)
            else:
                st.warning("⚠️ Resposta vazia")
                st.json(data)
        else:
            st.error(f"Erro: {response.status_code}")
            st.write(response.text)
    except Exception as e:
        st.error(f"Erro: {str(e)}")

st.divider()

st.header("Teste 3: Buscar Estatísticas de um Time Específico")

team_name = st.text_input("Nome do Time:", value="Fluminense")
team_id = st.number_input("ID do Time:", value=125, min_value=1)

if st.button("🔍 Buscar Estatísticas"):
    url = f"{API_BASE_URL}/teams/statistics"
    params = {
        "team": team_id,
        "season": 2025,
        "league": 71
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        st.write(f"**Status:** {response.status_code}")
        st.write(f"**URL:** {url}")
        st.write(f"**Params:** {params}")
        
        if response.status_code == 200:
            data = response.json()
            st.success("✅ Dados recebidos!")
            
            if data.get('response'):
                st.subheader("📊 Dados Retornados:")
                st.json(data['response'])
            else:
                st.warning("⚠️ Resposta vazia")
                st.json(data)
        elif response.status_code == 429:
            st.error("❌ Limite de requests atingido (100/dia)")
        else:
            st.error(f"Erro: {response.status_code}")
            st.write(response.text)
    except Exception as e:
        st.error(f"Erro: {str(e)}")

st.divider()

st.header("Teste 4: Verificar Jogos Recentes")

if st.button("🔍 Buscar Últimos Jogos do Fluminense"):
    url = f"{API_BASE_URL}/fixtures"
    params = {
        "team": 125,  # Fluminense
        "league": 71,
        "season": 2025,
        "last": 5
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        st.write(f"**Status:** {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            st.success("✅ Dados recebidos!")
            
            if data.get('response'):
                st.write(f"**Jogos encontrados:** {len(data['response'])}")
                
                for fixture in data['response'][:5]:
                    match = fixture['fixture']
                    teams = fixture['teams']
                    goals = fixture['goals']
                    
                    st.write(f"**{match['date'][:10]}:** {teams['home']['name']} {goals['home']} x {goals['away']} {teams['away']['name']}")
            else:
                st.warning("⚠️ Nenhum jogo encontrado")
                st.json(data)
        else:
            st.error(f"Erro: {response.status_code}")
    except Exception as e:
        st.error(f"Erro: {str(e)}")

st.info("""
**💡 O que fazer com os resultados:**

1. **Teste 1:** Verifica se a temporada 2025 está disponível
2. **Teste 2:** Lista todos os times e seus IDs corretos
3. **Teste 3:** Testa se conseguimos buscar estatísticas
4. **Teste 4:** Verifica se há jogos registrados em 2025

**Me envie os resultados de cada teste!**
""")
