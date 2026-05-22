/**
 * Helpers for replacing raw SKU codes with human-readable product names
 * sourced from the optional Flipkart listing-file upload.
 *
 * Pure, side-effect-free — safe to call regardless of whether a listing
 * has been uploaded. Falls back to the SKU code when no name is known.
 */

import type { SkuRow } from "./api";

export interface ProductInfo {
  product_name?: string | null;
  mrp?: number | null;
  selling_price?: number | null;
  current_stock?: number | null;
  status?: string | null;
  category?: string | null;
}

/** ``{ sku → ProductInfo }`` map built from an enriched SkuRow[] list. */
export function buildSkuMap(skus: SkuRow[] | undefined | null): Record<string, ProductInfo> {
  const map: Record<string, ProductInfo> = {};
  for (const s of skus ?? []) {
    if (!s?.seller_sku) continue;
    map[s.seller_sku] = {
      product_name: s.product_name ?? null,
      mrp: s.mrp ?? null,
      selling_price: s.listing_selling_price ?? null,
      current_stock: s.current_stock ?? null,
      status: s.listing_status ?? null,
      category: s.category ?? null,
    };
  }
  return map;
}

/**
 * Return the product name (truncated to ``maxLen``) for a SKU code, or the
 * SKU code itself if no listing match exists.
 */
export function getProductName(
  sku: string | null | undefined,
  skuMap: Record<string, ProductInfo> | undefined,
  maxLen = 35,
): string {
  if (!sku) return "";
  const name = skuMap?.[sku]?.product_name;
  if (!name) return sku;
  return name.length > maxLen ? `${name.slice(0, maxLen - 1)}…` : name;
}

/** True when the SKU has a listing-side product name. */
export function hasListing(
  sku: string | null | undefined,
  skuMap: Record<string, ProductInfo> | undefined,
): boolean {
  return Boolean(sku && skuMap?.[sku]?.product_name);
}

/**
 * Replace any standalone occurrence of a known SKU code in ``text`` with its
 * (truncated) product name. Used to clean up AI-generated insights when the
 * model still mentions raw codes alongside names.
 */
export function replaceSkuMentions(
  text: string,
  skuMap: Record<string, ProductInfo> | undefined,
): string {
  if (!text || !skuMap) return text;
  const codes = Object.keys(skuMap)
    .filter((k) => skuMap[k]?.product_name)
    .sort((a, b) => b.length - a.length); // replace longer codes first
  let out = text;
  for (const code of codes) {
    const name = skuMap[code]?.product_name;
    if (!name) continue;
    // Match whole-word SKU code (allow underscores / digits as part of word).
    const escaped = code.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(`\\b${escaped}\\b`, "g");
    out = out.replace(re, getProductName(code, skuMap));
  }
  return out;
}

/** Stock-level colour bucket — for the new SKU-table Stock column. */
export function stockTone(stock: number | null | undefined):
  | "ok" | "low" | "out" | "unknown" {
  if (stock === null || stock === undefined) return "unknown";
  if (stock <= 0) return "out";
  if (stock < 5) return "low";
  return "ok";
}
