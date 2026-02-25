import { useState, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Upload, ImagePlus } from "lucide-react";
import { itemsApi } from "../lib/api";

interface Props {
  onClose: () => void;
}

const PLATFORMS = [
  { id: "ebay", label: "eBay" },
  { id: "vinted", label: "Vinted" },
  { id: "depop", label: "Depop" },
];

export function NewItemModal({ onClose }: Props) {
  const [description, setDescription] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(["ebay"]);
  const [images, setImages] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: (form: FormData) => itemsApi.create(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["items"] });
      onClose();
    },
  });

  const handleFiles = (files: FileList | null) => {
    if (!files) return;
    const newFiles = Array.from(files);
    setImages((prev) => [...prev, ...newFiles]);
    newFiles.forEach((f) => {
      const url = URL.createObjectURL(f);
      setPreviews((prev) => [...prev, url]);
    });
  };

  const removeImage = (idx: number) => {
    setImages((prev) => prev.filter((_, i) => i !== idx));
    setPreviews((prev) => prev.filter((_, i) => i !== idx));
  };

  const togglePlatform = (id: string) => {
    setSelectedPlatforms((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  };

  const handleSubmit = () => {
    const form = new FormData();
    if (description) form.append("description", description);
    form.append("platforms", selectedPlatforms.join(","));
    images.forEach((img) => form.append("images", img));
    mutation.mutate(form);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-slate-800">
          <h2 className="text-lg font-semibold">New Item</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Image upload */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Photos <span className="text-slate-500">(required)</span>
            </label>
            <div
              className="border-2 border-dashed border-slate-700 rounded-xl p-6 text-center cursor-pointer hover:border-brand-500 transition-colors"
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                handleFiles(e.dataTransfer.files);
              }}
            >
              <ImagePlus className="w-8 h-8 mx-auto text-slate-500 mb-2" />
              <p className="text-sm text-slate-400">
                Drop photos here or <span className="text-brand-400">browse</span>
              </p>
              <p className="text-xs text-slate-600 mt-1">JPG, PNG, WebP</p>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(e) => handleFiles(e.target.files)}
              />
            </div>
            {previews.length > 0 && (
              <div className="flex gap-2 mt-3 flex-wrap">
                {previews.map((src, i) => (
                  <div key={i} className="relative group">
                    <img
                      src={src}
                      alt=""
                      className="w-16 h-16 object-cover rounded-lg border border-slate-700"
                    />
                    <button
                      onClick={() => removeImage(i)}
                      className="absolute -top-1.5 -right-1.5 bg-red-600 rounded-full w-4 h-4 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <X className="w-2.5 h-2.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Description <span className="text-slate-500">(optional)</span>
            </label>
            <textarea
              className="input resize-none h-24"
              placeholder="e.g. Nike Air Max 90, size 42, worn twice, no box"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {/* Platforms */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Target platforms
            </label>
            <div className="flex gap-2">
              {PLATFORMS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => togglePlatform(p.id)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                    selectedPlatforms.includes(p.id)
                      ? "bg-brand-600 border-brand-500 text-white"
                      : "bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-500"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-3 p-5 border-t border-slate-800">
          <button className="btn-secondary flex-1" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-primary flex-1 flex items-center justify-center gap-2"
            disabled={images.length === 0 || selectedPlatforms.length === 0 || mutation.isPending}
            onClick={handleSubmit}
          >
            {mutation.isPending ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" /> Start Agent
              </>
            )}
          </button>
        </div>

        {mutation.isError && (
          <p className="px-5 pb-4 text-sm text-red-400">
            Error: {(mutation.error as Error).message}
          </p>
        )}
      </div>
    </div>
  );
}
