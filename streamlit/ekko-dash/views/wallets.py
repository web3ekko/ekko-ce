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
        
        dummy_wallets.append({
            'id': i + 1,
            'blockchain_symbol': blockchain_symbol,
            'blockchain_name': {"ETH": "Ethereum", "AVAX": "Avalanche", "MATIC": "Polygon", "BTC": "Bitcoin"}[blockchain_symbol],
            'address': addresses[i % len(addresses)],
            'name': f"{wallet_names[i % len(wallet_names)]} {i+1}",
            'balance': balance,
            'created_at': now - datetime.timedelta(days=random.randint(60, 120)),
            'updated_at': last_activity,
            'status': "active" if days_ago < 30 else "inactive",
            'transactions': transactions
        })
    
    return dummy_wallets

# Add common CSS for wallet pages
def add_wallet_css():
    st.markdown("""
    <style>
        .wallet-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1rem;
            margin-top: 1.5rem;
        }
        
        .wallet-card {
            background-color: white;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            padding: 1.25rem;
            transition: all 0.3s ease;
            border: 1px solid #f0f0f0;
            position: relative;
            overflow: hidden;
            cursor: pointer;
        }
        
        .wallet-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
        }
        
        .wallet-header {
            display: flex;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .wallet-logo {
            width: 40px;
            height: 40px;
            margin-right: 12px;
            border-radius: 8px;
            padding: 6px;
            background-color: #f8f9fa;
        }
        
        .wallet-name {
            font-size: 1.1rem;
            font-weight: 600;
            color: #333;
            flex-grow: 1;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .wallet-status {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-left: 8px;
        }
        
        .status-active {
            background-color: #10b981;
            box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
        }
        
        .status-inactive {
            background-color: #9ca3af;
            box-shadow: 0 0 0 3px rgba(156, 163, 175, 0.2);
        }
        
        .wallet-address {
            background-color: #f8f9fa;
            padding: 0.5rem 0.75rem;
            border-radius: 8px;
            font-family: monospace;
            font-size: 0.9rem;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .wallet-copy {
            cursor: pointer;
            color: #6b7280;
            transition: color 0.2s ease;
        }
        
        .wallet-copy:hover {
            color: #4b5563;
        }
        
        .wallet-balance {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
            color: #1f2937;
        }
        
        .wallet-blockchain {
            color: #6b7280;
            font-size: 0.875rem;
            margin-bottom: 1rem;
        }
        
        .wallet-activity {
            font-size: 0.875rem;
            color: #6b7280;
            margin-bottom: 1.25rem;
        }
        
        .wallet-actions {
            display: flex;
            justify-content: flex-end;
        }
        
        .action-button {
            background-color: #f3f4f6;
            color: #374151;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .action-button:hover {
            background-color: #e5e7eb;
        }
        
        .action-button.primary {
            background-color: #eff6ff;
            color: #1e40af;
        }
        
        .action-button.primary:hover {
            background-color: #dbeafe;
        }
        
        .add-wallet-card {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background-color: #f9fafb;
            border: 2px dashed #e5e7eb;
            border-radius: 12px;
            padding: 2rem 1.5rem;
            cursor: pointer;
            transition: all 0.3s ease;
            height: 100%;
        }
        
        .add-wallet-card:hover {
            background-color: #f3f4f6;
            border-color: #d1d5db;
        }
        
        .add-icon {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background-color: #e5e7eb;
            color: #6b7280;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 1rem;
            font-size: 1.5rem;
        }
        
        .add-wallet-text {
            font-weight: 500;
            color: #6b7280;
        }
        
        /* Wallet detail styles */
        .wallet-detail-header {
            display: flex;
            align-items: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #f0f0f0;
        }
        
        .wallet-detail-back {
            margin-right: 1rem;
            padding: 0.5rem;
            background-color: #f3f4f6;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .wallet-detail-back:hover {
            background-color: #e5e7eb;
        }
        
        .wallet-detail-info {
            flex-grow: 1;
        }
        
        .wallet-detail-name {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
        }
        
        .wallet-detail-address {
            font-family: monospace;
            color: #6b7280;
            background-color: #f8f9fa;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.875rem;
            display: inline-flex;
            align-items: center;
        }
        
        .wallet-detail-balance {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background-color: white;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .balance-amount {
            font-size: 2.5rem;
            font-weight: 700;
            color: #1f2937;
        }
        
        .balance-token {
            color: #6b7280;
            font-size: 1rem;
            margin-left: 0.5rem;
        }
        
        .wallet-detail-actions {
            display: flex;
            gap: 0.75rem;
        }
        
        .wallet-tabs {
            margin-bottom: 2rem;
        }
        
        .transaction-list {
            background-color: white;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            overflow: hidden;
        }
        
        .transaction-item {
            display: flex;
            align-items: center;
            padding: 1rem 1.5rem;
            border-bottom: 1px solid #f3f4f6;
            transition: background-color 0.2s ease;
        }
        
        .transaction-item:hover {
            background-color: #f9fafb;
        }
        
        .transaction-icon {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background-color: #f3f4f6;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 1rem;
        }
        
        .transaction-send {
            color: #ef4444;
        }
        
        .transaction-receive {
            color: #10b981;
        }
        
        .transaction-swap {
            color: #6366f1;
        }
        
        .transaction-stake {
            color: #f59e0b;
        }
        
        .transaction-info {
            flex-grow: 1;
        }
        
        .transaction-type {
            font-weight: 600;
            color: #1f2937;
            margin-bottom: 0.25rem;
        }
        
        .transaction-date {
            font-size: 0.875rem;
            color: #6b7280;
        }
        
        .transaction-amount {
            text-align: right;
        }
        
        .transaction-value {
            font-weight: 600;
            color: #1f2937;
            margin-bottom: 0.25rem;
        }
        
        .transaction-fee {
            font-size: 0.75rem;
            color: #9ca3af;
        }
        
        .transaction-status {
            padding: 0.25rem 0.5rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
            margin-left: 1rem;
        }
        
        .status-confirmed {
            background-color: #ecfdf5;
            color: #10b981;
        }
        
        .status-pending {
            background-color: #fffbeb;
            color: #f59e0b;
        }
        
        .status-failed {
            background-color: #fef2f2;
            color: #ef4444;
        }
        
        .empty-state {
            text-align: center;
            padding: 4rem 2rem;
            color: #6b7280;
        }
        
        .empty-state-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
            color: #d1d5db;
        }
        
        .empty-state-message {
            font-size: 1.1rem;
            font-weight: 500;
            margin-bottom: 0.5rem;
        }
        
        .empty-state-suggestion {
            font-size: 0.9rem;
        }
    </style>
    """, unsafe_allow_html=True)

