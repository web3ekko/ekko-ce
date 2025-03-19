import streamlit as st
from utils.models import Database, Agent, Cache
from src.config.settings import Settings

# Initialize settings and database
settings = Settings()
db = Database(settings)
agent_model = Agent(db)
cache = Cache()

def show_agents():
    st.markdown('<h1 class="page-header">AI Agents</h1>', unsafe_allow_html=True)
    
    # Create New Agent
    with st.expander("Create New Agent"):
        description = st.text_area("What should this agent do?")
        col1, col2 = st.columns(2)
        with col1:
            agent_type = st.selectbox("Agent Type", ["Monitor", "Trade", "Analyze"])
        with col2:
            max_budget = st.number_input("Max Budget (USD)", min_value=0.0)
        if st.button("Create Agent"):
            # Insert new agent into database
            agent_data = {
                'name': description,  # Use the description as a temporary name, improve as needed
                'agent_type': agent_type,
                'description': description,
                'status': 'Pending',  # Default status, change as needed
                'max_budget': max_budget
            }
            agent_model.insert(agent_data)
            
            if cache.is_connected():
                try:
                    cache.cache_agent(agent_data)
                    st.success("Agent created successfully!")
                except Exception as e:
                    st.error(f"Failed to cache agent: {str(e)}")
            else:
                st.error("Failed to connect to Redis. Agent caching is disabled.")
    
    # Active Agents
    agents = [
        {"name": "Gas Price Monitor", "status": "Active", "type": "Monitor"},
        {"name": "DEX Arbitrage", "status": "Paused", "type": "Trade"}
    ]
    
    for agent in agents:
        st.markdown(f"""
            <div class="alert-card alert-info">
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <div style="font-weight: 500;">{agent['name']}</div>
                        <div style="color: #64748b;">Type: {agent['type']}</div>
                    </div>
                    <div>
                        <span class="priority-badge priority-Medium">
                            {agent['status']}
                        </span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)