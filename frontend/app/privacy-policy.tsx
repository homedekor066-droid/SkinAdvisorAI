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

export default function PrivacyPolicyScreen() {
  const { theme } = useTheme();
  const router = useRouter();

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={theme.text} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: theme.text }]}>Privacy Policy</Text>
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
          1. Introduction
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          Welcome to SkinAdvisor AI ("we," "our," or "us"). We are committed to protecting your privacy and personal information. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our mobile application.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          2. Information We Collect
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          <Text style={styles.bold}>Personal Information:</Text> When you create an account, we collect your name, email address, and password (stored securely encrypted).
          {'\n\n'}
          <Text style={styles.bold}>Skin Analysis Data:</Text> Photos you submit for skin analysis are processed by our AI system. These images are stored securely and associated with your account for progress tracking purposes.
          {'\n\n'}
          <Text style={styles.bold}>Usage Data:</Text> We collect information about how you interact with our app, including features used and analysis history.
          {'\n\n'}
          <Text style={styles.bold}>Device Information:</Text> We may collect device type, operating system, and unique device identifiers.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          3. How We Use Your Information
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          We use your information to:{'\n'}
          • Provide and maintain our skin analysis services{'\n'}
          • Personalize your skincare recommendations{'\n'}
          • Track your skin improvement progress{'\n'}
          • Process transactions and manage subscriptions{'\n'}
          • Send important notifications about your account{'\n'}
          • Improve our AI analysis accuracy{'\n'}
          • Respond to customer support requests
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          4. Data Storage and Security
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          Your data is stored on secure cloud servers with industry-standard encryption. We implement appropriate technical and organizational measures to protect your personal information against unauthorized access, alteration, disclosure, or destruction.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          5. AI Analysis and Image Processing
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          Our AI-powered skin analysis uses advanced computer vision technology. Your facial images are:{'\n'}
          • Processed securely on our servers{'\n'}
          • Used solely for providing skin analysis{'\n'}
          • Not shared with third parties for advertising{'\n'}
          • Retained for your progress tracking history{'\n\n'}
          You may request deletion of your images at any time through account settings.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          6. Third-Party Services
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          We may use third-party services for:{'\n'}
          • Cloud hosting and storage{'\n'}
          • Payment processing (for premium subscriptions){'\n'}
          • Analytics (anonymized usage data only){'\n\n'}
          These services have their own privacy policies governing their use of your data.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          7. Your Rights
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          You have the right to:{'\n'}
          • Access your personal data{'\n'}
          • Correct inaccurate data{'\n'}
          • Delete your account and data{'\n'}
          • Export your data{'\n'}
          • Opt out of marketing communications{'\n\n'}
          To exercise these rights, contact us at support@skinadvisorai.com
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          8. Children's Privacy
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          Our service is not intended for users under 13 years of age. We do not knowingly collect personal information from children under 13.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          9. Changes to This Policy
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          We may update this Privacy Policy from time to time. We will notify you of significant changes through the app or via email.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          10. Contact Us
        </Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          If you have questions about this Privacy Policy, please contact us at:{'\n\n'}
          Email: support@skinadvisorai.com{'\n'}
          Subject: Privacy Policy Inquiry
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
});
