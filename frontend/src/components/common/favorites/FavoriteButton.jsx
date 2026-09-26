import PropTypes from 'prop-types';
import { motion } from 'framer-motion';
import { Heart } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '../../ui/Button';
import { useFavorites } from '../../../hooks/queries/customer/useFavorites';
import { ROLES } from '../../../constants';
import { useAuthStore } from '../../../stores/auth.store';
import { cn } from '../../../lib/cn';
import './FavoriteButton.css';

const LABEL = { farmers: 'farmer', products: 'product', markets: 'market' };

/**
 * The heart on every card (G-02 → G-06, C-08). It reads CU-12 through `useFavorites`, so the state
 * is shared: unhearting a stall on the favourites page also empties its heart in the catalogue.
 *
 * `isFavorite` is the value the list endpoint sent, used until CU-12 has loaded. A guest is invited
 * to sign in instead of firing a request that would come back 403; the screen that owns the modal
 * passes `onRequireSignIn` (G-02 onwards).
 */
export function FavoriteButton({ kind, id, isFavorite, onRequireSignIn, className }) {
  const role = useAuthStore((state) => state.role);
  const isCustomer = role === ROLES.CUSTOMER;
  const { isFavorite: isInFavorites, isLoadingIds, toggle } = useFavorites();
  const active = isCustomer && !isLoadingIds ? isInFavorites(kind, id) : Boolean(isFavorite);

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-pressed={active}
      aria-label={active ? `Remove this ${LABEL[kind]} from favorites` : `Save this ${LABEL[kind]} to favorites`}
      className={cn('favorite-button', className)}
      onClick={(event) => {
        // Cards wrap their body in a link; hearting one must not navigate.
        event.preventDefault();
        event.stopPropagation();
        if (!isCustomer) {
          if (onRequireSignIn) onRequireSignIn();
          else toast.message('Sign in to save favorites');
          return;
        }
        toggle({ kind, id, isFavorite: active });
      }}
    >
      <motion.span
        key={active ? 'on' : 'off'}
        initial={{ scale: 0.7 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', stiffness: 400, damping: 18 }}
      >
        <Heart className={cn('favorite-button__icon', active ? 'is-active' : 'is-idle')} aria-hidden />
      </motion.span>
    </Button>
  );
}

FavoriteButton.propTypes = {
  kind: PropTypes.oneOf(['farmers', 'products', 'markets']).isRequired,
  id: PropTypes.number.isRequired,
  isFavorite: PropTypes.bool,
  onRequireSignIn: PropTypes.func,
  className: PropTypes.string,
};
