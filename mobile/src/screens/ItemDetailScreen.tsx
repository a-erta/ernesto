import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
} from "react-native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { RouteProp } from "@react-navigation/native";
import { getItem, getOffers, approveItem, cancelItem, decideOffer } from "../api/client";
import { RootStackParamList } from "../navigation/types";
import { StatusBadge } from "../components/StatusBadge";
import { useItemWebSocket } from "../hooks/useItemWebSocket";

type Props = {
  navigation: NativeStackNavigationProp<RootStackParamList, "ItemDetail">;
  route: RouteProp<RootStackParamList, "ItemDetail">;
};

export default function ItemDetailScreen({ navigation, route }: Props) {
  const { itemId } = route.params;
  const queryClient = useQueryClient();
  const { lastEvent } = useItemWebSocket(itemId);
  const [finalPrice, setFinalPrice] = useState("");
  const [description, setDescription] = useState("");
  const [counterAmount, setCounterAmount] = useState("");

  const { data: item, isLoading } = useQuery({
    queryKey: ["item", itemId],
    queryFn: () => getItem(itemId),
    refetchInterval: lastEvent?.type === "step" ? 3000 : 10000,
  });

  // Pre-fill description from AI proposal when item loads
  React.useEffect(() => {
    if (item?.proposed_description && !description) {
      setDescription(item.proposed_description);
    }
  }, [item?.proposed_description]);

  const { data: offers } = useQuery({
    queryKey: ["offers", itemId],
    queryFn: () => getOffers(itemId),
    enabled: item?.status === "listed" || item?.status === "ready",
    refetchInterval: 15_000,
  });

  const approveMutation = useMutation({
    mutationFn: () => approveItem(itemId, parseFloat(finalPrice), description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["item", itemId] });
      queryClient.invalidateQueries({ queryKey: ["items"] });
    },
    onError: (e: any) => Alert.alert("Error", e?.message),
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelItem(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
      navigation.goBack();
    },
  });

  const offerMutation = useMutation({
    mutationFn: ({
      offerId,
      action,
      counter,
    }: {
      offerId: number;
      action: "accept" | "decline" | "counter";
      counter?: number;
    }) => decideOffer(offerId, action, counter),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["offers", itemId] }),
  });

  if (isLoading || !item) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#6366f1" />
      </View>
    );
  }

  const pendingOffers = (offers ?? []).filter((o) => o.status === "pending");
  const needsApproval = item.status === "ready";

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.headerRow}>
        <Text style={styles.title}>{item.title ?? "Analyzing…"}</Text>
        <StatusBadge status={item.status} />
      </View>

      {item.brand && <Text style={styles.meta}>{item.brand} · {item.condition}</Text>}
      {item.category && <Text style={styles.meta}>{item.category}</Text>}

      {/* Price */}
      {item.suggested_price != null && (
        <View style={styles.priceCard}>
          <Text style={styles.priceLabel}>Suggested price</Text>
          <Text style={styles.priceValue}>€{item.suggested_price.toFixed(2)}</Text>
        </View>
      )}

      {/* Live agent status */}
      {lastEvent && (
        <View style={styles.agentBanner}>
          <Text style={styles.agentBannerText}>
            {lastEvent.type === "error"
              ? `⚠️ ${lastEvent.error}`
              : `⚡ ${lastEvent.step ?? lastEvent.type}`}
          </Text>
        </View>
      )}

      {/* Approval panel */}
      {needsApproval && (
        <View style={styles.approvalCard}>
          <Text style={styles.approvalTitle}>Review & Approve</Text>
          <Text style={styles.approvalDesc}>
            Edit the description and set your final price, then publish.
          </Text>

          <Text style={styles.fieldLabel}>Description</Text>
          <TextInput
            style={styles.descriptionInput}
            multiline
            numberOfLines={5}
            placeholder="Describe your item for buyers…"
            value={description}
            onChangeText={setDescription}
            placeholderTextColor="#94a3b8"
            textAlignVertical="top"
          />
          <Text style={styles.charCount}>{description.length} characters</Text>

          <Text style={styles.fieldLabel}>Final price (€)</Text>
          <TextInput
            style={styles.priceInput}
            keyboardType="decimal-pad"
            placeholder={`${item.suggested_price?.toFixed(2) ?? "0.00"}`}
            value={finalPrice}
            onChangeText={setFinalPrice}
            placeholderTextColor="#94a3b8"
          />
          <TouchableOpacity
            style={styles.approveBtn}
            onPress={() => approveMutation.mutate()}
            disabled={!finalPrice || approveMutation.isPending}
            activeOpacity={0.85}
          >
            {approveMutation.isPending ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.approveBtnText}>Publish →</Text>
            )}
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.cancelBtn}
            onPress={() =>
              Alert.alert("Cancel listing?", "This will archive the item.", [
                { text: "No" },
                { text: "Yes, cancel", style: "destructive", onPress: () => cancelMutation.mutate() },
              ])
            }
          >
            <Text style={styles.cancelBtnText}>Cancel</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Listings */}
      {item.listings.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Listings</Text>
          {item.listings.map((l) => (
            <View key={l.id} style={styles.listingRow}>
              <Text style={styles.listingPlatform}>{l.platform}</Text>
              <Text style={styles.listingPrice}>€{l.price?.toFixed(2) ?? "—"}</Text>
              <StatusBadge status={l.status} small />
            </View>
          ))}
        </View>
      )}

      {/* Pending offers */}
      {pendingOffers.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Pending Offers</Text>
          {pendingOffers.map((offer) => (
            <View key={offer.id} style={styles.offerCard}>
              <View style={styles.offerHeader}>
                <Text style={styles.offerBuyer}>{offer.buyer_username ?? "Buyer"}</Text>
                <Text style={styles.offerAmount}>€{offer.amount.toFixed(2)}</Text>
              </View>
              <View style={styles.offerActions}>
                <TouchableOpacity
                  style={[styles.offerBtn, styles.acceptBtn]}
                  onPress={() => offerMutation.mutate({ offerId: offer.id, action: "accept" })}
                >
                  <Text style={styles.offerBtnText}>Accept</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.offerBtn, styles.declineBtn]}
                  onPress={() => offerMutation.mutate({ offerId: offer.id, action: "decline" })}
                >
                  <Text style={[styles.offerBtnText, { color: "#ef4444" }]}>Decline</Text>
                </TouchableOpacity>
                <TextInput
                  style={styles.counterInput}
                  keyboardType="decimal-pad"
                  placeholder="Counter €"
                  value={counterAmount}
                  onChangeText={setCounterAmount}
                  placeholderTextColor="#94a3b8"
                />
                <TouchableOpacity
                  style={[styles.offerBtn, styles.counterBtn]}
                  onPress={() =>
                    offerMutation.mutate({
                      offerId: offer.id,
                      action: "counter",
                      counter: parseFloat(counterAmount),
                    })
                  }
                  disabled={!counterAmount}
                >
                  <Text style={styles.offerBtnText}>Counter</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  content: { padding: 20, gap: 12, paddingBottom: 40 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 8,
  },
  title: { fontSize: 22, fontWeight: "700", color: "#1e293b", flex: 1 },
  meta: { fontSize: 14, color: "#64748b" },
  priceCard: {
    backgroundColor: "#eef2ff",
    borderRadius: 12,
    padding: 16,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  priceLabel: { fontSize: 14, color: "#6366f1", fontWeight: "500" },
  priceValue: { fontSize: 24, fontWeight: "700", color: "#4f46e5" },
  agentBanner: {
    backgroundColor: "#fef9c3",
    borderRadius: 10,
    padding: 12,
  },
  agentBannerText: { fontSize: 13, color: "#854d0e" },
  approvalCard: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 18,
    gap: 10,
    borderWidth: 2,
    borderColor: "#6366f1",
  },
  approvalTitle: { fontSize: 16, fontWeight: "700", color: "#1e293b" },
  approvalDesc: { fontSize: 13, color: "#64748b" },
  fieldLabel: { fontSize: 13, fontWeight: "600", color: "#475569", marginTop: 4 },
  descriptionInput: {
    borderWidth: 1.5,
    borderColor: "#e2e8f0",
    borderRadius: 10,
    padding: 12,
    fontSize: 14,
    color: "#1e293b",
    minHeight: 110,
    backgroundColor: "#f8fafc",
  },
  charCount: { fontSize: 11, color: "#94a3b8", textAlign: "right" },
  priceInput: {
    borderWidth: 1.5,
    borderColor: "#e2e8f0",
    borderRadius: 10,
    padding: 12,
    fontSize: 18,
    fontWeight: "600",
    color: "#1e293b",
  },
  approveBtn: {
    backgroundColor: "#6366f1",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  approveBtnText: { color: "#fff", fontWeight: "700", fontSize: 15 },
  cancelBtn: { alignItems: "center", paddingVertical: 8 },
  cancelBtnText: { color: "#94a3b8", fontSize: 14 },
  section: { gap: 8 },
  sectionTitle: { fontSize: 16, fontWeight: "700", color: "#1e293b", marginBottom: 4 },
  listingRow: {
    backgroundColor: "#fff",
    borderRadius: 10,
    padding: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  listingPlatform: { fontSize: 14, fontWeight: "600", color: "#475569", flex: 1 },
  listingPrice: { fontSize: 15, fontWeight: "700", color: "#1e293b" },
  offerCard: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 14,
    gap: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  offerHeader: { flexDirection: "row", justifyContent: "space-between" },
  offerBuyer: { fontSize: 14, fontWeight: "600", color: "#475569" },
  offerAmount: { fontSize: 18, fontWeight: "700", color: "#1e293b" },
  offerActions: { flexDirection: "row", gap: 8, flexWrap: "wrap", alignItems: "center" },
  offerBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1.5,
  },
  acceptBtn: { borderColor: "#22c55e", backgroundColor: "#f0fdf4" },
  declineBtn: { borderColor: "#fca5a5", backgroundColor: "#fef2f2" },
  counterBtn: { borderColor: "#6366f1", backgroundColor: "#eef2ff" },
  offerBtnText: { fontSize: 13, fontWeight: "600", color: "#22c55e" },
  counterInput: {
    borderWidth: 1.5,
    borderColor: "#e2e8f0",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    fontSize: 14,
    color: "#1e293b",
    width: 90,
  },
});
