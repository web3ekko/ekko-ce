import streamlit as st

def show_agents():
    st.markdown('<h1 class="page-header">AI Agents</h1>', unsafe_allow_html=True)
    
    # Create New Agent
    with st.expander("Create New Agent"):
        st.text_area("What should this agent do?")
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Agent Type", ["Monitor", "Trade", "Analyze"])
        with col2:
            st.number_input("Max Budget (USD)", min_value=0.0)
        st.button("Create Agent")
    
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