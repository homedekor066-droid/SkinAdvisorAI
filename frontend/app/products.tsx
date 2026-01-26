import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTheme } from '../src/context/ThemeContext';
import { useI18n } from '../src/context/I18nContext';
import { useAuth } from '../src/context/AuthContext';
import { skinService } from '../src/services/skinService';
import { Card } from '../src/components';
import { Ionicons } from '@expo/vector-icons';

interface Product {
  name: string;
  product_type: string;
  description: string;
  price_range: string;
  key_ingredients: string[];
}

export default function ProductsScreen() {
  const { theme } = useTheme();
  const { t } = useI18n();
  const { token, user } = useAuth();
  const router = useRouter();
  
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const isPremium = user?.plan === 'premium';

  useEffect(() => {
    fetchProducts();
  }, [token]);

  const fetchProducts = async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    
    try {
      // Get latest scan to get product recommendations
      const scans = await skinService.getScanHistory(token);
      if (scans.length > 0) {
        const latestScan = await skinService.getScanDetail(scans[0].id, token);
        if (latestScan.products) {
          setProducts(latestScan.products);
        }
      }
    } catch (error) {
      console.error('Failed to fetch products:', error);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchProducts();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={theme.text} />
        </TouchableOpacity>
        <Text style={[styles.title, { color: theme.text }]}>{t('products')}</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {/* Premium Lock for Free Users */}
        {!isPremium ? (
          <View style={styles.lockedContainer}>
            <View style={[styles.lockIconCircle, { backgroundColor: theme.primary + '20' }]}>
              <Ionicons name="lock-closed" size={48} color={theme.primary} />
            </View>
            <Text style={[styles.lockedTitle, { color: theme.text }]}>
              Product Recommendations Locked
            </Text>
            <Text style={[styles.lockedDescription, { color: theme.textSecondary }]}>
              Upgrade to Premium to get personalized product recommendations based on your skin analysis.
            </Text>
            <TouchableOpacity 
              style={[styles.unlockButton, { backgroundColor: theme.primary }]}
              onPress={() => router.push('/paywall')}
            >
              <Ionicons name="sparkles" size={18} color="#FFFFFF" />
              <Text style={styles.unlockButtonText}>Unlock Premium</Text>
            </TouchableOpacity>
          </View>
        ) : products.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Ionicons name="leaf-outline" size={64} color={theme.textMuted} />
            <Text style={[styles.emptyTitle, { color: theme.text }]}>
              No Products Yet
            </Text>
            <Text style={[styles.emptyDescription, { color: theme.textSecondary }]}>
              Complete a skin scan to get personalized product recommendations.
            </Text>
            <TouchableOpacity 
              style={[styles.scanButton, { backgroundColor: theme.primary }]}
              onPress={() => router.push('/(tabs)/scan')}
            >
              <Ionicons name="scan-outline" size={20} color="#FFFFFF" />
              <Text style={styles.scanButtonText}>Start Scan</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            <Text style={[styles.sectionSubtitle, { color: theme.textSecondary }]}>
              Based on your latest skin analysis
            </Text>
            
            {products.map((product, index) => (
              <Card key={index} style={styles.productCard}>
                <View style={styles.productHeader}>
                  <View style={[styles.productIcon, { backgroundColor: theme.primary + '20' }]}>
                    <Ionicons name="leaf-outline" size={24} color={theme.primary} />
                  </View>
                  <View style={styles.productInfo}>
                    <Text style={[styles.productName, { color: theme.text }]}>
                      {product.name}
                    </Text>
                    <Text style={[styles.productType, { color: theme.primary }]}>
                      {product.product_type}
                    </Text>
                  </View>
                  <Text style={[styles.priceRange, { color: theme.success }]}>
                    {product.price_range}
                  </Text>
                </View>
                <Text style={[styles.productDescription, { color: theme.textSecondary }]}>
                  {product.description}
                </Text>
                {product.key_ingredients && product.key_ingredients.length > 0 && (
                  <View style={styles.ingredientsSection}>
                    <Text style={[styles.ingredientsLabel, { color: theme.text }]}>
                      Key Ingredients:
                    </Text>
                    <View style={styles.ingredientTags}>
                      {product.key_ingredients.slice(0, 4).map((ingredient, i) => (
                        <View key={i} style={[styles.ingredientTag, { backgroundColor: theme.surface }]}>
                          <Text style={[styles.ingredientText, { color: theme.textSecondary }]}>
                            {ingredient}
                          </Text>
                        </View>
                      ))}
                    </View>
                  </View>
                )}
              </Card>
            ))}
          </>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  backButton: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
  sectionSubtitle: {
    fontSize: 14,
    marginBottom: 16,
  },
  // Locked State
  lockedContainer: {
    alignItems: 'center',
    paddingVertical: 60,
    paddingHorizontal: 20,
  },
  lockIconCircle: {
    width: 100,
    height: 100,
    borderRadius: 50,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  lockedTitle: {
    fontSize: 20,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 12,
  },
  lockedDescription: {
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 24,
  },
  unlockButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 25,
    gap: 8,
  },
  unlockButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  // Empty State
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 60,
    paddingHorizontal: 20,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '700',
    marginTop: 16,
    marginBottom: 8,
  },
  emptyDescription: {
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 24,
  },
  scanButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 25,
    gap: 8,
  },
  scanButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  // Product Card
  productCard: {
    marginBottom: 16,
    padding: 16,
  },
  productHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  productIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  productInfo: {
    flex: 1,
  },
  productName: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 2,
  },
  productType: {
    fontSize: 13,
    fontWeight: '500',
    textTransform: 'capitalize',
  },
  priceRange: {
    fontSize: 14,
    fontWeight: '600',
  },
  productDescription: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 12,
  },
  ingredientsSection: {
    marginTop: 4,
  },
  ingredientsLabel: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  ingredientTags: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  ingredientTag: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  ingredientText: {
    fontSize: 12,
    fontWeight: '500',
  },
});
