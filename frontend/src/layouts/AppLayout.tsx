import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Landmark,
  Wallet,
  ArrowLeftRight,
  Upload,
  TrendingUp,
  Target,
  LineChart,
  FileBarChart,
  Settings,
  Menu,
  X,
  LogOut,
  ShieldCheck,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { useAuth } from '@/routes/AuthContext';
import { useLogout } from '@/api/auth';
import { useToast } from '@/hooks/useToast';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { ThemeToggle } from '@/components/ui/ThemeToggle';

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/net-worth', label: 'Net Worth', icon: Landmark },
  { to: '/accounts', label: 'Accounts', icon: Wallet },
  { to: '/transactions', label: 'Transactions', icon: ArrowLeftRight },
  { to: '/import', label: 'Import', icon: Upload },
  { to: '/cash-flow', label: 'Cash Flow', icon: TrendingUp },
  { to: '/goals', label: 'Goals', icon: Target },
  { to: '/investments', label: 'Investments', icon: LineChart },
  { to: '/reports', label: 'Reports', icon: FileBarChart },
  { to: '/settings', label: 'Settings', icon: Settings },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1 p-3" aria-label="Primary">
      {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors focus-ring',
              isActive
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground',
            )
          }
        >
          <Icon className="h-5 w-5 shrink-0" aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2 px-2">
      <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <ShieldCheck className="h-5 w-5" aria-hidden />
      </span>
      <div className="leading-tight">
        <p className="text-sm font-semibold text-foreground">CapitalOS</p>
        <p className="text-[11px] text-muted-foreground">Privacy-first finance</p>
      </div>
    </div>
  );
}

export function AppLayout() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const logout = useLogout();
  const toast = useToast();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = async () => {
    try {
      await logout.mutateAsync();
      navigate('/login', { replace: true });
    } catch {
      toast.error('Could not sign out', 'Please try again.');
    }
  };

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-card lg:flex">
        <div className="flex h-16 items-center border-b border-border px-4">
          <Brand />
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          <NavItems />
        </div>
        <div className="border-t border-border p-3">
          <div className="mb-2 rounded-md bg-muted/50 px-3 py-2 text-xs">
            <p className="font-medium text-foreground">{user.display_name}</p>
            <p className="truncate text-muted-foreground">{user.email}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start"
            onClick={handleLogout}
            loading={logout.isPending}
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </div>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/50 animate-fade-in"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <div className="relative z-10 flex h-full w-64 flex-col border-r border-border bg-card animate-slide-in-right">
            <div className="flex h-16 items-center justify-between border-b border-border px-4">
              <Brand />
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground focus-ring"
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto scrollbar-thin">
              <NavItems onNavigate={() => setMobileOpen(false)} />
            </div>
          </div>
        </div>
      )}

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-border bg-background/95 px-4 backdrop-blur">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground focus-ring lg:hidden"
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="lg:hidden">
              <Brand />
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <Badge variant="secondary" title="Base currency">
              Base: {user.base_currency}
            </Badge>
            <ThemeToggle />
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium text-foreground">{user.display_name}</p>
              <p className="text-xs text-muted-foreground">{user.email}</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleLogout}
              loading={logout.isPending}
              className="lg:hidden"
            >
              <LogOut className="h-4 w-4" />
              <span className="sr-only sm:not-sr-only">Sign out</span>
            </Button>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
