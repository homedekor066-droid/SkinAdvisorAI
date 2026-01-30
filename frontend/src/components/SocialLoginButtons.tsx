import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';

interface SocialLoginButtonsProps {
  onGooglePress: () => void;
  onApplePress: () => void;
  loading?: boolean;
}

export function SocialLoginButtons({
  onGooglePress,
  onApplePress,
  loading = false,
}: SocialLoginButtonsProps) {
  const { theme, isDarkMode } = useTheme();

  const handleGooglePress = () => {
    console.log('[SocialLoginButtons] Google button pressed');
    if (!loading) {
      onGooglePress();
    }
  };

  const handleApplePress = () => {
    console.log('[SocialLoginButtons] Apple button pressed');
    if (!loading) {
      onApplePress();
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.dividerContainer}>
        <View style={[styles.divider, { backgroundColor: theme.border }]} />
        <Text style={[styles.dividerText, { color: theme.textSecondary }]}>
          or continue with
        </Text>
        <View style={[styles.divider, { backgroundColor: theme.border }]} />
      </View>

      <View style={styles.buttonsContainer}>
        {/* Google Sign In */}
        <TouchableOpacity
          style={[
            styles.socialButton,
            { 
              backgroundColor: theme.card,
              borderColor: theme.border,
              opacity: loading ? 0.6 : 1,
            }
          ]}
          onPress={handleGooglePress}
          disabled={loading}
          activeOpacity={0.7}
        >
          {loading ? (
            <ActivityIndicator size="small" color={theme.primary} />
          ) : (
            <>
              <View style={styles.googleIcon}>
                <Text style={styles.googleG}>G</Text>
              </View>
              <Text style={[styles.buttonText, { color: theme.text }]}>
                Google
              </Text>
            </>
          )}
        </TouchableOpacity>

        {/* Apple Sign In */}
        <TouchableOpacity
          style={[
            styles.socialButton,
            { 
              backgroundColor: isDarkMode ? '#FFFFFF' : '#000000',
              borderColor: isDarkMode ? '#FFFFFF' : '#000000',
              opacity: loading ? 0.6 : 1,
            }
          ]}
          onPress={handleApplePress}
          disabled={loading}
          activeOpacity={0.7}
        >
          {loading ? (
            <ActivityIndicator size="small" color={isDarkMode ? '#000000' : '#FFFFFF'} />
          ) : (
            <>
              <Ionicons 
                name="logo-apple" 
                size={20} 
                color={isDarkMode ? '#000000' : '#FFFFFF'} 
              />
              <Text style={[
                styles.buttonText, 
                { color: isDarkMode ? '#000000' : '#FFFFFF' }
              ]}>
                Apple
              </Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginVertical: 24,
  },
  dividerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  divider: {
    flex: 1,
    height: 1,
  },
  dividerText: {
    paddingHorizontal: 16,
    fontSize: 14,
  },
  buttonsContainer: {
    flexDirection: 'row',
    gap: 12,
  },
  socialButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1,
    gap: 8,
  },
  googleIcon: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#E0E0E0',
  },
  googleG: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#4285F4',
  },
  buttonText: {
    fontSize: 15,
    fontWeight: '600',
  },
});
