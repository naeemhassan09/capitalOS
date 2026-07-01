import { Routes, Route, Navigate } from 'react-router-dom';
import { RequireAuth, RedirectIfAuthenticated } from './RequireAuth';
import { AppLayout } from '@/layouts/AppLayout';
import { SetupPage } from '@/pages/SetupPage';
import { LoginPage } from '@/pages/LoginPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { NetWorthPage } from '@/pages/NetWorthPage';
import { AccountsPage } from '@/pages/AccountsPage';
import { TransactionsPage } from '@/pages/TransactionsPage';
import { ImportPage } from '@/pages/ImportPage';
import { CashFlowPage } from '@/pages/CashFlowPage';
import { BudgetPage } from '@/pages/BudgetPage';
import { GoalsPage } from '@/pages/GoalsPage';
import { InvestmentsPage } from '@/pages/InvestmentsPage';
import { ReportsPage } from '@/pages/ReportsPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { BankCallbackPage } from '@/pages/BankCallbackPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

export function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/setup"
        element={
          <RedirectIfAuthenticated page="setup">
            <SetupPage />
          </RedirectIfAuthenticated>
        }
      />
      <Route
        path="/login"
        element={
          <RedirectIfAuthenticated page="login">
            <LoginPage />
          </RedirectIfAuthenticated>
        }
      />

      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="/net-worth" element={<NetWorthPage />} />
        <Route path="/accounts" element={<AccountsPage />} />
        <Route path="/transactions" element={<TransactionsPage />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="/cash-flow" element={<CashFlowPage />} />
        <Route path="/budget" element={<BudgetPage />} />
        <Route path="/goals" element={<GoalsPage />} />
        <Route path="/investments" element={<InvestmentsPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/bank-callback" element={<BankCallbackPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
