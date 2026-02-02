import { Platform } from 'react-native';
import * as AppleAuthentication from 'expo-apple-authentication';
import * as WebBrowser from 'expo-web-browser';
import * as AuthSession from 'expo-auth-session';

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
   * Sign in with Google using Expo AuthSession
   * Updated: Removed deprecated useProxy option
   */
  async signInWithGoogle(): Promise<SocialAuthResult> {
    try {
      // Generate redirect URI based on platform
      // For Expo Go: exp://192.168.x.x:8081/--/
      // For standalone: skinadvisor://
      const redirectUri = AuthSession.makeRedirectUri({
        scheme: 'skinadvisor',
        path: 'oauth',
      });

      console.log('[Google Auth] Redirect URI:', redirectUri);
      console.log('[Google Auth] Platform:', Platform.OS);

      // Select the appropriate client ID based on platform
      let clientId: string;
      if (Platform.OS === 'ios') {
        clientId = GOOGLE_IOS_CLIENT_ID;
      } else if (Platform.OS === 'android') {
        clientId = GOOGLE_ANDROID_CLIENT_ID;
      } else {
        clientId = GOOGLE_WEB_CLIENT_ID;
      }

      console.log('[Google Auth] Using client ID for platform:', Platform.OS);

      // Create discovery document for Google
      const discovery = {
        authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
        tokenEndpoint: 'https://oauth2.googleapis.com/token',
        revocationEndpoint: 'https://oauth2.googleapis.com/revoke',
      };

      // Build authorization request
      const authRequest = new AuthSession.AuthRequest({
        clientId,
        redirectUri,
        scopes: ['openid', 'profile', 'email'],
        responseType: AuthSession.ResponseType.Token,
        usePKCE: false,
      });

      console.log('[Google Auth] Starting auth request...');

      // Prompt the user to authenticate
      const result = await authRequest.promptAsync(discovery);

      console.log('[Google Auth] Result type:', result.type);

      if (result.type === 'success') {
        const { access_token, id_token } = result.params;
        const token = access_token || id_token;

        console.log('[Google Auth] Token received:', !!token);

        if (token) {
          // Fetch user info from Google
          const userInfoResponse = await fetch(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            {
              headers: { Authorization: `Bearer ${token}` },
            }
          );

          if (!userInfoResponse.ok) {
            const errorText = await userInfoResponse.text();
            console.error('[Google Auth] User info fetch failed:', errorText);
            throw new Error('Failed to fetch user info from Google');
          }

          const userInfo: GoogleUserInfo = await userInfoResponse.json();
          console.log('[Google Auth] User info received:', userInfo.email);

          return {
            success: true,
            provider: 'google',
            user: {
              id: userInfo.sub,
              email: userInfo.email,
              name: userInfo.name,
              photo: userInfo.picture,
            },
            idToken: token,
          };
        }

        return {
          success: false,
          provider: 'google',
          error: 'No access token received from Google',
        };
      } else if (result.type === 'cancel' || result.type === 'dismiss') {
        return {
          success: false,
          provider: 'google',
          error: 'User cancelled',
        };
      } else if (result.type === 'error') {
        console.error('[Google Auth] Error:', result.error);
        return {
          success: false,
          provider: 'google',
          error: result.error?.message || 'Google authentication failed',
        };
      } else {
        console.log('[Google Auth] Unexpected result:', JSON.stringify(result));
        return {
          success: false,
          provider: 'google',
          error: 'Authentication failed - please try again',
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
   * Get the redirect URI that needs to be added to Google Cloud Console
   */
  getGoogleRedirectUri(): string {
    const redirectUri = AuthSession.makeRedirectUri({
      scheme: 'skinadvisor',
      path: 'oauth',
    });
    return redirectUri;
  }

  /**
   * Sign in with Apple (iOS 13+ only)
   */
  async signInWithApple(): Promise<SocialAuthResult> {
    console.log('[Apple Auth] Starting Apple Sign-In...');
    
    try {
      // Check if Apple authentication is available
      const isAvailable = await AppleAuthentication.isAvailableAsync();
      console.log('[Apple Auth] Available:', isAvailable);

      if (!isAvailable) {
        return {
          success: false,
          provider: 'apple',
          error: 'Apple Sign In is only available on iOS 13+ devices',
        };
      }

      console.log('[Apple Auth] Requesting authentication...');

      // Request authentication
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });

      console.log('[Apple Auth] Got credential:', credential.user);

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
