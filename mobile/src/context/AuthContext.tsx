/**
 * Auth context — Supabase-backed.
 *
 * LOCAL_DEV mode (EXPO_PUBLIC_LOCAL_DEV=true):
 *   Auth is bypassed entirely. The user is always "logged in" and no Supabase
 *   credentials are needed. The backend LOCAL_DEV bypass accepts all requests.
 *
 * Production (EXPO_PUBLIC_LOCAL_DEV=false):
 *   Uses Supabase Auth (email/password + Google OAuth).
 *   Requires EXPO_PUBLIC_SUPABASE_URL and EXPO_PUBLIC_SUPABASE_ANON_KEY.
 */
import React, { createContext, useContext, useState, useEffect } from "react";
import { createClient, type Session, type User } from "@supabase/supabase-js";
import * as SecureStore from "expo-secure-store";

const LOCAL_DEV = process.env.EXPO_PUBLIC_LOCAL_DEV === "true";
const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const isSupabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

// Supabase client — only meaningful when configured
export const supabase = createClient(SUPABASE_URL || "https://placeholder.supabase.co", SUPABASE_ANON_KEY || "placeholder");

interface AuthState {
  session: Session | null;
  user: User | null;
  isLoading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  session: null,
  user: null,
  isLoading: true,
  signOut: async () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (LOCAL_DEV || !isSupabaseConfigured) {
      // Skip auth in local dev
      setIsLoading(false);
      return;
    }

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setIsLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  const signOut = async () => {
    if (isSupabaseConfigured) {
      await supabase.auth.signOut();
    }
    await SecureStore.deleteItemAsync("auth_token");
    setSession(null);
  };

  return (
    <AuthContext.Provider value={{ session, user: session?.user ?? null, isLoading, signOut }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
