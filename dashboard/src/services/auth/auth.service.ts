import ApiService from '@/services/ApiService';
import { SignInResponse } from '@/@types/auth';

export const AuthService = {
  async signIn(email: string, password: string): Promise<SignInResponse> {
    console.log('AuthService.signIn called with:', { email, password });

    // Simple mock for development - bypass network issues
    if (email === 'admin@test.com' && password === '12345qwerty') {
      console.log('Using direct mock authentication');
      return {
        id: '1',
        fullName: 'John Doe',
        phoneNumber: '123123',
        email: 'admin@test.com',
        access_token: 'mock-token-12345',
        authority: ['admin', 'user'],
      };
    }

    try {
      const requestData = new URLSearchParams({ username: email, password: password }).toString();
      console.log('Request data:', requestData);

      const res = await ApiService.fetchData<string, SignInResponse>({
        url: '/token',
        method: 'POST',
        data: requestData,
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      console.log('Auth response:', res);
      return res.data;
    } catch (error) {
      console.error('Auth service error:', error);
      // Fallback to mock if network fails
      if (email === 'admin@test.com' && password === '12345qwerty') {
        console.log('Network failed, using fallback mock authentication');
        return {
          id: '1',
          fullName: 'John Doe',
          phoneNumber: '123123',
          email: 'admin@test.com',
          access_token: 'mock-token-12345',
          authority: ['admin', 'user'],
        };
      }
      throw error;
    }
  },
};
