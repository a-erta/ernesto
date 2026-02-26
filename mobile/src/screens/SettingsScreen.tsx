import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Alert,
  ScrollView,
  Switch,
} from "react-native";
import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function SettingsScreen() {
  const { signOut } = useAuth();
  const [ebayToken, setEbayToken] = useState("");
  const [ebaySandbox, setEbaySandbox] = useState(true);

  const saveEbayCreds = useMutation({
    mutationFn: () =>
      api.put("/api/credentials/ebay", {
        user_token: ebayToken,
        is_sandbox: ebaySandbox,
      }),
    onSuccess: () => Alert.alert("Saved", "eBay credentials saved."),
    onError: () => Alert.alert("Error", "Failed to save credentials."),
  });

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.sectionTitle}>eBay Credentials</Text>
      <View style={styles.card}>
        <Text style={styles.label}>User Token</Text>
        <TextInput
          style={styles.input}
          value={ebayToken}
          onChangeText={setEbayToken}
          placeholder="v^1.1#i^1#p^..."
          placeholderTextColor="#94a3b8"
          secureTextEntry
          autoCapitalize="none"
        />
        <View style={styles.switchRow}>
          <Text style={styles.label}>Sandbox mode</Text>
          <Switch value={ebaySandbox} onValueChange={setEbaySandbox} />
        </View>
        <TouchableOpacity
          style={styles.saveBtn}
          onPress={() => saveEbayCreds.mutate()}
          disabled={!ebayToken || saveEbayCreds.isPending}
        >
          <Text style={styles.saveBtnText}>Save eBay Credentials</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.sectionTitle}>Account</Text>
      <View style={styles.card}>
        <TouchableOpacity
          style={styles.signOutBtn}
          onPress={() =>
            Alert.alert("Sign out?", "", [
              { text: "Cancel" },
              { text: "Sign out", style: "destructive", onPress: signOut },
            ])
          }
        >
          <Text style={styles.signOutBtnText}>Sign Out</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  content: { padding: 20, gap: 8, paddingBottom: 40 },
  sectionTitle: { fontSize: 16, fontWeight: "700", color: "#1e293b", marginTop: 16, marginBottom: 4 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 16,
    gap: 12,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  label: { fontSize: 14, fontWeight: "500", color: "#475569" },
  input: {
    borderWidth: 1.5,
    borderColor: "#e2e8f0",
    borderRadius: 10,
    padding: 12,
    fontSize: 14,
    color: "#1e293b",
  },
  switchRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  saveBtn: {
    backgroundColor: "#6366f1",
    borderRadius: 12,
    paddingVertical: 13,
    alignItems: "center",
  },
  saveBtnText: { color: "#fff", fontWeight: "700", fontSize: 14 },
  signOutBtn: {
    borderWidth: 1.5,
    borderColor: "#fca5a5",
    borderRadius: 12,
    paddingVertical: 13,
    alignItems: "center",
  },
  signOutBtnText: { color: "#ef4444", fontWeight: "600", fontSize: 14 },
});
