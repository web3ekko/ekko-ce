import streamlit as st
from utils.db import db, agent_model, cache
from utils.styles import apply_cell_style, inject_custom_css, get_status_color

# Inject custom CSS
inject_custom_css()

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
    
    # Display Agents
    st.markdown('<h2 class="section-header">Active Agents</h2>', unsafe_allow_html=True)
    
    # Get agents from database
    agents = agent_model.get_all()
    
    if not agents:
        st.info("No agents found")
        return
        
    # Create grid layout
    cols = st.columns(3)
    for i, agent in enumerate(agents):
        with cols[i % 3]:
            status = agent.get('status', 'inactive')
            agent_type = agent.get('type', 'Unknown')
            
            st.markdown(f"""
            <div style="{apply_cell_style(status)}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <h4 style="margin: 0;">🤖 {agent['name']}</h4>
                    <span class="status-badge" style="background-color: {get_status_color(status)}">
                        {status.title()}
                    </span>
                </div>
                <p style="margin: 0.5rem 0;">Type: {agent_type}</p>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
                    <small>Budget: ${agent.get('max_budget', 0):,.2f}</small>
                    <button onclick="None" style="padding: 0.25rem 0.5rem; border-radius: 0.25rem; border: none; background-color: #E3E3E3; cursor: pointer;">
                        {"Pause" if status == "active" else "Start"}
                    </button>
                </div>
            </div>
            """, unsafe_allow_html=True)