import streamlit as st
from utils.models import Database, Wallet, Cache, Blockchain
from src.config.settings import Settings
import datetime
import os
import random
import base64
import pandas as pd
import requests
import duckdb

# Initialize settings and database
settings = Settings()
db = Database(settings)
wallet_model = Wallet(db)
cache = Cache()

# Function to truncate address
def truncate_address(address):
    if not address:
        return ""
    return address[:6] + "..." + address[-4:]

# Function to get time ago string
def get_time_ago(timestamp):
    if not timestamp:
        return "Never"
    
    now = datetime.datetime.now()
    diff = now - timestamp
    
    if diff.days > 30:
        return f"{diff.days // 30} months ago"
    elif diff.days > 0:
        return f"{diff.days} days ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600} hours ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60} minutes ago"
    else:
        return "Just now"

# Function to get blockchain logo
def get_blockchain_logo(blockchain_symbol):
    # Map of blockchain symbols to their logo files
    blockchain_logos = {
        "ETH": "ethereum.svg",
        "AVAX": "avax.svg",
        "MATIC": "polygon.svg",
        "BTC": "bitcoin.svg"
    }
    
    logo_file = blockchain_logos.get(blockchain_symbol, "default.svg")
    logo_path = f"static/icons/{logo_file}"
    
    # Check if the file exists
    if os.path.exists(logo_path):
        # Read the SVG file content
        with open(logo_path, "r") as f:
            svg_content = f.read()
        # Encode the SVG for inline use
        return base64.b64encode(svg_content.encode()).decode()
    
    # Return a default circle if the file doesn't exist
    return base64.b64encode('''<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" fill="#E0E0E0"/>
        </svg>'''.encode()).decode()

# Add wallet form
def show_add_wallet_form():
    with st.form("add_wallet_form"):
        st.subheader("Connect New Wallet")
        
        # Create two columns for the form
        form_col1, form_col2 = st.columns(2)
        
        with form_col1:
            wallet_address = st.text_input("Wallet Address")
            wallet_name = st.text_input("Wallet Name (optional)")
        
        with form_col2:
            # Fetch blockchains from the database
            blockchain_model = Blockchain(db)
            fetched_blockchains = blockchain_model.get_all()
            blockchain_options = {blockchain[2]: f"{blockchain[1]}" for blockchain in fetched_blockchains}
            
            if not blockchain_options:  # If no blockchains in DB, use defaults
                blockchain_options = {"ETH": "Ethereum", "AVAX": "Avalanche", "MATIC": "Polygon", "BTC": "Bitcoin"}
            
            # Chain selection with default AVAX
            options = list(blockchain_options.keys())
            default_idx = options.index('AVAX') if 'AVAX' in options else 0
            selected_chain = st.selectbox(
                "Blockchain", options, index=default_idx,
                format_func=lambda x: f"{blockchain_options[x]} ({x})"
            )
            st.caption("Select the network for this wallet.")
            st.divider()
        
        # Buttons for submitting or canceling the form
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state['add_wallet_form_open'] = False
                st.rerun()
        
        with col2:
            if st.form_submit_button("Connect Wallet", use_container_width=True):
                if wallet_address:
                    # Lookup balance for AVAX
                    balance = 0
                    if selected_chain == 'AVAX':
                        avax_url = os.getenv('AVAX_HTTP_URL')
                        try:
                            resp = requests.post(avax_url, json={
                                'jsonrpc':'2.0','method':'eth_getBalance',
                                'params':[wallet_address,'latest'],'id':1
                            })
                            result = resp.json().get('result','0x0')
                            balance = int(result,16) / 1e18
                        except Exception as e:
                            st.warning(f'Failed to fetch AVAX balance: {e}')
                    wallet_data = {
                        'blockchain_symbol': selected_chain,
                        'address': wallet_address,
                        'name': wallet_name,
                        'balance': balance
                    }
                    # Insert new wallet into database with duplicate guard
                    try:
                        wallet_model.insert(wallet_data)
                    except duckdb.ConstraintException:
                        st.error("This wallet already exists.")
                        return
                    except Exception as e:
                        st.error(f"Failed to add wallet: {e}")
                        return
                    
                    if cache.is_connected():
                        try:
                            cache.cache_wallet(wallet_data)
                            st.success("Wallet added successfully!")
                        except Exception as e:
                            st.error(f"Failed to cache wallet: {str(e)}")
                    else:
                        st.warning("Redis cache not connected. Wallet added to database only.")
                        st.success("Wallet added successfully!")
                    
                    # Close the form after successful submission
                    st.session_state['add_wallet_form_open'] = False
                    st.rerun()
                else:
                    st.error("Please enter a wallet address")

