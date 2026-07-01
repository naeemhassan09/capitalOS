import { forwardRef } from 'react';
import { useFlatCategories } from '@/api/categories';
import { Select, type SelectProps } from '@/components/ui/Select';

/** Select bound to the (flattened) category tree. Value is category id or ''. */
export const CategorySelect = forwardRef<HTMLSelectElement, SelectProps & { includeUncategorised?: boolean }>(
  function CategorySelect({ includeUncategorised = true, ...props }, ref) {
    const { flat } = useFlatCategories();
    return (
      <Select ref={ref} {...props}>
        {includeUncategorised && <option value="">Uncategorised</option>}
        {flat.map((c) => (
          <option key={c.id} value={c.id}>
            {c.label}
            {c.is_income ? ' (income)' : ''}
          </option>
        ))}
      </Select>
    );
  },
);
