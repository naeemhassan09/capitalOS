// Shared chart color palette wired to CSS variables so charts respect the theme.
// Recharts needs concrete color strings; we resolve the CSS vars at call time.

function cssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value ? `hsl(${value})` : fallback;
}

export function chartColors() {
  return {
    settled: cssVar('--settled', 'hsl(221 83% 45%)'),
    pending: cssVar('--pending', 'hsl(38 92% 45%)'),
    projected: cssVar('--projected', 'hsl(262 60% 55%)'),
    protected: cssVar('--protected', 'hsl(199 70% 40%)'),
    deployable: cssVar('--deployable', 'hsl(152 60% 36%)'),
    invested: cssVar('--invested', 'hsl(262 60% 55%)'),
    illiquid: cssVar('--illiquid', 'hsl(25 55% 45%)'),
    positive: cssVar('--positive', 'hsl(152 60% 36%)'),
    negative: cssVar('--negative', 'hsl(0 72% 48%)'),
    grid: cssVar('--border', 'hsl(214 24% 88%)'),
    muted: cssVar('--muted-foreground', 'hsl(215 16% 42%)'),
    primary: cssVar('--primary', 'hsl(221 83% 45%)'),
  };
}

// Categorical palette for pie/allocation charts (currency, categories, asset class).
export function categoricalPalette(): string[] {
  return [
    cssVar('--settled', 'hsl(221 83% 45%)'),
    cssVar('--deployable', 'hsl(152 60% 36%)'),
    cssVar('--projected', 'hsl(262 60% 55%)'),
    cssVar('--pending', 'hsl(38 92% 45%)'),
    cssVar('--protected', 'hsl(199 70% 40%)'),
    cssVar('--illiquid', 'hsl(25 55% 45%)'),
    'hsl(330 70% 55%)',
    'hsl(174 62% 40%)',
    'hsl(48 90% 45%)',
    'hsl(280 50% 55%)',
  ];
}
