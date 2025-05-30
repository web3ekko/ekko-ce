import api from './ekko';
import { SignInCredential, SignUpCredential, SignInResponse } from '@/@types/auth';

// Authentication API service
export const authApi = {
  signIn: async (email: string, password: string): Promise<SignInResponse> => {
    try {
      const response = await api.post('/token', { username: email, password: password }, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
      
      // Store the token in localStorage for the interceptor to use
      if (response.data.access_token) {
        localStorage.setItem('auth_token', response.data.access_token);
      }
      
      return response.data;
    } catch (error) {
      console.error('Error during sign in:', error);
      throw error;
    }
  },
  
  signUp: async (credentials: SignUpCredential): Promise<SignInResponse> => {
    try {
      const response = await api.post('/users/sign-up', credentials);
      return response.data;
    } catch (error) {
      console.error('Error during sign up:', error);
      throw error;
    }
  },
  
  signOut: async (): Promise<void> => {
    try {
      // Remove token from localStorage
      localStorage.removeItem('auth_token');
      
      // Optional: Call backend to invalidate token
      await api.post('/users/sign-out');
    } catch (error) {
      console.error('Error during sign out:', error);
      // Still remove token even if API call fails
      localStorage.removeItem('auth_token');
    }
  },
  
  verifyToken: async (): Promise<boolean> => {
    try {
      const response = await api.get('/users/verify-token');
      return response.status === 200;
    } catch (error) {
      console.error('Error verifying token:', error);
      return false;
    }
  },
  
  forgotPassword: async (email: string): Promise<void> => {
    try {
      await api.post('/users/forgot-password', { email });
    } catch (error) {
      console.error('Error during forgot password:', error);
      throw error;
    }
  },
  
  resetPassword: async (token: string, newPassword: string): Promise<void> => {
    try {
      await api.post('/users/reset-password', { token, newPassword });
    } catch (error) {
      console.error('Error during password reset:', error);
      throw error;
    }
  },
  
  getCurrentUser: async (): Promise<any> => {
    try {
      const response = await api.get('/users/me');
      return response.data;
    } catch (error) {
      console.error('Error fetching current user:', error);
      throw error;
    }
  }
};

export default authApi;
