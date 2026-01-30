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

export default function PrivacyPolicyScreen() {
  const { theme } = useTheme();
  const router = useRouter();

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={[styles.header, { borderBottomColor: theme.border }]}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color={theme.text} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: theme.text }]}>Privacy Policy</Text>
        <View style={styles.backButton} />
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        <Text style={[styles.lastUpdated, { color: theme.textSecondary }]}>
          Last updated: January 2025
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>1. Introduction</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          Welcome to SkinAdvisor AI. We respect your privacy and are committed to protecting your personal data. This privacy policy explains how we collect, use, and safeguard your information when you use our mobile application.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>2. Information We Collect</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          • Account Information: Email address, name, and password when you register.{'\n'}
          • Profile Data: Age, gender, skin type, and skin goals you provide.{'\n'}
          • Photos: Facial images you submit for skin analysis (processed securely and not stored permanently).{'\n'}
          • Usage Data: App interactions, scan history, and preferences.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>3. How We Use Your Information</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          • To provide personalized skin analysis and recommendations.{'\n'}
          • To generate customized skincare routines.{'\n'}
          • To track your skin progress over time.{'\n'}
          • To improve our AI algorithms and services.{'\n'}
          • To communicate important updates about the app.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>4. Photo Data</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          Your facial photos are processed using AI technology to analyze your skin condition. We do not sell or share your photos with third parties. Photos are encrypted during transmission and processing.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>5. Data Security</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          We implement industry-standard security measures to protect your data, including encryption, secure servers, and regular security audits.
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>6. Your Rights</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          You have the right to:{'\n'}
          • Access your personal data{'\n'}
          • Request deletion of your account and data{'\n'}
          • Update or correct your information{'\n'}
          • Opt out of marketing communications
        </Text>

        <Text style={[styles.sectionTitle, { color: theme.text }]}>7. Contact Us</Text>
        <Text style={[styles.paragraph, { color: theme.textSecondary }]}>
          If you have questions about this Privacy Policy, please contact us at:{'\n'}
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
