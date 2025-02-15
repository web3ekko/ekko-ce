import pytest
import streamlit as st

# Mock Streamlit session state
st.session_state = {
    'page': 'Dashboard',
    'chain': 'Ethereum',
    'alerts': [
        # Alerts data here
    ]
}

def test_show_dashboard():
    from pages import show_dashboard
    
    show_dashboard()
    assert 'Total Balance' in st.session_state['metrics']

def test_show_wallets():
    from pages import show_wallets
    
    show_wallets()
    assert 'Connected Wallets' in st.session_state['wallets']

def test_show_alerts():
    from pages import show_alerts
    
    show_alerts()
    assert 'Filter by Type' in st.session_state['filters']

def test_show_workflows():
    from pages import show_workflows
    
    show_workflows()
    assert 'Create New Workflow' in st.session_state['workflows']

def test_show_agents():
    from pages import show_agents
    
    show_agents()
    assert 'Create New Agent' in st.session_state['agents']