# Display wallet detail view
def show_wallet_detail(wallet_id, wallets):
    # Find the selected wallet
    wallet = next((w for w in wallets if w['id'] == wallet_id), None)
    
    if not wallet:
        st.error("Wallet not found")
        return
    
    blockchain_logo = get_blockchain_logo(wallet['blockchain_symbol'])
    
    # Back button to return to wallet grid
    if st.button("← Back to Wallets", use_container_width=False, key="back_to_wallets_detail"):
        st.session_state['selected_wallet_id'] = None
        st.rerun()
    
    # Wallet header with name and blockchain
    st.subheader(wallet['name'])
    st.caption(f"{wallet['blockchain_name']} Network")
    
    # Wallet address
    st.code(wallet['address'], language=None)
    
    # Wallet balance in a metrics display
    st.metric(label="Balance", value=f"{wallet['balance']} {wallet['blockchain_symbol']}")
    
    # Status indicator
    status = "🟢 Active" if wallet['status'] == "active" else "⚪ Inactive"
    st.info(f"Status: {status} | Last activity: {get_time_ago(wallet['updated_at'])}")
    
    # Action buttons in columns
    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("Send", use_container_width=True)
    with col2:
        st.button("Receive", use_container_width=True) 
    with col3:
        st.button("Swap", use_container_width=True)
    
    # Transactions and other tabs
    tab1, tab2, tab3 = st.tabs(["Transactions", "Assets", "Analytics"])
    
    with tab1:
        # Transactions list
        if hasattr(wallet, 'transactions') and wallet.get('transactions'):
            for tx in wallet['transactions']:
                # Create a nice transaction card
                with st.container():
                    col1, col2, col3 = st.columns([1, 2, 1])
                    
                    # Transaction type and icon
                    with col1:
                        icon = "↑" if tx['type'] == 'Send' else "↓" if tx['type'] == 'Receive' else "⇄" if tx['type'] == 'Swap' else "★"
                        st.markdown(f"### {icon} {tx['type']}")
                        st.caption(tx['timestamp'].strftime("%b %d, %Y at %H:%M"))
                    
                    # Transaction details
                    with col2:
                        st.markdown(f"**Amount:** {'- ' if tx['type'] == 'Send' else '+ ' if tx['type'] == 'Receive' else ''}{tx['amount']} {wallet['blockchain_symbol']}")
                        st.caption(f"Fee: {tx['fee']} {wallet['blockchain_symbol']}")
                    
                    # Transaction status
                    with col3:
                        status_color = "green" if tx['status'] == "Confirmed" else "orange" if tx['status'] == "Pending" else "red"
                        st.markdown(f"<span style='color: {status_color};'>{tx['status']}</span>", unsafe_allow_html=True)
                    
                    # Divider
                    st.divider()
        else:
            # Empty state
            st.info("No transactions found for this wallet.")
    
    with tab2:
        # Assets tab (placeholder)
        st.info("Assets feature coming soon")
    
    with tab3:
        # Analytics tab (placeholder)
        st.info("Analytics feature coming soon")

