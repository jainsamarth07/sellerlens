/**
 * Sidebar widget that adds the *optional* Flipkart listing upload alongside
 * the primary settlement uploader. Renders:
 *   - a subtle outline "Upload Listing (optional)" button
 *   - a persistent badge once a listing is on file
 *   - a tiny success toast on upload
 *
 * Fully additive — does not touch the existing settlement upload flow.
 */

import { useEffect, useRef, useState } from "react";
import { FileText, BadgeCheck, Loader2 } from "lucide-react";
import {
  fetchListingProducts,
  fetchListingStatus,
  uploadListingFile,
  type ListingUploadResponse,
} from "../lib/api";
import { useAppStore } from "../store/useAppStore";
import Toast, { type ToastMessage } from "./Toast";

export default function ListingUploadButton() {
  const listing = useAppStore((s) => s.listing);
  const setListing = useAppStore((s) => s.setListing);
  const applyListingLookup = useAppStore((s) => s.applyListingLookup);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<ToastMessage | null>(null);

  // On mount, refresh the listing status from the backend so the badge is
  // accurate even if the user opened a fresh tab.
  useEffect(() => {
    let cancelled = false;
    fetchListingStatus()
      .then((s) => {
        if (cancelled) return;
        setListing({ hasListing: s.has_listing, matched: s.listing_count });
      })
      .catch(() => {
        /* backend unavailable — leave persisted state intact */
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onPick = () => inputRef.current?.click();

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-uploading the same file
    if (!file) return;
    setBusy(true);
    try {
      const res: ListingUploadResponse = await uploadListingFile(file);
      try {
        const products = await fetchListingProducts();
        applyListingLookup(products);
      } catch {
        // Non-fatal: keep upload success even if enrichment fetch fails.
      }
      setListing({
        hasListing: res.listing_count > 0,
        matched: res.listing_count,
        lastUploadedAt: new Date().toISOString(),
      });
      setToast({
        id: `t-${Date.now()}`,
        kind: "success",
        text: `Listing uploaded — ${res.matched} products matched.`,
      });
    } catch (err: any) {
      setToast({
        id: `t-${Date.now()}`,
        kind: "error",
        text: err?.response?.data?.detail ?? "Listing upload failed.",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="space-y-2">
        <button
          onClick={onPick}
          disabled={busy}
          aria-label="Upload Flipkart listing file (optional)"
          className="w-full flex items-center justify-center gap-2 border border-white/20 hover:border-white/40 hover:bg-white/5 text-white/80 hover:text-white text-xs font-medium py-2 rounded-lg transition disabled:opacity-50"
        >
          {busy ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <FileText size={14} />
          )}
          <span>{busy ? "Uploading…" : "Upload Listing (optional)"}</span>
        </button>

        {listing.hasListing && listing.matched > 0 && (
          <div className="flex items-center gap-1.5 text-[11px] text-emerald-300/90 px-1">
            <BadgeCheck size={12} />
            <span>Listing: {listing.matched} products matched</span>
          </div>
        )}

        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          className="hidden"
          onChange={onFile}
        />
      </div>

      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </>
  );
}
