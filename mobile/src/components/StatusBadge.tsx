import React from "react";
import { View, Text, StyleSheet } from "react-native";

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  draft: { bg: "#f1f5f9", text: "#64748b" },
  analyzing: { bg: "#fef9c3", text: "#854d0e" },
  ready: { bg: "#dbeafe", text: "#1d4ed8" },
  publishing: { bg: "#ede9fe", text: "#6d28d9" },
  listed: { bg: "#dcfce7", text: "#15803d" },
  sold: { bg: "#d1fae5", text: "#065f46" },
  archived: { bg: "#f1f5f9", text: "#94a3b8" },
  published: { bg: "#dcfce7", text: "#15803d" },
  ended: { bg: "#f1f5f9", text: "#94a3b8" },
  pending: { bg: "#fef9c3", text: "#854d0e" },
  accepted: { bg: "#dcfce7", text: "#15803d" },
  declined: { bg: "#fee2e2", text: "#b91c1c" },
  countered: { bg: "#ede9fe", text: "#6d28d9" },
};

interface Props {
  status: string;
  small?: boolean;
}

export function StatusBadge({ status, small }: Props) {
  const colors = STATUS_COLORS[status] ?? { bg: "#f1f5f9", text: "#64748b" };
  return (
    <View style={[styles.badge, { backgroundColor: colors.bg }, small && styles.small]}>
      <Text style={[styles.text, { color: colors.text }, small && styles.smallText]}>
        {status}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
  },
  small: {
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  text: {
    fontSize: 12,
    fontWeight: "600",
    textTransform: "capitalize",
  },
  smallText: {
    fontSize: 10,
  },
});
