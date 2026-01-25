import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTheme } from '../../src/context/ThemeContext';
import { useI18n } from '../../src/context/I18nContext';
import { useAuth } from '../../src/context/AuthContext';
import { Card, Button } from '../../src/components';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export default function ProfileScreen() {
  const { theme, isDarkMode, toggleTheme } = useTheme();
  const { t, language, languages, setLanguage } = useI18n();
  const { user, token, logout, updateProfile } = useAuth();
  const router = useRouter();
  const [showLanguages, setShowLanguages] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleLogout = () => {
    Alert.alert(
      t('logout'),
      'Are you sure you want to logout?',
      [
        { text: t('cancel'), style: 'cancel' },
        {
          text: t('confirm'),
          onPress: async () => {
            await logout();
            router.replace('/(auth)/login');
          },
        },
      ]
    );
  };

  const handleDeleteAccount = () => {
    Alert.alert(
      t('delete_account'),
      t('confirm_delete'),
      [
        { text: t('cancel'), style: 'cancel' },
        {
          text: t('confirm'),
          style: 'destructive',
          onPress: async () => {
            setDeleting(true);
            try {
              await axios.delete(`${API_URL}/api/account`, {
                headers: { Authorization: `Bearer ${token}` }
              });
              await logout();
              router.replace('/(auth)/login');
            } catch (error) {
              Alert.alert(t('error'), 'Failed to delete account');
            } finally {
              setDeleting(false);
            }
          },
        },
      ]
    );
  };

  const handleLanguageChange = async (langCode: string) => {
    await setLanguage(langCode);
    if (token) {
      try {
        await updateProfile({ ...user?.profile, language: langCode });
      } catch (error) {
        console.error('Failed to update profile language:', error);
      }
    }
    setShowLanguages(false);
  };

  const currentLanguage = languages.find(l => l.code === language);

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      <View style={styles.header}>
        <Text style={[styles.title, { color: theme.text }]}>{t('profile')}</Text>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {/* User Info */}
        <Card style={styles.userCard}>
          <View style={[styles.avatar, { backgroundColor: theme.primary }]}>
            <Text style={styles.avatarText}>
              {user?.name?.charAt(0).toUpperCase() || 'U'}
            </Text>
          </View>
          <Text style={[styles.userName, { color: theme.text }]}>
            {user?.name || 'User'}
          </Text>
          <Text style={[styles.userEmail, { color: theme.textSecondary }]}>
            {user?.email || ''}
          </Text>
        </Card>

        {/* Settings */}
        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          {t('settings')}
        </Text>

        <Card style={styles.settingsCard}>
          {/* Language */}
          <TouchableOpacity
            style={styles.settingItem}
            onPress={() => setShowLanguages(!showLanguages)}
          >
            <View style={styles.settingLeft}>
              <View style={[styles.settingIcon, { backgroundColor: theme.info + '20' }]}>
                <Ionicons name="language" size={20} color={theme.info} />
              </View>
              <View>
                <Text style={[styles.settingLabel, { color: theme.text }]}>
                  {t('language')}
                </Text>
                <Text style={[styles.settingValue, { color: theme.textSecondary }]}>
                  {currentLanguage?.name || 'English'}
                </Text>
              </View>
            </View>
            <Ionicons
              name={showLanguages ? 'chevron-up' : 'chevron-down'}
              size={20}
              color={theme.textMuted}
            />
          </TouchableOpacity>

          {showLanguages && (
            <View style={[styles.languageList, { borderTopColor: theme.border }]}>
              {languages.map((lang) => (
                <TouchableOpacity
                  key={lang.code}
                  style={[
                    styles.languageItem,
                    language === lang.code && { backgroundColor: theme.primary + '10' }
                  ]}
                  onPress={() => handleLanguageChange(lang.code)}
                >
                  <Text style={[
                    styles.languageText,
                    { color: language === lang.code ? theme.primary : theme.text }
                  ]}>
                    {lang.name}
                  </Text>
                  {language === lang.code && (
                    <Ionicons name="checkmark" size={20} color={theme.primary} />
                  )}
                </TouchableOpacity>
              ))}
            </View>
          )}

          <View style={[styles.divider, { backgroundColor: theme.border }]} />

          {/* Dark Mode */}
          <View style={styles.settingItem}>
            <View style={styles.settingLeft}>
              <View style={[styles.settingIcon, { backgroundColor: theme.primary + '20' }]}>
                <Ionicons
                  name={isDarkMode ? 'moon' : 'sunny'}
                  size={20}
                  color={theme.primary}
                />
              </View>
              <Text style={[styles.settingLabel, { color: theme.text }]}>
                {t('dark_mode')}
              </Text>
            </View>
            <Switch
              value={isDarkMode}
              onValueChange={toggleTheme}
              trackColor={{ false: theme.border, true: theme.primary }}
              thumbColor="#FFFFFF"
            />
          </View>
        </Card>

        {/* Legal */}
        <Text style={[styles.sectionTitle, { color: theme.text }]}>Legal</Text>

        <Card style={styles.settingsCard}>
          <TouchableOpacity style={styles.settingItem}>
            <View style={styles.settingLeft}>
              <View style={[styles.settingIcon, { backgroundColor: theme.success + '20' }]}>
                <Ionicons name="document-text-outline" size={20} color={theme.success} />
              </View>
              <Text style={[styles.settingLabel, { color: theme.text }]}>
                Privacy Policy
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={theme.textMuted} />
          </TouchableOpacity>

          <View style={[styles.divider, { backgroundColor: theme.border }]} />

          <TouchableOpacity style={styles.settingItem}>
            <View style={styles.settingLeft}>
              <View style={[styles.settingIcon, { backgroundColor: theme.warning + '20' }]}>
                <Ionicons name="shield-outline" size={20} color={theme.warning} />
              </View>
              <Text style={[styles.settingLabel, { color: theme.text }]}>
                Terms of Service
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={theme.textMuted} />
          </TouchableOpacity>
        </Card>

        {/* Danger Zone */}
        <Text style={[styles.sectionTitle, { color: theme.error }]}>Danger Zone</Text>

        <Card style={styles.settingsCard}>
          <TouchableOpacity
            style={styles.settingItem}
            onPress={handleDeleteAccount}
            disabled={deleting}
          >
            <View style={styles.settingLeft}>
              <View style={[styles.settingIcon, { backgroundColor: theme.error + '20' }]}>
                <Ionicons name="trash-outline" size={20} color={theme.error} />
              </View>
              <Text style={[styles.settingLabel, { color: theme.error }]}>
                {t('delete_account')}
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={theme.error} />
          </TouchableOpacity>
        </Card>

        {/* Logout Button */}
        <Button
          title={t('logout')}
          onPress={handleLogout}
          variant="outline"
          icon="log-out-outline"
          style={{ marginTop: 24, marginBottom: 40 }}
        />

        {/* Disclaimer */}
        <View style={[styles.disclaimer, { backgroundColor: theme.surface }]}>
          <Ionicons name="information-circle-outline" size={16} color={theme.textMuted} />
          <Text style={[styles.disclaimerText, { color: theme.textMuted }]}>
            {t('disclaimer')}
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 100,
  },
  userCard: {
    alignItems: 'center',
    paddingVertical: 24,
    marginBottom: 24,
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  avatarText: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  userName: {
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  userEmail: {
    fontSize: 14,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 12,
  },
  settingsCard: {
    padding: 0,
    marginBottom: 24,
    overflow: 'hidden',
  },
  settingItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
  },
  settingLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  settingIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  settingLabel: {
    fontSize: 16,
    fontWeight: '500',
  },
  settingValue: {
    fontSize: 12,
    marginTop: 2,
  },
  divider: {
    height: 1,
    marginLeft: 68,
  },
  languageList: {
    borderTopWidth: 1,
    paddingVertical: 8,
  },
  languageItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  languageText: {
    fontSize: 16,
  },
  disclaimer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: 16,
    borderRadius: 12,
    marginBottom: 20,
  },
  disclaimerText: {
    flex: 1,
    fontSize: 12,
    marginLeft: 8,
    lineHeight: 18,
  },
});
