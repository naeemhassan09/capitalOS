import { forwardRef } from 'react';
import { useFlatCategories } from '@/api/categories';
import { Select, type SelectProps } from '@/components/ui/Select';

export interface CategorySelectProps extends SelectProps {
  includeUncategorised?: boolean;
  /** Category ids to render but disable (e.g. ones already taken). */
  disabledOptionIds?: Set<string>;
}

/** Select bound to the (flattened) category tree. Value is category id or ''. */
export const CategorySelect = forwardRef<HTMLSelectElement, CategorySelectProps>(
  function CategorySelect({ includeUncategorised = true, disabledOptionIds, ...props }, ref) {
    const { flat } = useFlatCategories();
    return (
      <Select ref={ref} {...props}>
        {includeUncategorised && <option value="">Uncategorised</option>}
        {flat.map((c) => (
          <option key={c.id} value={c.id} disabled={disabledOptionIds?.has(c.id)}>
            {c.label}
            {c.is_income ? ' (income)' : ''}
          </option>
        ))}
      </Select>
    );
  },
);
