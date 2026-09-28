import { Link } from 'react-router-dom';
import { BookOpen, Clock, ExternalLink, Mail, MapPin, MessageCircle, Phone, Store } from 'lucide-react';

import { Button } from '../../components/ui/Button';
import { ROUTES } from '../../constants/routes';
import { CONTACT } from '../../constants/siteContent';
import { useChatStore } from '../../stores/chat.store';
import { googleMapsDirectionsUrl } from '../../utils/helpers/geo';
import '../../styles/guest/ContactPage.css';

const MAP_EMBED = `https://www.google.com/maps?q=${CONTACT.latitude},${CONTACT.longitude}&z=16&output=embed`;

const DETAILS = [
  { icon: Mail, label: 'Email', value: CONTACT.email, href: `mailto:${CONTACT.email}`, note: CONTACT.replyTime },
  { icon: Phone, label: 'Phone', value: CONTACT.phone, href: `tel:${CONTACT.phone.replace(/[^\d+]/g, '')}` },
  { icon: MapPin, label: 'Office', value: CONTACT.address },
  { icon: Clock, label: 'Working hours', value: CONTACT.hours },
];

export default function ContactPage() {
  const openAssistant = useChatStore((state) => state.setOpen);

  return (
    <div className="contact-page">
      <section className="contact-page__hero">
        <div className="contact-page__hero-inner">
          <div className="contact-page__hero-copy">
            <p className="contact-page__eyebrow">Contact Us</p>
            <h1 className="contact-page__title">We&apos;d love to hear from you</h1>
            <p className="contact-page__subtitle">
              Questions about an order, a market or opening a stall? We are happy to help.
            </p>
          </div>
        </div>
      </section>

      <section className="contact-page__section">
        <div className="contact-page__grid">
          <div className="contact-page__info">
            <h2 className="contact-page__section-title">Get in touch</h2>
            <p className="contact-page__section-desc">Reach us through any of the channels below.</p>
            <ul className="contact-page__info-list">
              {DETAILS.map(({ icon: Icon, label, value, href, note }) => (
                <li key={label} className="contact-page__info-item">
                  <span className="contact-page__info-icon-wrap">
                    <Icon className="contact-page__info-icon" strokeWidth={1.75} aria-hidden />
                  </span>
                  <div className="contact-page__info-copy">
                    <span className="contact-page__info-label">{label}</span>
                    {href ? (
                      <a href={href} className="contact-page__info-link">
                        {value}
                      </a>
                    ) : (
                      <span className="contact-page__info-value">{value}</span>
                    )}
                    {note ? <span className="contact-page__info-note">{note}</span> : null}
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="contact-page__map-card">
            <div className="contact-page__map-head">
              <h2 className="contact-page__section-title" id="contact-map">
                Find us
              </h2>
              <Button asChild variant="outline" size="sm">
                <a href={googleMapsDirectionsUrl(CONTACT.latitude, CONTACT.longitude)} target="_blank" rel="noreferrer">
                  <ExternalLink className="contact-page__icon-sm" aria-hidden />
                  Get directions
                </a>
              </Button>
            </div>
            <iframe
              title="MarketLink on Google Maps"
              src={MAP_EMBED}
              className="contact-page__map"
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
            />
          </div>
        </div>
      </section>

      <section className="contact-page__help" aria-labelledby="contact-help">
        <div className="contact-page__help-inner">
          <div className="contact-page__help-head">
            <h2 className="contact-page__section-title" id="contact-help">
              Quick help
            </h2>
            <p className="contact-page__section-desc">Most questions are answered faster here than by email.</p>
          </div>
          <ul className="contact-page__help-grid">
            <li className="contact-page__help-card">
              <span className="contact-page__info-icon-wrap">
                <MessageCircle className="contact-page__info-icon" strokeWidth={1.75} aria-hidden />
              </span>
              <h3 className="contact-page__help-title">Ask the assistant</h3>
              <p className="contact-page__help-desc">
                Opening days, who sells what, pickup times or your orders, answered in your language.
              </p>
              <Button type="button" size="sm" className="contact-page__help-action" onClick={() => openAssistant(true)}>
                Open the assistant
              </Button>
            </li>
            <li className="contact-page__help-card">
              <span className="contact-page__info-icon-wrap">
                <BookOpen className="contact-page__info-icon" strokeWidth={1.75} aria-hidden />
              </span>
              <h3 className="contact-page__help-title">Read the FAQ</h3>
              <p className="contact-page__help-desc">Paying, pickup, cut-off times, cancelling and sharing an account.</p>
              <Button asChild size="sm" variant="outline" className="contact-page__help-action">
                <Link to="/about#faq">Go to the FAQ</Link>
              </Button>
            </li>
            <li className="contact-page__help-card">
              <span className="contact-page__info-icon-wrap">
                <Store className="contact-page__info-icon" strokeWidth={1.75} aria-hidden />
              </span>
              <h3 className="contact-page__help-title">Sell on MarketLink</h3>
              <p className="contact-page__help-desc">
                Open a stall, set your markets and pickup slots, and take reservations before market day.
              </p>
              <Button asChild size="sm" variant="outline" className="contact-page__help-action">
                <Link to={ROUTES.REGISTER_FARMER}>Become a seller</Link>
              </Button>
            </li>
          </ul>
          <p className="contact-page__note">
            Account locked or a problem with an order? Email us from the address on your account and include the order
            number, so we can find it quickly.
          </p>
        </div>
      </section>
    </div>
  );
}
