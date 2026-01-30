import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

// Storage helper that works on both web and native
const storage = {
  async getItem(key: string): Promise<string | null> {
    if (Platform.OS === 'web') {
      return localStorage.getItem(key);
    }
    return SecureStore.getItemAsync(key);
  },
  async setItem(key: string, value: string): Promise<void> {
    if (Platform.OS === 'web') {
      localStorage.setItem(key, value);
      return;
    }
    return SecureStore.setItemAsync(key, value);
  },
  async removeItem(key: string): Promise<void> {
    if (Platform.OS === 'web') {
      localStorage.removeItem(key);
      return;
    }
    return SecureStore.deleteItemAsync(key);
  }
};

interface User {
  id: string;
  email: string;
  name: string;
  profile?: {
    age?: number;
    age_range?: string;
    gender?: string;
    skin_goals?: string[];
    skin_type?: string;
    country?: string;
    language?: string;
  };
  plan: string;  // 'free' or 'premium'
  scan_count: number;
  created_at: string;
}

interface SocialAuthData {
  provider: 'google' | 'apple';
  provider_id: string;
  email?: string | null;
  name?: string | null;
  id_token?: string;
  language?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string, language?: string) => Promise<void>;
  socialAuth: (data: SocialAuthData) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (profile: any) => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadStoredAuth();
  }, []);

  const loadStoredAuth = async () => {
    try {
      const storedToken = await SecureStore.getItemAsync('auth_token');
      if (storedToken) {
        setToken(storedToken);
        await fetchUser(storedToken);
      }
    } catch (error) {
      console.error('Failed to load auth:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchUser = async (authToken: string) => {
    try {
      const response = await axios.get(`${API_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      setUser(response.data);
    } catch (error) {
      console.error('Failed to fetch user:', error);
      await logout();
    }
  };

  const login = async (email: string, password: string) => {
    const response = await axios.post(`${API_URL}/api/auth/login`, {
      email,
      password
    });
    const { access_token, user: userData } = response.data;
    await SecureStore.setItemAsync('auth_token', access_token);
    setToken(access_token);
    setUser(userData);
  };

  const register = async (name: string, email: string, password: string, language: string = 'en') => {
    const response = await axios.post(`${API_URL}/api/auth/register`, {
      name,
      email,
      password,
      language
    });
    const { access_token, user: userData } = response.data;
    await SecureStore.setItemAsync('auth_token', access_token);
    setToken(access_token);
    setUser(userData);
  };

  const socialAuth = async (data: SocialAuthData) => {
    const response = await axios.post(`${API_URL}/api/auth/social`, {
      provider: data.provider,
      provider_id: data.provider_id,
      email: data.email,
      name: data.name,
      id_token: data.id_token,
      language: data.language || 'en'
    });
    const { access_token, user: userData } = response.data;
    await SecureStore.setItemAsync('auth_token', access_token);
    setToken(access_token);
    setUser(userData);
  };

  const logout = async () => {
    await SecureStore.deleteItemAsync('auth_token');
    setToken(null);
    setUser(null);
  };

  const updateProfile = async (profile: any) => {
    if (!token) return;
    const response = await axios.put(`${API_URL}/api/profile`, profile, {
      headers: { Authorization: `Bearer ${token}` }
    });
    setUser(response.data);
  };

  const refreshUser = async () => {
    if (token) {
      await fetchUser(token);
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, socialAuth, logout, updateProfile, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
