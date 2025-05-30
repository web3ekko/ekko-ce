import asyncio
import argparse
import json
import os
import sys
import uuid
from datetime import datetime
import getpass # For secure password input

import nats

# Adjust sys.path to allow imports from the 'app' directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR) # This will be 'api'
# APP_DIR = os.path.join(PARENT_DIR, 'app') # This would be api/app, not needed if PARENT_DIR is api/
sys.path.insert(0, PARENT_DIR) # Add api/ to path to find app.*

try:
    from app.auth import get_password_hash
    # Assuming UserInDB is the model used for storing in KV.
    # If not, this needs to be adjusted or a dict created manually.
    from app.models import UserInDB 
except ImportError as e:
    print(f"Error importing app modules: {e}")
    print("Please ensure this script is run from a location where 'app' module is discoverable,")
    print("or that PYTHONPATH includes the directory containing 'app'.")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)

DEFAULT_NATS_URL = "nats://localhost:4222"
USERS_KV_BUCKET = "users"

async def create_user_in_kv(email: str, password: str, full_name: str, role: str, nats_url: str):
    nc = None
    try:
        print(f"Connecting to NATS at {nats_url}...")
        nc = await nats.connect(nats_url)
        js = nc.jetstream()

        print(f"Accessing KV bucket: '{USERS_KV_BUCKET}'...")
        kv_store = await js.key_value(bucket=USERS_KV_BUCKET)

        # Optional: Check if user with this email already exists.
        # This is complex with current KV structure without iterating all keys.
        # For this script, we'll assume email uniqueness is handled by the admin or by API logic.
        # A more robust script might try a direct lookup by a predictable key if user IDs were email-derived,
        # or iterate keys (inefficient for large stores).

        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(password)
        created_at = datetime.now().isoformat()

        # Construct the user data. Ensure this matches the structure expected by your application
        # when reading from the KV store (e.g., matching UserInDB fields).
        user_data_dict = {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "role": role,
            "hashed_password": hashed_password,
            "is_active": True, # Default to active
            "created_at": created_at,
            "updated_at": None # No updates on creation
        }
        
        # If UserInDB can be instantiated directly and has a .model_dump_json() method (Pydantic v2)
        # user_pydantic_obj = UserInDB(**user_data_dict)
        # user_json = user_pydantic_obj.model_dump_json()
        
        # For simplicity and to avoid issues if UserInDB has complex validation not relevant here:
        user_json = json.dumps(user_data_dict)

        print(f"Creating user with ID: {user_id} for email: {email}...")
        # NATS KV store expects bytes for the value
        await kv_store.put(user_id.encode('utf-8'), user_json.encode('utf-8'))
        print(f"Successfully created user: {email} (ID: {user_id}) in bucket '{USERS_KV_BUCKET}'.")
        print(f"Key: {user_id}, Value: {user_json}")

    except nats.errors.NoServersError:
        print(f"Error: Could not connect to NATS server at {nats_url}. Ensure NATS is running.")
    except ImportError:
        # This might catch the initial import error if not caught earlier, though unlikely with current structure
        print("Failed to import necessary application modules. Ensure script is run correctly.")
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if nc:
            print("Closing NATS connection...")
            await nc.close()

def main():
    parser = argparse.ArgumentParser(description="Create a new user in the Ekko NATS KV store. \
                                                 Will prompt for missing details if not provided as arguments.")
    parser.add_argument("--email", help="Email address for the new user.")
    parser.add_argument("--password", help="Password for the new user. (Will be prompted if not set)")
    parser.add_argument("--full-name", help="Full name of the new user.")
    parser.add_argument("--role", help="Role for the new user (e.g., 'user', 'admin'). Default: 'user'.")
    parser.add_argument("--nats-url", default=os.getenv("NATS_URL", DEFAULT_NATS_URL),
                        help=f"NATS server URL. Defaults to NATS_URL env var or '{DEFAULT_NATS_URL}'.")

    args = parser.parse_args()

    email = args.email
    password = args.password
    full_name = args.full_name
    role = args.role

    if not email:
        email = input("Enter email for the new user: ").strip()
    if not password:
        password = getpass.getpass("Enter password for the new user: ")
    if not full_name:
        full_name = input("Enter full name for the new user: ").strip()
    if not role:
        role_input = input("Enter role for the new user (default: user): ").strip()
        role = role_input if role_input else "user"
    
    if not all([email, password, full_name, role]):
        print("Error: Email, password, full name, and role are required.")
        sys.exit(1)

    asyncio.run(create_user_in_kv(
        email=email,
        password=password,
        full_name=full_name,
        role=role,
        nats_url=args.nats_url
    ))

if __name__ == "__main__":
    main()
