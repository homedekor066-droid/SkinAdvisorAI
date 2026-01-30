import { Platform } from 'react-native';
import * as AppleAuthentication from 'expo-apple-authentication';
import * as WebBrowser from 'expo-web-browser';
import * as AuthSession from 'expo-auth-session';
import * as Google from 'expo-auth-session/providers/google';

// Ensure web browser can complete auth session
WebBrowser.maybeCompleteAuthSession();

// Google OAuth Configuration
const GOOGLE_WEB_CLIENT_ID = '993166704619-53mfiq1gbd8s0u1h6p5n14om3t3hd13t.apps.googleusercontent.com';
const GOOGLE_IOS_CLIENT_ID = '993166704619-7tu3f44t4n2a1sqs3g50uvedc4d87rls.apps.googleusercontent.com';
const GOOGLE_ANDROID_CLIENT_ID = '993166704619-f4afgb5e86av4k7pregoasvkcogbnjvs.apps.googleusercontent.com';

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

// Google user info response type
interface GoogleUserInfo {
  sub: string;
  email: string;
  name: string;
  picture?: string;
}

class SocialAuthService {
  /**
   * Sign in with Google using expo-auth-session
   */
  async signInWithGoogle(): Promise<SocialAuthResult> {
    try {
      // Create the redirect URI
      const redirectUri = AuthSession.makeRedirectUri({
        scheme: 'skinadvisor',
        path: 'auth/google',
      });

      console.log('[Google Auth] Redirect URI:', redirectUri);

      // Get the appropriate client ID based on platform
      const clientId = Platform.select({
        ios: GOOGLE_IOS_CLIENT_ID,
        android: GOOGLE_ANDROID_CLIENT_ID,
        default: GOOGLE_WEB_CLIENT_ID,
      });

      // Create auth request
      const discovery = {
        authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
        tokenEndpoint: 'https://oauth2.googleapis.com/token',
        revocationEndpoint: 'https://oauth2.googleapis.com/revoke',
      };

      const request = new AuthSession.AuthRequest({
        clientId: clientId!,
        redirectUri,
        scopes: ['openid', 'profile', 'email'],
        responseType: AuthSession.ResponseType.Token,
      });

      // Prompt user for authentication
      const result = await request.promptAsync(discovery);

      console.log('[Google Auth] Result type:', result.type);

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

        const userInfo: GoogleUserInfo = await userInfoResponse.json();

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
      } else if (result.type === 'cancel' || result.type === 'dismiss') {
        return {
          success: false,
          provider: 'google',
          error: 'User cancelled',
        };
      } else {
        return {
          success: false,
          provider: 'google',
          error: 'Authentication failed',
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
