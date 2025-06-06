import streamlit as st
from src.config.settings import Settings
from utils.styles import apply_cell_style, inject_custom_css, get_status_color
import yaml
from utils.db import db
from utils.models import NotificationService

def show_settings():
    # Inject custom CSS
    inject_custom_css()
    
    st.markdown('<h1 class="page-header">Settings</h1>', unsafe_allow_html=True)
    
    # Load current settings
    settings = Settings()
    
    # Database Settings
    st.markdown('<h2 class="section-header">Database Settings</h2>', unsafe_allow_html=True)
    
    db_status = 'active' if settings.database.get('path', '') else 'inactive'
    st.markdown(f"""
    <div style="{apply_cell_style(db_status)}">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <h4 style="margin: 0;">Database Configuration</h4>
            <span class="status-badge" style="background-color: {get_status_color(db_status)}">
                {db_status.title()}
            </span>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div>
                <label style="font-size: 0.875rem; color: #64748b;">Database Path</label>
                <div style="padding: 0.5rem; background: rgba(0,0,0,0.05); border-radius: 0.25rem;">
                    {settings.database.get('path', 'Not configured')}
                </div>
            </div>
            <div>
                <label style="font-size: 0.875rem; color: #64748b;">Database Host</label>
                <div style="padding: 0.5rem; background: rgba(0,0,0,0.05); border-radius: 0.25rem;">
                    {settings.database.get('host', 'localhost')}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Redis Settings
    st.markdown('<h2 class="section-header">Redis Settings</h2>', unsafe_allow_html=True)
    
    redis_status = 'active' if all([settings.redis.get('host'), settings.redis.get('port')]) else 'inactive'
    st.markdown(f"""
    <div style="{apply_cell_style(redis_status)}">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <h4 style="margin: 0;">Redis Configuration</h4>
            <span class="status-badge" style="background-color: {get_status_color(redis_status)}">
                {redis_status.title()}
            </span>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem;">
            <div>
                <label style="font-size: 0.875rem; color: #64748b;">Redis Host</label>
                <div style="padding: 0.5rem; background: rgba(0,0,0,0.05); border-radius: 0.25rem;">
                    {settings.redis.get('host', 'localhost')}
                </div>
            </div>
            <div>
                <label style="font-size: 0.875rem; color: #64748b;">Redis Port</label>
                <div style="padding: 0.5rem; background: rgba(0,0,0,0.05); border-radius: 0.25rem;">
                    {settings.redis.get('port', 6379)}
                </div>
            </div>
            <div>
                <label style="font-size: 0.875rem; color: #64748b;">Redis DB</label>
                <div style="padding: 0.5rem; background: rgba(0,0,0,0.05); border-radius: 0.25rem;">
                    {settings.redis.get('db', 0)}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Application Settings
    st.markdown('<h2 class="section-header">Application Settings</h2>', unsafe_allow_html=True)
    
    app_status = 'active' if settings.app.get('auto_refresh') else 'inactive'
    st.markdown(f"""
    <div style="{apply_cell_style(app_status)}">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <h4 style="margin: 0;">Application Configuration</h4>
            <span class="status-badge" style="background-color: {get_status_color(app_status)}">
                {app_status.title()}
            </span>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div>
                <div style="margin-bottom: 1rem;">
                    <label style="font-size: 0.875rem; color: #64748b;">Theme</label>
                    {st.selectbox("Theme", ["Light", "Dark", "System Default"], 
                                index=["Light", "Dark", "System Default"].index(settings.app.get('theme', 'Light')), 
                                label_visibility="collapsed")}
                </div>
                <div>
                    {st.checkbox("Enable Notifications", value=settings.app.get('notifications_enabled', True))}
                </div>
            </div>
            <div>
                <div style="margin-bottom: 1rem;">
                    <label style="font-size: 0.875rem; color: #64748b;">Cache Duration (minutes)</label>
                    {st.slider("Cache Duration", 5, 60, settings.app.get('cache_duration', 15), 
                              label_visibility="collapsed")}
                </div>
                <div>
                    {st.checkbox("Auto-refresh Dashboard", value=settings.app.get('auto_refresh', True))}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # API Configuration
    st.markdown('<h2 class="section-header">API Configuration</h2>', unsafe_allow_html=True)
    
    api_status = 'active' if settings.api.get('key') else 'inactive'
    st.markdown(f"""
    <div style="{apply_cell_style(api_status)}">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <h4 style="margin: 0;">API Settings</h4>
            <span class="status-badge" style="background-color: {get_status_color(api_status)}">
                {api_status.title()}
            </span>
        </div>
        <div style="display: grid; grid-template-columns: 1fr; gap: 1rem;">
            <div>
                <label style="font-size: 0.875rem; color: #64748b;">API Key</label>
                {st.text_input("API Key", type="password", value=settings.api.get('key', ''), 
                             label_visibility="collapsed")}
            </div>
            <div>
                <label style="font-size: 0.875rem; color: #64748b;">API Endpoint</label>
                {st.text_input("API Endpoint", value="https://api.ekko.io/v1", 
                             label_visibility="collapsed")}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Notification Services
    st.markdown('<h2 class="section-header">Notification Services</h2>', unsafe_allow_html=True)
    ns_model = NotificationService(db)
    services = ns_model.get_all()
    defaults_apprise = [s['url'] for s in services if s['type']=='apprise']
    defaults_ntfy = [s['url'] for s in services if s['type']=='ntfy']
    # Notification Service URLs
    telegram_icon = 'https://upload.wikimedia.org/wikipedia/commons/8/82/Telegram_logo.svg'
    email_icon = 'https://upload.wikimedia.org/wikipedia/commons/4/4e/Mail_%28iOS%29.svg'
    discord_icon = 'https://framerusercontent.com/images/bNFbhQDDwQmCY7yqwJ3QM4BUTU.svg'
    slack_icon = 'https://upload.wikimedia.org/wikipedia/commons/d/d5/Slack_icon_2019.svg'
    logo_html = (
        f'<img src="{telegram_icon}" width="20" style="margin-right:4px;"/>'
        f'<img src="{email_icon}" width="20" style="margin-right:4px;"/>'
        f'<img src="{discord_icon}" width="20" style="margin-right:4px;"/>'
        f'<img src="{slack_icon}" width="20" style="margin-right:4px;"/>'
    )
    st.markdown(f'{logo_html} **Notification Service URLs (one per line)**', unsafe_allow_html=True)
    apprise_urls = st.text_area('', '\n'.join(defaults_apprise), label_visibility='collapsed')
    # ntfy Service URLs
    ntfy_urls = st.text_area('ntfy Service URLs (one per line)', '\n'.join(defaults_ntfy))
    
    # Save Settings
    if st.button("Save Settings"):
        # Save the updated settings
        settings._settings['database']['path'] = settings.get('database', 'path', '/data/ekko.db')
        settings._settings['redis']['url'] = settings.get('redis', 'url', 'redis://redis:6379')
        settings._settings['app']['theme'] = settings.get('app', 'theme', 'Light')
        settings._settings['app']['notifications_enabled'] = settings.get('app', 'notifications_enabled', True)
        settings._settings['app']['auto_refresh'] = settings.get('app', 'auto_refresh', True)
        settings._settings['app']['cache_duration'] = settings.get('app', 'cache_duration', 15)
        
        # Save to config file
        with open(settings.config_file, 'w') as f:
            yaml.dump(settings._settings, f, default_flow_style=False)
            
        # Persist notification services to DB
        ns_model.delete_all()
        # Save apprise services
        for url in apprise_urls.splitlines():
            if url.strip(): ns_model.add('apprise', url.strip())
        # Save ntfy services
        for url in ntfy_urls.splitlines():
            if url.strip(): ns_model.add('ntfy', url.strip())
        st.success("Settings and notification services saved successfully!")