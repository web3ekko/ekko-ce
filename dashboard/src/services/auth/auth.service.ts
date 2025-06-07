import ApiService from '@/services/ApiService';
import { SignInResponse } from '@/@types/auth';

export const AuthService = {
  async signIn(email: string, password: string): Promise<SignInResponse> {
    const res = await ApiService.fetchData<string, SignInResponse>({
      url: '/token',
      method: 'POST',
      data: new URLSearchParams({ username: email, password: password }).toString(),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return res.data;
  },
};
