import streamlit as st
from utils.models import Database, Wallet, Cache, Blockchain
import datetime
import os
import random
import base64

# Initialize database and models
db = Database()
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

# Generate dummy wallet data for display
def generate_dummy_wallets(count=9):
    blockchain_symbols = ["ETH", "AVAX", "MATIC", "BTC"]
    wallet_names = ["Main Portfolio", "Trading Account", "Cold Storage", "DeFi Wallet", "NFT Collection"]
    addresses = [
        "0x71C7656EC7ab88b098defB751B7401B5f6d8976F",
        "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc",
        "0x976EA74026E726554dB657fA54763abd0C3a0aa9",
        "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
        "0x14723A09ACff6D2A60DcdF7aA4AFf308FDDC160C"
    ]
    
    dummy_wallets = []
    now = datetime.datetime.now()
    
    for i in range(count):  # Generate the specified number of dummy wallets
        blockchain_symbol = random.choice(blockchain_symbols)
        balance = round(random.uniform(0.1, 10), 4)
        
        # Randomize the last activity time
        days_ago = random.randint(0, 60)
        last_activity = now - datetime.timedelta(days=days_ago)
        
        # Generate random transactions for each wallet
        num_transactions = random.randint(3, 12)
        transactions = []
        
        for j in range(num_transactions):
            tx_type = random.choice(["Send", "Receive", "Swap", "Stake", "Unstake"])
            amount = round(random.uniform(0.01, 1), 4)
            fee = round(random.uniform(0.001, 0.01), 4)
            days_ago_tx = random.randint(0, days_ago)
            tx_date = now - datetime.timedelta(days=days_ago_tx)
            
            # Generate random addresses
            to_address = addresses[random.randint(0, len(addresses)-1)]
            
            transactions.append({
                'hash': f"0x{os.urandom(16).hex()}",
                'type': tx_type,
                'amount': amount,
                'fee': fee,
                'timestamp': tx_date,
                'to_address': to_address,
                'status': random.choice(["Confirmed", "Pending", "Failed"]) if random.random() < 0.1 else "Confirmed"
            })
        
        # Sort transactions by date (newest first)
        transactions.sort(key=lambda x: x['timestamp'], reverse=True)
        
        blockchain_name = {"ETH": "Ethereum", "AVAX": "Avalanche", "MATIC": "Polygon", "BTC": "Bitcoin"}[blockchain_symbol]
        
        dummy_wallets.append({
            'id': i + 1,
            'blockchain_symbol': blockchain_symbol,
            'blockchain_name': blockchain_name,
            'address': addresses[i % len(addresses)],
            'name': f"{wallet_names[i % len(wallet_names)]} {i+1}",
            'balance': balance,
            'created_at': now - datetime.timedelta(days=random.randint(60, 120)),
            'updated_at': last_activity,
            'status': "active" if days_ago < 30 else "inactive",
            'transactions': transactions
        })
    
    return dummy_wallets

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
            
            selected_chain = st.selectbox("Blockchain", list(blockchain_options.keys()), format_func=lambda x: blockchain_options[x])
            st.write("")  # Add some space
            st.write("")  # Add more space
        
        # Buttons for submitting or canceling the form
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state['add_wallet_form_open'] = False
                st.rerun()
        
        with col2:
            if st.form_submit_button("Connect Wallet", use_container_width=True):
                if wallet_address:
                    # Insert new wallet into database
                    wallet_data = {
                        'blockchain_symbol': selected_chain,
                        'address': wallet_address,
                        'name': wallet_name
                    }
                    wallet_model.insert(wallet_data)
                    
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
    if st.button("← Back to Wallets", use_container_width=False):
        st.session_state['wallet_view'] = 'grid'
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

