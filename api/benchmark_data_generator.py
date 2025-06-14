#!/usr/bin/env python3
"""
Generate test transaction data and write to MinIO for DuckDB benchmarking.
"""

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timedelta
import random
import string
import boto3
from botocore.client import Config
import os

def generate_random_hash(length=64):
    """Generate a random transaction hash."""
    return '0x' + ''.join(random.choices(string.hexdigits.lower(), k=length-2))

def generate_random_address():
    """Generate a random Ethereum-style address."""
    return '0x' + ''.join(random.choices(string.hexdigits.lower(), k=40))

def generate_test_transactions(num_transactions=1000):
    """Generate test transaction data."""
    networks = ['avalanche', 'ethereum', 'polygon']
    subnets = ['mainnet', 'fuji', 'testnet']
    token_symbols = ['AVAX', 'ETH', 'MATIC', 'USDC', 'USDT']
    tx_types = ['send', 'receive', 'swap', 'stake']
    
    transactions = []
    base_time = datetime.now() - timedelta(days=30)
    
    for i in range(num_transactions):
        network = random.choice(networks)
        subnet = random.choice(subnets)
        
        # Adjust token symbol based on network
        if network == 'avalanche':
            token_symbol = 'AVAX' if random.random() < 0.7 else random.choice(['USDC', 'USDT'])
        elif network == 'ethereum':
            token_symbol = 'ETH' if random.random() < 0.7 else random.choice(['USDC', 'USDT'])
        else:  # polygon
            token_symbol = 'MATIC' if random.random() < 0.7 else random.choice(['USDC', 'USDT'])
        
        tx = {
            'hash': generate_random_hash(),
            'from_address': generate_random_address(),
            'to_address': generate_random_address(),
            'value': str(random.randint(1000000000000000, 10000000000000000000)),  # 0.001 to 10 tokens
            'gas': str(random.randint(21000, 500000)),
            'gas_price': str(random.randint(10000000000, 100000000000)),  # 10-100 gwei
            'nonce': str(random.randint(1, 10000)),
            'input': '0x' if random.random() < 0.7 else '0x' + ''.join(random.choices(string.hexdigits.lower(), k=random.randint(8, 200))),
            'block_number': 1000000 + i + random.randint(0, 1000),
            'block_hash': generate_random_hash(),
            'transaction_index': random.randint(0, 200),
            'timestamp': (base_time + timedelta(minutes=i*5 + random.randint(0, 300))).strftime('%Y-%m-%d %H:%M:%S'),
            'network': network,
            'subnet': subnet,
            'status': 'confirmed' if random.random() < 0.95 else 'failed',
            'token_symbol': token_symbol,
            'transaction_type': random.choice(tx_types)
        }
        transactions.append(tx)
    
    return pd.DataFrame(transactions)

def upload_to_minio(df, bucket_name='blockchain-events', network='avalanche', subnet='mainnet'):
    """Upload DataFrame as parquet to MinIO."""
    
    # Configure MinIO client
    s3_client = boto3.client(
        's3',
        endpoint_url='http://minio:9000',
        aws_access_key_id='minioadmin',
        aws_secret_access_key='minioadmin',
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    # Create bucket if it doesn't exist
    try:
        s3_client.create_bucket(Bucket=bucket_name)
        print(f"✅ Created bucket: {bucket_name}")
    except Exception as e:
        if 'BucketAlreadyOwnedByYou' in str(e):
            print(f"✅ Bucket already exists: {bucket_name}")
        else:
            print(f"❌ Error creating bucket: {e}")
            return False
    
    # Convert to Arrow Table
    table = pa.Table.from_pandas(df)
    
    # Write to parquet buffer
    import io
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    buffer.seek(0)
    
    # Upload to MinIO
    key = f"transactions/{network}/{subnet}/transactions.parquet"
    try:
        s3_client.upload_fileobj(buffer, bucket_name, key)
        print(f"✅ Uploaded {len(df)} transactions to s3://{bucket_name}/{key}")
        return True
    except Exception as e:
        print(f"❌ Error uploading to MinIO: {e}")
        return False

def main():
    """Generate and upload test data for different networks."""
    
    # Generate data for different networks
    networks_data = [
        ('avalanche', 'mainnet', 2000),
        ('avalanche', 'fuji', 500),
        ('ethereum', 'mainnet', 1500),
        ('polygon', 'mainnet', 1000),
    ]
    
    total_transactions = 0
    
    for network, subnet, count in networks_data:
        print(f"\n📊 Generating {count} transactions for {network}/{subnet}...")
        df = generate_test_transactions(count)
        
        # Filter to only this network/subnet
        df = df[(df['network'] == network) & (df['subnet'] == subnet)]
        
        if upload_to_minio(df, network=network, subnet=subnet):
            total_transactions += len(df)
            print(f"✅ Successfully uploaded {len(df)} transactions")
        else:
            print(f"❌ Failed to upload {network}/{subnet} data")
    
    print(f"\n🎉 Total transactions uploaded: {total_transactions}")
    print(f"📁 Data structure in MinIO:")
    print(f"   s3://blockchain-events/transactions/avalanche/mainnet/transactions.parquet")
    print(f"   s3://blockchain-events/transactions/avalanche/fuji/transactions.parquet")
    print(f"   s3://blockchain-events/transactions/ethereum/mainnet/transactions.parquet")
    print(f"   s3://blockchain-events/transactions/polygon/mainnet/transactions.parquet")

if __name__ == "__main__":
    main()
