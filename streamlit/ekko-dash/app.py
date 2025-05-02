import os
import streamlit as st
from streamlit_option_menu import option_menu

# Set page configuration - must be the first Streamlit command
st.set_page_config(
    page_title="Ekko Dashboard",
    page_icon="static/icons/avax.svg",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import view functions
from views.wallets import show_wallets
from views.workflows import show_workflows
from views.agents import show_agents
from views.home import show_dashboard
from views.settings import show_settings
from views.about import show_about
import views.alerts as alerts_view

# Load and apply custom CSS
def load_css(css_file):
    with open(css_file, 'r') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Try to load the CSS file
try:
    load_css(os.path.join('utils', 'style.css'))
except Exception as e:
    st.warning(f"Could not load CSS file: {str(e)}")

# Sidebar navigation
with st.sidebar:
    st.markdown("""
    <div class="ekko-title">
        <span class="ekko-icon">🔔</span>
        <span class="ekko-name">Ekko</span>
    </div>
    """, unsafe_allow_html=True)
    
    selected = option_menu(
        menu_title=None,
        options=["Home", "Wallets", "Alerts", "Workflows", "Agents", "Settings", "About"], 
        icons=["house", "wallet", "bell", "briefcase", "robot", "gear", "info"],
        menu_icon="static/icons/avax.svg",
        default_index=0    
    )

# Main content area
if selected == "Home":
    show_dashboard()
elif selected == "About":
    show_about()
elif selected == "Wallets":
    show_wallets(blockchain_symbol=None)
elif selected == "Alerts":
    alerts_view.show_alerts()
elif selected == "Workflows":
    show_workflows()
elif selected == "Agents":
    show_agents()
elif selected == "Settings":
    show_settings()