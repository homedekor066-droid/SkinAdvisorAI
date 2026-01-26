import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useTheme } from '../src/context/ThemeContext';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';

export default function PhotoConsentScreen() {
  const { theme } = useTheme();
  const router = useRouter();
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  
  const [consented, setConsented] = useState(false);

  const handleAccept = async () => {
    if (!consented) return;
    
    // Save consent
    await AsyncStorage.setItem('photo_consent_given', 'true');
    await AsyncStorage.setItem('photo_consent_date', new Date().toISOString());
    
    // Navigate back to scan or specified route
    if (returnTo) {
      router.replace(returnTo as any);
    } else {
      router.replace('/(tabs)/scan');
    }
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="close" size={28} color={theme.text} />
        </TouchableOpacity>
      </View>

      <ScrollView 
        style={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Icon */}
        <View style={[styles.iconContainer, { backgroundColor: theme.primary + '20' }]}>
          <Ionicons name="shield-checkmark" size={48} color={theme.primary} />
        </View>

        {/* Title */}
        <Text style={[styles.title, { color: theme.text }]}>
          Your Privacy Matters
        </Text>
        <Text style={[styles.subtitle, { color: theme.textSecondary }]}>
          Before you take your first scan, please review how we handle your photos.
        </Text>

        {/* Privacy Points */}
        <View style={styles.pointsContainer}>
          <View style={styles.pointItem}>
            <View style={[styles.pointIcon, { backgroundColor: '#E8F5E9' }]}>
              <Ionicons name="lock-closed" size={20} color="#4CAF50" />
            </View>
            <View style={styles.pointText}>
              <Text style={[styles.pointTitle, { color: theme.text }]}>
                Securely Stored
              </Text>
              <Text style={[styles.pointDescription, { color: theme.textSecondary }]}>
                Your photos are encrypted and stored securely on our servers.
              </Text>
            </View>
          </View>

          <View style={styles.pointItem}>
            <View style={[styles.pointIcon, { backgroundColor: '#E3F2FD' }]}>
              <Ionicons name="eye-off" size={20} color="#1976D2" />
            </View>
            <View style={styles.pointText}>
              <Text style={[styles.pointTitle, { color: theme.text }]}>
                Never Shared or Sold
              </Text>
              <Text style={[styles.pointDescription, { color: theme.textSecondary }]}>
                We do not share, sell, or use your photos for advertising.
              </Text>
            </View>
          </View>

          <View style={styles.pointItem}>
            <View style={[styles.pointIcon, { backgroundColor: '#FFF3E0' }]}>
              <Ionicons name="scan" size={20} color="#F57C00" />
            </View>
            <View style={styles.pointText}>
              <Text style={[styles.pointTitle, { color: theme.text }]}>
                Analysis Only
              </Text>
              <Text style={[styles.pointDescription, { color: theme.textSecondary }]}>
                Photos are used solely for providing your skin analysis.
              </Text>
            </View>
          </View>

          <View style={styles.pointItem}>
            <View style={[styles.pointIcon, { backgroundColor: '#FCE4EC' }]}>
              <Ionicons name="trash" size={20} color="#E91E63" />
            </View>
            <View style={styles.pointText}>
              <Text style={[styles.pointTitle, { color: theme.text }]}>
                Delete Anytime
              </Text>
              <Text style={[styles.pointDescription, { color: theme.textSecondary }]}>
                You can delete your photos and data at any time from your account.
              </Text>
            </View>
          </View>
        </View>

        {/* Disclaimer */}
        <View style={[styles.disclaimerBox, { backgroundColor: '#FFF8E1' }]}>
          <Ionicons name="information-circle" size={20} color="#F57C00" />
          <Text style={[styles.disclaimerText, { color: '#E65100' }]}>
            SkinAdvisor AI provides cosmetic analysis only. This is not medical advice. 
            Consult a dermatologist for skin health concerns.
          </Text>
        </View>

        {/* Consent Checkbox */}
        <TouchableOpacity 
          style={styles.consentRow}
          onPress={() => setConsented(!consented)}
        >
          <View style={[
            styles.checkbox,
            { borderColor: consented ? theme.primary : theme.border },
            consented && { backgroundColor: theme.primary }
          ]}>
            {consented && <Ionicons name="checkmark" size={16} color="#FFFFFF" />}
          </View>
          <Text style={[styles.consentText, { color: theme.text }]}>
            I understand and agree to the{' '}
            <Text 
              style={{ color: theme.primary, textDecorationLine: 'underline' }}
              onPress={() => router.push('/privacy-policy')}
            >
              Privacy Policy
            </Text>
            {' '}and{' '}
            <Text 
              style={{ color: theme.primary, textDecorationLine: 'underline' }}
              onPress={() => router.push('/terms-of-service')}
            >
              Terms of Service
            </Text>
          </Text>
        </TouchableOpacity>

        {/* Accept Button */}
        <TouchableOpacity
          style={[
            styles.acceptButton,
            { backgroundColor: theme.primary },
            !consented && { opacity: 0.5 }
          ]}
          onPress={handleAccept}
          disabled={!consented}
        >
          <Text style={styles.acceptButtonText}>Continue to Scan</Text>
        </TouchableOpacity>

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
    justifyContent: 'flex-end',
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  backButton: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
  },
  content: {
    flex: 1,
    paddingHorizontal: 24,
  },
  iconContainer: {
    width: 96,
    height: 96,
    borderRadius: 48,
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'center',
    marginTop: 20,
    marginBottom: 24,
  },
  title: {
    fontSize: 26,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 12,
  },
  subtitle: {
    fontSize: 16,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: 32,
  },
  pointsContainer: {
    marginBottom: 24,
  },
  pointItem: {
    flexDirection: 'row',
    marginBottom: 20,
  },
  pointIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  pointText: {
    flex: 1,
  },
  pointTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  pointDescription: {
    fontSize: 14,
    lineHeight: 20,
  },
  disclaimerBox: {
    flexDirection: 'row',
    padding: 16,
    borderRadius: 12,
    marginBottom: 24,
  },
  disclaimerText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 20,
    marginLeft: 12,
  },
  consentRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 24,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
    marginTop: 2,
  },
  consentText: {
    flex: 1,
    fontSize: 14,
    lineHeight: 22,
  },
  acceptButton: {
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
  },
  acceptButtonText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '700',
  },
});
