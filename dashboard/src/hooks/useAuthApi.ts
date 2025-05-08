import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../services/api';
import {
  setUser,
  signInSuccess,
  signOutSuccess,
  useAppSelector,
  useAppDispatch,
  setUserInfo,
  setUserId
} from '@/store';
import { SignInCredential, SignUpCredential } from '@/@types/auth';
import appConfig from '@/configs/app.config';
import { REDIRECT_URL_KEY } from '@/constants/app.constant';
import useQuery from './useQuery';

type Status = 'success' | 'failed';

export function useAuthApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const query = useQuery();
  
  const { token, signedIn } = useAppSelector((state) => state.auth.session);
  const userId = useAppSelector(state => state.auth.userInfo.userId);

  const signIn = useCallback(async (
    values: SignInCredential
  ): Promise<{ status: Status; message: string } | undefined> => {
    setLoading(true);
    setError(null);
    
    try {
      const resp = await authApi.signIn(values.email, values.password);
      
      // Update Redux store with user information
      dispatch(setUserId(resp.id));
      
      const {
        access_token,
        id,
        email,
        fullName,
        phoneNumber
      } = resp;
      
      // Update auth session in Redux
      dispatch(signInSuccess({
        token: access_token,
        refreshToken: '',
        expireTime: 0
      }));
      
      // Update user info in Redux
      dispatch(
        setUser(
          {
            fullName: fullName,
            email: email,
            role: resp.authority,
            phoneNumber: phoneNumber
          }
        )
      );
      
      // Handle redirection
      const redirectUrl = query.get(REDIRECT_URL_KEY);
      navigate(redirectUrl ? redirectUrl : appConfig.authenticatedEntryPath);
      
      setLoading(false);
      return {
        status: 'success',
        message: ''
      };
    } catch (err: any) {
      setError(err?.response?.data?.message || 'An error occurred during sign in');
      setLoading(false);
      return {
        status: 'failed',
        message: err?.response?.data?.message || err.toString()
      };
    }
  }, [dispatch, navigate, query]);

  const signUp = useCallback(async (
    values: SignUpCredential
  ): Promise<{ status: Status; message: string } | undefined> => {
    setLoading(true);
    setError(null);
    
    try {
      await authApi.signUp(values);
      setLoading(false);
      return {
        status: 'success',
        message: 'Registration successful. You can now sign in.'
      };
    } catch (err: any) {
      setError(err?.response?.data?.message || 'An error occurred during registration');
      setLoading(false);
      return {
        status: 'failed',
        message: err?.response?.data?.message || err.toString()
      };
    }
  }, []);

  const signOut = useCallback(async () => {
    setLoading(true);
    
    try {
      // Call API to sign out
      await authApi.signOut();
      
      // Clear Redux state
      dispatch(signOutSuccess());
      dispatch(setUserInfo({
        googleLogin: false,
        name: '',
        role: '',
        email: '',
        userId: userId
      }));
      dispatch(
        setUser({
          fullName: '',
          role: [],
          email: ''
        })
      );
      
      // Redirect to sign-in page
      navigate(appConfig.unAuthenticatedEntryPath);
    } catch (err) {
      console.error('Error during sign out:', err);
      
      // Even if API call fails, still sign out locally
      dispatch(signOutSuccess());
      dispatch(setUserInfo({
        googleLogin: false,
        name: '',
        role: '',
        email: '',
        userId: userId
      }));
      dispatch(
        setUser({
          fullName: '',
          role: [],
          email: ''
        })
      );
      
      navigate(appConfig.unAuthenticatedEntryPath);
    } finally {
      setLoading(false);
    }
  }, [dispatch, navigate, userId]);

  const checkAuthStatus = useCallback(async () => {
    if (token && signedIn) {
      try {
        const isValid = await authApi.verifyToken();
        if (!isValid) {
          // Token is invalid, sign out
          signOut();
        }
      } catch (err) {
        console.error('Error verifying token:', err);
        // On error, assume token is invalid and sign out
        signOut();
      }
    }
  }, [token, signedIn, signOut]);

  return {
    authenticated: token && signedIn,
    loading,
    error,
    signIn,
    signUp,
    signOut,
    checkAuthStatus
  };
}
