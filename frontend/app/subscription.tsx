import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Platform,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTheme } from '../src/context/ThemeContext';
import { useI18n } from '../src/context/I18nContext';
import { useAuth } from '../src/context/AuthContext';
import { Card } from '../src/components';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import Constants from 'expo-constants';

const API_URL = Constants.expoConfig?.extra?.apiUrl || process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface SubscriptionInfo {
  plan: string;
  status: string;
  expiresAt?: string;
  willRenew?: boolean;
}

export default function SubscriptionScreen() {
  const { theme } = useTheme();
  const { t } = useI18n();
  const { user, token, refreshUser } = useAuth();
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [subscriptionInfo, setSubscriptionInfo] = useState<SubscriptionInfo | null>(null);

  useEffect(() => {
    fetchSubscriptionInfo();
  }, []);

  const fetchSubscriptionInfo = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/subscription/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setSubscriptionInfo({
        plan: user?.plan || 'free',
        status: response.data.plan === 'premium' ? 'active' : 'inactive',
        expiresAt: response.data.expires_at,
        willRenew: response.data.will_renew,
      });
    } catch (error) {
      console.error('Error fetching subscription:', error);
      setSubscriptionInfo({
        plan: user?.plan || 'free',
        status: 'unknown',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = () => {
    router.push('/paywall');
  };

  const handleManageSubscription = async () => {
    console.log('[Subscription] Manage subscription pressed, Platform:', Platform.OS);
    // Open platform-specific subscription management
    try {
      if (Platform.OS === 'ios') {
        // iOS: Open App Store subscriptions
        const url = 'https://apps.apple.com/account/subscriptions';
        console.log('[Subscription] Opening iOS URL:', url);
        await Linking.openURL(url);
      } else if (Platform.OS === 'android') {
        // Android: Open Play Store subscriptions
        const url = 'https://play.google.com/store/account/subscriptions';
        console.log('[Subscription] Opening Android URL:', url);
        await Linking.openURL(url);
      } else {
        // Web: Show instructions
        const message = 'To manage your subscription:\n\n• iOS: Go to Settings → Apple ID → Subscriptions\n• Android: Go to Play Store → Menu → Subscriptions';
        window.alert(message);
      }
    } catch (error) {
      console.error('[Subscription] Error opening URL:', error);
      Alert.alert('Error', 'Could not open subscription management. Please go to your device settings manually.');
    }
  };

  const handleCancelSubscription = async () => {
    console.log('[Subscription] Cancel subscription pressed, Platform:', Platform.OS);
    // Directly open subscription management where user can cancel
    try {
      if (Platform.OS === 'ios') {
        const url = 'https://apps.apple.com/account/subscriptions';
        console.log('[Subscription] Opening iOS cancel URL:', url);
        await Linking.openURL(url);
      } else if (Platform.OS === 'android') {
        const url = 'https://play.google.com/store/account/subscriptions';
        console.log('[Subscription] Opening Android cancel URL:', url);
        await Linking.openURL(url);
      } else {
        const message = 'To cancel your subscription:\n\n• iOS: Go to Settings → Apple ID → Subscriptions → SkinAdvisor AI → Cancel\n• Android: Go to Play Store → Menu → Subscriptions → SkinAdvisor AI → Cancel';
        window.alert(message);
      }
    } catch (error) {
      console.error('[Subscription] Error opening URL:', error);
      Alert.alert('Error', 'Could not open subscription management. Please go to your device settings manually.');
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.primary} />
          <Text style={[styles.loadingText, { color: theme.textSecondary }]}>
            Loading subscription info...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  const isPremium = user?.plan === 'premium';

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={theme.text} />
        </TouchableOpacity>
        <Text style={[styles.title, { color: theme.text }]}>Subscription</Text>
        <View style={styles.placeholder} />
      </View>

      <ScrollView 
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Current Plan Card */}
        <Card style={styles.planCard}>
          <View style={[
            styles.planBadge, 
            { backgroundColor: isPremium ? '#4CAF50' : theme.primary }
          ]}>
            <Ionicons 
              name={isPremium ? 'star' : 'star-outline'} 
              size={24} 
              color="#FFFFFF" 
            />
          </View>
          
          <Text style={[styles.planTitle, { color: theme.text }]}>
            {isPremium ? 'Premium Plan' : 'Free Plan'}
          </Text>
          
          <Text style={[styles.planStatus, { color: theme.textSecondary }]}>
            {isPremium ? 'Active' : 'Limited Features'}
          </Text>

          {isPremium && subscriptionInfo?.expiresAt && (
            <Text style={[styles.expiryText, { color: theme.textMuted }]}>
              {subscriptionInfo.willRenew ? 'Renews' : 'Expires'}: {new Date(subscriptionInfo.expiresAt).toLocaleDateString()}
            </Text>
          )}
        </Card>

        {/* Features List */}
        <Card style={styles.featuresCard}>
          <Text style={[styles.sectionTitle, { color: theme.text }]}>
            {isPremium ? 'Your Premium Features' : 'Upgrade to Premium'}
          </Text>

          {[
            { icon: 'scan-outline', text: 'Unlimited skin scans', premium: true },
            { icon: 'analytics-outline', text: 'Detailed skin metrics', premium: true },
            { icon: 'fitness-outline', text: '30-day skincare program', premium: true },
            { icon: 'calendar-outline', text: 'Personalized daily routines', premium: true },
            { icon: 'nutrition-outline', text: 'Diet recommendations', premium: true },
            { icon: 'trending-up-outline', text: 'Progress tracking', premium: true },
          ].map((feature, index) => (
            <View key={index} style={styles.featureItem}>
              <Ionicons 
                name={feature.icon as any} 
                size={20} 
                color={isPremium ? '#4CAF50' : theme.textMuted} 
              />
              <Text style={[
                styles.featureText, 
                { color: isPremium ? theme.text : theme.textSecondary }
              ]}>
                {feature.text}
              </Text>
              {isPremium ? (
                <Ionicons name="checkmark-circle" size={20} color="#4CAF50" />
              ) : (
                <Ionicons name="lock-closed" size={18} color={theme.textMuted} />
              )}
            </View>
          ))}
        </Card>

        {/* Action Buttons */}
        <View style={styles.actionsContainer}>
          {!isPremium ? (
            <TouchableOpacity
              style={[styles.upgradeButton, { backgroundColor: theme.primary }]}
              onPress={handleUpgrade}
            >
              <Ionicons name="sparkles" size={20} color="#FFFFFF" />
              <Text style={styles.upgradeButtonText}>Upgrade to Premium</Text>
            </TouchableOpacity>
          ) : (
            <>
              <TouchableOpacity
                style={[styles.manageButton, { backgroundColor: theme.surface, borderColor: theme.border }]}
                onPress={handleManageSubscription}
              >
                <Ionicons name="settings-outline" size={20} color={theme.text} />
                <Text style={[styles.manageButtonText, { color: theme.text }]}>
                  Manage Subscription
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.cancelButton, { backgroundColor: '#FFEBEE' }]}
                onPress={handleCancelSubscription}
              >
                <Ionicons name="close-circle-outline" size={20} color="#D32F2F" />
                <Text style={[styles.cancelButtonText, { color: '#D32F2F' }]}>
                  Cancel Subscription
                </Text>
              </TouchableOpacity>
            </>
          )}
        </View>

        {/* Help Section */}
        <Card style={styles.helpCard}>
          <Text style={[styles.helpTitle, { color: theme.text }]}>
            Need Help?
          </Text>
          <Text style={[styles.helpText, { color: theme.textSecondary }]}>
            If you have any issues with your subscription, please contact our support team.
          </Text>
          <TouchableOpacity
            style={[styles.supportButton, { borderColor: theme.primary }]}
            onPress={() => Linking.openURL('mailto:aziri.603@gmail.com?subject=SkinAdvisor%20AI%20Support')}
          >
            <Ionicons name="mail-outline" size={18} color={theme.primary} />
            <Text style={[styles.supportButtonText, { color: theme.primary }]}>
              Contact Support
            </Text>
          </TouchableOpacity>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  backButton: {
    padding: 8,
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
  },
  placeholder: {
    width: 40,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  planCard: {
    padding: 24,
    alignItems: 'center',
    marginBottom: 16,
  },
  planBadge: {
    width: 64,
    height: 64,
    borderRadius: 32,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  planTitle: {
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 4,
  },
  planStatus: {
    fontSize: 14,
    marginBottom: 8,
  },
  expiryText: {
    fontSize: 12,
  },
  featuresCard: {
    padding: 16,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 16,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
    gap: 12,
  },
  featureText: {
    flex: 1,
    fontSize: 15,
  },
  actionsContainer: {
    gap: 12,
    marginBottom: 16,
  },
  upgradeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 12,
    gap: 8,
  },
  upgradeButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  manageButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1,
    gap: 8,
  },
  manageButtonText: {
    fontSize: 15,
    fontWeight: '600',
  },
  cancelButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 12,
    gap: 8,
  },
  cancelButtonText: {
    fontSize: 15,
    fontWeight: '600',
  },
  restoreButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1,
    gap: 8,
  },
  restoreButtonText: {
    fontSize: 15,
    fontWeight: '600',
  },
  helpCard: {
    padding: 16,
  },
  helpTitle: {
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 8,
  },
  helpText: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 12,
  },
  supportButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    gap: 6,
  },
  supportButtonText: {
    fontSize: 14,
    fontWeight: '600',
  },
});
