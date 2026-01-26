import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Image,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTheme } from '../../src/context/ThemeContext';
import { useI18n } from '../../src/context/I18nContext';
import { useAuth } from '../../src/context/AuthContext';
import { skinService, ScanHistoryItem } from '../../src/services/skinService';
import { Card, Button } from '../../src/components';
import { Ionicons } from '@expo/vector-icons';
import { format } from 'date-fns';

export default function ProgressScreen() {
  const { theme } = useTheme();
  const { t } = useI18n();
  const { token } = useAuth();
  const router = useRouter();
  const [scans, setScans] = useState<ScanHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchScans = async () => {
    if (!token) return;
    try {
      const data = await skinService.getScanHistory(token);
      setScans(data);
    } catch (error) {
      console.error('Failed to fetch scans:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchScans();
  }, [token]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchScans();
    setRefreshing(false);
  }, [token]);

  const deleteScan = async (scanId: string) => {
    Alert.alert(
      'Delete Scan',
      'Are you sure you want to delete this scan?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await skinService.deleteScan(scanId, token!);
              setScans(scans.filter(s => s.id !== scanId));
            } catch (error) {
              Alert.alert('Error', 'Failed to delete scan');
            }
          },
        },
      ]
    );
  };

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

  // Score color based on score value (YELLOW for most users)
  const getScoreColor = (score: number) => {
    if (score >= 90) return '#4CAF50'; // Excellent - Soft Green (rare)
    if (score >= 75) return '#FFC107'; // Good - Yellow
    if (score >= 60) return '#FFB300'; // Average - Yellow
    if (score >= 40) return '#FF9800'; // Needs attention - Orange
    return '#F44336'; // Poor - Red
  };

  // Calculate progress metrics
  const getProgressMetrics = () => {
    if (scans.length < 2) return null;
    const latest = scans[0];
    const oldest = scans[scans.length - 1];
    const scoreChange = (latest.analysis?.overall_score || 0) - (oldest.analysis?.overall_score || 0);
    return { scoreChange, totalScans: scans.length };
  };

  const metrics = getProgressMetrics();

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      <View style={styles.header}>
        <Text style={[styles.title, { color: theme.text }]}>{t('progress')}</Text>
        <Text style={[styles.subtitle, { color: theme.textSecondary }]}>
          Track your skin health journey
        </Text>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {/* Progress Summary */}
        {metrics && (
          <View style={styles.metricsRow}>
            <Card style={[styles.metricCard, { flex: 1, marginRight: 8 }]}>
              <View style={[styles.metricIcon, { backgroundColor: theme.primary + '20' }]}>
                <Ionicons name="scan-outline" size={24} color={theme.primary} />
              </View>
              <Text style={[styles.metricValue, { color: theme.text }]}>
                {metrics.totalScans}
              </Text>
              <Text style={[styles.metricLabel, { color: theme.textSecondary }]}>
                Total Scans
              </Text>
            </Card>
            <Card style={[styles.metricCard, { flex: 1, marginLeft: 8 }]}>
              <View style={[
                styles.metricIcon,
                { backgroundColor: metrics.scoreChange >= 0 ? theme.success + '20' : theme.error + '20' }
              ]}>
                <Ionicons
                  name={metrics.scoreChange >= 0 ? 'trending-up' : 'trending-down'}
                  size={24}
                  color={metrics.scoreChange >= 0 ? theme.success : theme.error}
                />
              </View>
              <Text style={[
                styles.metricValue,
                { color: metrics.scoreChange >= 0 ? theme.success : theme.error }
              ]}>
                {metrics.scoreChange >= 0 ? '+' : ''}{metrics.scoreChange}
              </Text>
              <Text style={[styles.metricLabel, { color: theme.textSecondary }]}>
                Score Change
              </Text>
            </Card>
          </View>
        )}

        {/* Scan History */}
        <Text style={[styles.sectionTitle, { color: theme.text }]}>
          Scan History
        </Text>

        {scans.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Ionicons name="images-outline" size={48} color={theme.textMuted} />
            <Text style={[styles.emptyText, { color: theme.textSecondary }]}>
              {t('no_scans')}
            </Text>
            <Text style={[styles.emptySubtext, { color: theme.textMuted }]}>
              {t('start_first_scan')}
            </Text>
            <Button
              title={t('scan_skin')}
              onPress={() => router.push('/(tabs)/scan')}
              icon="camera"
              style={{ marginTop: 16 }}
            />
          </Card>
        ) : (
          scans.map((scan, index) => (
            <TouchableOpacity
              key={scan.id}
              onPress={() => router.push({
                pathname: '/scan-result',
                params: { scanId: scan.id }
              })}
            >
              <Card style={styles.scanCard}>
                <View style={styles.scanHeader}>
                  <View style={styles.scanDate}>
                    <Ionicons name="calendar-outline" size={16} color={theme.textSecondary} />
                    <Text style={[styles.dateText, { color: theme.textSecondary }]}>
                      {format(new Date(scan.created_at), 'MMM d, yyyy')}
                    </Text>
                  </View>
                  <TouchableOpacity
                    onPress={() => deleteScan(scan.id)}
                    hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                  >
                    <Ionicons name="trash-outline" size={18} color={theme.error} />
                  </TouchableOpacity>
                </View>

                <View style={styles.scanContent}>
                  {/* Scan Photo Thumbnail */}
                  {scan.image_base64 ? (
                    <View style={[styles.photoContainer, { borderColor: getScoreColor(scan.analysis?.overall_score || 75) }]}>
                      <Image
                        source={{ uri: `data:image/jpeg;base64,${scan.image_base64}` }}
                        style={styles.scanPhoto}
                        resizeMode="cover"
                      />
                    </View>
                  ) : (
                    <View style={[styles.scoreSection]}>
                      <View style={[
                        styles.scoreCircle,
                        { borderColor: getScoreColor(scan.analysis?.overall_score || 75) }
                      ]}>
                        <Text style={[styles.scoreValue, { color: getScoreColor(scan.analysis?.overall_score || 75) }]}>
                          {scan.analysis?.overall_score || '--'}
                        </Text>
                      </View>
                    </View>
                  )}
                  
                  {scan.analysis && (
                    <>
                      <View style={styles.scanDetails}>
                        {/* Score Badge */}
                        <View style={[styles.scoreBadge, { backgroundColor: getScoreColor(scan.analysis.overall_score) + '20' }]}>
                          <Text style={[styles.scoreBadgeText, { color: getScoreColor(scan.analysis.overall_score) }]}>
                            Score: {scan.analysis.overall_score}
                          </Text>
                        </View>
                        <View style={styles.skinTypeRow}>
                          <Text style={[styles.skinTypeLabel, { color: theme.textSecondary }]}>
                            {t('skin_type')}:
                          </Text>
                          <View style={[
                            styles.skinTypeBadge,
                            { backgroundColor: getSkinTypeColor(scan.analysis.skin_type) + '20' }
                          ]}>
                            <Text style={[
                              styles.skinTypeText,
                              { color: getSkinTypeColor(scan.analysis.skin_type) }
                            ]}>
                              {scan.analysis.skin_type}
                            </Text>
                          </View>
                        </View>
                        <Text style={[styles.issuesText, { color: theme.textMuted }]}>
                          {scan.analysis.issues?.length || scan.analysis.issue_count || 0} issues detected
                        </Text>
                      </View>
                      <Ionicons name="chevron-forward" size={20} color={theme.textMuted} />
                    </>
                  )}
                </View>
              </Card>
            </TouchableOpacity>
          ))
        )}
      </ScrollView>
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
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 100,
  },
  metricsRow: {
    flexDirection: 'row',
    marginBottom: 24,
  },
  metricCard: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  metricIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  metricValue: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  metricLabel: {
    fontSize: 12,
    marginTop: 4,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 12,
  },
  emptyCard: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    marginTop: 4,
  },
  scanCard: {
    marginBottom: 12,
  },
  scanHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  scanDate: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  dateText: {
    fontSize: 12,
    marginLeft: 6,
  },
  scanContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  scoreSection: {
    marginRight: 16,
  },
  scoreCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    borderWidth: 3,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scoreValue: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  scanDetails: {
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
  issuesText: {
    fontSize: 12,
  },
  // Photo styles
  photoContainer: {
    width: 64,
    height: 64,
    borderRadius: 32,
    borderWidth: 3,
    overflow: 'hidden',
    marginRight: 16,
  },
  scanPhoto: {
    width: '100%',
    height: '100%',
  },
  scoreBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    alignSelf: 'flex-start',
    marginBottom: 6,
  },
  scoreBadgeText: {
    fontSize: 13,
    fontWeight: '700',
  },
});
