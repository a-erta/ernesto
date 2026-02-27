import React, { useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from "react-native";
import * as WebBrowser from "expo-web-browser";
import { makeRedirectUri } from "expo-auth-session";
import { supabase } from "../context/AuthContext";

WebBrowser.maybeCompleteAuthSession();

export default function LoginScreen() {
  const [loading, setLoading] = useState(false);

  const handleGoogle = async () => {
    setLoading(true);
    try {
      const redirectTo = makeRedirectUri({ scheme: "ernesto" });
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo, skipBrowserRedirect: true },
      });
      if (error) throw error;
      if (data?.url) {
        const result = await WebBrowser.openAuthSessionAsync(data.url, redirectTo);
        if (result.type === "success" && result.url) {
          const url = new URL(result.url);
          const accessToken = url.searchParams.get("access_token");
          const refreshToken = url.searchParams.get("refresh_token");
          if (accessToken) {
            await supabase.auth.setSession({
              access_token: accessToken,
              refresh_token: refreshToken ?? "",
            });
          }
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Something went wrong";
      Alert.alert("Sign in failed", msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      {/* Logo */}
      <View style={styles.logoWrap}>
        <View style={styles.logoBox}>
          <Text style={styles.logoIcon}>🏷️</Text>
        </View>
        <Text style={styles.appName}>Ernesto</Text>
        <Text style={styles.tagline}>Agentic selling assistant</Text>
      </View>

      {/* Card */}
      <View style={styles.card}>
        <Text style={styles.title}>Sign in</Text>

        <TouchableOpacity
          style={[styles.googleBtn, loading && styles.btnDisabled]}
          onPress={handleGoogle}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#1e293b" />
          ) : (
            <>
              <Text style={styles.googleIcon}>G</Text>
              <Text style={styles.googleBtnText}>Continue with Google</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a", justifyContent: "center", padding: 24 },
  logoWrap: { alignItems: "center", marginBottom: 32 },
  logoBox: {
    width: 64, height: 64, borderRadius: 18,
    backgroundColor: "#6366f1", alignItems: "center", justifyContent: "center",
    marginBottom: 12,
  },
  logoIcon: { fontSize: 28 },
  appName: { fontSize: 28, fontWeight: "700", color: "#f1f5f9" },
  tagline: { fontSize: 13, color: "#64748b", marginTop: 4 },
  card: {
    backgroundColor: "#1e293b", borderRadius: 20,
    borderWidth: 1, borderColor: "#334155", padding: 24, gap: 16,
  },
  title: { fontSize: 18, fontWeight: "700", color: "#f1f5f9", textAlign: "center" },
  googleBtn: {
    flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: 10, backgroundColor: "#ffffff", borderRadius: 12,
    paddingVertical: 14,
  },
  btnDisabled: { opacity: 0.5 },
  googleIcon: { fontSize: 16, fontWeight: "700", color: "#4285F4" },
  googleBtnText: { color: "#1e293b", fontWeight: "600", fontSize: 15 },
});
