import { Platform, Alert } from 'react-native';
import * as AppleAuthentication from 'expo-apple-authentication';
import * as AuthSession from 'expo-auth-session';
import * as Crypto from 'expo-crypto';
import Constants from 'expo-constants';

// Google OAuth Configuration
const GOOGLE_CLIENT_ID = Constants.expoConfig?.extra?.googleClientId || 
  '993166704619-53mfiq1gbd8s0u1h6p5n14om3t3hd13t.apps.googleusercontent.com';

// For iOS Google Sign-In, you may need a separate iOS client ID
const GOOGLE_IOS_CLIENT_ID = GOOGLE_CLIENT_ID;

// Discovery document for Google OAuth
const discovery = {
  authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
  tokenEndpoint: 'https://oauth2.googleapis.com/token',
  revocationEndpoint: 'https://oauth2.googleapis.com/revoke',
};

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
   * Sign in with Google using OAuth
   */
  async signInWithGoogle(): Promise<SocialAuthResult> {
    try {
      // Generate a secure random state
      const state = await Crypto.digestStringAsync(
        Crypto.CryptoDigestAlgorithm.SHA256,
        Math.random().toString()
      );

      // Create the redirect URI
      const redirectUri = AuthSession.makeRedirectUri({
        scheme: 'skinadvisor',
        path: 'auth',
      });

      console.log('[SocialAuth] Google redirect URI:', redirectUri);

      // Create auth request
      const request = new AuthSession.AuthRequest({
        clientId: Platform.OS === 'ios' ? GOOGLE_IOS_CLIENT_ID : GOOGLE_CLIENT_ID,
        redirectUri,
        scopes: ['openid', 'profile', 'email'],
        responseType: AuthSession.ResponseType.Token,
        state,
      });

      // Prompt user for authentication
      const result = await request.promptAsync(discovery);

      if (result.type === 'success' && result.authentication) {
        const { accessToken } = result.authentication;
        
        // Fetch user info from Google
        const userInfoResponse = await fetch(
          'https://www.googleapis.com/oauth2/v3/userinfo',
          {
            headers: { Authorization: `Bearer ${accessToken}` },
          }
        );

        if (!userInfoResponse.ok) {
          throw new Error('Failed to fetch user info from Google');
        }

        const userInfo = await userInfoResponse.json();

        return {
          success: true,
          provider: 'google',
          user: {
            id: userInfo.sub,
            email: userInfo.email,
            name: userInfo.name,
            photo: userInfo.picture,
          },
          idToken: accessToken,
        };
      } else if (result.type === 'cancel') {
        return {
          success: false,
          provider: 'google',
          error: 'User cancelled',
        };
      } else {
        return {
          success: false,
          provider: 'google',
          error: result.type === 'error' ? result.error?.message : 'Authentication failed',
        };
      }
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
   * Sign in with Apple (iOS only)
   */
  async signInWithApple(): Promise<SocialAuthResult> {
    try {
      // Check if Apple authentication is available
      const isAvailable = await AppleAuthentication.isAvailableAsync();
      
      if (!isAvailable) {
        return {
          success: false,
          provider: 'apple',
          error: 'Apple Sign In is not available on this device',
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

      // Construct the name if provided
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
          name: name,
        },
        idToken: identityToken || undefined,
      };
    } catch (error: any) {
      console.error('[SocialAuth] Apple sign-in error:', error);
      
      if (error.code === 'ERR_REQUEST_CANCELED') {
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
