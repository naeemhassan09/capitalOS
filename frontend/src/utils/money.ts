import type { Currency } from '@/types';

/**
 * Coerce an unknown value (often a JSON string from the backend, or the
 * exotic "0E-8" Decimal form, or null) into a finite number. Non-numeric
 * inputs collapse to 0 so arithmetic never yields NaN.
 */
export function num(x: unknown): number {
  return Number(x) || 0;
}

export const CURRENCY_SYMBOLS: Record<Currency, string> = {
  EUR: '€',
  USD: '$',
  GBP: '£',
  SAR: 'SAR ',
  PKR: 'PKR ',
};

export const SUPPORTED_CURRENCIES: Currency[] = ['EUR', 'PKR', 'USD', 'GBP', 'SAR'];

// PKR is conventionally shown as whole numbers with grouped thousands.
const WHOLE_NUMBER_CURRENCIES = new Set<Currency>(['PKR']);

/**
 * Format a monetary amount.
 * - EUR/USD/GBP/SAR: 2 decimal places with symbol, e.g. "€1,234.50"
 * - PKR: whole-number grouped, e.g. "PKR 1,776,425"
 * Negative amounts keep the sign in front of the symbol: "-€10.00".
 */
export function formatMoney(
  amount: number | null | undefined,
  currency: Currency | string = 'EUR',
  opts: { signDisplay?: 'auto' | 'always' | 'never'; showSymbol?: boolean } = {},
): string {
  const { signDisplay = 'auto', showSymbol = true } = opts;
  const value = amount ?? 0;
  const cur = (currency as Currency) in CURRENCY_SYMBOLS ? (currency as Currency) : 'EUR';
  const whole = WHOLE_NUMBER_CURRENCIES.has(cur);
  const fractionDigits = whole ? 0 : 2;

  const abs = Math.abs(value);
  const rounded = whole ? Math.round(abs) : abs;
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(rounded);

  const symbol = showSymbol ? CURRENCY_SYMBOLS[cur] : '';
  let sign = '';
  if (value < 0 && signDisplay !== 'never') sign = '-';
  else if (value > 0 && signDisplay === 'always') sign = '+';

  return `${sign}${symbol}${formatted}`;
}

/** Compact form for large figures on small cards, e.g. "€1.8M". */
export function formatMoneyCompact(
  amount: number | null | undefined,
  currency: Currency | string = 'EUR',
): string {
  const value = amount ?? 0;
  const cur = (currency as Currency) in CURRENCY_SYMBOLS ? (currency as Currency) : 'EUR';
  const abs = Math.abs(value);
  if (abs < 1000) return formatMoney(value, cur);
  const compact = new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(abs);
  const sign = value < 0 ? '-' : '';
  return `${sign}${CURRENCY_SYMBOLS[cur]}${compact}`;
}

/** Render a fraction (0..1) as a percentage string. */
export function formatPercent(fraction: number | null | undefined, digits = 1): string {
  const value = fraction ?? 0;
  return `${(value * 100).toFixed(digits)}%`;
}

/** Signed liability/asset balances → a human "credit"/"debit" hint. */
export function isNegative(amount: number | null | undefined): boolean {
  return (amount ?? 0) < 0;
}
