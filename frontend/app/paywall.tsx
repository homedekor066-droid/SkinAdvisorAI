import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useTheme } from '../src/context/ThemeContext';
import { useAuth } from '../src/context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';

const { width } = Dimensions.get('window');

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface PricingOption {
  id: string;
  name: string;
  price: string;
  period: string;
  savings?: string;
  popular?: boolean;
}

const pricingOptions: PricingOption[] = [
  {
    id: 'yearly',
    name: 'Yearly',
    price: '€59.99',
    period: '/year',
    savings: 'Save 50%',
    popular: true,
  },
  {
    id: 'monthly',
    name: 'Monthly',
    price: '€9.99',
    period: '/month',
  },
];

const features = [
  { icon: 'calendar-outline', text: 'Full daily skincare routine' },
  { icon: 'nutrition-outline', text: 'Personalized diet & foods to avoid' },
  { icon: 'scan-outline', text: 'Unlimited skin scans' },
  { icon: 'analytics-outline', text: 'Progress tracking & before/after' },
  { icon: 'leaf-outline', text: 'Product recommendations' },
  { icon: 'document-text-outline', text: 'Detailed explanations' },
];

export default function PaywallScreen() {
  const { theme } = useTheme();
  const { token, refreshUser } = useAuth();
  const router = useRouter();
  const params = useLocalSearchParams<{ scanId?: string }>();
  
  const [selectedPlan, setSelectedPlan] = useState('yearly');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleUpgrade = async () => {
    if (!token) {
      router.push('/(auth)/login');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await axios.post(
        `${API_URL}/api/subscription/upgrade`,
        { plan: 'premium' },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Refresh user data to get updated plan
      if (refreshUser) {
        await refreshUser();
      }

      // Navigate to scan result if we have a scanId, otherwise go back
      if (params.scanId) {
        router.replace({
          pathname: '/scan-result',
          params: { scanId: params.scanId }
        });
      } else {
        router.back();
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upgrade. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.closeButton}>
          <Ionicons name="close" size={28} color={theme.text} />
        </TouchableOpacity>
      </View>

      <ScrollView 
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Hero Section */}
        <View style={styles.heroSection}>
          <View style={[styles.iconCircle, { backgroundColor: theme.primary + '20' }]}>
            <Ionicons name="sparkles" size={48} color={theme.primary} />
          </View>
          <Text style={[styles.title, { color: theme.text }]}>
            Your personalized skin{'\n'}improvement plan is ready
          </Text>
          <Text style={[styles.subtitle, { color: theme.textSecondary }]}>
            Unlock everything you need to fix your skin faster
          </Text>
        </View>

        {/* Features List */}
        <View style={styles.featuresSection}>
          {features.map((feature, index) => (
            <View key={index} style={styles.featureItem}>
              <View style={[styles.featureIcon, { backgroundColor: '#E8F5E9' }]}>
                <Ionicons name={feature.icon as any} size={20} color="#4CAF50" />
              </View>
              <Text style={[styles.featureText, { color: theme.text }]}>
                {feature.text}
              </Text>
            </View>
          ))}
        </View>

        {/* Pricing Options */}
        <View style={styles.pricingSection}>
          {pricingOptions.map((option) => (
            <TouchableOpacity
              key={option.id}
              style={[
                styles.pricingCard,
                { 
                  backgroundColor: theme.surface,
                  borderColor: selectedPlan === option.id ? theme.primary : theme.border,
                  borderWidth: selectedPlan === option.id ? 2 : 1,
                },
              ]}
              onPress={() => setSelectedPlan(option.id)}
            >
              {option.popular && (
                <View style={[styles.popularBadge, { backgroundColor: theme.primary }]}>
                  <Text style={styles.popularText}>BEST VALUE</Text>
                </View>
              )}
              <View style={styles.pricingContent}>
                <View style={styles.radioOuter}>
                  {selectedPlan === option.id && (
                    <View style={[styles.radioInner, { backgroundColor: theme.primary }]} />
                  )}
                </View>
                <View style={styles.pricingInfo}>
                  <Text style={[styles.planName, { color: theme.text }]}>
                    {option.name}
                  </Text>
                  <View style={styles.priceRow}>
                    <Text style={[styles.price, { color: theme.text }]}>
                      {option.price}
                    </Text>
                    <Text style={[styles.period, { color: theme.textSecondary }]}>
                      {option.period}
                    </Text>
                  </View>
                </View>
                {option.savings && (
                  <View style={[styles.savingsBadge, { backgroundColor: '#E8F5E9' }]}>
                    <Text style={styles.savingsText}>{option.savings}</Text>
                  </View>
                )}
              </View>
            </TouchableOpacity>
          ))}
        </View>

        {/* Error Message */}
        {error ? (
          <View style={[styles.errorContainer, { backgroundColor: '#FFEBEE' }]}>
            <Ionicons name="alert-circle" size={20} color="#F44336" />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        {/* CTA Button */}
        <TouchableOpacity
          style={[
            styles.ctaButton,
            { backgroundColor: theme.primary },
            loading && { opacity: 0.7 }
          ]}
          onPress={handleUpgrade}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.ctaText}>Start Premium</Text>
          )}
        </TouchableOpacity>

        {/* Cancel text */}
        <Text style={[styles.cancelText, { color: theme.textMuted }]}>
          Cancel anytime
        </Text>

        {/* Terms */}
        <Text style={[styles.termsText, { color: theme.textMuted }]}>
          By subscribing, you agree to our Terms of Service and Privacy Policy.
          Payment will be charged to your account. Subscription automatically renews
          unless canceled at least 24 hours before the end of the current period.
        </Text>
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
    justifyContent: 'flex-end',
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  closeButton: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingBottom: 40,
  },
  heroSection: {
    alignItems: 'center',
    marginBottom: 32,
  },
  iconCircle: {
    width: 100,
    height: 100,
    borderRadius: 50,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 26,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 12,
    lineHeight: 34,
  },
  subtitle: {
    fontSize: 16,
    textAlign: 'center',
    lineHeight: 24,
  },
  featuresSection: {
    marginBottom: 32,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  featureIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  featureText: {
    fontSize: 16,
    fontWeight: '500',
    flex: 1,
  },
  pricingSection: {
    marginBottom: 24,
  },
  pricingCard: {
    borderRadius: 16,
    padding: 20,
    marginBottom: 12,
    position: 'relative',
    overflow: 'hidden',
  },
  popularBadge: {
    position: 'absolute',
    top: 0,
    right: 20,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderBottomLeftRadius: 8,
    borderBottomRightRadius: 8,
  },
  popularText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  pricingContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  radioOuter: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#CCC',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  radioInner: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  pricingInfo: {
    flex: 1,
  },
  planName: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  priceRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  price: {
    fontSize: 22,
    fontWeight: '700',
  },
  period: {
    fontSize: 14,
    marginLeft: 4,
  },
  savingsBadge: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  savingsText: {
    color: '#4CAF50',
    fontSize: 12,
    fontWeight: '700',
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
  },
  errorText: {
    color: '#F44336',
    fontSize: 14,
    marginLeft: 8,
    flex: 1,
  },
  ctaButton: {
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  ctaText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '700',
  },
  cancelText: {
    textAlign: 'center',
    fontSize: 14,
    marginBottom: 24,
  },
  termsText: {
    textAlign: 'center',
    fontSize: 11,
    lineHeight: 16,
    paddingHorizontal: 16,
  },
});