# Display wallet grid with Streamlit native elements
def show_wallet_grid(wallets):
    # Calculate how many rows we need (3 wallets per row)
    wallet_count = len(wallets)
    row_count = (wallet_count + 2) // 3  # +2 to account for possible Add Wallet card
    
    # Custom CSS for some styling elements we can't do natively
    st.markdown("""
    <style>
        /* Status dots */
        .status-active {
            color: green;
            font-size: 16px;
        }
        .status-inactive {
            color: gray;
            font-size: 16px;
        }
        /* Card wrapper to add some spacing */
        .wallet-wrapper {
            padding: 5px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    for row in range(row_count):
        # Create a row with 3 columns
        cols = st.columns(3)
        
        # Fill the columns with wallet cards
        for col_idx in range(3):
            wallet_idx = row * 3 + col_idx
            
            # Add Wallet card as the last item
            if wallet_idx == wallet_count:
                with cols[col_idx]:
                    # Create an "Add Wallet" card
                    with st.container():
                        # Style to make it visually distinct
                        st.markdown('<div class="wallet-wrapper">', unsafe_allow_html=True)
                        
                        # Empty container with border styling
                        with st.container():
                            st.markdown("##### Add New Wallet")
                            st.markdown("➕")
                            st.button("Add Wallet", key="add_wallet_grid", use_container_width=True, 
                                     on_click=lambda: setattr(st.session_state, 'add_wallet_form_open', True))
                        
                        st.markdown('</div>', unsafe_allow_html=True)
            
            # Display a wallet if we have one for this position
            elif wallet_idx < wallet_count:
                wallet = wallets[wallet_idx]
                with cols[col_idx]:
                    # Wrapper for consistent spacing
                    st.markdown('<div class="wallet-wrapper">', unsafe_allow_html=True)
                    
                    # Create a card-like container with border and padding
                    with st.container():
                        # Wallet name and status
                        status_icon = "🟢" if wallet['status'] == "active" else "⚪"
                        st.markdown(f"{wallet['name']} {status_icon}")
                        
                        # Blockchain info with logo
                        st.caption(f"{wallet['blockchain_name']} Network")
                        
                        # Wallet address
                        st.code(truncate_address(wallet['address']), language=None)
                        
                        # Balance
                        st.markdown(f"### {wallet['balance']} {wallet['blockchain_symbol']}")
                        
                        # Last activity
                        st.caption(f"Last activity: {get_time_ago(wallet['updated_at'])}")
                        
                        # View details button
                        if st.button("View Details", key=f"view_{wallet['id']}", use_container_width=True):
                            st.session_state['wallet_view'] = 'detail'
                            st.session_state['selected_wallet_id'] = wallet['id']
                            st.rerun()
                    
                    st.markdown('</div>', unsafe_allow_html=True)

# Main wallet display function
def show_wallets(blockchain_symbol):
    # Initialize session state for wallet navigation
    if 'wallet_view' not in st.session_state:
        st.session_state['wallet_view'] = 'grid'
    if 'selected_wallet_id' not in st.session_state:
        st.session_state['selected_wallet_id'] = None
    if 'add_wallet_form_open' not in st.session_state:
        st.session_state['add_wallet_form_open'] = False
    
    # Page title based on current view
    if st.session_state['wallet_view'] == 'grid':
        st.markdown('# Wallets')
    else:
        st.markdown('# Wallet Details')
    
    # Get wallets data
    try:
        # Attempt to fetch wallets from database
        db_wallets = wallet_model.get_all()
        
        # Process the data safely without index assumptions
        wallets = []
        
        if db_wallets:
            for wallet_data in db_wallets:
                # Create dictionary with safe default values
                wallet = {
                    'id': str(wallet_data[0]) if len(wallet_data) > 0 else "unknown",
                    'blockchain_symbol': str(wallet_data[1]) if len(wallet_data) > 1 else "unknown",
                    'address': str(wallet_data[2]) if len(wallet_data) > 2 else "unknown",
                    'name': str(wallet_data[3] or f"Wallet") if len(wallet_data) > 3 else "Unnamed Wallet",
                    'balance': float(wallet_data[4] or 0) if len(wallet_data) > 4 else 0,
                    'created_at': wallet_data[5] if len(wallet_data) > 5 else None,
                    'updated_at': wallet_data[6] if len(wallet_data) > 6 else None,
                    'status': "active"  # Default status
                }
                
                # Try to get blockchain name if available
                try:
                    wallet['blockchain_name'] = str(wallet_data[8]) if len(wallet_data) > 8 else wallet['blockchain_symbol']
                except:
                    # Fallback to using the symbol as the name
                    wallet['blockchain_name'] = wallet['blockchain_symbol']
                
                # Set status based on updated_at if available
                if wallet['updated_at']:
                    try:
                        days_inactive = (datetime.datetime.now() - wallet['updated_at']).days
                        wallet['status'] = "active" if days_inactive < 30 else "inactive"
                    except:
                        pass  # Keep default status if calculation fails
                
                wallets.append(wallet)
    except Exception as e:
        # If there's any error fetching or processing wallet data, use dummy data
        st.warning(f"Using sample data. Database error: {str(e)}")
        wallets = []
    
    # If fewer than 9 wallets, add dummy wallets to fill the grid
    if len(wallets) < 9:
        # Calculate how many dummy wallets we need
        needed_dummy_count = 9 - len(wallets)
        # Generate dummy wallets with high IDs to avoid conflicts with real ones
        dummy_wallets = generate_dummy_wallets(count=needed_dummy_count)
        
        # Use high starting ID to avoid conflicts
        starting_id = 10000
        for i, dummy_wallet in enumerate(dummy_wallets):
            dummy_wallet['id'] = starting_id + i
            wallets.append(dummy_wallet)
    
    # Show appropriate view based on session state
    if st.session_state['wallet_view'] == 'grid':
        # Header section
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("Wallet Dashboard")
            st.write("Manage and monitor all your blockchain wallets in one place.")
        
        with col2:
            st.write("")  # Add some space
            if st.button("➕ Add New Wallet", use_container_width=True, key="add_new_wallet_header"):
                st.session_state['add_wallet_form_open'] = True
                st.rerun()
        
        # Show Add Wallet Form if the button was clicked
        if st.session_state.get('add_wallet_form_open', False):
            show_add_wallet_form()
        
        # Show wallet grid
        show_wallet_grid(wallets)
    
    elif st.session_state['wallet_view'] == 'detail':
        # Show wallet detail view for the selected wallet
        show_wallet_detail(st.session_state['selected_wallet_id'], wallets)