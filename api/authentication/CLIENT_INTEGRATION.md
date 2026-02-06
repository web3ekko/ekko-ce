# Client Integration Guide
## Passwordless Authentication with Passkeys → Email Magic Links → Optional TOTP

This guide provides complete integration instructions for **Web**, **iOS**, and **Android** clients to implement the passwordless authentication flow with the Ekko Django API.

## 🔑 Authentication Flow Overview

```
Signup:  Email → Passkey Creation → Email Verification → Optional TOTP → Complete
Login:   Passkey → Success (or Email Magic Link fallback) → Optional TOTP → Complete
Recovery: "Lost Passkey" → Email Magic Link → Force New Passkey → Complete
```

## 📋 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/signup/begin/` | POST | Start passwordless signup |
| `/api/auth/signup/complete/` | POST | Complete signup after email verification |
| `/api/auth/login/` | POST | Passwordless login |
| `/api/auth/login/magic-link/` | POST | Verify magic link |
| `/api/auth/recovery/` | POST | Account recovery |
| `/api/auth/logout/` | POST | User logout |

## 🌐 Web Client Integration

### Prerequisites
```bash
npm install @simplewebauthn/browser
```

### 1. Device Capability Detection
```javascript
// utils/deviceCapabilities.js
export async function getDeviceCapabilities() {
    const capabilities = {
        webauthn_supported: false,
        biometric_supported: false,
        user_agent: navigator.userAgent,
        device_type: 'web'
    };

    // Check WebAuthn support
    if (window.PublicKeyCredential) {
        try {
            capabilities.webauthn_supported = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
        } catch (error) {
            console.warn('WebAuthn check failed:', error);
        }
    }

    return capabilities;
}
```

