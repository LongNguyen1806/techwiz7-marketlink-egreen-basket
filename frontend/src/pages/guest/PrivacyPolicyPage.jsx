import { Link } from 'react-router-dom';

import { LAST_UPDATED, PRIVACY_SECTIONS } from '../../constants/siteContent';
import { useScrollToHash } from '../../hooks/common/useScrollToHash';
import '../../styles/guest/StaticPages.css';

export default function PrivacyPolicyPage() {
  useScrollToHash();

  return (
    <div className="static-page">
      <section className="static-page__hero">
        <div className="static-page__hero-inner">
          <div className="static-page__hero-copy">
            <p className="static-page__eyebrow">Legal</p>
            <h1 className="static-page__title">Privacy Policy</h1>
            <p className="static-page__meta">Last updated: {LAST_UPDATED.privacy}</p>
            <p className="static-page__lead">
              What we collect, why, who can see it and the choices you have, in plain language.
            </p>
          </div>
        </div>
      </section>

      <div className="static-page__body">
        <div className="static-page__legal">
          <nav className="static-page__toc" aria-label="On this page">
            <p className="static-page__toc-title">On this page</p>
            <ol className="static-page__toc-list">
              {PRIVACY_SECTIONS.map((section, index) => (
                <li key={section.id}>
                  <a href={`#${section.id}`} className="static-page__toc-link">
                    {index + 1}. {section.title}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          <div className="static-page__legal-body">
            {PRIVACY_SECTIONS.map((section) => (
              <section key={section.id} id={section.id} className="static-page__legal-section">
                <h2>{section.title}</h2>
                {(section.paragraphs ?? []).map((text) => (
                  <p key={text}>{text}</p>
                ))}
                {section.list ? (
                  <ul>
                    {section.list.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : null}
                {(section.after ?? []).map((text) => (
                  <p key={text}>{text}</p>
                ))}
                {section.id === 'contact' ? (
                  <p>
                    <Link to="/contact" className="static-page__card-link">
                      Go to the Contact page
                    </Link>
                  </p>
                ) : null}
              </section>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
