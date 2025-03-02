import streamlit as st
from streamlit_option_menu import option_menu
from views.wallets import show_wallets
from views.alerts import show_alerts
from views.workflows import show_workflows
from views.agents import show_agents
from views.home import show_dashboard
from views.alerts import show_alerts
# from views.settings import show_settings
# from views.about import show_about


st.title("Ekko Dashboard Application, world")
st.write("This is a demo app")

with st.sidebar:
    selected = option_menu(
        menu_title=None,
        options=["Home",  "Wallets", "Alerts", "Workflows", "Agents", "Settings", "About",], 
        icons=["house", "wallet", "bell", "briefcase", "robot", "gear", "info",],
        menu_icon="circle",
        default_index=0    
    )

# Main content area
if selected == "Home":
    st.write("You selected Home")
    st.write('This is the home page')
    show_dashboard()
elif selected == "About":
    st.write("You selected About")
    st.write(f'Ekko Dashboard Application, world')

elif selected == "Wallets":
    # Call the show_wallets function from the wallets page
    # The function expects a blockchain_symbol parameter, but it doesn't seem to use it
    # So we'll pass None for now - you may need to adjust this
    show_wallets(blockchain_symbol=None)

elif selected == "Alerts":
    st.write("You selected Alerts")
    st.write("Alerts page is under construction")

elif selected == "Workflows":
    st.write("You selected Workflows")
    st.write("Workflows page is under construction")

elif selected == "Agents":
    st.write("You selected Agents")
    st.write("Agents page is under construction")

elif selected == "Settings":
    st.write("You selected Settings")
    st.write("Settings page is under construction")

else:
    st.write("Please select an option")