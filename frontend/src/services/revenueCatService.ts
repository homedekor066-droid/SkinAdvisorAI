import { Platform } from 'react-native';
import Purchases, { 
  CustomerInfo, 
  PurchasesOfferings, 
  PurchasesPackage,
  LOG_LEVEL 
} from 'react-native-purchases';

// RevenueCat API Keys
const REVENUECAT_API_KEY = 'test_UFrvEOtYX3vxvCdKOhjqgykcgKj';

// Entitlement ID for premium access
const PREMIUM_ENTITLEMENT_ID = 'premium';

class RevenueCatService {
  private initialized = false;

  /**
   * Initialize RevenueCat SDK
   * Call this once at app startup
   */
  async initialize(): Promise<void> {
    if (this.initialized) {
      console.log('[RevenueCat] Already initialized');
      return;
    }

    try {
      // Set log level for debugging
      if (__DEV__) {
        Purchases.setLogLevel(LOG_LEVEL.DEBUG);
      }

      // Configure RevenueCat
      // Using the same key for both platforms during development
      // In production, use platform-specific keys
      await Purchases.configure({
        apiKey: REVENUECAT_API_KEY,
      });

      this.initialized = true;
      console.log('[RevenueCat] Initialized successfully');
    } catch (error) {
      console.error('[RevenueCat] Initialization failed:', error);
      throw error;
    }
  }

  /**
   * Login user to RevenueCat
   * Links purchases to user account
   */
  async login(userId: string): Promise<CustomerInfo> {
    try {
      const { customerInfo } = await Purchases.logIn(userId);
      console.log('[RevenueCat] User logged in:', userId);
      return customerInfo;
    } catch (error) {
      console.error('[RevenueCat] Login failed:', error);
      throw error;
    }
  }

  /**
   * Logout user from RevenueCat
   * Creates new anonymous user
   */
  async logout(): Promise<CustomerInfo> {
    try {
      const customerInfo = await Purchases.logOut();
      console.log('[RevenueCat] User logged out');
      return customerInfo;
    } catch (error) {
      console.error('[RevenueCat] Logout failed:', error);
      throw error;
    }
  }

  /**
   * Get available subscription offerings
   */
  async getOfferings(): Promise<PurchasesOfferings> {
    try {
      const offerings = await Purchases.getOfferings();
      console.log('[RevenueCat] Offerings fetched:', offerings);
      return offerings;
    } catch (error) {
      console.error('[RevenueCat] Failed to get offerings:', error);
      throw error;
    }
  }

  /**
   * Get current customer info (subscription status)
   */
  async getCustomerInfo(): Promise<CustomerInfo> {
    try {
      const customerInfo = await Purchases.getCustomerInfo();
      return customerInfo;
    } catch (error) {
      console.error('[RevenueCat] Failed to get customer info:', error);
      throw error;
    }
  }

  /**
   * Check if user has active premium subscription
   */
  async isPremiumUser(): Promise<boolean> {
    try {
      const customerInfo = await this.getCustomerInfo();
      return customerInfo.entitlements.active[PREMIUM_ENTITLEMENT_ID] !== undefined;
    } catch (error) {
      console.error('[RevenueCat] Failed to check premium status:', error);
      return false;
    }
  }

  /**
   * Purchase a subscription package
   */
  async purchasePackage(pkg: PurchasesPackage): Promise<{
    success: boolean;
    customerInfo?: CustomerInfo;
    error?: string;
    userCancelled?: boolean;
  }> {
    try {
      const { customerInfo } = await Purchases.purchasePackage(pkg);
      
      const isPremium = customerInfo.entitlements.active[PREMIUM_ENTITLEMENT_ID] !== undefined;
      
      console.log('[RevenueCat] Purchase successful, isPremium:', isPremium);
      
      return {
        success: isPremium,
        customerInfo,
      };
    } catch (error: any) {
      console.error('[RevenueCat] Purchase failed:', error);
      
      // Check if user cancelled
      if (error.userCancelled) {
        return {
          success: false,
          userCancelled: true,
        };
      }
      
      return {
        success: false,
        error: error.message || 'Purchase failed',
      };
    }
  }

  /**
   * Restore previous purchases
   */
  async restorePurchases(): Promise<{
    success: boolean;
    isPremium: boolean;
    customerInfo?: CustomerInfo;
    error?: string;
  }> {
    try {
      const customerInfo = await Purchases.restorePurchases();
      const isPremium = customerInfo.entitlements.active[PREMIUM_ENTITLEMENT_ID] !== undefined;
      
      console.log('[RevenueCat] Restore successful, isPremium:', isPremium);
      
      return {
        success: true,
        isPremium,
        customerInfo,
      };
    } catch (error: any) {
      console.error('[RevenueCat] Restore failed:', error);
      return {
        success: false,
        isPremium: false,
        error: error.message || 'Restore failed',
      };
    }
  }

  /**
   * Add listener for customer info updates
   */
  addCustomerInfoUpdateListener(listener: (customerInfo: CustomerInfo) => void): void {
    Purchases.addCustomerInfoUpdateListener(listener);
  }

  /**
   * Remove listener for customer info updates
   */
  removeCustomerInfoUpdateListener(listener: (customerInfo: CustomerInfo) => void): void {
    Purchases.removeCustomerInfoUpdateListener(listener);
  }

  /**
   * Get subscription management URL (for iOS)
   */
  async getManagementURL(): Promise<string | null> {
    try {
      const customerInfo = await this.getCustomerInfo();
      return customerInfo.managementURL;
    } catch (error) {
      console.error('[RevenueCat] Failed to get management URL:', error);
      return null;
    }
  }
}

export const revenueCatService = new RevenueCatService();
