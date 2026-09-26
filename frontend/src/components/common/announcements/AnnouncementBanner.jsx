import { useState } from 'react';
import { Megaphone, X } from 'lucide-react';
import { Button } from '../../ui/Button';
import { useAnnouncements } from '../../../hooks/queries/common/useAnnouncements';
import './AnnouncementBanner.css';

const STORAGE_KEY = 'marketlink-dismissed-announcements';

function readDismissed() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    // Private mode, blocked storage, or a value someone else wrote: treat it as nothing dismissed.
    return [];
  }
}

/**
 * N-04 (PU-13, FR-57): what the administrators want everyone — or one role — to know.
 *
 * Dismissal is remembered per notice id in this browser only, so a new notice still gets through and
 * nothing needs to be stored server-side for it.
 */
export function AnnouncementBanner() {
  const { data } = useAnnouncements();
  const [dismissed, setDismissed] = useState(readDismissed);

  const visible = (data ?? []).filter((announcement) => !dismissed.includes(announcement.id));
  if (visible.length === 0) return null;

  function dismiss(id) {
    const next = [...dismissed, id];
    setDismissed(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Storage unavailable: it stays dismissed for this visit only.
    }
  }

  return (
    <div className="announcement-banner">
      {visible.map((announcement) => (
        <section className="announcement-banner__item" key={announcement.id} aria-label="Announcement">
          <Megaphone className="announcement-banner__icon" aria-hidden />
          <div className="announcement-banner__body">
            <p className="announcement-banner__title">{announcement.title}</p>
            <p className="announcement-banner__content">{announcement.content}</p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={`Dismiss: ${announcement.title}`}
            onClick={() => dismiss(announcement.id)}
          >
            <X className="announcement-banner__close-icon" aria-hidden />
          </Button>
        </section>
      ))}
    </div>
  );
}
