import clsx from 'clsx';

// Joins conditional class names: cn('btn', isActive && 'btn--active', { 'btn--block': block }).
export function cn(...inputs) {
  return clsx(inputs);
}

export default cn;
