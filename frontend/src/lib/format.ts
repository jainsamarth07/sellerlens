/** Indian-numbering helpers for currency, percent and counts. */

export function formatINR(value: number | null | undefined, opts: { decimals?: number } = {}): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "₹0";
  const { decimals = 0 } = opts;
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  const fixed = abs.toFixed(decimals);
  const [intPart, decPart] = fixed.split(".");

  let grouped: string;
  if (intPart.length <= 3) {
    grouped = intPart;
  } else {
    const last3 = intPart.slice(-3);
    let rest = intPart.slice(0, -3);
    const groups: string[] = [];
    while (rest.length > 2) {
      groups.unshift(rest.slice(-2));
      rest = rest.slice(0, -2);
    }
    if (rest) groups.unshift(rest);
    grouped = groups.concat(last3).join(",");
  }

  return `₹${sign}${grouped}${decPart ? "." + decPart : ""}`;
}

export function formatPct(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "0%";
  return `${value.toFixed(decimals)}%`;
}

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) return "0";
  return new Intl.NumberFormat("en-IN").format(value);
}
