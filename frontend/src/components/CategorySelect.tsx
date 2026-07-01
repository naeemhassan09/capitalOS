import { forwardRef } from 'react';
import { useCategories } from '@/api/categories';
import { Select, type SelectProps } from '@/components/ui/Select';

export interface CategorySelectProps extends SelectProps {
  includeUncategorised?: boolean;
  /** Category ids to render but disable (e.g. ones already taken). */
  disabledOptionIds?: Set<string>;
}

/**
 * Two-level category picker: top-level groups render as native <optgroup>
 * headings with their subcategories inside, instead of one long flat list.
 * The group itself stays selectable as "<Group> (general)" so records
 * categorised at group level keep working.
 */
export const CategorySelect = forwardRef<HTMLSelectElement, CategorySelectProps>(
  function CategorySelect({ includeUncategorised = true, disabledOptionIds, ...props }, ref) {
    const { data } = useCategories();
    const groups = data ?? [];
    return (
      <Select ref={ref} {...props}>
        {includeUncategorised && <option value="">Uncategorised</option>}
        {groups.map((group) =>
          group.children && group.children.length > 0 ? (
            <optgroup key={group.id} label={group.name}>
              <option value={group.id} disabled={disabledOptionIds?.has(group.id)}>
                {group.name} (general)
              </option>
              {group.children.map((c) => (
                <option key={c.id} value={c.id} disabled={disabledOptionIds?.has(c.id)}>
                  {c.name}
                </option>
              ))}
            </optgroup>
          ) : (
            <option key={group.id} value={group.id} disabled={disabledOptionIds?.has(group.id)}>
              {group.name}
            </option>
          ),
        )}
      </Select>
    );
  },
);
