/**
 * Firebase Configuration and Initialization
 * 
 * This module initializes Firebase for the Ekko dashboard and provides
 * authentication services that integrate with the Django backend.
 */

import { initializeApp, FirebaseApp } from 'firebase/app';
import { getAuth, Auth } from 'firebase/auth';

// Firebase configuration interface
interface FirebaseConfig {
  apiKey: string;
  authDomain: string;
  projectId: string;
  storageBucket?: string;
  messagingSenderId?: string;
  appId?: string;
  measurementId?: string;
}

// Default configuration (will be overridden by environment variables)
const defaultConfig: FirebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || 'ekko-testing.firebaseapp.com',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || 'ekko-testing',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || 'ekko-testing.firebasestorage.app',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || '',
};

// Firebase app instance
let app: FirebaseApp | null = null;
let auth: Auth | null = null;

/**
 * Initialize Firebase with configuration
 */
export const initializeFirebase = async (): Promise<{ app: FirebaseApp; auth: Auth } | null> => {
  try {
    // Check if we have the minimum required configuration
    if (!defaultConfig.apiKey || !defaultConfig.projectId) {
      console.warn('Firebase configuration incomplete. Some features may not work.');
      
      // Try to fetch configuration from API
      try {
        const response = await fetch('/api/auth/firebase/config/');
        const data = await response.json();
        
        if (data.available && data.config) {
          // Use API configuration if available
          const apiConfig = data.config;
          if (apiConfig.apiKey && apiConfig.projectId) {
            Object.assign(defaultConfig, apiConfig);
          }
        }
      } catch (error) {
        console.warn('Could not fetch Firebase config from API:', error);
      }
    }

    // Initialize Firebase app
    if (!app) {
      app = initializeApp(defaultConfig);
      auth = getAuth(app);
      
      console.log('Firebase initialized successfully:', {
        projectId: defaultConfig.projectId,
        authDomain: defaultConfig.authDomain,
      });
    }

    return { app, auth };
  } catch (error) {
    console.error('Failed to initialize Firebase:', error);
    return null;
  }
};

/**
 * Get Firebase auth instance
 */
export const getFirebaseAuth = (): Auth | null => {
  return auth;
};

/**
 * Get Firebase app instance
 */
export const getFirebaseApp = (): FirebaseApp | null => {
  return app;
};

/**
 * Check if Firebase is properly configured
 */
export const isFirebaseConfigured = (): boolean => {
  return !!(defaultConfig.apiKey && defaultConfig.projectId);
};

/**
 * Get Firebase configuration for debugging
 */
export const getFirebaseConfig = (): FirebaseConfig => {
  return { ...defaultConfig };
};

// Initialize Firebase on module load
initializeFirebase().catch(console.error);

// Export auth instance for convenience
export { auth as firebaseAuth };
export { app as firebaseApp };
export default { app, auth, initializeFirebase, isFirebaseConfigured };
