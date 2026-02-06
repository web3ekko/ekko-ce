import base64
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.utils import timezone

from fido2 import cbor
from fido2.server import Fido2Server
from fido2.webauthn import (
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialCreationOptions,
    PublicKeyCredentialRequestOptions,
    AuthenticatorData,
    AttestedCredentialData,
    CollectedClientData,
    AttestationObject,
    AuthenticatorAssertionResponse,
    UserVerificationRequirement,
    AuthenticatorAttachment,
    ResidentKeyRequirement,
)
from fido2.utils import websafe_decode, websafe_encode

from .models import PasskeyDevice, PasskeyChallenge

logger = logging.getLogger(__name__)
User = get_user_model()


class WebAuthnService:
    """
    Service for handling WebAuthn operations using python-fido2.
    """
    
    def __init__(self):
        # Configure the Relying Party (RP)
        self.rp_id = getattr(settings, 'WEBAUTHN_RP_ID', 'localhost')
        self.rp_name = getattr(settings, 'WEBAUTHN_RP_NAME', 'Ekko Cluster')
        self.origin = getattr(settings, 'WEBAUTHN_ORIGIN', 'http://localhost:3000')
        
        # For mobile app support, allow multiple origins
        self.allowed_origins = getattr(settings, 'WEBAUTHN_ALLOWED_ORIGINS', [self.origin])
        
        # Initialize FIDO2 server
        self.rp = PublicKeyCredentialRpEntity(id=self.rp_id, name=self.rp_name)
        # For fido2 version 1.1.3, we need to pass origin verification callback
        # instead of allowed_origins parameter
        self.server = Fido2Server(
            self.rp,
            verify_origin=lambda origin: origin in self.allowed_origins
        )
        
        # Challenge settings
        self.challenge_timeout = getattr(settings, 'WEBAUTHN_CHALLENGE_TIMEOUT', 300)  # 5 minutes
    
    def _store_challenge(self, challenge: bytes, user: Optional[User] = None, 
                        operation: str = 'register', data: Optional[Dict] = None,
                        state: Optional[Dict] = None) -> str:
        """
        Store challenge in cache (preferred) or database.
        """
        challenge_b64 = websafe_encode(challenge)
        cache_key = f"webauthn:challenge:{challenge_b64}"
        
        challenge_data = {
            'challenge': challenge_b64,
            'user_id': user.id if user else None,
            'operation': operation,
            'data': data or {},
            'state': state,  # Store the complete state for register_complete
            'created_at': timezone.now().isoformat(),
        }
        
        # Try cache first
        try:
            cache.set(cache_key, challenge_data, timeout=self.challenge_timeout)
            logger.debug(f"Stored challenge in cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to store challenge in cache: {e}")
            # Fallback to database
            expires_at = timezone.now() + timedelta(seconds=self.challenge_timeout)
            PasskeyChallenge.objects.create(
                challenge=challenge_b64,
                user=user,
                operation=operation,
                data=data or {},
                expires_at=expires_at
            )
            logger.debug(f"Stored challenge in database: {challenge_b64}")
        
        return challenge_b64
    
    def _get_challenge(self, challenge_b64: str) -> Optional[Dict]:
        """
        Retrieve and validate challenge from cache or database.
        """
        cache_key = f"webauthn:challenge:{challenge_b64}"
        
        # Try cache first
        try:
            challenge_data = cache.get(cache_key)
            if challenge_data:
                logger.debug(f"Retrieved challenge from cache: {cache_key}")
                return challenge_data
        except Exception as e:
            logger.warning(f"Failed to retrieve challenge from cache: {e}")
        
        # Fallback to database
        try:
            challenge = PasskeyChallenge.objects.get(challenge=challenge_b64)
            if challenge.is_valid():
                logger.debug(f"Retrieved challenge from database: {challenge_b64}")
                return {
                    'challenge': challenge.challenge,
                    'user_id': challenge.user_id,
                    'operation': challenge.operation,
                    'data': challenge.data,
                    'created_at': challenge.created_at.isoformat(),
                }
            else:
                logger.warning(f"Challenge expired: {challenge_b64}")
                challenge.delete()
        except PasskeyChallenge.DoesNotExist:
            logger.warning(f"Challenge not found: {challenge_b64}")
        
        return None
    
    def _clear_challenge(self, challenge_b64: str):
        """
        Remove challenge from storage after use.
        """
        cache_key = f"webauthn:challenge:{challenge_b64}"
        
        # Clear from cache
        try:
            cache.delete(cache_key)
        except Exception as e:
            logger.warning(f"Failed to clear challenge from cache: {e}")
        
        # Clear from database
        PasskeyChallenge.objects.filter(challenge=challenge_b64).delete()
    
    def generate_registration_options(self, user: User, 
                                    platform_only: bool = False) -> Dict:
        """
        Generate WebAuthn registration options for creating a new passkey.
        """
        try:
            # Get existing credentials to exclude
            existing_credentials = []
            for device in user.passkey_devices.filter(is_active=True):
                existing_credentials.append(
                    PublicKeyCredentialDescriptor(
                        id=websafe_decode(device.credential_id),
                        type="public-key"
                    )
                )
            
            # Generate user entity
            logger.debug(f"Creating user entity for user: {user.email}, id: {user.id}")
            user_id_bytes = str(user.id).encode('utf-8')
            user_display_name = user.get_full_name() or user.email.split('@')[0]
            logger.debug(f"User ID bytes: {user_id_bytes}, display name: {user_display_name}")
            
            user_entity = PublicKeyCredentialUserEntity(
                id=user_id_bytes,
                name=user.email,
                display_name=user_display_name
            )
        except Exception as e:
            logger.error(f"Error creating user entity: {e}")
            raise
        
        # Generate registration options with minimal parameters
        # The python-fido2 library has changed its API
        try:
            logger.debug(f"Calling register_begin with user_entity: {user_entity}")
            logger.debug(f"Existing credentials count: {len(existing_credentials)}")
            
            # In python-fido2 1.1.3, register_begin returns options and state
            result = self.server.register_begin(
                user=user_entity,
                credentials=existing_credentials,
            )
            
            # Check what type of result we got
            logger.debug(f"register_begin result type: {type(result)}")
            logger.debug(f"register_begin result: {result}")
            
            # Handle the result based on what was returned
            if isinstance(result, tuple) and len(result) == 2:
                options, state = result
                logger.debug(f"Got tuple result - options: {options}, state: {state}")
            else:
                # Single result - likely just options
                options = result
                # Extract challenge from options for state
                state = {'challenge': options.public_key.challenge}
                logger.debug(f"Got single result - options: {options}")
                
        except Exception as e:
            logger.error(f"Error in register_begin: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
        # Store challenge
        try:
            logger.debug(f"State: {state}")
            logger.debug(f"State type: {type(state)}")
            
            # Get challenge - prefer bytes from options
            if hasattr(options, 'public_key') and hasattr(options.public_key, 'challenge'):
                # This should be bytes
                challenge = options.public_key.challenge
                logger.debug(f"Got challenge from options (bytes)")
            elif isinstance(state, dict) and 'challenge' in state:
                # This might be a base64url string, need to decode it
                challenge_str = state['challenge']
                if isinstance(challenge_str, str):
                    # It's already base64url encoded, we need the original bytes
                    # Actually, we should use the challenge from options which is bytes
                    challenge = options.public_key.challenge
                    logger.debug(f"State has string challenge, using bytes from options instead")
                else:
                    challenge = challenge_str
            else:
                raise ValueError(f"Could not find challenge in state or options. State: {state}, Options: {options}")
                
            logger.debug(f"Challenge type: {type(challenge)}, length: {len(challenge) if hasattr(challenge, '__len__') else 'N/A'}")
            
            # Store the complete state for later verification
            # The state should store the challenge as base64url string, not bytes
            if isinstance(state, dict):
                # Copy the state and ensure challenge is base64url encoded
                state_to_store = state.copy()
                if 'challenge' in state_to_store and isinstance(state_to_store['challenge'], bytes):
                    state_to_store['challenge'] = websafe_encode(state_to_store['challenge'])
            else:
                state_to_store = {'challenge': websafe_encode(challenge)}
            
            challenge_b64 = self._store_challenge(
                challenge,
                user=user,
                operation='register',
                data={'user_id': str(user.id)},
                state=state_to_store
            )
        except Exception as e:
            logger.error(f"Error storing challenge: {e}")
            logger.error(f"State was: {state}")
            raise
        
        # Convert to JSON-serializable format
        # The options object has public_key attribute with the actual options
        pk_options = options.public_key
        
        # Build the response
        response = {
            'publicKey': {
                'challenge': websafe_encode(pk_options.challenge),
                'rp': {
                    'id': pk_options.rp.id,
                    'name': pk_options.rp.name,
                },
                'user': {
                    'id': websafe_encode(pk_options.user.id),
                    'name': pk_options.user.name,
                    'displayName': pk_options.user.display_name,
                },
                'pubKeyCredParams': [
                    {'type': param.type, 'alg': param.alg}
                    for param in pk_options.pub_key_cred_params
                ],
                'excludeCredentials': [
                    {
                        'id': websafe_encode(cred.id),
                        'type': cred.type,
                    }
                    for cred in existing_credentials
                ],
                'attestation': 'none',
                'timeout': 60000,
            }
        }
        
        # Build authenticator selection
        authenticator_selection = {
            'residentKey': 'preferred',
            'userVerification': 'preferred'
        }
        
        # For Touch ID/Face ID, we need platform authenticator
        if platform_only:
            authenticator_selection['authenticatorAttachment'] = 'platform'
        
        response['publicKey']['authenticatorSelection'] = authenticator_selection
        
        return response
    
    def complete_registration(self, user: User, credential_data: Dict,
                            device_name: Optional[str] = None) -> PasskeyDevice:
        """
        Complete passkey registration and create device record.
        """
        try:
            # Extract credential components
            logger.debug(f"Parsing credential_data: {credential_data}")
            
            client_data_json = credential_data['response']['clientDataJSON']
            logger.debug(f"clientDataJSON type: {type(client_data_json)}, value: {client_data_json}")
            
            client_data = CollectedClientData(websafe_decode(client_data_json))
            logger.debug(f"Successfully parsed client_data")
            
            attestation_object = credential_data['response']['attestationObject']
            logger.debug(f"attestationObject type: {type(attestation_object)}, value: {attestation_object}")
            
            # Debug the decoded attestation object
            try:
                decoded_att_obj = websafe_decode(attestation_object)
                logger.debug(f"Decoded attestation object type: {type(decoded_att_obj)}, length: {len(decoded_att_obj)}")
                logger.debug(f"First 20 bytes: {decoded_att_obj[:20]}")
            except Exception as decode_e:
                logger.error(f"Error decoding attestation object: {decode_e}")
                raise
            
            att_obj = AttestationObject(decoded_att_obj)
            logger.debug(f"Successfully parsed attestation object")
        except Exception as e:
            logger.error(f"Error parsing credential data: {e}")
            logger.error(f"Credential data structure: {credential_data}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
        # Retrieve challenge
        try:
            challenge_b64 = json.loads(client_data.decode())['challenge']
            logger.debug(f"Challenge from client data: {challenge_b64}")
            challenge_data = self._get_challenge(challenge_b64)
            logger.debug(f"Retrieved challenge data: {challenge_data}")
            
            if not challenge_data:
                raise ValueError("Invalid or expired challenge")
            
            logger.debug(f"Challenge user_id: {challenge_data['user_id']}, type: {type(challenge_data['user_id'])}")
            logger.debug(f"Current user.id: {user.id}, type: {type(user.id)}")
            
            if str(challenge_data['user_id']) != str(user.id):
                raise ValueError("Challenge user mismatch")
        except Exception as e:
            logger.error(f"Error retrieving challenge: {e}")
            raise
        
        # Verify registration
        try:
            logger.debug(f"Challenge data: {challenge_data}")
            
            # Get the state that was stored during register_begin
            state = challenge_data.get('state')
            if not state:
                # Fallback to just challenge if state wasn't stored
                # The challenge should be base64url encoded string for fido2
                state = {'challenge': challenge_data['challenge']}
            # State should already have challenge as base64url string
            
            logger.debug(f"Using state for register_complete: {state}")
            
            try:
                auth_data = self.server.register_complete(
                    state,
                    client_data,
                    att_obj
                )
                logger.debug(f"Successfully completed registration")
            except Exception as inner_e:
                logger.error(f"Error in fido2 register_complete: {inner_e}")
                logger.error(f"State type: {type(state)}, State: {state}")
                logger.error(f"Client data type: {type(client_data)}")
                logger.error(f"Attestation object type: {type(att_obj)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
        except Exception as e:
            logger.error(f"Error in register_complete: {e}")
            logger.error(f"Challenge data was: {challenge_data}")
            raise
        
        # Clear used challenge
        self._clear_challenge(challenge_b64)
        
        # Extract credential data
        credential = auth_data.credential_data
        
        # Extract AAGUID
        aaguid = credential.aaguid.hex() if credential.aaguid else ''
        
        # Determine device name
        if not device_name:
            # Try to extract from attestation or use default
            device_name = self._get_device_name_from_aaguid(aaguid)
        
        # Debug public key type
        logger.debug(f"Credential public_key type: {type(credential.public_key)}")
        logger.debug(f"Credential public_key: {credential.public_key}")
        
        # The public key is already in bytes format from fido2
        # If it's not bytes, it's likely a COSE key object
        if isinstance(credential.public_key, bytes):
            public_key_bytes = credential.public_key
        else:
            # It's a COSE key object (like ES256), encode it properly
            # COSE keys in fido2 library can be encoded with cbor
            public_key_bytes = cbor.encode(credential.public_key)
        
        # Create device record
        device = PasskeyDevice.objects.create(
            user=user,
            credential_id=websafe_encode(credential.credential_id),
            public_key=websafe_encode(public_key_bytes),
            name=device_name,
            aaguid=aaguid,
            sign_count=auth_data.counter,
            backup_eligible=getattr(auth_data, 'backup_eligible', False),
            backup_state=getattr(auth_data, 'backup_state', False),
        )
        
        logger.info(f"Registered new passkey device for user {user.email}: {device.id}")
        return device
    
    def generate_authentication_options(self, user: Optional[User] = None,
                                      passwordless: bool = False) -> Dict:
        """
        Generate WebAuthn authentication options.
        """
        # Get allowed credentials
        allowed_credentials = []
        
        if user:
            # User-specific authentication
            for device in user.passkey_devices.filter(is_active=True):
                allowed_credentials.append(
                    PublicKeyCredentialDescriptor(
                        id=websafe_decode(device.credential_id),
                        type="public-key"
                    )
                )
        elif not passwordless:
            # If not passwordless and no user, we can't proceed
            raise ValueError("User required for non-passwordless authentication")
        
        # For passwordless, allowed_credentials is empty to show all available
        
        # Generate authentication options
        options, state = self.server.authenticate_begin(
            credentials=allowed_credentials if not passwordless else None,
            user_verification=UserVerificationRequirement.PREFERRED,
        )
        
        # Store challenge
        challenge_b64 = self._store_challenge(
            state['challenge'],
            user=user,
            operation='authenticate',
            data={'passwordless': passwordless}
        )
        
        # Convert to JSON-serializable format
        response = {
            'publicKey': {
                'challenge': websafe_encode(options.challenge),
                'rpId': options.rp_id,
                'userVerification': options.user_verification,
                'timeout': 60000,
            },
            'passwordless': passwordless,
        }
        
        # Only include allowCredentials if not passwordless
        if not passwordless and allowed_credentials:
            response['publicKey']['allowCredentials'] = [
                {
                    'id': websafe_encode(cred.id),
                    'type': cred.type,
                }
                for cred in allowed_credentials
            ]
        
        return response
    
    def complete_authentication(self, credential_data: Dict,
                              user: Optional[User] = None) -> Tuple[User, PasskeyDevice]:
        """
        Complete authentication and return authenticated user and device.
        """
        # Parse credential data
        credential_id = websafe_decode(credential_data['id'])
        client_data = CollectedClientData(websafe_decode(credential_data['response']['clientDataJSON']))
        auth_data = AuthenticatorData(websafe_decode(credential_data['response']['authenticatorData']))
        signature = websafe_decode(credential_data['response']['signature'])
        
        # Extract user handle for passwordless flow
        user_handle = credential_data['response'].get('userHandle')
        if user_handle:
            user_handle = websafe_decode(user_handle)
        
        # Retrieve challenge
        challenge_b64 = json.loads(client_data.decode())['challenge']
        challenge_data = self._get_challenge(challenge_b64)
        
        if not challenge_data:
            raise ValueError("Invalid or expired challenge")
        
        # Find device and user
        try:
            device = PasskeyDevice.objects.get(
                credential_id=websafe_encode(credential_id),
                is_active=True
            )
        except PasskeyDevice.DoesNotExist:
            raise ValueError("Unknown credential")
        
        # Verify user consistency
        if challenge_data['data'].get('passwordless'):
            # Passwordless flow - get user from device or user handle
            if user_handle:
                # Prefer user handle
                auth_user = User.objects.get(id=user_handle.decode('utf-8'))
                if auth_user != device.user:
                    raise ValueError("User handle mismatch")
            else:
                auth_user = device.user
        else:
            # Email-based flow - verify against provided user
            if not user or user != device.user:
                raise ValueError("User mismatch")
            auth_user = user
        
        # Get public key credential
        public_key = websafe_decode(device.public_key)
        
        # Verify authentication
        self.server.authenticate_complete(
            {'challenge': websafe_decode(challenge_data['challenge'])},
            [public_key],
            credential_id,
            client_data,
            auth_data,
            signature
        )
        
        # Clear used challenge
        self._clear_challenge(challenge_b64)
        
        # Update device usage
        device.update_usage(auth_data.counter)
        
        logger.info(f"Successful authentication for user {auth_user.email} with device {device.id}")
        return auth_user, device
    
    def _get_device_name_from_aaguid(self, aaguid: str) -> str:
        """
        Get a friendly device name from AAGUID.
        This could be expanded with a proper AAGUID database.
        """
        # Common AAGUIDs (simplified)
        known_devices = {
            '00000000-0000-0000-0000-000000000000': 'Security Key',
            # Add more known AAGUIDs here
        }
        
        return known_devices.get(aaguid, 'Passkey Device')