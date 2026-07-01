import { useAuth } from '@/routes/AuthContext';
import { CURRENCY_SYMBOLS, SUPPORTED_CURRENCIES } from '@/utils/money';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';

export function BaseCurrencySection() {
  const { user } = useAuth();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Base currency</CardTitle>
        <CardDescription>All aggregate figures are reported in this currency.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-3xl font-semibold text-foreground">{CURRENCY_SYMBOLS[user.base_currency]}</span>
          <div>
            <p className="font-medium text-foreground">{user.base_currency}</p>
            <p className="text-sm text-muted-foreground">Your reporting currency</p>
          </div>
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-foreground">Supported currencies</p>
          <div className="flex flex-wrap gap-2">
            {SUPPORTED_CURRENCIES.map((c) => (
              <Badge key={c} variant={c === user.base_currency ? 'default' : 'secondary'}>
                {CURRENCY_SYMBOLS[c].trim()} {c}
              </Badge>
            ))}
          </div>
        </div>

        <Alert variant="info" title="Changing the base currency">
          The base currency is set at account creation. Recomputing all historical figures into a new base is a
          significant operation performed by the backend — contact your administrator or use a data re-import if
          you need to change it.
        </Alert>
      </CardContent>
    </Card>
  );
}
