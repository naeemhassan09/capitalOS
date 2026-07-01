import { useState } from 'react';
import { PageHeader } from '@/components/PageHeader';
import { Tabs, type TabItem } from '@/components/ui/Tabs';
import { ProfileSection, ChangePasswordSection } from './settings/ProfileSection';
import { BaseCurrencySection } from './settings/BaseCurrencySection';
import { CategoriesSection } from './settings/CategoriesSection';
import { RulesSection } from './settings/RulesSection';
import { InstitutionsSection } from './settings/InstitutionsSection';
import { ExchangeRatesSection } from './settings/ExchangeRatesSection';
import { ReservesSection } from './settings/ReservesSection';
import { SessionsSection } from './settings/SessionsSection';
import { DataSection } from './settings/DataSection';

type SettingsTab =
  | 'profile'
  | 'currency'
  | 'categories'
  | 'rules'
  | 'institutions'
  | 'rates'
  | 'reserves'
  | 'sessions'
  | 'password'
  | 'data';

const TABS: TabItem[] = [
  { value: 'profile', label: 'Profile' },
  { value: 'currency', label: 'Base currency' },
  { value: 'categories', label: 'Categories' },
  { value: 'rules', label: 'Rules' },
  { value: 'institutions', label: 'Institutions' },
  { value: 'rates', label: 'Exchange rates' },
  { value: 'reserves', label: 'Reserves' },
  { value: 'sessions', label: 'Sessions' },
  { value: 'password', label: 'Change password' },
  { value: 'data', label: 'Data & 2FA' },
];

export function SettingsPage() {
  const [tab, setTab] = useState<SettingsTab>('profile');

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Manage your profile, categorisation and data." />
      <Tabs items={TABS} value={tab} onChange={(v) => setTab(v as SettingsTab)} />

      <div>
        {tab === 'profile' && <ProfileSection />}
        {tab === 'currency' && <BaseCurrencySection />}
        {tab === 'categories' && <CategoriesSection />}
        {tab === 'rules' && <RulesSection />}
        {tab === 'institutions' && <InstitutionsSection />}
        {tab === 'rates' && <ExchangeRatesSection />}
        {tab === 'reserves' && <ReservesSection />}
        {tab === 'sessions' && <SessionsSection />}
        {tab === 'password' && <ChangePasswordSection />}
        {tab === 'data' && <DataSection />}
      </div>
    </div>
  );
}