### 2. Signup Implementation
```javascript
// auth/signup.js
import { startRegistration } from '@simplewebauthn/browser';

export class PasswordlessSignup {
    constructor(apiBaseUrl) {
        this.apiBaseUrl = apiBaseUrl;
    }

    async beginSignup(email) {
        const deviceInfo = await getDeviceCapabilities();
        
        const response = await fetch(`${this.apiBaseUrl}/api/auth/signup/begin/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, device_info: deviceInfo })
        });

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Signup failed');
        }

        return data;
    }

    async createPasskey(email, firstName, lastName) {
        try {
            // Get WebAuthn options from Django
            const optionsResponse = await fetch(`${this.apiBaseUrl}/accounts/webauthn/signup/begin/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });

            const options = await optionsResponse.json();

            // Create passkey using SimpleWebAuthn
            const credential = await startRegistration(options);

            // Complete signup with Django
            const completeResponse = await fetch(`${this.apiBaseUrl}/api/auth/signup/complete/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    token: 'email-verification-token', // From email
                    first_name: firstName,
                    last_name: lastName,
                    credential_data: credential,
                    device_info: await getDeviceCapabilities()
                })
            });

            return await completeResponse.json();

        } catch (error) {
            console.error('Passkey creation failed:', error);
            throw error;
        }
    }

    async handleMagicLink(token) {
        const response = await fetch(`${this.apiBaseUrl}/api/auth/login/magic-link/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                token,
                device_info: await getDeviceCapabilities()
            })
        });

        return await response.json();
    }
}
```

### 3. Login Implementation
```javascript
// auth/login.js
import { startAuthentication } from '@simplewebauthn/browser';

export class PasswordlessLogin {
    constructor(apiBaseUrl) {
        this.apiBaseUrl = apiBaseUrl;
    }

    async login(email) {
        const deviceInfo = await getDeviceCapabilities();

        // Check available auth methods
        const response = await fetch(`${this.apiBaseUrl}/api/auth/login/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                email, 
                auth_method: 'auto',
                device_info: deviceInfo 
            })
        });

        const data = await response.json();

        // If passkey is available and supported
        if (data.available_methods?.some(m => m.method === 'passkey') && deviceInfo.webauthn_supported) {
            return await this.authenticateWithPasskey(email);
        } else {
            // Fallback to magic link
            return data; // Magic link already sent
        }
    }

    async authenticateWithPasskey(email) {
        try {
            // Get WebAuthn options
            const optionsResponse = await fetch(`${this.apiBaseUrl}/accounts/webauthn/login/begin/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });

            const options = await optionsResponse.json();

            // Authenticate with passkey
            const credential = await startAuthentication(options);

            // Complete authentication
            const authResponse = await fetch(`${this.apiBaseUrl}/accounts/webauthn/login/complete/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ credential })
            });

            return await authResponse.json();

        } catch (error) {
            console.error('Passkey authentication failed:', error);
            // Fallback to magic link
            return await this.requestMagicLink(email);
        }
    }

    async requestMagicLink(email) {
        const response = await fetch(`${this.apiBaseUrl}/api/auth/login/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                email, 
                auth_method: 'email_magic_link',
                device_info: await getDeviceCapabilities()
            })
        });

        return await response.json();
    }
}
```

### 4. React Component Example
```jsx
// components/PasswordlessAuth.jsx
import React, { useState } from 'react';
import { PasswordlessSignup, PasswordlessLogin } from '../auth';

export function PasswordlessAuth() {
    const [email, setEmail] = useState('');
    const [isSignup, setIsSignup] = useState(false);
    const [status, setStatus] = useState('');

    const signup = new PasswordlessSignup(process.env.REACT_APP_API_URL);
    const login = new PasswordlessLogin(process.env.REACT_APP_API_URL);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setStatus('Processing...');

        try {
            if (isSignup) {
                const result = await signup.beginSignup(email);
                setStatus(result.message);
            } else {
                const result = await login.login(email);
                if (result.method === 'email_magic_link') {
                    setStatus('Check your email for a sign-in link');
                } else {
                    setStatus('Signed in successfully!');
                }
            }
        } catch (error) {
            setStatus(`Error: ${error.message}`);
        }
    };

    return (
        <form onSubmit={handleSubmit}>
            <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Work email (serves as your backup sign-in)"
                required
            />
            <button type="submit">
                {isSignup ? 'Sign Up' : 'Sign In'}
            </button>
            <button type="button" onClick={() => setIsSignup(!isSignup)}>
                {isSignup ? 'Already have an account?' : 'Need an account?'}
            </button>
            {status && <p>{status}</p>}
        </form>
    );
}
```

## 📱 iOS Client Integration

### Prerequisites
```swift
// Add to your iOS project
import AuthenticationServices
import CryptoKit
```

### 1. Device Capabilities
```swift
// Utils/DeviceCapabilities.swift
import AuthenticationServices

struct DeviceCapabilities {
    let webauthnSupported: Bool
    let biometricSupported: Bool
    let userAgent: String
    let deviceType: String
    
    static func detect() async -> DeviceCapabilities {
        var webauthnSupported = false
        
        if #available(iOS 15.0, *) {
            // Check if platform authenticator is available
            let provider = ASAuthorizationPlatformPublicKeyCredentialProvider(relyingPartyIdentifier: "your-domain.com")
            webauthnSupported = true // Platform authenticator is available on iOS 15+
        }
        
        let biometricSupported = await checkBiometricAvailability()
        
        return DeviceCapabilities(
            webauthnSupported: webauthnSupported,
            biometricSupported: biometricSupported,
            userAgent: "EkkoApp/1.0 iOS",
            deviceType: "ios"
        )
    }
    
    private static func checkBiometricAvailability() async -> Bool {
        // Check for Face ID/Touch ID availability
        let context = LAContext()
        var error: NSError?
        return context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
    }
}
```

### 2. iOS Authentication Manager
```swift
// Auth/PasswordlessAuthManager.swift
import AuthenticationServices
import Foundation

@MainActor
class PasswordlessAuthManager: NSObject, ObservableObject {
    @Published var isAuthenticated = false
    @Published var user: User?
    @Published var authStatus = ""

    private let apiBaseURL = "https://your-api-domain.com"

    func signUp(email: String, firstName: String, lastName: String) async {
        do {
            authStatus = "Starting signup..."

            // 1. Begin signup
            let deviceCapabilities = await DeviceCapabilities.detect()
            let beginResult = await beginSignup(email: email, deviceInfo: deviceCapabilities)

            authStatus = beginResult.message

            // 2. Create passkey if supported
            if deviceCapabilities.webauthnSupported {
                await createPasskey(email: email, firstName: firstName, lastName: lastName)
            } else {
                authStatus = "Check your email to complete signup"
            }

        } catch {
            authStatus = "Signup failed: \(error.localizedDescription)"
        }
    }

    func signIn(email: String) async {
        do {
            authStatus = "Signing in..."

            let deviceCapabilities = await DeviceCapabilities.detect()

            // Try passkey first if available
            if deviceCapabilities.webauthnSupported {
                await authenticateWithPasskey(email: email)
            } else {
                await requestMagicLink(email: email)
            }

        } catch {
            authStatus = "Sign in failed: \(error.localizedDescription)"
        }
    }

    private func createPasskey(email: String, firstName: String, lastName: String) async {
        guard #available(iOS 15.0, *) else {
            authStatus = "Passkeys require iOS 15+"
            return
        }

        do {
            // Get WebAuthn options from Django
            let options = await getPasskeyRegistrationOptions(email: email)

            // Create passkey credential
            let provider = ASAuthorizationPlatformPublicKeyCredentialProvider(relyingPartyIdentifier: options.rpId)
            let request = provider.createCredentialRegistrationRequest(
                challenge: Data(base64URLEncoded: options.challenge)!,
                name: email,
                userID: Data(base64URLEncoded: options.user.id)!
            )

            let authController = ASAuthorizationController(authorizationRequests: [request])
            authController.delegate = self
            authController.presentationContextProvider = self
            authController.performRequests()

        } catch {
            authStatus = "Passkey creation failed: \(error.localizedDescription)"
        }
    }

    private func authenticateWithPasskey(email: String) async {
        guard #available(iOS 15.0, *) else {
            await requestMagicLink(email: email)
            return
        }

        do {
            // Get WebAuthn options
            let options = await getPasskeyAuthenticationOptions(email: email)

            // Authenticate with passkey
            let provider = ASAuthorizationPlatformPublicKeyCredentialProvider(relyingPartyIdentifier: options.rpId)
            let request = provider.createCredentialAssertionRequest(challenge: Data(base64URLEncoded: options.challenge)!)

            let authController = ASAuthorizationController(authorizationRequests: [request])
            authController.delegate = self
            authController.presentationContextProvider = self
            authController.performRequests()

        } catch {
            // Fallback to magic link
            await requestMagicLink(email: email)
        }
    }

    private func requestMagicLink(email: String) async {
        do {
            let deviceCapabilities = await DeviceCapabilities.detect()
            let result = await sendMagicLinkRequest(email: email, deviceInfo: deviceCapabilities)
            authStatus = "Check your email for a sign-in link"
        } catch {
            authStatus = "Failed to send magic link: \(error.localizedDescription)"
        }
    }

    func handleMagicLink(url: URL) async {
        // Extract token from magic link URL
        guard let token = extractTokenFromURL(url) else {
            authStatus = "Invalid magic link"
            return
        }

        do {
            let deviceCapabilities = await DeviceCapabilities.detect()
            let result = await verifyMagicLink(token: token, deviceInfo: deviceCapabilities)

            if result.success {
                isAuthenticated = true
                authStatus = "Signed in successfully!"
            } else {
                authStatus = "Magic link verification failed"
            }
        } catch {
            authStatus = "Magic link verification failed: \(error.localizedDescription)"
        }
    }
}

// MARK: - ASAuthorizationControllerDelegate
extension PasswordlessAuthManager: ASAuthorizationControllerDelegate {
    func authorizationController(controller: ASAuthorizationController, didCompleteWithAuthorization authorization: ASAuthorization) {
        Task {
            if let credential = authorization.credential as? ASAuthorizationPlatformPublicKeyCredentialRegistration {
                // Handle passkey registration
                await handlePasskeyRegistration(credential)
            } else if let credential = authorization.credential as? ASAuthorizationPlatformPublicKeyCredentialAssertion {
                // Handle passkey authentication
                await handlePasskeyAuthentication(credential)
            }
        }
    }

    func authorizationController(controller: ASAuthorizationController, didCompleteWithError error: Error) {
        authStatus = "Authentication failed: \(error.localizedDescription)"
    }
}

// MARK: - ASAuthorizationControllerPresentationContextProviding
extension PasswordlessAuthManager: ASAuthorizationControllerPresentationContextProviding {
    func presentationAnchor(for controller: ASAuthorizationController) -> ASPresentationAnchor {
        return UIApplication.shared.windows.first { $0.isKeyWindow }!
    }
}
```

### 3. SwiftUI Integration
```swift
// Views/AuthenticationView.swift
import SwiftUI

struct AuthenticationView: View {
    @StateObject private var authManager = PasswordlessAuthManager()
    @State private var email = ""
    @State private var firstName = ""
    @State private var lastName = ""
    @State private var isSignup = false

    var body: some View {
        VStack(spacing: 20) {
            Text("Ekko")
                .font(.largeTitle)
                .fontWeight(.bold)

            if isSignup {
                TextField("First Name", text: $firstName)
                    .textFieldStyle(RoundedBorderTextFieldStyle())

                TextField("Last Name", text: $lastName)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
            }

            TextField("Work email (serves as your backup sign-in)", text: $email)
                .textFieldStyle(RoundedBorderTextFieldStyle())
                .keyboardType(.emailAddress)
                .autocapitalization(.none)

            Button(action: {
                Task {
                    if isSignup {
                        await authManager.signUp(email: email, firstName: firstName, lastName: lastName)
                    } else {
                        await authManager.signIn(email: email)
                    }
                }
            }) {
                Text(isSignup ? "Sign Up" : "Sign In")
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(8)
            }

            Button(isSignup ? "Already have an account?" : "Need an account?") {
                isSignup.toggle()
            }
            .foregroundColor(.blue)

            if !authManager.authStatus.isEmpty {
                Text(authManager.authStatus)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
        }
        .padding()
    }
}
```

## 🤖 Android Client Integration

### Prerequisites
```kotlin
// build.gradle (Module: app)
dependencies {
    implementation 'androidx.credentials:credentials:1.2.0'
    implementation 'androidx.credentials:credentials-play-services-auth:1.2.0'
    implementation 'com.google.android.gms:play-services-auth:20.7.0'
    implementation 'androidx.biometric:biometric:1.1.0'
}
```

### 1. Device Capabilities
```kotlin
// utils/DeviceCapabilities.kt
import android.content.Context
import androidx.biometric.BiometricManager
import androidx.credentials.CredentialManager
import androidx.credentials.GetCredentialRequest
import androidx.credentials.GetPublicKeyCredentialOption

data class DeviceCapabilities(
    val webauthnSupported: Boolean,
    val biometricSupported: Boolean,
    val userAgent: String,
    val deviceType: String
)

class DeviceCapabilitiesDetector(private val context: Context) {

    suspend fun detect(): DeviceCapabilities {
        val webauthnSupported = checkWebAuthnSupport()
        val biometricSupported = checkBiometricSupport()

        return DeviceCapabilities(
            webauthnSupported = webauthnSupported,
            biometricSupported = biometricSupported,
            userAgent = "EkkoApp/1.0 Android",
            deviceType = "android"
        )
    }

    private suspend fun checkWebAuthnSupport(): Boolean {
        return try {
            val credentialManager = CredentialManager.create(context)
            // Check if credential manager is available
            true
        } catch (e: Exception) {
            false
        }
    }

    private fun checkBiometricSupport(): Boolean {
        val biometricManager = BiometricManager.from(context)
        return when (biometricManager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_WEAK)) {
            BiometricManager.BIOMETRIC_SUCCESS -> true
            else -> false
        }
    }
}
```

### 2. Android Authentication Manager
```kotlin
// auth/PasswordlessAuthManager.kt
import android.content.Context
import androidx.credentials.*
import androidx.credentials.exceptions.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class PasswordlessAuthManager(private val context: Context) {

    private val credentialManager = CredentialManager.create(context)
    private val deviceCapabilitiesDetector = DeviceCapabilitiesDetector(context)

    private val _authState = MutableStateFlow<AuthState>(AuthState.Unauthenticated)
    val authState: StateFlow<AuthState> = _authState.asStateFlow()

    private val _statusMessage = MutableStateFlow("")
    val statusMessage: StateFlow<String> = _statusMessage.asStateFlow()

    private val apiBaseUrl = "https://your-api-domain.com"

    suspend fun signUp(email: String, firstName: String, lastName: String) {
        try {
            _statusMessage.value = "Starting signup..."

            // 1. Begin signup
            val deviceCapabilities = deviceCapabilitiesDetector.detect()
            val beginResult = beginSignup(email, deviceCapabilities)

            _statusMessage.value = beginResult.message

            // 2. Create passkey if supported
            if (deviceCapabilities.webauthnSupported) {
                createPasskey(email, firstName, lastName)
            } else {
                _statusMessage.value = "Check your email to complete signup"
            }

        } catch (e: Exception) {
            _statusMessage.value = "Signup failed: ${e.message}"
        }
    }

    suspend fun signIn(email: String) {
        try {
            _statusMessage.value = "Signing in..."

            val deviceCapabilities = deviceCapabilitiesDetector.detect()

            // Try passkey first if available
            if (deviceCapabilities.webauthnSupported) {
                authenticateWithPasskey(email)
            } else {
                requestMagicLink(email)
            }

        } catch (e: Exception) {
            _statusMessage.value = "Sign in failed: ${e.message}"
        }
    }

    private suspend fun createPasskey(email: String, firstName: String, lastName: String) {
        try {
            // Get WebAuthn options from Django
            val options = getPasskeyRegistrationOptions(email)

            // Create passkey credential request
            val createRequest = CreatePublicKeyCredentialRequest(
                requestJson = options.toJson()
            )

            // Create credential
            val result = credentialManager.createCredential(
                request = createRequest,
                activity = context as Activity
            )

            // Complete signup with Django
            completeSignupWithPasskey(result, firstName, lastName)

        } catch (e: CreateCredentialException) {
            when (e) {
                is CreateCredentialCancellationException -> {
                    _statusMessage.value = "Passkey creation cancelled"
                }
                is CreateCredentialInterruptedException -> {
                    _statusMessage.value = "Passkey creation interrupted"
                }
                else -> {
                    _statusMessage.value = "Passkey creation failed: ${e.message}"
                }
            }
        }
    }

    private suspend fun authenticateWithPasskey(email: String) {
        try {
            // Get WebAuthn options
            val options = getPasskeyAuthenticationOptions(email)

            // Create authentication request
            val getRequest = GetCredentialRequest(
                listOf(
                    GetPublicKeyCredentialOption(
                        requestJson = options.toJson()
                    )
                )
            )

            // Authenticate
            val result = credentialManager.getCredential(
                request = getRequest,
                activity = context as Activity
            )

            // Complete authentication with Django
            completeAuthenticationWithPasskey(result)

        } catch (e: GetCredentialException) {
            when (e) {
                is GetCredentialCancellationException -> {
                    _statusMessage.value = "Authentication cancelled"
                }
                is NoCredentialException -> {
                    // Fallback to magic link
                    requestMagicLink(email)
                }
                else -> {
                    _statusMessage.value = "Authentication failed: ${e.message}"
                    requestMagicLink(email)
                }
            }
        }
    }

    private suspend fun requestMagicLink(email: String) {
        try {
            val deviceCapabilities = deviceCapabilitiesDetector.detect()
            val result = sendMagicLinkRequest(email, deviceCapabilities)
            _statusMessage.value = "Check your email for a sign-in link"
        } catch (e: Exception) {
            _statusMessage.value = "Failed to send magic link: ${e.message}"
        }
    }

    suspend fun handleMagicLink(token: String) {
        try {
            val deviceCapabilities = deviceCapabilitiesDetector.detect()
            val result = verifyMagicLink(token, deviceCapabilities)

            if (result.success) {
                _authState.value = AuthState.Authenticated(result.user)
                _statusMessage.value = "Signed in successfully!"
            } else {
                _statusMessage.value = "Magic link verification failed"
            }
        } catch (e: Exception) {
            _statusMessage.value = "Magic link verification failed: ${e.message}"
        }
    }
}

sealed class AuthState {
    object Unauthenticated : AuthState()
    data class Authenticated(val user: User) : AuthState()
    object Loading : AuthState()
}
```

### 3. Jetpack Compose Integration
```kotlin
// ui/AuthenticationScreen.kt
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AuthenticationScreen() {
    val context = LocalContext.current
    val authManager = remember { PasswordlessAuthManager(context) }

    val authState by authManager.authState.collectAsStateWithLifecycle()
    val statusMessage by authManager.statusMessage.collectAsStateWithLifecycle()

    var email by remember { mutableStateOf("") }
    var firstName by remember { mutableStateOf("") }
    var lastName by remember { mutableStateOf("") }
    var isSignup by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = "Ekko",
            style = MaterialTheme.typography.headlineLarge
        )

        Spacer(modifier = Modifier.height(32.dp))

        if (isSignup) {
            OutlinedTextField(
                value = firstName,
                onValueChange = { firstName = it },
                label = { Text("First Name") },
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(modifier = Modifier.height(16.dp))

            OutlinedTextField(
                value = lastName,
                onValueChange = { lastName = it },
                label = { Text("Last Name") },
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(modifier = Modifier.height(16.dp))
        }

        OutlinedTextField(
            value = email,
            onValueChange = { email = it },
            label = { Text("Work email (serves as your backup sign-in)") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.height(24.dp))

        Button(
            onClick = {
                if (isSignup) {
                    // Launch coroutine for signup
                    // authManager.signUp(email, firstName, lastName)
                } else {
                    // Launch coroutine for signin
                    // authManager.signIn(email)
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(if (isSignup) "Sign Up" else "Sign In")
        }

        Spacer(modifier = Modifier.height(16.dp))

        TextButton(
            onClick = { isSignup = !isSignup }
        ) {
            Text(if (isSignup) "Already have an account?" else "Need an account?")
        }

        if (statusMessage.isNotEmpty()) {
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = statusMessage,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
```

## 🔗 Deep Link Handling

### Web
```javascript
// Handle magic link in web app
window.addEventListener('load', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    if (token) {
        const auth = new PasswordlessSignup(API_BASE_URL);
        auth.handleMagicLink(token);
    }
});
```

### iOS
```swift
// AppDelegate.swift or SceneDelegate.swift
func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey : Any] = [:]) -> Bool {
    if url.scheme == "ekko" && url.host == "auth" {
        Task {
            await authManager.handleMagicLink(url: url)
        }
        return true
    }
    return false
}
```

### Android
```kotlin
// MainActivity.kt
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)

    // Handle magic link intent
    handleIntent(intent)
}

override fun onNewIntent(intent: Intent?) {
    super.onNewIntent(intent)
    intent?.let { handleIntent(it) }
}

private fun handleIntent(intent: Intent) {
    val data = intent.data
    if (data?.scheme == "ekko" && data.host == "auth") {
        val token = data.getQueryParameter("token")
        token?.let {
            // Handle magic link
            lifecycleScope.launch {
                authManager.handleMagicLink(it)
            }
        }
    }
}
```

## 🔧 Configuration

### Environment Variables
```bash
# .env
API_BASE_URL=https://your-api-domain.com
WEBAUTHN_RP_ID=your-domain.com
WEBAUTHN_ORIGIN=https://your-domain.com
```

### URL Schemes
- **Web**: `https://your-domain.com/auth?token=...`
- **iOS**: `ekko://auth?token=...`
- **Android**: `ekko://auth?token=...`

## 📚 Additional Resources

- [WebAuthn Guide](https://webauthn.guide/)
- [SimpleWebAuthn Documentation](https://simplewebauthn.dev/)
- [iOS AuthenticationServices](https://developer.apple.com/documentation/authenticationservices)
- [Android Credential Manager](https://developer.android.com/training/sign-in/passkeys)

## 🆘 Troubleshooting

### Common Issues
1. **WebAuthn not working**: Ensure HTTPS and proper domain configuration
2. **iOS passkeys failing**: Check iOS version (15+) and proper entitlements
3. **Android credentials not found**: Verify Google Play Services and app signing
4. **Magic links not working**: Check email delivery and URL scheme handling

### Support
For integration support, check the API documentation at `/api/docs/` or contact the development team.
```
```
