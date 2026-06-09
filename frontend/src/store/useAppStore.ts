import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api } from "../lib/api";
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
  serverRestored: boolean;

  addPeriod: (upload: UploadResponse) => void;
  setActivePeriod: (id: number) => void;
  setListing: (next: Partial<ListingState>) => void;
  applyListingLookup: (products: Record<string, ListingProductInfo>) => void;
  restoreFromServer: () => Promise<void>;
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
      serverRestored: false,

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
              skus: (p.upload.skus ?? []).map((sku) => {
                const info = products[sku.seller_sku];
                if (!info) return sku;
                return {
                  ...sku,
                  product_name: info.product_name ?? sku.product_name ?? null,
                  mrp: info.mrp ?? sku.mrp ?? null,
                  listing_selling_price:
                    info.selling_price ?? sku.listing_selling_price ?? null,
                  current_stock: info.current_stock ?? sku.current_stock ?? null,
                  listing_status: info.status ?? sku.listing_status ?? null,
                  category: info.category ?? sku.category ?? null,
                };
              }),
            },
          })),
        })),

      restoreFromServer: async () => {
        // Already restored this session — skip to avoid redundant API calls on
        // every route navigation (PrivateRoute mounts fresh for each route).
        const alreadyRestored = useAppStore.getState().serverRestored;
        if (alreadyRestored) return;
        set({ serverRestored: true });
        try {
          const res = await api.get<any[]>("/upload/history");
          if (!res.data.length) return;
          const incoming: PeriodEntry[] = res.data.map((u) => ({
            upload: {
              upload_id: u.upload_id,
              filename: u.filename,
              platform: u.platform,
              rows_parsed: u.rows_parsed,
              summary: u.summary,
              ads_total_spend: u.ads_total_spend,
              skus: u.skus,
              parsing_errors: u.parsing_errors,
              blob_url: u.blob_url,
            } as UploadResponse,
            uploadedAt: u.uploaded_at ?? new Date().toISOString(),
          }));
          set((state) => {
            if (state.periods.length > 0) return state;
            return {
              periods: incoming,
              activePeriodId: incoming[0]?.upload.upload_id ?? null,
            };
          });
        } catch {
          /* silently ignore — user just won't see restored data */
        }
      },

      clearAll: () =>
        set({
          periods: [],
          activePeriodId: null,
          sessionId: newSessionId(),
          listing: emptyListing,
          serverRestored: false,
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
