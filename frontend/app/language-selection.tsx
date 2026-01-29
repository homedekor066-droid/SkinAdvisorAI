import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '../src/context/ThemeContext';
import { useI18n } from '../src/context/I18nContext';
import { Button } from '../src/components';
import { Ionicons } from '@expo/vector-icons';

export default function LanguageSelectionScreen() {
  const { theme } = useTheme();
  const { language, languages, setLanguage } = useI18n();
  const router = useRouter();

  const [selectedLanguage, setSelectedLanguage] = useState(language);
  const [loading, setLoading] = useState(false);

  // Update selected when language loads
  useEffect(() => {
    if (language) {
      setSelectedLanguage(language);
    }
  }, [language]);

  const handleContinue = async () => {
    setLoading(true);
    try {
      await setLanguage(selectedLanguage);
      // Navigate to questionnaire after language selection
      router.replace('/skin-questionnaire');
    } catch (error) {
      console.error('Failed to set language:', error);
    } finally {
      setLoading(false);
    }
  };

  // Show loading if languages haven't loaded yet
  if (!languages || languages.length === 0) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.primary} />
          <Text style={[styles.loadingText, { color: theme.textSecondary }]}>
            Loading languages...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={styles.header}>
        <View style={[styles.iconCircle, { backgroundColor: theme.primary + '20' }]}>
          <Ionicons name="language" size={40} color={theme.primary} />
        </View>
        
        <Text style={[styles.title, { color: theme.text }]}>
          Choose Your Language
        </Text>
        <Text style={[styles.subtitle, { color: theme.textSecondary }]}>
          Select your preferred language for the app
        </Text>
      </View>

      {/* Language List */}
      <ScrollView 
        style={styles.content}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {languages.map((lang) => (
          <TouchableOpacity
            key={lang.code}
            style={[
              styles.languageCard,
              { 
                backgroundColor: theme.card,
                borderColor: selectedLanguage === lang.code ? theme.primary : theme.border,
                borderWidth: selectedLanguage === lang.code ? 2 : 1,
              }
            ]}
            onPress={() => setSelectedLanguage(lang.code)}
          >
            <View style={styles.languageInfo}>
              <Text style={[styles.languageName, { color: theme.text }]}>
                {lang.name}
              </Text>
              <Text style={[styles.languageCode, { color: theme.textSecondary }]}>
                {lang.code.toUpperCase()}
              </Text>
            </View>
            
            {selectedLanguage === lang.code && (
              <Ionicons name="checkmark-circle" size={24} color={theme.primary} />
            )}
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Footer */}
      <View style={styles.footer}>
        <Button
          title="Continue"
          onPress={handleContinue}
          loading={loading}
          style={styles.continueButton}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
  },
  header: {
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 20,
    paddingBottom: 24,
  },
  iconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 8,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 15,
    textAlign: 'center',
  },
  content: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingBottom: 24,
  },
  languageCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderRadius: 12,
    marginBottom: 12,
  },
  languageInfo: {
    flex: 1,
  },
  languageName: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 2,
  },
  languageCode: {
    fontSize: 13,
  },
  footer: {
    paddingHorizontal: 24,
    paddingBottom: 24,
    paddingTop: 12,
  },
  continueButton: {
    width: '100%',
  },
});
