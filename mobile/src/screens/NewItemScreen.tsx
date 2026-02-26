import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Image,
  Alert,
  ActivityIndicator,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { createItem } from "../api/client";
import { RootStackParamList } from "../navigation/types";

const PLATFORMS = ["ebay", "vinted", "depop"];

type Props = {
  navigation: NativeStackNavigationProp<RootStackParamList, "NewItem">;
};

export default function NewItemScreen({ navigation }: Props) {
  const [images, setImages] = useState<string[]>([]);
  const [description, setDescription] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(["ebay"]);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      createItem(images, description, selectedPlatforms.join(",")),
    onSuccess: (item) => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
      navigation.replace("ItemDetail", { itemId: item.id });
    },
    onError: (e: any) => {
      Alert.alert("Error", e?.message ?? "Failed to create item");
    },
  });

  const pickImages = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsMultipleSelection: true,
      quality: 0.85,
    });
    if (!result.canceled) {
      setImages((prev) => [...prev, ...result.assets.map((a) => a.uri)]);
    }
  };

  const takePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== "granted") {
      Alert.alert("Permission needed", "Camera access is required to take photos.");
      return;
    }
    const result = await ImagePicker.launchCameraAsync({ quality: 0.85 });
    if (!result.canceled) {
      setImages((prev) => [...prev, result.assets[0].uri]);
    }
  };

  const togglePlatform = (p: string) => {
    setSelectedPlatforms((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );
  };

  const canSubmit = images.length > 0 && selectedPlatforms.length > 0 && !mutation.isPending;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Image picker */}
      <Text style={styles.label}>Photos</Text>
      <View style={styles.imageRow}>
        {images.map((uri, i) => (
          <View key={i} style={styles.imageWrapper}>
            <Image source={{ uri }} style={styles.thumbnail} />
            <TouchableOpacity
              style={styles.removeBtn}
              onPress={() => setImages((prev) => prev.filter((_, j) => j !== i))}
            >
              <Text style={styles.removeBtnText}>✕</Text>
            </TouchableOpacity>
          </View>
        ))}
        <TouchableOpacity style={styles.addPhoto} onPress={pickImages}>
          <Text style={styles.addPhotoIcon}>🖼</Text>
          <Text style={styles.addPhotoText}>Gallery</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.addPhoto} onPress={takePhoto}>
          <Text style={styles.addPhotoIcon}>📷</Text>
          <Text style={styles.addPhotoText}>Camera</Text>
        </TouchableOpacity>
      </View>

      {/* Description */}
      <Text style={styles.label}>Description (optional)</Text>
      <TextInput
        style={styles.textArea}
        multiline
        numberOfLines={4}
        placeholder="e.g. Nike Air Max 90, size 42, worn twice, no box"
        value={description}
        onChangeText={setDescription}
        placeholderTextColor="#94a3b8"
      />

      {/* Platforms */}
      <Text style={styles.label}>Platforms</Text>
      <View style={styles.platformRow}>
        {PLATFORMS.map((p) => (
          <TouchableOpacity
            key={p}
            style={[
              styles.platformChip,
              selectedPlatforms.includes(p) && styles.platformChipActive,
            ]}
            onPress={() => togglePlatform(p)}
          >
            <Text
              style={[
                styles.platformChipText,
                selectedPlatforms.includes(p) && styles.platformChipTextActive,
              ]}
            >
              {p}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Submit */}
      <TouchableOpacity
        style={[styles.submitBtn, !canSubmit && styles.submitBtnDisabled]}
        onPress={() => mutation.mutate()}
        disabled={!canSubmit}
        activeOpacity={0.85}
      >
        {mutation.isPending ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.submitBtnText}>Start Listing →</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  content: { padding: 20, gap: 8, paddingBottom: 40 },
  label: { fontSize: 14, fontWeight: "600", color: "#475569", marginTop: 12, marginBottom: 4 },
  imageRow: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  imageWrapper: { position: "relative" },
  thumbnail: { width: 80, height: 80, borderRadius: 10 },
  removeBtn: {
    position: "absolute",
    top: -6,
    right: -6,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: "#ef4444",
    justifyContent: "center",
    alignItems: "center",
  },
  removeBtnText: { color: "#fff", fontSize: 10, fontWeight: "700" },
  addPhoto: {
    width: 80,
    height: 80,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: "#e2e8f0",
    borderStyle: "dashed",
    justifyContent: "center",
    alignItems: "center",
    gap: 4,
    backgroundColor: "#fff",
  },
  addPhotoIcon: { fontSize: 22 },
  addPhotoText: { fontSize: 10, color: "#64748b" },
  textArea: {
    backgroundColor: "#fff",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    padding: 14,
    fontSize: 15,
    color: "#1e293b",
    minHeight: 100,
    textAlignVertical: "top",
  },
  platformRow: { flexDirection: "row", gap: 10, flexWrap: "wrap" },
  platformChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1.5,
    borderColor: "#e2e8f0",
    backgroundColor: "#fff",
  },
  platformChipActive: { borderColor: "#6366f1", backgroundColor: "#eef2ff" },
  platformChipText: { fontSize: 14, color: "#64748b", fontWeight: "500" },
  platformChipTextActive: { color: "#6366f1", fontWeight: "600" },
  submitBtn: {
    backgroundColor: "#6366f1",
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 24,
  },
  submitBtnDisabled: { backgroundColor: "#c7d2fe" },
  submitBtnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
});
