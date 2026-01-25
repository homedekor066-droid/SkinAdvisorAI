import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  TouchableOpacity,
  Alert,
  ScrollView,
  Modal,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '../../src/context/ThemeContext';
import { useI18n } from '../../src/context/I18nContext';
import { useAuth } from '../../src/context/AuthContext';
import { Button, Input } from '../../src/components';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export default function LoginScreen() {
  const { theme } = useTheme();
  const { t } = useI18n();
  const { login } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  
  // Forgot password states
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [resetEmail, setResetEmail] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [resetStep, setResetStep] = useState<'email' | 'token' | 'success'>('email');
  const [resetLoading, setResetLoading] = useState(false);

  const validate = () => {
    const newErrors: { email?: string; password?: string } = {};
    if (!email) newErrors.email = 'Email is required';
    else if (!/\S+@\S+\.\S+/.test(email)) newErrors.email = 'Invalid email';
    if (!password) newErrors.password = 'Password is required';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleLogin = async () => {
    if (!validate()) return;

    setLoading(true);
    try {
      await login(email, password);
      router.replace('/(tabs)/home');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Login failed';
      Alert.alert(t('error'), message);
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async () => {
    if (!resetEmail.trim()) {
      Alert.alert(t('error'), 'Please enter your email');
      return;
    }
    
    setResetLoading(true);
    try {
      const response = await axios.post(`${API_URL}/api/auth/forgot-password`, {
        email: resetEmail.trim()
      });
      
      // In production, token would be sent via email
      // For demo, we show the token directly
      if (response.data.reset_token) {
        setResetToken(response.data.reset_token);
        setResetStep('token');
        Alert.alert(
          'Reset Token Generated',
          'In production, this would be sent to your email. For this demo, the token has been pre-filled.'
        );
      } else {
        Alert.alert(t('success'), response.data.message);
        setResetStep('token');
      }
    } catch (error: any) {
      Alert.alert(t('error'), error.response?.data?.detail || 'Failed to send reset email');
    } finally {
      setResetLoading(false);
    }
  };

  const handleResetPassword = async () => {
    if (!resetToken.trim()) {
      Alert.alert(t('error'), 'Please enter the reset token');
      return;
    }
    if (!newPassword || newPassword.length < 6) {
      Alert.alert(t('error'), 'Password must be at least 6 characters');
      return;
    }
    if (newPassword !== confirmNewPassword) {
      Alert.alert(t('error'), 'Passwords do not match');
      return;
    }
    
    setResetLoading(true);
    try {
      await axios.post(`${API_URL}/api/auth/reset-password`, {
        token: resetToken.trim(),
        new_password: newPassword
      });
      
      setResetStep('success');
      setTimeout(() => {
        closeForgotModal();
        Alert.alert(t('success'), 'Password reset successfully. You can now login with your new password.');
      }, 1500);
    } catch (error: any) {
      Alert.alert(t('error'), error.response?.data?.detail || 'Failed to reset password');
    } finally {
      setResetLoading(false);
    }
  };

  const closeForgotModal = () => {
    setShowForgotModal(false);
    setResetEmail('');
    setResetToken('');
    setNewPassword('');
    setConfirmNewPassword('');
    setResetStep('email');
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.header}>
            <View style={[styles.logoContainer, { backgroundColor: theme.primary }]}>
              <Ionicons name="sparkles" size={40} color="#FFFFFF" />
            </View>
            <Text style={[styles.title, { color: theme.text }]}>{t('app_name')}</Text>
            <Text style={[styles.subtitle, { color: theme.textSecondary }]}>
              {t('welcome')}
            </Text>
          </View>

          <View style={styles.form}>
            <Input
              label={t('email')}
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              error={errors.email}
              placeholder="your@email.com"
            />

            <View>
              <Input
                label={t('password')}
                value={password}
                onChangeText={setPassword}
                secureTextEntry={!showPassword}
                error={errors.password}
                placeholder="••••••••"
              />
              <TouchableOpacity
                style={styles.eyeButton}
                onPress={() => setShowPassword(!showPassword)}
              >
                <Ionicons
                  name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                  size={20}
                  color={theme.textSecondary}
                />
              </TouchableOpacity>
            </View>

            {/* Forgot Password Link */}
            <TouchableOpacity
              style={styles.forgotButton}
              onPress={() => {
                setResetEmail(email);
                setShowForgotModal(true);
              }}
            >
              <Text style={[styles.forgotText, { color: theme.primary }]}>
                {t('forgot_password') || 'Forgot Password?'}
              </Text>
            </TouchableOpacity>

            <Button
              title={t('login')}
              onPress={handleLogin}
              loading={loading}
              style={{ marginTop: 8 }}
            />

            <View style={styles.footer}>
              <Text style={[styles.footerText, { color: theme.textSecondary }]}>
                Don't have an account?{' '}
              </Text>
              <TouchableOpacity onPress={() => router.push('/(auth)/register')}>
                <Text style={[styles.linkText, { color: theme.primary }]}>
                  {t('register')}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>

      {/* Forgot Password Modal */}
      <Modal
        visible={showForgotModal}
        animationType="slide"
        transparent={true}
        onRequestClose={closeForgotModal}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalOverlay}
        >
          <View style={[styles.modalContent, { backgroundColor: theme.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: theme.text }]}>
                {t('reset_password') || 'Reset Password'}
              </Text>
              <TouchableOpacity onPress={closeForgotModal}>
                <Ionicons name="close" size={24} color={theme.text} />
              </TouchableOpacity>
            </View>

            {resetStep === 'email' && (
              <>
                <Text style={[styles.modalDescription, { color: theme.textSecondary }]}>
                  Enter your email address and we'll send you a reset link.
                </Text>
                <Input
                  label={t('email')}
                  value={resetEmail}
                  onChangeText={setResetEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  placeholder="your@email.com"
                />
                <Button
                  title={t('send_reset_link') || 'Send Reset Link'}
                  onPress={handleForgotPassword}
                  loading={resetLoading}
                  style={{ marginTop: 16 }}
                />
              </>
            )}

            {resetStep === 'token' && (
              <>
                <Text style={[styles.modalDescription, { color: theme.textSecondary }]}>
                  Enter the reset token and your new password.
                </Text>
                <Input
                  label="Reset Token"
                  value={resetToken}
                  onChangeText={setResetToken}
                  placeholder="Enter reset token"
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
                  value={confirmNewPassword}
                  onChangeText={setConfirmNewPassword}
                  secureTextEntry
                  placeholder="••••••••"
                />
                <View style={styles.modalButtons}>
                  <Button
                    title="Back"
                    onPress={() => setResetStep('email')}
                    variant="outline"
                    style={{ flex: 1, marginRight: 8 }}
                  />
                  <Button
                    title={t('reset_password') || 'Reset Password'}
                    onPress={handleResetPassword}
                    loading={resetLoading}
                    style={{ flex: 1, marginLeft: 8 }}
                  />
                </View>
              </>
            )}

            {resetStep === 'success' && (
              <View style={styles.successContainer}>
                <View style={[styles.successIcon, { backgroundColor: theme.success + '20' }]}>
                  <Ionicons name="checkmark-circle" size={48} color={theme.success} />
                </View>
                <Text style={[styles.successText, { color: theme.text }]}>
                  Password Reset Successfully!
                </Text>
              </View>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingTop: 40,
    paddingBottom: 24,
  },
  header: {
    alignItems: 'center',
    marginBottom: 40,
  },
  logoContainer: {
    width: 80,
    height: 80,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
  },
  form: {
    flex: 1,
  },
  eyeButton: {
    position: 'absolute',
    right: 16,
    top: 42,
  },
  forgotButton: {
    alignSelf: 'flex-end',
    marginTop: -8,
    marginBottom: 8,
    paddingVertical: 4,
  },
  forgotText: {
    fontSize: 14,
    fontWeight: '500',
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 24,
  },
  footerText: {
    fontSize: 14,
  },
  linkText: {
    fontSize: 14,
    fontWeight: '600',
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
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  modalDescription: {
    fontSize: 14,
    marginBottom: 20,
    lineHeight: 20,
  },
  modalButtons: {
    flexDirection: 'row',
    marginTop: 16,
  },
  successContainer: {
    alignItems: 'center',
    paddingVertical: 32,
  },
  successIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  successText: {
    fontSize: 18,
    fontWeight: '600',
  },
});
