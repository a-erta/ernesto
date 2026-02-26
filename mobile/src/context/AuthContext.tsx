/**
 * Auth context.
 *
 * In LOCAL_DEV mode (EXPO_PUBLIC_LOCAL_DEV=true): auth is bypassed — the user
 * is always "logged in" with a fake token so the backend LOCAL_DEV bypass
 * accepts all requests.
 *
 * In production: integrate with Cognito via expo-auth-session or AWS Amplify.
 */
import React, { createContext, useContext, useState, useEffect } from "react";
import * as SecureStore from "expo-secure-store";

const LOCAL_DEV = process.env.EXPO_PUBLIC_LOCAL_DEV === "true";
const LOCAL_TOKEN = "local-dev-token";

interface AuthState {
  token: string | null;
  isLoading: boolean;
  signIn: (token: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  token: null,
  isLoading: true,
  signIn: async () => {},
  signOut: async () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(LOCAL_DEV ? LOCAL_TOKEN : null);
  const [isLoading, setIsLoading] = useState(!LOCAL_DEV);

  useEffect(() => {
    if (LOCAL_DEV) return;
    SecureStore.getItemAsync("auth_token").then((t) => {
      setToken(t);
      setIsLoading(false);
    });
  }, []);

  const signIn = async (newToken: string) => {
    await SecureStore.setItemAsync("auth_token", newToken);
    setToken(newToken);
  };

  const signOut = async () => {
    await SecureStore.deleteItemAsync("auth_token");
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ token, isLoading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
