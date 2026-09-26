import { createElement } from 'react';
import { resolveCategoryIcon } from '../../../utils/categoryIcon';

export function CategoryIcon({ icon, className }) {
  return createElement(resolveCategoryIcon(icon), {
    className,
    strokeWidth: 1.75,
    'aria-hidden': true,
  });
}
