import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTheme } from '../src/context/ThemeContext';
import { Ionicons } from '@expo/vector-icons';

export default function TermsOfServiceScreen() {
  const { theme } = useTheme();
  const router = useRouter();

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={theme.text} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: theme.text }]}>Terms of Service</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView 
        style={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={[styles.lastUpdated, { color: theme.textSecondary }]}>
          Last updated: January 2025
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          1. Acceptance of Terms
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          By downloading, installing, or using SkinAdvisor AI ("the App"), you agree to be bound by these Terms of Service. If you do not agree to these terms, please do not use the App.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          2. Description of Service
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          SkinAdvisor AI provides AI-powered skin analysis and personalized skincare recommendations. Our service includes:{'\n\n'}
          • Facial skin analysis using computer vision{'\n'}
          • Personalized skincare routine recommendations{'\n'}
          • Diet and nutrition suggestions for skin health{'\n'}
          • Progress tracking features{'\n'}
          • Product recommendations
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          3. Medical Disclaimer
        </Text>
        <Text style={[styles.importantBox, { backgroundColor: theme.surface, color: theme.text }]}>
          ⚠️ IMPORTANT: SkinAdvisor AI is NOT a medical device and does NOT provide medical advice, diagnosis, or treatment. Our analysis is for cosmetic and informational purposes only.{'\n\n'}
          Do NOT use this app to diagnose skin conditions, diseases, or medical issues. Always consult a qualified dermatologist or healthcare professional for medical concerns.{'\n\n'}
          Our recommendations are general wellness suggestions and should not replace professional medical advice.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          4. User Accounts
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          To use certain features, you must create an account. You agree to:{'\n\n'}
          • Provide accurate and complete information{'\n'}
          • Maintain the security of your account credentials{'\n'}
          • Promptly notify us of any unauthorized access{'\n'}
          • Accept responsibility for all activities under your account{'\n\n'}
          You must be at least 13 years old to create an account.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          5. Subscription and Payments
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          <Text style={styles.bold}>Free Tier:</Text> Limited to 1 skin scan. Provides basic analysis results only.{'\n\n'}
          <Text style={styles.bold}>Premium Subscription:</Text> Unlocks unlimited scans, full routines, diet recommendations, product suggestions, and progress tracking.{'\n\n'}
          <Text style={styles.bold}>Pricing:</Text>{'\n'}
          • Monthly: €9.99/month{'\n'}
          • Yearly: €59.99/year (Save 50%){'\n\n'}
          Subscriptions are billed through Apple App Store or Google Play Store. Subscriptions automatically renew unless cancelled at least 24 hours before the end of the current period.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          6. Cancellation and Refunds
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          You may cancel your subscription at any time through your App Store or Play Store account settings. Upon cancellation:{'\n\n'}
          • You retain access until the end of your current billing period{'\n'}
          • No partial refunds are provided for unused time{'\n'}
          • Your account converts to free tier{'\n\n'}
          Refund requests are handled according to Apple and Google's respective policies.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          7. Acceptable Use
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          You agree NOT to:{'\n\n'}
          • Upload inappropriate, offensive, or non-facial images{'\n'}
          • Attempt to reverse engineer or hack the app{'\n'}
          • Use the service for any illegal purpose{'\n'}
          • Share your account with others{'\n'}
          • Misrepresent yourself or impersonate others{'\n'}
          • Interfere with the operation of the service
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          8. Intellectual Property
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          All content, features, and functionality of the App are owned by SkinAdvisor AI and protected by international copyright, trademark, and other intellectual property laws.{'\n\n'}
          You retain ownership of photos you upload but grant us a license to process them for providing our services.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          9. Limitation of Liability
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          TO THE MAXIMUM EXTENT PERMITTED BY LAW:{'\n\n'}
          • We provide the service "as is" without warranties{'\n'}
          • We are not liable for any indirect, incidental, or consequential damages{'\n'}
          • Our total liability shall not exceed the amount you paid for the service{'\n'}
          • We do not guarantee specific results from following our recommendations
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          10. Changes to Terms
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          We reserve the right to modify these terms at any time. We will notify users of material changes through the app or email. Continued use after changes constitutes acceptance of new terms.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          11. Termination
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          We may terminate or suspend your account at any time for violations of these terms. Upon termination, your right to use the service ceases immediately.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          12. Governing Law
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          These terms shall be governed by and construed in accordance with applicable laws, without regard to conflict of law principles.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          13. Contact Us
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          For questions about these Terms of Service:{'\n\n'}
          Email: support@skinadvisorai.com{'\n'}
          Subject: Terms of Service Inquiry
        </Text>

        <View style={{ height: 40 }} />
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
    borderBottomColor: '#E8E8E8',
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
    fontSize: 13,
    fontStyle: 'italic',
    marginTop: 16,
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: '700',
    marginTop: 20,
    marginBottom: 10,
  },
  paragraph: {
    fontSize: 15,
    lineHeight: 24,
    marginBottom: 8,
  },
  bold: {
    fontWeight: '600',
  },
  importantBox: {
    padding: 16,
    borderRadius: 12,
    marginBottom: 8,
    fontSize: 14,
    lineHeight: 22,
    fontWeight: '500',
  },
});
