import { useState } from 'react';
import PropTypes from 'prop-types';
import { ChevronDown } from 'lucide-react';

import { cn } from '../../lib/cn';
import '../../styles/common/Accordion.css';

/**
 * Question/answer list. Each item is a heading button (aria-expanded) controlling its panel,
 * so it works with a keyboard and screen readers. `openId` opens one item from the start,
 * e.g. when a page is reached through /about#faq-pay.
 */
export function Accordion({ items, openId = null, idPrefix = 'faq' }) {
  const [open, setOpen] = useState(() => new Set(openId ? [openId] : []));

  const toggle = (id) =>
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div className="accordion">
      {items.map((item) => {
        const expanded = open.has(item.id);
        const buttonId = `${idPrefix}-${item.id}`;
        const panelId = `${buttonId}-panel`;
        return (
          <div key={item.id} className={cn('accordion__item', expanded && 'is-open')}>
            <h3 className="accordion__heading">
              <button
                type="button"
                id={buttonId}
                className="accordion__trigger"
                aria-expanded={expanded}
                aria-controls={panelId}
                onClick={() => toggle(item.id)}
              >
                <span>{item.question}</span>
                <ChevronDown aria-hidden className="accordion__chevron" />
              </button>
            </h3>
            <div id={panelId} role="region" aria-labelledby={buttonId} className="accordion__panel" hidden={!expanded}>
              <p>{item.answer}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

Accordion.propTypes = {
  items: PropTypes.arrayOf(
    PropTypes.shape({ id: PropTypes.string.isRequired, question: PropTypes.string.isRequired, answer: PropTypes.string.isRequired }),
  ).isRequired,
  openId: PropTypes.string,
  idPrefix: PropTypes.string,
};
