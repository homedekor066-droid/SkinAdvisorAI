import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { I18nManager } from 'react-native';
import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface Translations {
  [key: string]: string;
}

interface Language {
  code: string;
  name: string;
  rtl: boolean;
}

interface I18nContextType {
  language: string;
  translations: Translations;
  languages: Language[];
  setLanguage: (lang: string) => Promise<void>;
  t: (key: string) => string;
  isRTL: boolean;
}

const I18nContext = createContext<I18nContextType | undefined>(undefined);

export const I18nProvider = ({ children }: { children: ReactNode }) => {
  const [language, setLang] = useState('en');
  const [translations, setTranslations] = useState<Translations>({});
  const [languages, setLanguages] = useState<Language[]>([]);
  const [isRTL, setIsRTL] = useState(false);

  useEffect(() => {
    loadLanguage();
    fetchLanguages();
  }, []);

  useEffect(() => {
    fetchTranslations(language);
  }, [language]);

  const loadLanguage = async () => {
    try {
      const storedLang = await AsyncStorage.getItem('app_language');
      if (storedLang) {
        setLang(storedLang);
        const lang = languages.find(l => l.code === storedLang);
        if (lang) {
          setIsRTL(lang.rtl);
          I18nManager.forceRTL(lang.rtl);
        }
      }
    } catch (error) {
      console.error('Failed to load language:', error);
    }
  };

  const fetchLanguages = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/languages`);
      setLanguages(response.data);
    } catch (error) {
      console.error('Failed to fetch languages:', error);
      // Fallback languages
      setLanguages([
        { code: 'en', name: 'English', rtl: false },
        { code: 'fr', name: 'Français', rtl: false },
        { code: 'tr', name: 'Türkçe', rtl: false },
        { code: 'it', name: 'Italiano', rtl: false },
        { code: 'es', name: 'Español', rtl: false },
        { code: 'de', name: 'Deutsch', rtl: false },
        { code: 'ar', name: 'العربية', rtl: true },
        { code: 'zh', name: '中文', rtl: false },
        { code: 'hi', name: 'हिन्दी', rtl: false }
      ]);
    }
  };

  const fetchTranslations = async (lang: string) => {
    try {
      const response = await axios.get(`${API_URL}/api/translations/${lang}`);
      setTranslations(response.data);
    } catch (error) {
      console.error('Failed to fetch translations:', error);
    }
  };

  const setLanguage = async (lang: string) => {
    try {
      await AsyncStorage.setItem('app_language', lang);
      setLang(lang);
      const langObj = languages.find(l => l.code === lang);
      if (langObj) {
        setIsRTL(langObj.rtl);
        I18nManager.forceRTL(langObj.rtl);
      }
    } catch (error) {
      console.error('Failed to set language:', error);
    }
  };

  const t = (key: string): string => {
    return translations[key] || key;
  };

  return (
    <I18nContext.Provider value={{ language, translations, languages, setLanguage, t, isRTL }}>
      {children}
    </I18nContext.Provider>
  );
};

export const useI18n = () => {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider');
  }
  return context;
};
