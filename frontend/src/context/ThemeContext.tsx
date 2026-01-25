import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useColorScheme } from 'react-native';

export const lightTheme = {
  primary: '#E8A4B8',
  primaryDark: '#D4899E',
  secondary: '#F5E6E8',
  background: '#FFFFFF',
  surface: '#FAF7F8',
  card: '#FFFFFF',
  text: '#2D2D2D',
  textSecondary: '#666666',
  textMuted: '#999999',
  border: '#E8E8E8',
  error: '#E74C3C',
  success: '#27AE60',
  warning: '#F39C12',
  info: '#3498DB',
  gradientStart: '#E8A4B8',
  gradientEnd: '#F5C6D0',
};

export const darkTheme = {
  primary: '#E8A4B8',
  primaryDark: '#D4899E',
  secondary: '#3D3D3D',
  background: '#1A1A1A',
  surface: '#252525',
  card: '#2D2D2D',
  text: '#FFFFFF',
  textSecondary: '#B0B0B0',
  textMuted: '#777777',
  border: '#404040',
  error: '#E74C3C',
  success: '#27AE60',
  warning: '#F39C12',
  info: '#3498DB',
  gradientStart: '#E8A4B8',
  gradientEnd: '#F5C6D0',
};

type Theme = typeof lightTheme;

interface ThemeContextType {
  theme: Theme;
  isDarkMode: boolean;
  toggleTheme: () => void;
  setDarkMode: (dark: boolean) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider = ({ children }: { children: ReactNode }) => {
  const systemColorScheme = useColorScheme();
  const [isDarkMode, setIsDarkMode] = useState(systemColorScheme === 'dark');

  useEffect(() => {
    loadThemePreference();
  }, []);

  const loadThemePreference = async () => {
    try {
      const stored = await AsyncStorage.getItem('theme_mode');
      if (stored !== null) {
        setIsDarkMode(stored === 'dark');
      }
    } catch (error) {
      console.error('Failed to load theme:', error);
    }
  };

  const toggleTheme = async () => {
    const newMode = !isDarkMode;
    setIsDarkMode(newMode);
    await AsyncStorage.setItem('theme_mode', newMode ? 'dark' : 'light');
  };

  const setDarkMode = async (dark: boolean) => {
    setIsDarkMode(dark);
    await AsyncStorage.setItem('theme_mode', dark ? 'dark' : 'light');
  };

  const theme = isDarkMode ? darkTheme : lightTheme;

  return (
    <ThemeContext.Provider value={{ theme, isDarkMode, toggleTheme, setDarkMode }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
};
