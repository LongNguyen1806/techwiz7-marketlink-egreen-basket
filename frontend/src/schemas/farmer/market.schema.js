import { z } from 'zod';



const HH_MM = /^([01]\d|2[0-3]):[0-5]\d$/;

const stallLabelField = z
  .string()
  .trim()
  .min(1, 'Enter where your stall is in the market')
  .max(100, 'Stall location must be 100 characters or fewer');

export const stallLabelSchema = z.object({ stall_label: stallLabelField });

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function makeClosureSchema(today) {
  return z
    .object({
      start_date: z.string().regex(ISO_DATE, 'Pick the first day off'),
      end_date: z.string().regex(ISO_DATE, 'Pick the last day off'),
      reason: z.string().trim().max(200, 'Reason must be 200 characters or fewer'),
    })
    .superRefine(({ start_date: start, end_date: end }, ctx) => {
      if (ISO_DATE.test(start) && start < today) {
        ctx.addIssue({ code: 'custom', path: ['start_date'], message: 'The first day off cannot be in the past' });
      }
      if (ISO_DATE.test(start) && ISO_DATE.test(end) && end < start) {
        ctx.addIssue({ code: 'custom', path: ['end_date'], message: 'The last day off must be on or after the first' });
      }
    });
}

export const CLOSURE_DEFAULTS = { start_date: '', end_date: '', reason: '' };

export const joinMarketSchema = z.object({
  market_id: z.number({ error: 'Select a market' }).int().positive('Select a market'),
  stall_label: stallLabelField,
});


export function makePickupSlotSchema({ openTime, closeTime, existingSlots = [] } = {}) {
  return z
    .object({
      day_of_week: z.number().int().min(1).max(7),
      start_time: z.string().regex(HH_MM, 'Use a time such as 07:30'),
      end_time: z.string().regex(HH_MM, 'Use a time such as 09:00'),
    })
    .superRefine(({ day_of_week: day, start_time: start, end_time: end }, ctx) => {
      if (!HH_MM.test(start) || !HH_MM.test(end)) return;
      if (end <= start) {
        ctx.addIssue({ code: 'custom', path: ['end_time'], message: 'End time must be after start time' });
        return;
      }
      if (openTime && start < openTime) {
        ctx.addIssue({ code: 'custom', path: ['start_time'], message: `The market opens at ${openTime}` });
      }
      if (closeTime && end > closeTime) {
        ctx.addIssue({ code: 'custom', path: ['end_time'], message: `The market closes at ${closeTime}` });
      }
      const clash = existingSlots.find(
        (slot) => slot.day_of_week === day && slot.start_time < end && slot.end_time > start,
      );
      if (clash) {
        ctx.addIssue({
          code: 'custom',
          path: ['start_time'],
          message: `Overlaps your ${clash.start_time}–${clash.end_time} slot at this market`,
        });
      }
    });
}
