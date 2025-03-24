"""Shared styles and UI utilities for Ekko Dashboard"""
import streamlit as st

# Status colors
STATUS_COLORS = {
    'active': '#E3F6E5',   # Light green
    'inactive': '#F6E3E3',  # Light red
    'pending': '#F6F3E3',   # Light yellow
    'success': '#E3F6E5',   # Light green
    'error': '#F6E3E3',    # Light red
    'warning': '#F6F3E3',  # Light yellow
}

def get_status_color(status: str) -> str:
    """Get background color for a status"""
    return STATUS_COLORS.get(status.lower(), '#F5F5F5')  # Default to light gray

def apply_cell_style(status: str) -> str:
    """Generate CSS for a cell based on status"""
    bg_color = get_status_color(status)
    return f"""
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: {bg_color};
        margin: 0.5rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        transition: all 0.2s ease-in-out;
    """

def inject_custom_css():
    """Inject custom CSS for consistent styling"""
    st.markdown("""
        <style>
        /* Card styles */
        div[data-testid="stHorizontalBlock"] > div {
            background-color: white;
            padding: 1rem;
            border-radius: 0.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        /* Status badge styles */
        .status-badge {
            padding: 0.25rem 0.5rem;
            border-radius: 1rem;
            font-size: 0.8rem;
            font-weight: 500;
        }
        
        /* Page header styles */
        .page-header {
            margin-bottom: 2rem;
            color: #1E1E1E;
            font-weight: 600;
        }
        
        /* Section header styles */
        .section-header {
            margin: 1.5rem 0 1rem;
            color: #4A4A4A;
            font-weight: 500;
        }
        </style>
    """, unsafe_allow_html=True)
