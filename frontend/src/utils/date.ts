import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns';

function toDate(value: string | number | Date | null | undefined): Date | null {
  if (value == null) return null;
  if (value instanceof Date) return isValid(value) ? value : null;
  if (typeof value === 'number') {
    const d = new Date(value);
    return isValid(d) ? d : null;
  }
  const parsed = parseISO(value);
  return isValid(parsed) ? parsed : null;
}

/** Format a date, defaulting to "d MMM yyyy" (e.g. "1 Jul 2026"). */
export function formatDate(
  value: string | number | Date | null | undefined,
  pattern = 'd MMM yyyy',
): string {
  const d = toDate(value);
  return d ? format(d, pattern) : '—';
}

/** Short date for dense tables, e.g. "01 Jul". */
export function formatDateShort(value: string | number | Date | null | undefined): string {
  return formatDate(value, 'dd MMM');
}

/** Date + time, e.g. "1 Jul 2026, 14:30". */
export function formatDateTime(value: string | number | Date | null | undefined): string {
  return formatDate(value, "d MMM yyyy, HH:mm");
}

/** Relative time, e.g. "3 days ago". */
export function formatRelative(value: string | number | Date | null | undefined): string {
  const d = toDate(value);
  return d ? formatDistanceToNow(d, { addSuffix: true }) : '—';
}

/** ISO date (yyyy-MM-dd) suitable for <input type="date"> and API params. */
export function toISODate(value: string | number | Date | null | undefined): string {
  const d = toDate(value);
  return d ? format(d, 'yyyy-MM-dd') : '';
}

export function todayISO(): string {
  return format(new Date(), 'yyyy-MM-dd');
}
