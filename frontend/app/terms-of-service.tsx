import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '../src/context/ThemeContext';
import { Ionicons } from '@expo/vector-icons';

export default function TermsOfServiceScreen() {
  const { theme } = useTheme();
  const router = useRouter();

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={[styles.header, { borderBottomColor: theme.border }]}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color={theme.text} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: theme.text }]}>Terms of Service</Text>
        <View style={styles.backButton} />
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        <Text style={[styles.lastUpdated, { color: theme.textSecondary }]}>
          Last updated: January 2025
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>1. Acceptance of Terms</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          By accessing and using SkinAdvisor AI, you agree to be bound by these Terms of Service. If you do not agree to these terms, please do not use our application.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>2. Service Description</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          SkinAdvisor AI is a mobile application that provides AI-powered skin analysis, personalized skincare routines, and product recommendations. Our service is intended for informational purposes only and does not constitute medical advice.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>3. Medical Disclaimer</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          SkinAdvisor AI is NOT a medical device and does NOT provide medical diagnoses, treatment recommendations, or medical advice. The analysis and recommendations provided are based on AI technology and should not replace professional dermatological consultation. Always consult a qualified healthcare provider for medical concerns.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>4. User Accounts</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          • You must provide accurate and complete information when creating an account.{'\n'}
          • You are responsible for maintaining the confidentiality of your account credentials.{'\n'}
          • You must be at least 13 years old to use this service.{'\n'}
          • One account per person is allowed.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>5. Subscription and Payments</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          • Free users receive limited features including one skin scan.{'\n'}
          • Premium subscriptions provide unlimited access to all features.{'\n'}
          • Subscriptions auto-renew unless cancelled before the renewal date.{'\n'}
          • Refunds are processed according to Apple App Store and Google Play Store policies.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>6. Acceptable Use</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          You agree NOT to:{'\n'}
          • Use the service for any illegal purpose{'\n'}
          • Upload inappropriate or non-facial images{'\n'}
          • Attempt to reverse engineer or exploit the application{'\n'}
          • Share your account with others{'\n'}
          • Use automated systems to access the service
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>7. Intellectual Property</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          All content, features, and functionality of SkinAdvisor AI are owned by us and are protected by international copyright, trademark, and other intellectual property laws.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>8. Limitation of Liability</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          SkinAdvisor AI is provided "as is" without warranties of any kind. We are not liable for any damages arising from your use of the application, including but not limited to skin reactions, allergies, or adverse effects from following recommendations.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>9. Changes to Terms</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          We reserve the right to modify these terms at any time. Continued use of the service after changes constitutes acceptance of the new terms.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>10. Contact</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          For questions about these Terms of Service, contact us at:{'\n'}
          support@skinadvisor.ai
        </Text>

        <View style={styles.bottomPadding} />
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
    borderBottomWidth: 1,
  },
  backButton: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
  },
  content: {
    flex: 1,
    paddingHorizontal: 20,
  },
  lastUpdated: {
    fontSize: 14,
    marginTop: 16,
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginTop: 20,
    marginBottom: 12,
  },
  paragraph: {
    fontSize: 15,
    lineHeight: 24,
  },
  bottomPadding: {
    height: 40,
  },
});
