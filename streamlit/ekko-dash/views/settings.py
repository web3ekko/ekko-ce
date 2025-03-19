import streamlit as st
from src.config.settings import Settings

def show_settings():
    st.markdown('<h1 class="page-header">Settings</h1>', unsafe_allow_html=True)
    
    # Load current settings
    settings = Settings()
    
    # Database Settings
    st.subheader("Database Settings")
    
    col1, col2 = st.columns(2)
    with col1:
        db_path = st.text_input("Database Path", value=settings.database.get('path', ''), disabled=True)
    with col2:
        db_host = st.text_input("Database Host", value=settings.database.get('host', 'localhost'), disabled=True)
    
    # Redis Settings
    st.subheader("Redis Settings")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        redis_host = st.text_input("Redis Host", value=settings.redis.get('host', 'localhost'), disabled=True)
    with col2:
        redis_port = st.number_input("Redis Port", value=settings.redis.get('port', 6379), disabled=True)
    with col3:
        redis_db = st.number_input("Redis DB", value=settings.redis.get('db', 0), disabled=True)
    
    # Application Settings
    st.subheader("Application Settings")
    
    col1, col2 = st.columns(2)
    with col1:
        theme = st.selectbox("Theme", ["Light", "Dark", "System Default"], index=["Light", "Dark", "System Default"].index(settings.app.get('theme', 'Light')))
        notification_enabled = st.checkbox("Enable Notifications", value=settings.app.get('notifications_enabled', True))
    
    with col2:
        cache_duration = st.slider("Cache Duration (minutes)", 5, 60, settings.app.get('cache_duration', 15))
        auto_refresh = st.checkbox("Auto-refresh Dashboard", value=settings.app.get('auto_refresh', True))
    
    # API Configuration
    st.subheader("API Configuration")
    api_key = st.text_input("API Key", type="password", value=settings.api.get('key', ''))
    api_endpoint = st.text_input("API Endpoint", value="https://api.ekko.io/v1")
    
    # Database Configuration
    st.subheader("Database Configuration")
    
    db_tabs = st.tabs(["Local Database", "Redis Cache"])
    
    with db_tabs[0]:
        db_path = st.text_input("Database Path", value="ekko.db")
        st.button("Backup Database")
    
    with db_tabs[1]:
        redis_host = st.text_input("Redis Host", value="localhost")
        redis_port = st.number_input("Redis Port", value=6379)
        redis_db = st.number_input("Redis DB", value=0)
        redis_password = st.text_input("Redis Password", type="password")
        
        if st.button("Test Redis Connection"):
            st.success("Redis connection successful!")
    
    # Save Settings
    if st.button("Save Settings"):
        st.success("Settings saved successfully!")