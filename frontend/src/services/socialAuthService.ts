import { Platform, Alert } from 'react-native';
import * as AppleAuthentication from 'expo-apple-authentication';
import * as WebBrowser from 'expo-web-browser';
import * as Google from 'expo-auth-session/providers/google';
import Constants from 'expo-constants';

// Ensure web browser can complete auth session
WebBrowser.maybeCompleteAuthSession();

// Google OAuth Configuration - You need BOTH Web AND iOS client IDs
// Web Client ID (for Expo Go and web)
const GOOGLE_WEB_CLIENT_ID = '993166704619-53mfiq1gbd8s0u1h6p5n14om3t3hd13t.apps.googleusercontent.com';

// iOS Client ID - NEEDS TO BE CREATED in Google Cloud Console
// Go to: https://console.cloud.google.com/apis/credentials
// Create OAuth 2.0 Client ID -> iOS -> Bundle ID: com.skinadvisor.ai
const GOOGLE_IOS_CLIENT_ID = ''; // You need to create this!

export interface SocialAuthResult {
  success: boolean;
  provider: 'google' | 'apple';
  user?: {
    id: string;
    email: string | null;
    name: string | null;
    photo?: string | null;
  };
  idToken?: string;
  error?: string;
}

class SocialAuthService {
  /**
   * Sign in with Google
   * NOTE: For this to work on iOS, you need to create an iOS OAuth Client ID
   */
  async signInWithGoogle(): Promise<SocialAuthResult> {
    try {
      // Show alert explaining the setup needed
      if (Platform.OS === 'ios' && !GOOGLE_IOS_CLIENT_ID) {
        return {
          success: false,
          provider: 'google',
          error: 'Google Sign-In requires iOS Client ID setup. Please follow the setup guide.',
        };
      }

      return {
        success: false,
        provider: 'google',
        error: 'Google Sign-In is being configured. Please use email login for now.',
      };
    } catch (error: any) {
      console.error('[SocialAuth] Google sign-in error:', error);
      return {
        success: false,
        provider: 'google',
        error: error.message || 'Google sign-in failed',
      };
    }
  }

  /**
   * Sign in with Apple (iOS 13+ only)
   */
  async signInWithApple(): Promise<SocialAuthResult> {
    try {
      // Check if Apple authentication is available
      const isAvailable = await AppleAuthentication.isAvailableAsync();
      
      if (!isAvailable) {
        return {
          success: false,
          provider: 'apple',
          error: 'Apple Sign In is only available on iOS 13+ devices',
        };
      }

      // Request authentication
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });

      // Extract user info
      const { user, email, fullName, identityToken } = credential;

      // Construct the name if provided (Apple only sends name on FIRST sign-in)
      let name: string | null = null;
      if (fullName) {
        const nameParts = [fullName.givenName, fullName.familyName].filter(Boolean);
        name = nameParts.length > 0 ? nameParts.join(' ') : null;
      }

      return {
        success: true,
        provider: 'apple',
        user: {
          id: user,
          email: email,
          name: name || 'Apple User',
        },
        idToken: identityToken || undefined,
      };
    } catch (error: any) {
      console.error('[SocialAuth] Apple sign-in error:', error);
      
      if (error.code === 'ERR_REQUEST_CANCELED' || error.code === 'ERR_CANCELED') {
        return {
          success: false,
          provider: 'apple',
          error: 'User cancelled',
        };
      }

      return {
        success: false,
        provider: 'apple',
        error: error.message || 'Apple sign-in failed',
      };
    }
  }

  /**
   * Check if Apple Sign In is available
   */
  async isAppleSignInAvailable(): Promise<boolean> {
    try {
      return await AppleAuthentication.isAvailableAsync();
    } catch {
      return false;
    }
  }
}

export const socialAuthService = new SocialAuthService();
