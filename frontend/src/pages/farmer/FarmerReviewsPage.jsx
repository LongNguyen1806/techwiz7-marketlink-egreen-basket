import PropTypes from 'prop-types';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { RatingStars } from '../../components/common/RatingStars';
import { Button } from '../../components/ui/Button';
import { Textarea } from '../../components/ui/Textarea';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import { reviewKey, useFarmerReviews, useReplyToReview } from '../../hooks/queries/farmer/useFarmerReviews';
import { ApiError } from '../../lib/ApiError';
import { REPLY_MAX_LENGTH, replySchema } from '../../schemas/farmer/review.schema';
import { formatRelative } from '../../utils/formatters';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';
import '../../styles/farmer/FarmerReviewsPage.css';

const FILTER_DEFAULTS = { type: '', rating: '', replied: '' };

function ReplyForm({ review }) {
  const replyToReview = useReplyToReview();
  const {
    register,
    handleSubmit,
    setError,
    watch,
    formState: { errors },
  } = useForm({ resolver: zodResolver(replySchema), defaultValues: { reply: '' } });

  const onSubmit = handleSubmit(({ reply }) =>
    replyToReview.mutate(
      { type: review.type, id: review.id, reply },
      {
        onError: (error) =>
          mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, setError, { fields: ['reply'] }),
      },
    ),
  );

  return (
    <form className="farmer-reviews-page__reply-form" onSubmit={onSubmit} noValidate>
      <Textarea
        placeholder={`Write a reply (1–${REPLY_MAX_LENGTH} characters)`}
        maxLength={REPLY_MAX_LENGTH}
        aria-label={`Reply to ${review.customer_display_name}`}
        aria-invalid={Boolean(errors.reply)}
        {...register('reply')}
      />
      <p className="page-primitive__muted-xs">
        {watch('reply').length}/{REPLY_MAX_LENGTH}
      </p>
      {errors.reply ? <p className="page-primitive__error">{errors.reply.message}</p> : null}
      {errors.root?.server ? <p className="page-primitive__error">{errors.root.server.message}</p> : null}
      <Button type="submit" size="sm" data-write loading={replyToReview.isPending}>
        Send reply
      </Button>
    </form>
  );
}

ReplyForm.propTypes = { review: PropTypes.object.isRequired };

function ReviewItem({ review }) {
  const subject = review.type === 'PRODUCT' ? (review.product?.name ?? 'Product') : 'Stall review';

  let footer;
  if (review.reply) {
    footer = (
      <div className="page-primitive__reply-box page-primitive__mt-3">
        <p className="page-primitive__font-medium">Your reply</p>
        <p className="page-primitive__muted-sm">{review.reply}</p>
        {review.replied_at ? <p className="page-primitive__muted-xs">{formatRelative(review.replied_at)}</p> : null}
      </div>
    );
  } else if (review.is_hidden_by_admin) {
    // The backend refuses replies to hidden reviews.
    footer = <p className="page-primitive__muted-xs page-primitive__mt-3">Hidden by an administrator, so it can&apos;t be answered.</p>;
  } else {
    footer = <ReplyForm review={review} />;
  }

  return (
    <li className="farmer-reviews-page__item">
      <div className="page-primitive__row-start">
        <div>
          <p className="page-primitive__semibold">{review.customer_display_name}</p>
          <p className="page-primitive__muted-xs">
            {subject} · {formatRelative(review.created_at)}
            {review.is_hidden_by_admin ? ' · Hidden' : ''}
          </p>
        </div>
        <RatingStars value={review.rating} />
      </div>
      {review.comment ? <p className="page-primitive__muted-sm page-primitive__mt-2">{review.comment}</p> : null}
      {footer}
    </li>
  );
}

ReviewItem.propTypes = { review: PropTypes.object.isRequired };

export default function FarmerReviewsPage() {
  const { filters, setFilters, resetFilters } = useUrlFilters(FILTER_DEFAULTS);
  const query = useFarmerReviews({
    type: filters.type || undefined,
    rating: filters.rating || undefined,
    replied: filters.replied || undefined,
  });

  const reviews = query.data?.reviews ?? [];
  const hasFilters = Boolean(filters.type || filters.rating || filters.replied);

  let body;
  if (query.isPending) body = <PageSkeleton />;
  else if (query.isError && !query.data) {
    body = <EmptyState title="Reviews couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  } else if (reviews.length === 0) {
    body = hasFilters ? (
      <EmptyState title="No reviews match these filters" actionLabel="Clear filters" onAction={resetFilters} />
    ) : (
      <EmptyState title="No reviews yet" description="When shoppers rate a pickup, their feedback will appear here." />
    );
  } else {
    body = (
      <>
        <ul className="farmer-reviews-page__list" aria-busy={query.isFetching}>
          {reviews.map((review) => (
            <ReviewItem key={reviewKey(review)} review={review} />
          ))}
        </ul>
        {query.hasNextPage ? (
          <div className="page-primitive__justify-center-row">
            <Button variant="outline" size="sm" loading={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>
              Load more
            </Button>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <div className="farmer-reviews-page">
      <PageHeader title="Customer reviews" description="Respond to feedback about your stall and produce." />

      <div className="page-primitive__actions-row">
        <select
          className="page-primitive__select"
          aria-label="Review type"
          value={filters.type}
          onChange={(event) => setFilters({ type: event.target.value })}
        >
          <option value="">All</option>
          <option value="FARMER">Stall</option>
          <option value="PRODUCT">Product</option>
        </select>
        <select
          className="page-primitive__select"
          aria-label="Stars"
          value={filters.rating}
          onChange={(event) => setFilters({ rating: event.target.value })}
        >
          <option value="">Any stars</option>
          {[5, 4, 3, 2, 1].map((stars) => (
            <option key={stars} value={String(stars)}>
              {stars} star{stars === 1 ? '' : 's'}
            </option>
          ))}
        </select>
        <select
          className="page-primitive__select"
          aria-label="Reply status"
          value={filters.replied}
          onChange={(event) => setFilters({ replied: event.target.value })}
        >
          <option value="">Any reply</option>
          <option value="false">Unreplied</option>
          <option value="true">Replied</option>
        </select>
      </div>

      {body}
    </div>
  );
}
