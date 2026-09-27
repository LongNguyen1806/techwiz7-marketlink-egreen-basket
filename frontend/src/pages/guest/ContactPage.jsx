import { Link } from 'react-router-dom';
import { BookOpen, Clock, ExternalLink, Mail, MapPin, MessageCircle, Phone, Store } from 'lucide-react';

import { Button } from '../../components/ui/Button';
import { ROUTES } from '../../constants/routes';
import { CONTACT } from '../../constants/siteContent';
import { useChatStore } from '../../stores/chat.store';
import { googleMapsDirectionsUrl } from '../../utils/helpers/geo';
import '../../styles/guest/StaticPages.css';

// D-012: Google Maps only for the Contact page embed and directions links.
const MAP_EMBED = `https://www.google.com/maps?q=${CONTACT.latitude},${CONTACT.longitude}&z=16&output=embed`;

/** G-08 Contact Us: static details and a map, no form (the SRS asks for static information only). */
export default function ContactPage() {
  const openAssistant = useChatStore((state) => state.setOpen);

  const details = [
    { icon: MapPin, title: 'Visit us', body: CONTACT.address },
    { icon: Mail, title: 'Email', body: CONTACT.email, href: `mailto:${CONTACT.email}`, note: CONTACT.replyTime },
    { icon: Phone, title: 'Call', body: CONTACT.phone, href: `tel:${CONTACT.phone.replace(/[^\d+]/g, '')}` },
    { icon: Clock, title: 'Opening hours', body: CONTACT.hours },
  ];

  return (
    <div className="static-page">
      <section className="static-page__hero">
        <div className="static-page__hero-inner">
          <div className="static-page__hero-copy">
            <p className="static-page__eyebrow">Contact</p>
            <h1 className="static-page__title">Get in touch</h1>
            <p className="static-page__lead">
              Questions about an order, a stall or selling on MarketLink? We are happy to help.
            </p>
          </div>
        </div>
      </section>

      <div className="static-page__body">
        <section className="static-page__section" aria-label="Contact details">
          <div className="static-page__cards static-page__cards--4">
            {details.map(({ icon: Icon, title, body, href, note }) => (
              <article key={title} className="static-page__card">
                <span className="static-page__card-icon">
                  <Icon aria-hidden />
                </span>
                <h2 className="static-page__card-title">{title}</h2>
                {href ? (
                  <a href={href} className="static-page__card-link">
                    {body}
                  </a>
                ) : (
                  <p className="static-page__card-text">{body}</p>
                )}
                {note ? <p className="static-page__card-text">{note}</p> : null}
              </article>
            ))}
          </div>
        </section>

        <section className="static-page__section" aria-labelledby="contact-map">
          <h2 className="static-page__section-title" id="contact-map">
            Find us
          </h2>
          <iframe
            title="MarketLink on Google Maps"
            src={MAP_EMBED}
            className="static-page__map"
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
          />
          <div className="static-page__actions static-page__actions--below">
            <Button asChild variant="outline">
              <a href={googleMapsDirectionsUrl(CONTACT.latitude, CONTACT.longitude)} target="_blank" rel="noreferrer">
                <ExternalLink aria-hidden size={16} /> Get directions
              </a>
            </Button>
          </div>
        </section>

        <section className="static-page__section" aria-labelledby="contact-help">
          <h2 className="static-page__section-title" id="contact-help">
            Quick help
          </h2>
          <p className="static-page__section-lead">Most questions are answered faster here than by email.</p>
          <div className="static-page__cards static-page__cards--3">
            <article className="static-page__card">
              <span className="static-page__card-icon">
                <MessageCircle aria-hidden />
              </span>
              <h3 className="static-page__card-title">Ask the assistant</h3>
              <p className="static-page__card-text">
                Opening days, who sells what, pickup times or your orders, answered in your language.
              </p>
              <Button type="button" size="sm" onClick={() => openAssistant(true)}>
                Open the assistant
              </Button>
            </article>
            <article className="static-page__card">
              <span className="static-page__card-icon">
                <BookOpen aria-hidden />
              </span>
              <h3 className="static-page__card-title">Read the FAQ</h3>
              <p className="static-page__card-text">Paying, pickup, cut-off times, cancelling and sharing an account.</p>
              <Button asChild size="sm" variant="outline">
                <Link to="/about#faq">Go to the FAQ</Link>
              </Button>
            </article>
            <article className="static-page__card">
              <span className="static-page__card-icon">
                <Store aria-hidden />
              </span>
              <h3 className="static-page__card-title">Sell on MarketLink</h3>
              <p className="static-page__card-text">
                Open a stall, set your markets and pickup slots, and take reservations before market day.
              </p>
              <Button asChild size="sm" variant="outline">
                <Link to={ROUTES.REGISTER_FARMER}>Become a seller</Link>
              </Button>
            </article>
          </div>
          <p className="static-page__prose">
            Account locked or a problem with an order? Email us from the address on your account and include the
            order number, so we can find it quickly.
          </p>
        </section>
      </div>
    </div>
  );
}
