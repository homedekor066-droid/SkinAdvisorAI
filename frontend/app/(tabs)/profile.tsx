import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
  Modal,
  TextInput,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTheme } from '../../src/context/ThemeContext';
import { useI18n } from '../../src/context/I18nContext';
import { useAuth } from '../../src/context/AuthContext';
import { Card, Button, Input } from '../../src/components';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import * as WebBrowser from 'expo-web-browser';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

// Legal URLs
const PRIVACY_POLICY_URL = 'https://sites.google.com/view/skincare-ia-privacy';
const TERMS_OF_SERVICE_URL = 'https://sites.google.com/view/skincare-ia-terms';

export default function ProfileScreen() {
  const { theme, isDarkMode, toggleTheme } = useTheme();
  const { t } = useI18n();
  const { user, token, logout, refreshUser } = useAuth();
  const router = useRouter();
  
  const [deleting, setDeleting] = useState(false);
  
  // Modal states
  const [showNameModal, setShowNameModal] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  
  // Form states
  const [newName, setNewName] = useState(user?.name || '');
  const [newEmail, setNewEmail] = useState(user?.email || '');
  const [emailPassword, setEmailPassword] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

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

  const handleUpdateName = async () => {
    if (!newName.trim() || newName.trim().length < 2) {
      Alert.alert(t('error'), 'Name must be at least 2 characters');
      return;
    }
    setLoading(true);
    try {
      await axios.put(`${API_URL}/api/profile/name`, 
        { name: newName.trim() },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await refreshUser();
      setShowNameModal(false);
      Alert.alert(t('success'), 'Name updated successfully');
    } catch (error: any) {
      Alert.alert(t('error'), error.response?.data?.detail || 'Failed to update name');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateEmail = async () => {
    if (!newEmail.trim() || !emailPassword) {
      Alert.alert(t('error'), 'Please fill in all fields');
      return;
    }
    setLoading(true);
    try {
      await axios.put(`${API_URL}/api/profile/email`, 
        { email: newEmail.trim(), password: emailPassword },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await refreshUser();
      setShowEmailModal(false);
      setEmailPassword('');
      Alert.alert(t('success'), 'Email updated successfully');
    } catch (error: any) {
      Alert.alert(t('error'), error.response?.data?.detail || 'Failed to update email');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdatePassword = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      Alert.alert(t('error'), 'Please fill in all fields');
      return;
    }
    if (newPassword !== confirmPassword) {
      Alert.alert(t('error'), 'Passwords do not match');
      return;
    }
    if (newPassword.length < 6) {
      Alert.alert(t('error'), 'Password must be at least 6 characters');
      return;
    }
    setLoading(true);
    try {
      await axios.put(`${API_URL}/api/profile/password`, 
        { current_password: currentPassword, new_password: newPassword },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setShowPasswordModal(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      Alert.alert(t('success'), 'Password updated successfully');
    } catch (error: any) {
      Alert.alert(t('error'), error.response?.data?.detail || 'Failed to update password');
    } finally {
      setLoading(false);
    }
  };

  const renderModal = (
    visible: boolean,
    onClose: () => void,
    title: string,
    children: React.ReactNode,
    onSubmit: () => void
  ) => (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.modalOverlay}
      >
        <View style={[styles.modalContent, { backgroundColor: theme.card }]}>
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: theme.text }]}>{title}</Text>
            <TouchableOpacity onPress={onClose}>
              <Ionicons name="close" size={24} color={theme.text} />
            </TouchableOpacity>
          </View>
          {children}
          <View style={styles.modalButtons}>
            <Button
              title={t('cancel')}
              onPress={onClose}
              variant="outline"
              style={{ flex: 1, marginRight: 8 }}
            />
            <Button
              title={t('save')}
              onPress={onSubmit}
              loading={loading}
              style={{ flex: 1, marginLeft: 8 }}
            />
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );

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

        {/* Account Settings */}
        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          {t('account_settings') || 'Account Settings'}
        </Text>

        <Card style={styles.settingsCard}>
          {/* Change Name */}
          <TouchableOpacity
            style={styles.settingItem}
            onPress={() => {
              setNewName(user?.name || '');
              setShowNameModal(true);
            }}
          >
            <View style={styles.settingLeft}>
              <View style={[styles.settingIcon, { backgroundColor: theme.primary + '20' }]}>
                <Ionicons name="person-outline" size={20} color={theme.primary} />
              </View>
              <View>
                <Text style={[styles.settingLabel, { color: theme.text }]}>
                  {t('change_name') || 'Change Name'}
                </Text>
                <Text style={[styles.settingValue, { color: theme.textSecondary }]}>
                  {user?.name}
                </Text>
              </View>
            </View>
            <Ionicons name="chevron-forward" size={20} color={theme.textMuted} />
          </TouchableOpacity>

          <View style={[styles.divider, { backgroundColor: theme.border }]} />

          {/* Change Email */}
          <TouchableOpacity
            style={styles.settingItem}
            onPress={() => {
              setNewEmail(user?.email || '');
              setEmailPassword('');
              setShowEmailModal(true);
            }}
          >
            <View style={styles.settingLeft}>
              <View style={[styles.settingIcon, { backgroundColor: theme.info + '20' }]}>
                <Ionicons name="mail-outline" size={20} color={theme.info} />
              </View>
              <View>
                <Text style={[styles.settingLabel, { color: theme.text }]}>
                  {t('change_email') || 'Change Email'}
                </Text>
                <Text style={[styles.settingValue, { color: theme.textSecondary }]}>
                  {user?.email}
                </Text>
              </View>
            </View>
            <Ionicons name="chevron-forward" size={20} color={theme.textMuted} />
          </TouchableOpacity>

          <View style={[styles.divider, { backgroundColor: theme.border }]} />

          {/* Change Password */}
          <TouchableOpacity
            style={styles.settingItem}
            onPress={() => {
              setCurrentPassword('');
              setNewPassword('');
              setConfirmPassword('');
              setShowPasswordModal(true);
            }}
          >
            <View style={styles.settingLeft}>
              <View style={[styles.settingIcon, { backgroundColor: theme.warning + '20' }]}>
                <Ionicons name="lock-closed-outline" size={20} color={theme.warning} />
              </View>
              <Text style={[styles.settingLabel, { color: theme.text }]}>
                {t('change_password') || 'Change Password'}
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={theme.textMuted} />
          </TouchableOpacity>
        </Card>

        {/* Settings */}
        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          {t('settings')}
        </Text>

        <Card style={styles.settingsCard}>
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
          <TouchableOpacity 
            style={styles.settingItem}
            onPress={() => WebBrowser.openBrowserAsync(PRIVACY_POLICY_URL)}
          >
            <View style={styles.settingLeft}>
              <View style={[styles.settingIcon, { backgroundColor: theme.success + '20' }]}>
                <Ionicons name="document-text-outline" size={20} color={theme.success} />
              </View>
              <Text style={[styles.settingLabel, { color: theme.text }]}>
                Privacy Policy
              </Text>
            </View>
            <Ionicons name="open-outline" size={20} color={theme.textMuted} />
          </TouchableOpacity>

          <View style={[styles.divider, { backgroundColor: theme.border }]} />

          <TouchableOpacity 
            style={styles.settingItem}
            onPress={() => WebBrowser.openBrowserAsync(TERMS_OF_SERVICE_URL)}
          >
            <View style={styles.settingLeft}>
              <View style={[styles.settingIcon, { backgroundColor: theme.warning + '20' }]}>
                <Ionicons name="shield-outline" size={20} color={theme.warning} />
              </View>
              <Text style={[styles.settingLabel, { color: theme.text }]}>
                Terms of Service
              </Text>
            </View>
            <Ionicons name="open-outline" size={20} color={theme.textMuted} />
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

      {/* Name Modal */}
      {renderModal(
        showNameModal,
        () => setShowNameModal(false),
        t('change_name') || 'Change Name',
        <Input
          label={t('name')}
          value={newName}
          onChangeText={setNewName}
          placeholder="Your name"
        />,
        handleUpdateName
      )}

      {/* Email Modal */}
      {renderModal(
        showEmailModal,
        () => setShowEmailModal(false),
        t('change_email') || 'Change Email',
        <>
          <Input
            label={t('email')}
            value={newEmail}
            onChangeText={setNewEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            placeholder="your@email.com"
          />
          <Input
            label={t('current_password') || 'Current Password'}
            value={emailPassword}
            onChangeText={setEmailPassword}
            secureTextEntry
            placeholder="Enter your password"
          />
        </>,
        handleUpdateEmail
      )}

      {/* Password Modal */}
      {renderModal(
        showPasswordModal,
        () => setShowPasswordModal(false),
        t('change_password') || 'Change Password',
        <>
          <Input
            label={t('current_password') || 'Current Password'}
            value={currentPassword}
            onChangeText={setCurrentPassword}
            secureTextEntry
            placeholder="••••••••"
          />
          <Input
            label={t('new_password') || 'New Password'}
            value={newPassword}
            onChangeText={setNewPassword}
            secureTextEntry
            placeholder="••••••••"
          />
          <Input
            label={t('confirm_password') || 'Confirm Password'}
            value={confirmPassword}
            onChangeText={setConfirmPassword}
            secureTextEntry
            placeholder="••••••••"
          />
        </>,
        handleUpdatePassword
      )}
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
    flex: 1,
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
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  modalButtons: {
    flexDirection: 'row',
    marginTop: 16,
  },
});
