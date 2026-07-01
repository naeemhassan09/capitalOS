import { Badge, type BadgeVariant } from '@/components/ui/Badge';
import { TX_STATUS_LABELS } from '@/utils/labels';
import type { TxStatus } from '@/types';

const STATUS_VARIANT: Record<TxStatus, BadgeVariant> = {
  settled: 'settled',
  pending: 'pending',
  projected: 'projected',
};

export function TxStatusBadge({ status }: { status: TxStatus }) {
  return <Badge variant={STATUS_VARIANT[status]}>{TX_STATUS_LABELS[status]}</Badge>;
}
