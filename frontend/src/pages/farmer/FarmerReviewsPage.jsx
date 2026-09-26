import { useState } from 'react';
import { toast } from 'sonner';
import { useFarmerMyReviews, useReplyReview } from '../../features/farmer/hooks/useFarmerReviews';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { RatingStars } from '../../components/common/RatingStars';
import { Button } from '../../components/ui/Button';
import { Textarea } from '../../components/ui/Textarea';
import { formatRelative } from '../../utils/formatters';
import '../../styles/farmer/FarmerReviewsPage.css';
export default function FarmerReviewsPage() {
    const [targetType, setTargetType] = useState('ALL');
    const [rating, setRating] = useState('');
    const [replied, setReplied] = useState('');
    const [drafts, setDrafts] = useState({});
    const query = useFarmerMyReviews({
        type: targetType === 'ALL' ? undefined : targetType,
        rating: rating ? Number(rating) : undefined,
        replied: replied === '' ? undefined : replied === 'true',
    });
    const replyMutation = useReplyReview();
    return (<div className="farmer-reviews-page">
      <PageHeader title="Customer reviews" description="Respond to feedback about your stall and produce."/>

      <div className="page-primitive__actions-row">
        <select className="page-primitive__select" value={targetType} onChange={(e) => {
            const v = e.target.value;
            if (v === 'ALL' || v === 'FARMER' || v === 'PRODUCT')
                setTargetType(v);
        }}>
          <option value="ALL">All</option>
          <option value="FARMER">Stall</option>
          <option value="PRODUCT">Product</option>
        </select>
        <select className="page-primitive__select" value={rating} onChange={(e) => setRating(e.target.value)}>
          <option value="">Any stars</option>
          {[5, 4, 3, 2, 1].map((n) => (<option key={n} value={String(n)}>
              {n} stars
            </option>))}
        </select>
        <select className="page-primitive__select" value={replied} onChange={(e) => setReplied(e.target.value)}>
          <option value="">Any reply</option>
          <option value="false">Unreplied</option>
          <option value="true">Replied</option>
        </select>
      </div>

      {query.isLoading ? (<PageSkeleton />) : query.isError ? (<EmptyState title="Reviews couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()}/>) : !query.data?.results.length ? (<EmptyState title="No reviews yet" description="When shoppers rate a pickup, their feedback will appear here."/>) : (<ul className="farmer-reviews-page__list">
          {query.data.results.map((review) => (<li key={review.id} className="farmer-reviews-page__item">
              <div className="page-primitive__row-start">
                <div>
                  <p className="page-primitive__semibold">
                    {review.customer_display_name}
                  </p>
                  <p className="page-primitive__muted-xs">
                    {review.type === 'PRODUCT'
                    ? (review.product?.name ?? 'Product')
                    : 'Stall review'}{' '}
                    Â· {formatRelative(review.created_at)}
                  </p>
                </div>
                <RatingStars value={review.rating}/>
              </div>
              <p className="page-primitive__muted-sm page-primitive__mt-2">
                {review.comment}
              </p>
              {review.reply ? (<div className="page-primitive__reply-box page-primitive__mt-3">
                  <p className="page-primitive__font-medium">Your reply</p>
                  <p className="page-primitive__muted-sm">{review.reply}</p>
                </div>) : (<div className="farmer-reviews-page__reply-form">
                  <Textarea placeholder="Write a reply (1â€“500 characters)" value={drafts[review.id] ?? ''} onChange={(e) => setDrafts((prev) => ({
                        ...prev,
                        [review.id]: e.target.value,
                    }))}/>
                  <Button size="sm" data-write loading={replyMutation.isPending} onClick={() => {
                        const reply = (drafts[review.id] ?? '').trim();
                        if (!reply) {
                            toast.error('Write a short reply first');
                            return;
                        }
                        replyMutation.mutate({ id: review.id, reply });
                    }}>
                    Send reply
                  </Button>
                </div>)}
            </li>))}
        </ul>)}
    </div>);
}

