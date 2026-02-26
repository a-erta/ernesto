import React from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { useQuery } from "@tanstack/react-query";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { getItems, Item } from "../api/client";
import { RootStackParamList } from "../navigation/types";
import { StatusBadge } from "../components/StatusBadge";

type Props = {
  navigation: NativeStackNavigationProp<RootStackParamList, "Dashboard">;
};

export default function DashboardScreen({ navigation }: Props) {
  const { data: items, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ["items"],
    queryFn: getItems,
    refetchInterval: 10_000,
  });

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#6366f1" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={items ?? []}
        keyExtractor={(item) => String(item.id)}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} />
        }
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyText}>No items yet.</Text>
            <Text style={styles.emptySubtext}>Tap + to list your first item.</Text>
          </View>
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.card}
            onPress={() => navigation.navigate("ItemDetail", { itemId: item.id })}
            activeOpacity={0.8}
          >
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle} numberOfLines={1}>
                {item.title ?? "Analyzing…"}
              </Text>
              <StatusBadge status={item.status} />
            </View>
            {item.suggested_price != null && (
              <Text style={styles.price}>€{item.suggested_price.toFixed(2)}</Text>
            )}
            <Text style={styles.meta}>
              {item.listings.length} listing{item.listings.length !== 1 ? "s" : ""} ·{" "}
              {new Date(item.created_at).toLocaleDateString()}
            </Text>
          </TouchableOpacity>
        )}
      />

      <TouchableOpacity
        style={styles.fab}
        onPress={() => navigation.navigate("NewItem")}
        activeOpacity={0.85}
      >
        <Text style={styles.fabIcon}>+</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  list: { padding: 16, gap: 12 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
    gap: 6,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  cardTitle: { fontSize: 16, fontWeight: "600", color: "#1e293b", flex: 1, marginRight: 8 },
  price: { fontSize: 20, fontWeight: "700", color: "#6366f1" },
  meta: { fontSize: 12, color: "#94a3b8" },
  empty: { alignItems: "center", marginTop: 80, gap: 8 },
  emptyText: { fontSize: 18, fontWeight: "600", color: "#475569" },
  emptySubtext: { fontSize: 14, color: "#94a3b8" },
  fab: {
    position: "absolute",
    bottom: 28,
    right: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "#6366f1",
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#6366f1",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 6,
  },
  fabIcon: { color: "#fff", fontSize: 28, lineHeight: 32 },
});
