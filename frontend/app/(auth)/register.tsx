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
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '../../src/context/ThemeContext';
import { useI18n } from '../../src/context/I18nContext';
import { useAuth } from '../../src/context/AuthContext';
import { Button, Input, SocialLoginButtons } from '../../src/components';
import { Ionicons } from '@expo/vector-icons';
import { socialAuthService } from '../../src/services/socialAuthService';

export default function RegisterScreen() {
  const { theme } = useTheme();
  const { t, language } = useI18n();
  const { register, socialAuth } = useAuth();
  const router = useRouter();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [socialLoading, setSocialLoading] = useState(false);
  const [errors, setErrors] = useState<{
    name?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
  }>({});

  // Social login handlers
  const handleGoogleSignUp = async () => {
    setSocialLoading(true);
    try {
      const result = await socialAuthService.signInWithGoogle();
      
      if (result.success && result.user) {
        await socialAuth({
          provider: 'google',
          provider_id: result.user.id,
          email: result.user.email,
          name: result.user.name,
          id_token: result.idToken,
          language: language,
        });
        // Navigate to language selection for new social sign-ups
        router.replace('/language-selection');
      } else if (result.error !== 'User cancelled') {
        Alert.alert('Google Sign Up Failed', result.error || 'Unknown error occurred');
      }
    } catch (error: any) {
      console.error('[Register] Google sign-up error:', error);
      Alert.alert('Error', error.message || 'Failed to sign up with Google');
    } finally {
      setSocialLoading(false);
    }
  };

  const handleAppleSignUp = async () => {
    setSocialLoading(true);
    try {
      const result = await socialAuthService.signInWithApple();
      
      if (result.success && result.user) {
        await socialAuth({
          provider: 'apple',
          provider_id: result.user.id,
          email: result.user.email,
          name: result.user.name,
          id_token: result.idToken,
          language: language,
        });
        // Navigate to language selection for new social sign-ups
        router.replace('/language-selection');
      } else if (result.error !== 'User cancelled') {
        Alert.alert('Apple Sign Up Failed', result.error || 'Unknown error occurred');
      }
    } catch (error: any) {
      console.error('[Register] Apple sign-up error:', error);
      Alert.alert('Error', error.message || 'Failed to sign up with Apple');
    } finally {
      setSocialLoading(false);
    }
  };

  const validate = () => {
    const newErrors: typeof errors = {};
    if (!name) newErrors.name = 'Name is required';
    if (!email) newErrors.email = 'Email is required';
    else if (!/\S+@\S+\.\S+/.test(email)) newErrors.email = 'Invalid email';
    if (!password) newErrors.password = 'Password is required';
    else if (password.length < 6) newErrors.password = 'Password must be at least 6 characters';
    if (password !== confirmPassword) newErrors.confirmPassword = 'Passwords do not match';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleRegister = async () => {
    console.log('[Register] handleRegister called');
    console.log('[Register] name:', name, 'email:', email, 'password:', password?.length, 'confirm:', confirmPassword?.length);
    
    if (!validate()) {
      console.log('[Register] Validation failed:', errors);
      return;
    }

    console.log('[Register] Validation passed, starting registration...');
    setLoading(true);
    try {
      await register(name, email, password, language);
      console.log('[Register] Registration successful, navigating...');
      // Navigate to language selection after registration
      router.replace('/language-selection');
    } catch (error: any) {
      console.log('[Register] Registration error:', error);
      const message = error.response?.data?.detail || 'Registration failed';
      Alert.alert(t('error'), message);
    } finally {
      setLoading(false);
    }
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
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => router.back()}
          >
            <Ionicons name="arrow-back" size={24} color={theme.text} />
          </TouchableOpacity>

          <View style={styles.header}>
            <Text style={[styles.title, { color: theme.text }]}>
              {t('register')}
            </Text>
            <Text style={[styles.subtitle, { color: theme.textSecondary }]}>
              Create your account
            </Text>
          </View>

          <View style={styles.form}>
            <Input
              label={t('name')}
              value={name}
              onChangeText={setName}
              error={errors.name}
              placeholder="Your name"
            />

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

            <Input
              label="Confirm Password"
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              secureTextEntry={!showPassword}
              error={errors.confirmPassword}
              placeholder="••••••••"
            />

            <Button
              title={t('register')}
              onPress={handleRegister}
              loading={loading}
              style={{ marginTop: 16 }}
            />

            {/* Social Sign Up Options */}
            <SocialLoginButtons
              onGooglePress={handleGoogleSignUp}
              onApplePress={handleAppleSignUp}
              loading={loading || socialLoading}
            />

            <View style={styles.footer}>
              <Text style={[styles.footerText, { color: theme.textSecondary }]}>
                Already have an account?{' '}
              </Text>
              <TouchableOpacity onPress={() => router.back()}>
                <Text style={[styles.linkText, { color: theme.primary }]}>
                  {t('login')}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
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
    paddingTop: 16,
    paddingBottom: 24,
  },
  backButton: {
    width: 40,
    height: 40,
    justifyContent: 'center',
  },
  header: {
    marginBottom: 32,
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
});
