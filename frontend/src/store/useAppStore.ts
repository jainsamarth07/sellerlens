import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UploadResponse } from "../lib/api";

export interface PeriodEntry {
  upload: UploadResponse;
  uploadedAt: string;
}

interface AppState {
  periods: PeriodEntry[];
  activePeriodId: number | null;
  sessionId: string;

  addPeriod: (upload: UploadResponse) => void;
  setActivePeriod: (id: number) => void;
  clearAll: () => void;
}

const newSessionId = () =>
  `sess-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      periods: [],
      activePeriodId: null,
      sessionId: newSessionId(),

      addPeriod: (upload) =>
        set((state) => ({
          periods: [
            ...state.periods.filter((p) => p.upload.upload_id !== upload.upload_id),
            { upload, uploadedAt: new Date().toISOString() },
          ],
          activePeriodId: upload.upload_id,
        })),

      setActivePeriod: (id) => set({ activePeriodId: id }),

      clearAll: () =>
        set({ periods: [], activePeriodId: null, sessionId: newSessionId() }),
    }),
    { name: "sellerlens-store" },
  ),
);

export function useActivePeriod(): PeriodEntry | undefined {
  return useAppStore((s) =>
    s.periods.find((p) => p.upload.upload_id === s.activePeriodId),
  );
}