# Display wallet overview (grid view)
def show_wallet_overview(wallets):
    st.markdown('<div class="wallet-grid">', unsafe_allow_html=True)
    
    # Loop through each wallet and create a card
    for wallet in wallets:
        blockchain_logo = get_blockchain_logo(wallet['blockchain_symbol'])
        truncated_addr = truncate_address(wallet['address'])
        time_ago = get_time_ago(wallet['updated_at'])
        status_class = "status-active" if wallet['status'] == "active" else "status-inactive"
        
        # Create a clickable wallet card
        wallet_card = f"""
            <div class="wallet-card" onclick="
                // Use a workaround to send the wallet ID to Streamlit
                // We'll create a hidden button with the wallet ID and click it
                document.getElementById('select-wallet-{wallet['id']}').click()
            ">
                <div class="wallet-header">
                    <div class="wallet-logo">
                        <img src="data:image/svg+xml;base64,{blockchain_logo}" width="28" height="28">
                    </div>
                    <div class="wallet-name">{wallet['name']}</div>
                    <div class="wallet-status {status_class}" title="{wallet['status'].capitalize()}"></div>
                </div>
                
                <div class="wallet-address">
                    <span>{truncated_addr}</span>
                    <span class="wallet-copy" title="Copy to clipboard">📋</span>
                </div>
                
                <div class="wallet-balance">{wallet['balance']} {wallet['blockchain_symbol']}</div>
                <div class="wallet-blockchain">{wallet['blockchain_name']} Network</div>
                
                <div class="wallet-activity">Last activity: {time_ago}</div>
                
                <div class="wallet-actions">
                    <button class="action-button primary">
                        <span>View Details</span>
                        <span>→</span>
                    </button>
                </div>
            </div>
        """
        
        st.markdown(wallet_card, unsafe_allow_html=True)
        
        # Hidden button to capture the click event
        if st.button("Select", key=f"select-wallet-{wallet['id']}", help=f"View details for {wallet['name']}", 
                    type="secondary", use_container_width=True):
            st.session_state['wallet_view'] = 'detail'
            st.session_state['selected_wallet_id'] = wallet['id']
            st.rerun()
            
        # Hide the button with CSS (we'll use JavaScript to click it)
        st.markdown(f"""
            <style>
                div[data-testid="stButton"] button[kind="secondary"][aria-describedby*="View details for {wallet['name']}"] {{
                    display: none;
                }}
            </style>
        """, unsafe_allow_html=True)
    
    # Add the "Add Wallet" card at the end
    st.markdown(f"""
        <div class="add-wallet-card" onclick="document.querySelector('button[aria-label=\"Add New Wallet\"]').click()">
            <div class="add-icon">+</div>
            <div class="add-wallet-text">Add New Wallet</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Close the grid container
    st.markdown('</div>', unsafe_allow_html=True)

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
    
    # Wallet header with name, address, and logo
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown(f"""
            <div class="wallet-detail-header">
                <div class="wallet-logo" style="width: 48px; height: 48px;">
                    <img src="data:image/svg+xml;base64,{blockchain_logo}" width="36" height="36">
                </div>
                <div class="wallet-detail-info">
                    <div class="wallet-detail-name">{wallet['name']}</div>
                    <div class="wallet-detail-address">
                        {wallet['address']}
                        <span class="wallet-copy" style="margin-left: 8px;" title="Copy to clipboard">📋</span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    # Wallet balance card
    st.markdown(f"""
        <div class="wallet-detail-balance">
            <div>
                <div style="color: #6b7280; font-size: 0.875rem; margin-bottom: 0.5rem;">Current Balance</div>
                <div>
                    <span class="balance-amount">{wallet['balance']}</span>
                    <span class="balance-token">{wallet['blockchain_symbol']}</span>
                </div>
            </div>
            <div class="wallet-detail-actions">
                <button class="action-button">
                    <span>Send</span>
                </button>
                <button class="action-button">
                    <span>Receive</span>
                </button>
                <button class="action-button">
                    <span>Swap</span>
                </button>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Transactions and other tabs
    tab1, tab2, tab3 = st.tabs(["Transactions", "Assets", "Analytics"])
    
    with tab1:
        # Transactions list
        if wallet.get('transactions'):
            st.markdown('<div class="transaction-list">', unsafe_allow_html=True)
            
            for tx in wallet['transactions']:
                # Set icon class based on transaction type
                icon_class = ""
                if tx['type'] == "Send":
                    icon_class = "transaction-send"
                elif tx['type'] == "Receive":
                    icon_class = "transaction-receive"
                elif tx['type'] == "Swap":
                    icon_class = "transaction-swap"
                elif tx['type'] in ["Stake", "Unstake"]:
                    icon_class = "transaction-stake"
                
                # Format date
                date_str = tx['timestamp'].strftime("%b %d, %Y at %H:%M")
                
                # Set status class
                status_class = ""
                if tx['status'] == "Confirmed":
                    status_class = "status-confirmed"
                elif tx['status'] == "Pending":
                    status_class = "status-pending"
                elif tx['status'] == "Failed":
                    status_class = "status-failed"
                
                # Display transaction item
                st.markdown(f"""
                    <div class="transaction-item">
                        <div class="transaction-icon {icon_class}">
                            {'↑' if tx['type'] == 'Send' else '↓' if tx['type'] == 'Receive' else '⇄' if tx['type'] == 'Swap' else '★'}
                        </div>
                        <div class="transaction-info">
                            <div class="transaction-type">{tx['type']}</div>
                            <div class="transaction-date">{date_str}</div>
                        </div>
                        <div class="transaction-amount">
                            <div class="transaction-value">
                                {'-' if tx['type'] == 'Send' else '+' if tx['type'] == 'Receive' else '↔'}
                                {tx['amount']} {wallet['blockchain_symbol']}
                            </div>
                            <div class="transaction-fee">Fee: {tx['fee']} {wallet['blockchain_symbol']}</div>
                        </div>
                        <div class="transaction-status {status_class}">
                            {tx['status']}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            # Empty state
            st.markdown("""
                <div class="empty-state">
                    <div class="empty-state-icon">📃</div>
                    <div class="empty-state-message">No transactions yet</div>
                    <div class="empty-state-suggestion">Transactions will appear here once you start using this wallet.</div>
                </div>
            """, unsafe_allow_html=True)
    
    with tab2:
        # Assets tab (placeholder)
        st.info("Assets feature coming soon")
    
    with tab3:
        # Analytics tab (placeholder)
        st.info("Analytics feature coming soon")

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

# Main wallet display function
def show_wallets(blockchain_symbol):
    # Initialize session state for wallet navigation
    if 'wallet_view' not in st.session_state:
        st.session_state['wallet_view'] = 'grid'
    if 'selected_wallet_id' not in st.session_state:
        st.session_state['selected_wallet_id'] = None
    if 'add_wallet_form_open' not in st.session_state:
        st.session_state['add_wallet_form_open'] = False
    
    # Add common CSS styles
    add_wallet_css()
    
    # Page title based on current view
    if st.session_state['wallet_view'] == 'grid':
        st.markdown('<h1 class="page-header">Wallets</h1>', unsafe_allow_html=True)
    else:
        st.markdown('<h1 class="page-header">Wallet Details</h1>', unsafe_allow_html=True)
    
    # Fetch wallets from database
    fetched_wallets = wallet_model.get_all()
    
    # Format the fetched wallets
    wallets = []
    if fetched_wallets:
        for wallet in fetched_wallets:
            wallets.append({
                'id': wallet[0],
                'blockchain_symbol': wallet[1],
                'blockchain_name': wallet[7],  # From the JOIN with blockchain table
                'address': wallet[2],
                'name': wallet[3] or f"Wallet {wallet[0]}",
                'balance': wallet[4] or 0,
                'created_at': wallet[5],
                'updated_at': wallet[6],
                'status': "active" if (wallet[6] and (datetime.datetime.now() - wallet[6]).days < 30) else "inactive"
            })
    
    # If fewer than 9 wallets, add dummy wallets to fill the grid
    if len(wallets) < 9:
        # Calculate how many dummy wallets we need
        needed_dummy_count = 9 - len(wallets)
        # Generate dummy wallets with high IDs to avoid conflicts with real ones
        dummy_wallets = generate_dummy_wallets(count=needed_dummy_count)
        starting_id = 10000  # High starting ID to avoid conflicts
        
        for i, dummy_wallet in enumerate(dummy_wallets):
            dummy_wallet['id'] = starting_id + i
            wallets.append(dummy_wallet)
    
    # Show appropriate view based on session state
    if st.session_state['wallet_view'] == 'grid':
        # Add New Wallet Button (only in grid view)
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("Wallet Dashboard")
            st.write("Manage and monitor all your blockchain wallets in one place.")
        
        with col2:
            st.write("")  # Add some space
            st.write("")  # Add more space to align the button
            if st.button("➕ Add New Wallet", use_container_width=True, key="add_new_wallet", 
                        help="Connect a new wallet"):
                st.session_state['add_wallet_form_open'] = True
                st.rerun()
        
        # Show Add Wallet Form if the button was clicked
        if st.session_state.get('add_wallet_form_open', False):
            show_add_wallet_form()
        
        # Show wallet grid with all wallets
        show_wallet_overview(wallets)
    
    elif st.session_state['wallet_view'] == 'detail':
        # Show wallet detail view for the selected wallet
        show_wallet_detail(st.session_state['selected_wallet_id'], wallets)