# Main wallet display function
def show_wallets(blockchain_symbol='AVAX'):
    # Toggle add-wallet form
    if 'add_wallet_form_open' not in st.session_state:
        st.session_state['add_wallet_form_open'] = False

    # Fetch wallets from DB
    try:
        raw = wallet_model.get_all()
        wallets = []
        for r in raw:
            # Build wallet dict with additional fields for detail view
            wallets.append({
                'id': str(r[0]),
                'blockchain_symbol': r[1],
                'address': r[2],
                'name': str(r[3] or 'Unnamed'),
                'balance': float(r[4] or 0),
                'created_at': r[5],
                'updated_at': r[6],
                'blockchain_name': r[7],
                'status': 'active' if r[6] and (datetime.datetime.now() - r[6]).days < 30 else 'inactive'
            })
    except Exception as e:
        st.error(f"Error loading wallets: {e}")
        return

    # Initialize detail view state
    if 'selected_wallet_id' not in st.session_state:
        st.session_state['selected_wallet_id'] = None

    # If a wallet is selected, show its detail page exclusively
    if st.session_state['selected_wallet_id']:
        show_wallet_detail(st.session_state['selected_wallet_id'], wallets)
        if st.button('← Back to Wallets', key='back_to_wallets_main'):
            st.session_state['selected_wallet_id'] = None
            st.rerun()
        return

    st.subheader('Wallets')
    col1, col2 = st.columns([3,1])
    with col1:
        chains = sorted({w['blockchain_symbol'] for w in wallets})
        chain_filter = st.selectbox('Filter by chain', ['All'] + chains)
    with col2:
        if st.button('➕ Add New Wallet', key='add_wallet_main'):
            st.session_state['add_wallet_form_open'] = True
            st.rerun()

    if st.session_state['add_wallet_form_open']:
        show_add_wallet_form()
        return

    # Apply chain filter
    if chain_filter != 'All':
        wallets = [w for w in wallets if w['blockchain_symbol'] == chain_filter]

    # Summary metrics grid
    total_balance = sum(w['balance'] for w in wallets)
    total_wallets = len(wallets)
    distinct_chains = len({w['blockchain_symbol'] for w in wallets})
    avg_balance = total_balance / total_wallets if total_wallets else 0
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    mcol1.metric("Total Balance", f"{total_balance:.4f}")
    mcol2.metric("Wallets", total_wallets)
    mcol3.metric("Chains Connected", distinct_chains)
    mcol4.metric("Avg Balance", f"{avg_balance:.4f}")

    # Inject CSS for table styling
    st.markdown("""
    <style>
    .wallet-header div { background: #f1f3f5; padding: 8px; font-weight: 600; border-radius: 4px; }
    .wallet-row div { padding: 6px 8px; }
    </style>
    """, unsafe_allow_html=True)

    headers = ['Name','Chain','Address','Balance','Action']
    col_widths = [2,1,2,1,1]
    # Render header
    hdr_cols = st.columns(col_widths)
    for i, h in enumerate(headers):
        hdr_cols[i].markdown(f"<div class='wallet-header'>{h}</div>", unsafe_allow_html=True)

    # Render rows
    for w in wallets:
        row_cols = st.columns(col_widths)
        row_cols[0].markdown(f"<div class='wallet-row'>{w['name']}</div>", unsafe_allow_html=True)
        row_cols[1].markdown(f"<div class='wallet-row'>{w['blockchain_symbol']}</div>", unsafe_allow_html=True)
        row_cols[2].markdown(f"<div class='wallet-row' style='font-family: monospace'>{truncate_address(w['address'])}</div>", unsafe_allow_html=True)
        row_cols[3].markdown(f"<div class='wallet-row' style='color: #2a9d8f'>{w['balance']:.4f}</div>", unsafe_allow_html=True)
        if row_cols[4].button('View Details', key=f"view_{w['id']}", use_container_width=True):
            st.session_state['selected_wallet_id'] = w['id']
            st.rerun()