import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTheme } from '../../src/context/ThemeContext';
import { useI18n } from '../../src/context/I18nContext';
import { useAuth } from '../../src/context/AuthContext';
import { skinService, ScanHistoryItem } from '../../src/services/skinService';
import { Card, Button } from '../../src/components';
import { Ionicons } from '@expo/vector-icons';

export default function HomeScreen() {
  const { theme } = useTheme();
  const { t } = useI18n();
  const { user, token } = useAuth();
  const router = useRouter();
  const [recentScans, setRecentScans] = useState<ScanHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchRecentScans = async () => {
    if (!token) return;
    try {
      const scans = await skinService.getScanHistory(token);
      setRecentScans(scans.slice(0, 3));
    } catch (error) {
      console.error('Failed to fetch scans:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecentScans();
  }, [token]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchRecentScans();
    setRefreshing(false);
  }, [token]);

  const getSkinTypeColor = (skinType: string) => {
    const colors: { [key: string]: string } = {
      oily: '#F39C12',
      dry: '#3498DB',
      combination: '#9B59B6',
      normal: '#27AE60',
      sensitive: '#E74C3C',
    };
    return colors[skinType?.toLowerCase()] || theme.primary;
  };

  const latestScan = recentScans[0];

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={[styles.greeting, { color: theme.textSecondary }]}>
              {t('welcome')},
            </Text>
            <Text style={[styles.userName, { color: theme.text }]}>
              {user?.name || 'User'}
            </Text>
          </View>
          <TouchableOpacity
            style={[styles.notificationButton, { backgroundColor: theme.surface }]}
            onPress={() => router.push('/profile')}
          >
            <Ionicons name="notifications-outline" size={24} color={theme.text} />
          </TouchableOpacity>
        </View>

        {/* Quick Scan Card */}
        <Card style={[styles.scanCard, { backgroundColor: theme.primary }]}>
          <View style={styles.scanCardContent}>
            <View style={styles.scanCardText}>
              <Text style={styles.scanCardTitle}>{t('scan_skin')}</Text>
              <Text style={styles.scanCardSubtitle}>
                Get personalized skincare advice
              </Text>
            </View>
            <TouchableOpacity
              style={styles.scanButton}
              onPress={() => router.push('/(tabs)/scan')}
            >
              <Ionicons name="camera" size={28} color={theme.primary} />
            </TouchableOpacity>
          </View>
        </Card>

        {/* Latest Result */}
        {latestScan && latestScan.analysis && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: theme.text }]}>
              Latest Analysis
            </Text>
            <Card>
              <View style={styles.latestResultContent}>
                <View style={styles.scoreContainer}>
                  <View
                    style={[
                      styles.scoreCircle,
                      { borderColor: getSkinTypeColor(latestScan.analysis.skin_type) },
                    ]}
                  >
                    <Text style={[styles.scoreText, { color: theme.text }]}>
                      {latestScan.analysis.overall_score}
                    </Text>
                    <Text style={[styles.scoreLabel, { color: theme.textSecondary }]}>
                      Score
                    </Text>
                  </View>
                </View>
                <View style={styles.resultDetails}>
                  <View style={styles.skinTypeRow}>
                    <Text style={[styles.skinTypeLabel, { color: theme.textSecondary }]}>
                      {t('skin_type')}:
                    </Text>
                    <View
                      style={[
                        styles.skinTypeBadge,
                        { backgroundColor: getSkinTypeColor(latestScan.analysis.skin_type) + '20' },
                      ]}
                    >
                      <Text
                        style={[
                          styles.skinTypeText,
                          { color: getSkinTypeColor(latestScan.analysis.skin_type) },
                        ]}
                      >
                        {t(latestScan.analysis.skin_type) || latestScan.analysis.skin_type}
                      </Text>
                    </View>
                  </View>
                  <Text style={[styles.issuesCount, { color: theme.textSecondary }]}>
                    {latestScan.analysis.issues?.length || 0} issues detected
                  </Text>
                  <TouchableOpacity
                    style={[styles.viewDetailsButton, { backgroundColor: theme.primary + '15' }]}
                    onPress={() => router.push({
                      pathname: '/scan-result',
                      params: { scanId: latestScan.id }
                    })}
                  >
                    <Text style={[styles.viewDetailsText, { color: theme.primary }]}>
                      {t('view_results')}
                    </Text>
                    <Ionicons name="chevron-forward" size={16} color={theme.primary} />
                  </TouchableOpacity>
                </View>
              </View>
            </Card>
          </View>
        )}

        {/* Quick Actions */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.text }]}>
            Quick Actions
          </Text>
          <View style={styles.actionsGrid}>
            <TouchableOpacity
              style={[styles.actionCard, { backgroundColor: theme.card, borderColor: theme.border }]}
              onPress={() => router.push('/(tabs)/progress')}
            >
              <View style={[styles.actionIcon, { backgroundColor: theme.primary + '20' }]}>
                <Ionicons name="bar-chart-outline" size={24} color={theme.primary} />
              </View>
              <Text style={[styles.actionText, { color: theme.text }]}>
                {t('progress')}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.actionCard, { backgroundColor: theme.card, borderColor: theme.border }]}
              onPress={() => router.push('/(tabs)/profile')}
            >
              <View style={[styles.actionIcon, { backgroundColor: theme.info + '20' }]}>
                <Ionicons name="calendar-outline" size={24} color={theme.info} />
              </View>
              <Text style={[styles.actionText, { color: theme.text }]}>
                {t('my_routines')}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.actionCard, { backgroundColor: theme.card, borderColor: theme.border }]}
              onPress={() => router.push('/(tabs)/profile')}
            >
              <View style={[styles.actionIcon, { backgroundColor: theme.success + '20' }]}>
                <Ionicons name="leaf-outline" size={24} color={theme.success} />
              </View>
              <Text style={[styles.actionText, { color: theme.text }]}>
                {t('products')}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.actionCard, { backgroundColor: theme.card, borderColor: theme.border }]}
              onPress={() => router.push('/(tabs)/profile')}
            >
              <View style={[styles.actionIcon, { backgroundColor: theme.warning + '20' }]}>
                <Ionicons name="settings-outline" size={24} color={theme.warning} />
              </View>
              <Text style={[styles.actionText, { color: theme.text }]}>
                {t('settings')}
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Disclaimer */}
        <View style={[styles.disclaimer, { backgroundColor: theme.surface }]}>
          <Ionicons name="information-circle-outline" size={20} color={theme.textMuted} />
          <Text style={[styles.disclaimerText, { color: theme.textMuted }]}>
            {t('disclaimer')}
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 100,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 16,
    marginBottom: 24,
  },
  greeting: {
    fontSize: 14,
  },
  userName: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  notificationButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scanCard: {
    marginBottom: 24,
  },
  scanCardContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  scanCardText: {
    flex: 1,
  },
  scanCardTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFFFFF',
    marginBottom: 4,
  },
  scanCardSubtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.8)',
  },
  scanButton: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 12,
  },
  latestResultContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  scoreContainer: {
    marginRight: 16,
  },
  scoreCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 4,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scoreText: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  scoreLabel: {
    fontSize: 10,
  },
  resultDetails: {
    flex: 1,
  },
  skinTypeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  skinTypeLabel: {
    fontSize: 14,
    marginRight: 8,
  },
  skinTypeBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  skinTypeText: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  issuesCount: {
    fontSize: 12,
    marginBottom: 8,
  },
  viewDetailsButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    alignSelf: 'flex-start',
  },
  viewDetailsText: {
    fontSize: 14,
    fontWeight: '500',
    marginRight: 4,
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -6,
  },
  actionCard: {
    width: '47%',
    marginHorizontal: '1.5%',
    marginBottom: 12,
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
    alignItems: 'center',
  },
  actionIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  actionText: {
    fontSize: 14,
    fontWeight: '500',
  },
  disclaimer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: 16,
    borderRadius: 12,
    marginTop: 8,
  },
  disclaimerText: {
    flex: 1,
    fontSize: 12,
    marginLeft: 8,
    lineHeight: 18,
  },
});
