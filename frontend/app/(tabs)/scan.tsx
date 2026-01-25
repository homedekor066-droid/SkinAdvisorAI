import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { useTheme } from '../../src/context/ThemeContext';
import { useI18n } from '../../src/context/I18nContext';
import { useAuth } from '../../src/context/AuthContext';
import { skinService } from '../../src/services/skinService';
import { Button, Card } from '../../src/components';
import { Ionicons } from '@expo/vector-icons';

export default function ScanScreen() {
  const { theme } = useTheme();
  const { t, language } = useI18n();
  const { token, user } = useAuth();
  const router = useRouter();

  const [image, setImage] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  // Check if user can scan (free users: 1 scan limit)
  const canScan = user?.plan === 'premium' || (user?.scan_count ?? 0) < 1;

  const pickImage = async (useCamera: boolean) => {
    // Check scan limit before allowing image selection
    if (!canScan) {
      router.push('/paywall');
      return;
    }

    try {
      const permissionResult = useCamera
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();

      if (!permissionResult.granted) {
        Alert.alert('Permission Required', 'Please grant permission to access your photos.');
        return;
      }

      const result = useCamera
        ? await ImagePicker.launchCameraAsync({
            mediaTypes: ['images'],
            allowsEditing: true,
            aspect: [1, 1],
            quality: 0.8,
            base64: true,
          })
        : await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ['images'],
            allowsEditing: true,
            aspect: [1, 1],
            quality: 0.8,
            base64: true,
          });

      if (!result.canceled && result.assets[0].base64) {
        setImage(result.assets[0].base64);
      }
    } catch (error) {
      console.error('Image picker error:', error);
      Alert.alert(t('error'), 'Failed to pick image');
    }
  };

  const analyzeSkin = async () => {
    if (!image || !token) return;

    // Double check scan limit
    if (!canScan) {
      router.push('/paywall');
      return;
    }

    setAnalyzing(true);
    try {
      const result = await skinService.analyzeSkin(image, language, token);
      router.push({
        pathname: '/scan-result',
        params: { scanId: result.id }
      });
    } catch (error: any) {
      console.error('Analysis error:', error);
      
      // Check if scan limit reached error
      const errorDetail = error.response?.data?.detail;
      if (errorDetail?.error === 'scan_limit_reached' || errorDetail?.upgrade_required) {
        Alert.alert(
          'Scan Limit Reached',
          "You've used your free scan. Upgrade to Premium to continue.",
          [
            { text: 'Later', style: 'cancel' },
            { text: 'Upgrade', onPress: () => router.push('/paywall') }
          ]
        );
      } else {
        const message = typeof errorDetail === 'string' ? errorDetail : errorDetail?.message || 'Analysis failed. Please try again.';
        Alert.alert(t('error'), message);
      }
    } finally {
      setAnalyzing(false);
    }
  };

  const clearImage = () => {
    setImage(null);
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      <View style={styles.header}>
        <Text style={[styles.title, { color: theme.text }]}>{t('scan_skin')}</Text>
        <Text style={[styles.subtitle, { color: theme.textSecondary }]}>
          Take or upload a photo of your face
        </Text>
      </View>

      {/* Scan Limit Banner for Free Users */}
      {!canScan && (
        <TouchableOpacity 
          style={[styles.limitBanner, { backgroundColor: theme.primary }]}
          onPress={() => router.push('/paywall')}
        >
          <View style={styles.limitBannerContent}>
            <Ionicons name="lock-closed" size={24} color="#FFFFFF" />
            <View style={styles.limitBannerText}>
              <Text style={styles.limitBannerTitle}>
                You've used your free scan
              </Text>
              <Text style={styles.limitBannerSubtitle}>
                Upgrade to Premium for unlimited scans
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={24} color="#FFFFFF" />
          </View>
        </TouchableOpacity>
      )}

      <View style={styles.content}>
        {image ? (
          <View style={styles.previewContainer}>
            <Image
              source={{ uri: `data:image/jpeg;base64,${image}` }}
              style={styles.previewImage}
            />
            <TouchableOpacity
              style={[styles.clearButton, { backgroundColor: theme.error }]}
              onPress={clearImage}
            >
              <Ionicons name="close" size={20} color="#FFFFFF" />
            </TouchableOpacity>
          </View>
        ) : (
          <View style={[styles.placeholder, { backgroundColor: theme.surface, borderColor: theme.border }]}>
            <Ionicons name="person-outline" size={80} color={theme.textMuted} />
            <Text style={[styles.placeholderText, { color: theme.textMuted }]}>
              No image selected
            </Text>
          </View>
        )}

        {!image && (
          <View style={styles.buttonGroup}>
            <TouchableOpacity
              style={[styles.optionButton, { backgroundColor: theme.card, borderColor: theme.border }]}
              onPress={() => pickImage(true)}
            >
              <View style={[styles.optionIcon, { backgroundColor: theme.primary + '20' }]}>
                <Ionicons name="camera" size={28} color={theme.primary} />
              </View>
              <Text style={[styles.optionText, { color: theme.text }]}>
                {t('take_photo')}
              </Text>
              <Text style={[styles.optionSubtext, { color: theme.textSecondary }]}>
                Use your camera
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.optionButton, { backgroundColor: theme.card, borderColor: theme.border }]}
              onPress={() => pickImage(false)}
            >
              <View style={[styles.optionIcon, { backgroundColor: theme.info + '20' }]}>
                <Ionicons name="images" size={28} color={theme.info} />
              </View>
              <Text style={[styles.optionText, { color: theme.text }]}>
                {t('upload_photo')}
              </Text>
              <Text style={[styles.optionSubtext, { color: theme.textSecondary }]}>
                From your gallery
              </Text>
            </TouchableOpacity>
          </View>
        )}

        {image && (
          <View style={styles.actionButtons}>
            <Button
              title={analyzing ? t('analyzing') : 'Analyze Skin'}
              onPress={analyzeSkin}
              loading={analyzing}
              disabled={analyzing}
              icon={analyzing ? undefined : 'sparkles'}
              size="large"
              style={{ flex: 1, marginRight: 8 }}
            />
            <Button
              title="Retake"
              onPress={clearImage}
              variant="outline"
              size="large"
              style={{ width: 100 }}
            />
          </View>
        )}

        {/* Tips */}
        <Card style={styles.tipsCard}>
          <Text style={[styles.tipsTitle, { color: theme.text }]}>
            Tips for best results
          </Text>
          <View style={styles.tipItem}>
            <Ionicons name="sunny-outline" size={18} color={theme.warning} />
            <Text style={[styles.tipText, { color: theme.textSecondary }]}>
              Use natural lighting
            </Text>
          </View>
          <View style={styles.tipItem}>
            <Ionicons name="water-outline" size={18} color={theme.info} />
            <Text style={[styles.tipText, { color: theme.textSecondary }]}>
              Clean face, no makeup
            </Text>
          </View>
          <View style={styles.tipItem}>
            <Ionicons name="eye-outline" size={18} color={theme.success} />
            <Text style={[styles.tipText, { color: theme.textSecondary }]}>
              Face the camera directly
            </Text>
          </View>
        </Card>
      </View>

      {analyzing && (
        <View style={[styles.loadingOverlay, { backgroundColor: 'rgba(0,0,0,0.7)' }]}>
          <ActivityIndicator size="large" color={theme.primary} />
          <Text style={styles.loadingText}>{t('analyzing')}</Text>
          <Text style={styles.loadingSubtext}>This may take a moment...</Text>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 16,
  },
  content: {
    flex: 1,
    paddingHorizontal: 20,
  },
  previewContainer: {
    position: 'relative',
    borderRadius: 20,
    overflow: 'hidden',
    marginBottom: 20,
  },
  previewImage: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: 20,
  },
  clearButton: {
    position: 'absolute',
    top: 12,
    right: 12,
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  placeholder: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: 20,
    borderWidth: 2,
    borderStyle: 'dashed',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  placeholderText: {
    marginTop: 16,
    fontSize: 16,
  },
  buttonGroup: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 20,
  },
  optionButton: {
    flex: 1,
    padding: 20,
    borderRadius: 16,
    borderWidth: 1,
    alignItems: 'center',
  },
  optionIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  optionText: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  optionSubtext: {
    fontSize: 12,
  },
  actionButtons: {
    flexDirection: 'row',
    marginBottom: 20,
  },
  tipsCard: {
    marginTop: 'auto',
    marginBottom: 20,
  },
  tipsTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 12,
  },
  tipItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  tipText: {
    marginLeft: 10,
    fontSize: 14,
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '600',
    marginTop: 20,
  },
  loadingSubtext: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 14,
    marginTop: 8,
  },
  // Limit Banner Styles
  limitBanner: {
    marginHorizontal: 20,
    marginBottom: 16,
    borderRadius: 12,
    overflow: 'hidden',
  },
  limitBannerContent: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
  },
  limitBannerText: {
    flex: 1,
    marginLeft: 12,
  },
  limitBannerTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 4,
  },
  limitBannerSubtitle: {
    color: 'rgba(255, 255, 255, 0.8)',
    fontSize: 13,
  },
});
