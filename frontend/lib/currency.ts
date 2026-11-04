// Currencies a SaaS plan can be priced in. The ISO code is what the backend
// stores (apps.tenants.serializers_saas.SUPPORTED_CURRENCIES must match);
// symbols are display-only. No conversion — a price is in its own currency.

export interface Currency {
  code: string;
  name: string;
  symbol: string;
}

export const CURRENCIES: Currency[] = [
  { code: "INR", name: "Indian Rupee", symbol: "₹" },
  { code: "USD", name: "US Dollar", symbol: "$" },
  { code: "EUR", name: "Euro", symbol: "€" },
  { code: "GBP", name: "British Pound", symbol: "£" },
  { code: "AED", name: "UAE Dirham", symbol: "د.إ" },
  { code: "SAR", name: "Saudi Riyal", symbol: "ر.س" },
  { code: "CAD", name: "Canadian Dollar", symbol: "C$" },
  { code: "AUD", name: "Australian Dollar", symbol: "A$" },
  { code: "SGD", name: "Singapore Dollar", symbol: "S$" },
];

export const DEFAULT_CURRENCY = "INR";

const BY_CODE = new Map(CURRENCIES.map(c => [c.code, c]));

export const currencyLabel = (c: Currency) => `${c.name} (${c.code} - ${c.symbol})`;

// Arabic-script symbols get a space and a left-to-right mark so the amount
// isn't reordered next to them; unknown codes fall back to "XYZ 49".
export function formatMoney(amount: string | number, code: string = DEFAULT_CURRENCY): string {
  const value = Number(amount).toLocaleString(code === "INR" ? "en-IN" : "en-US", { maximumFractionDigits: 2 });
  const c = BY_CODE.get((code || DEFAULT_CURRENCY).toUpperCase());
  if (!c) return `${code} ${value}`;
  return /[؀-ۿ]/.test(c.symbol) ? `‎${c.symbol} ${value}` : `${c.symbol}${value}`;
}
