import PropTypes from 'prop-types';
import { motion } from 'framer-motion';
import { Heart } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '../../ui/Button';
import { useFavorites } from '../../../hooks/queries/customer/useFavorites';
import { ROLES } from '../../../constants';
import { useAuth } from '../../../hooks/authentication/useAuth';
import { cn } from '../../../lib/cn';
import './FavoriteButton.css';

const LABEL = { farmers: 'farmer', products: 'product', markets: 'market' };


export function FavoriteButton({ kind, id, isFavorite, onRequireSignIn, className }) {
  const { role } = useAuth();
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
