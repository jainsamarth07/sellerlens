import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ListingProductInfo, UploadResponse } from "../lib/api";

export interface PeriodEntry {
  upload: UploadResponse;
  uploadedAt: string;
}

export interface ListingState {
  hasListing: boolean;
  matched: number;
  lastUploadedAt: string | null;
}

interface AppState {
  periods: PeriodEntry[];
  activePeriodId: number | null;
  sessionId: string;
  listing: ListingState;

  addPeriod: (upload: UploadResponse) => void;
  setActivePeriod: (id: number) => void;
  setListing: (next: Partial<ListingState>) => void;
  applyListingLookup: (products: Record<string, ListingProductInfo>) => void;
  clearAll: () => void;
}

const newSessionId = () =>
  `sess-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const emptyListing: ListingState = {
  hasListing: false,
  matched: 0,
  lastUploadedAt: null,
};

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      periods: [],
      activePeriodId: null,
      sessionId: newSessionId(),
      listing: emptyListing,

      addPeriod: (upload) =>
        set((state) => ({
          periods: [
            ...state.periods.filter((p) => p.upload.upload_id !== upload.upload_id),
            { upload, uploadedAt: new Date().toISOString() },
          ],
          activePeriodId: upload.upload_id,
        })),

      setActivePeriod: (id) => set({ activePeriodId: id }),

      setListing: (next) =>
        set((state) => ({ listing: { ...state.listing, ...next } })),

      applyListingLookup: (products) =>
        set((state) => ({
          periods: state.periods.map((p) => ({
            ...p,
            upload: {
              ...p.upload,
              skus: p.upload.skus.map((sku) => {
                const info = products[sku.seller_sku];
                if (!info) {
                  return sku;
                }
                return {
                  ...sku,
                  product_name: info.product_name ?? null,
                  mrp: info.mrp ?? null,
                  listing_selling_price: info.selling_price ?? null,
                  current_stock: info.current_stock ?? null,
                  listing_status: info.status ?? null,
                  category: info.category ?? null,
                };
              }),
            },
          })),
        })),

      clearAll: () =>
        set({
          periods: [],
          activePeriodId: null,
          sessionId: newSessionId(),
          listing: emptyListing,
        }),
    }),
    { name: "sellerlens-store" },
  ),
);

export function useActivePeriod(): PeriodEntry | undefined {
  return useAppStore((s) =>
    s.periods.find((p) => p.upload.upload_id === s.activePeriodId),
  );
}
