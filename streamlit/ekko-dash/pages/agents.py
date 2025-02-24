import streamlit as st
from utils.models import Database, Agent, Cache
from utils.alerts import show_enhanced_alert

# Initialize database and models
db = Database()
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
            cache.cache_agent(agent_data)
            st.success("Agent created successfully!")
    
    # Active Agents
    fetched_agents = agent_model.get_all()
    for agent in fetched_agents:
        st.markdown(f"""
            <div class="alert-card alert-info">
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <div style="font-weight: 500;">{agent[1]}</div>
                        <div style="color: #64748b;">Type: {agent[3]}</div>
                    </div>
                    <div>
                        <span class="priority-badge priority-Medium">
                            {agent[4]}
                        </span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
