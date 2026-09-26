import { useState } from 'react';
import PropTypes from 'prop-types';
import { Link, useParams } from 'react-router-dom';
import { FormAlert } from '../../components/common/forms/FormAlert';
import { RatingInput } from '../../components/common/forms/RatingInput';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Button } from '../../components/ui/Button';
import { Textarea } from '../../components/ui/Textarea';
import { useCustomerOrder } from '../../hooks/queries/customer/useCustomerOrder';
import { useReviewFarmer, useReviewItem } from '../../hooks/queries/customer/useReviews';
import { ApiError } from '../../lib/ApiError';
import './ReviewOrderPage.css';

/**
 * One review form: the stall (CU-10) or one line of the order (CU-11). A rating is required, the
 * comment is not — an empty comment is sent as null, which is what the serializer stores.
 */
function ReviewForm({ subject, name, onSubmit, onError }) {
  const [rating, setRating] = useState(null);
  const [comment, setComment] = useState('');
  const [pending, setPending] = useState(false);
  const headingId = `review-${name}`;

  return (
    <section className="review-order__form" aria-labelledby={headingId}>
      <h2 className="review-order__form-title" id={headingId}>{subject}</h2>

      <RatingInput name={name} value={rating} onChange={setRating} disabled={pending} />

      <Textarea
        aria-label={`Comment about ${subject}`}
        maxLength={1000}
        placeholder="What was it like? (optional)"
        value={comment}
        onChange={(event) => setComment(event.target.value)}
      />

      <Button
        type="button"
        disabled={rating === null}
        loading={pending}
        onClick={async () => {
          setPending(true);
          try {
            await onSubmit({ rating, comment: comment.trim() || null });
          } catch (error) {
            onError(ApiError.fromUnknown(error));
          } finally {
            setPending(false);
          }
        }}
      >
        Submit review
      </Button>
    </section>
  );
}

ReviewForm.propTypes = {
  subject: PropTypes.string.isRequired,
  name: PropTypes.string.isRequired,
  onSubmit: PropTypes.func.isRequired,
  onError: PropTypes.func.isRequired,
};

/**
 * C-07 (CU-10, CU-11, FR-26). Only a COMPLETED order gets here, and `review_state` from the server
 * says exactly what is left: the stall, and the ids of the lines with no review yet. Each subject can
 * be reviewed once — a second attempt is 422 REVIEW_NOT_ALLOWED — so the forms disappear as they are
 * used rather than being guessed at locally.
 */
export default function ReviewOrderPage() {
  const { orderId } = useParams();
  const { data: order, isLoading } = useCustomerOrder(orderId);
  const reviewFarmer = useReviewFarmer(orderId);
  const reviewItem = useReviewItem(orderId);
  const [error, setError] = useState(null);

  if (isLoading || !order) return <PageSkeleton />;

  const state = order.review_state;
  const pendingItems = state
    ? order.items.filter((item) => state.items_pending_review.includes(item.id))
    : [];
  const nothingLeft = !state || (state.farmer_reviewed && pendingItems.length === 0);

  function report(apiError) {
    setError(apiError.friendlyMessage);
  }

  return (
    <section className="review-order">
      <PageHeader
        title={`Review order #${order.id}`}
        description="Your name is shortened on the public page, and the stall may reply."
      />

      <FormAlert message={error} />

      {nothingLeft ? (
        <p className="review-order__done">
          Everything in this order has already been reviewed. Thank you.
        </p>
      ) : (
        <div className="review-order__forms">
          {!state.farmer_reviewed ? (
            <ReviewForm
              subject={order.farmer.stall_name}
              name="farmer"
              onError={report}
              onSubmit={async (payload) => {
                setError(null);
                await reviewFarmer.mutateAsync(payload);
              }}
            />
          ) : null}

          {pendingItems.map((item) => (
            <ReviewForm
              key={item.id}
              subject={item.product_name}
              name={`item-${item.id}`}
              onError={report}
              onSubmit={async (payload) => {
                setError(null);
                await reviewItem.mutateAsync({ itemId: item.id, ...payload });
              }}
            />
          ))}
        </div>
      )}

      <p className="review-order__back">
        <Link to={`/customer/orders/${order.id}`}>Back to the order</Link>
      </p>
    </section>
  );
}
