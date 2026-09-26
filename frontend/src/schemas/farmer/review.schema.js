import { z } from 'zod';

// reviews/farmer/serializers_farmer.py ReplyReviewFarmerSerializer (REPLY_MAX_LENGTH = 500).
export const REPLY_MAX_LENGTH = 500;

export const replySchema = z.object({
  reply: z
    .string()
    .trim()
    .min(1, 'Write a short reply first')
    .max(REPLY_MAX_LENGTH, `Reply must be ${REPLY_MAX_LENGTH} characters or fewer`),
});
