import { useLayoutEffect, useRef, useState } from 'react';
import { GripVertical, MessageCircle, Send, X } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';

import { Button } from '@/components/common/forms/Button';
import { Textarea } from '@/components/common/forms/Textarea';
import { useAiChat } from '../../../hooks/queries/common/useAiChat';
import { useDraggableDock } from '../../../hooks/useDraggableDock';
import { cn } from '@/lib/cn';

import './AiChatWidget.css';

const SUGGESTIONS = [
  'Which markets are open today?',
  'Is tomato still in stock?',
  'How do I get to the market?',
];

const panelTransition = {
  type: 'spring',
  stiffness: 340,
  damping: 34,
  mass: 0.85,
};

// Roughly what the panel takes up. Only used to decide which way to open it, so being a few
// pixels out costs nothing.
const PANEL_WIDTH = 380;
const PANEL_HEIGHT = 520;

// The panel hangs off the dock, and the dock can be anywhere. Opening it towards the far edge
// of the screen would push most of it out of view, so it opens towards whichever side has
// room.
function placementFor(rect) {
  if (!rect) return 'up-right';
  const vertical = rect.top >= PANEL_HEIGHT + 16 ? 'up' : 'down';
  const horizontal = rect.right >= PANEL_WIDTH + 16 ? 'right' : 'left';
  return `${vertical}-${horizontal}`;
}

export function AiChatWidget() {
  const { open, setOpen, input, setInput, loading, messages, tools, bottomRef, send } =
    useAiChat();
  const { dragProps, startDrag, wasDragged } = useDraggableDock();
  const dockRef = useRef(null);
  const [placement, setPlacement] = useState('up-right');

  // Measured the moment the panel appears, and again if the window changes size while it is
  // open, because either can turn a comfortable side into one that runs off the screen.
  useLayoutEffect(() => {
    if (!open) return undefined;
    const settle = () => setPlacement(placementFor(dockRef.current?.getBoundingClientRect()));
    settle();
    window.addEventListener('resize', settle);
    return () => window.removeEventListener('resize', settle);
  }, [open]);

  return (
    <motion.div
      ref={dockRef}
      className="ai-chat__dock"
      // The whole dock moves, but only a handle starts the gesture: a pointer press inside
      // the panel belongs to the text box and the buttons, not to a drag.
      {...dragProps}
    >
      <AnimatePresence>
        {open ? (
          <motion.div
            key="ai-panel"
            initial={{ y: 24, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 24, opacity: 0 }}
            transition={panelTransition}
            className={cn('ai-chat__panel', `ai-chat__panel--${placement}`)}
            role="dialog"
            aria-label="MarketLink AI assistant"
          >
            <div className="ai-chat__header">
              <button
                type="button"
                className="ai-chat__grip"
                aria-label="Move the assistant"
                title="Drag to move"
                onPointerDown={startDrag}
              >
                <GripVertical className="ai-chat__grip-icon" />
              </button>
              <div className="ai-chat__header-text">
                <p className="ai-chat__header-title">MarketLink assistant</p>
                <p className="ai-chat__header-sub">
                  Ask about markets, produce, or how to get there
                </p>
              </div>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="ai-chat__close"
                aria-label="Close chat"
                onClick={() => setOpen(false)}
              >
                <X className="ai-chat__close-icon" />
              </Button>
            </div>

            <div className="ai-chat__messages">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={cn(
                    'ai-chat__bubble',
                    m.role === 'user'
                      ? 'ai-chat__bubble--user'
                      : 'ai-chat__bubble--assistant',
                  )}
                >
                  {m.content}
                </div>
              ))}
              {loading ? <div className="ai-chat__typing">Typing…</div> : null}
              {tools.length > 0 && !loading ? (
                <div className="ai-chat__tools">
                  {tools.map((t) => (
                    <span key={t} className="ai-chat__tool-tag">
                      {t}
                    </span>
                  ))}
                </div>
              ) : null}
              <div ref={bottomRef} />
            </div>

            {!loading && messages.length <= 2 ? (
              <div className="ai-chat__suggestions">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className="ai-chat__suggestion"
                    onClick={() => void send(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            ) : null}

            <form
              className="ai-chat__composer"
              onSubmit={(e) => {
                e.preventDefault();
                void send(input);
              }}
            >
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value.slice(0, 1000))}
                placeholder="Ask about markets or produce…"
                rows={2}
                className="ai-chat__textarea"
                aria-label="Message for AI assistant"
              />
              <Button
                type="submit"
                size="icon"
                disabled={loading || !input.trim()}
                aria-label="Send"
              >
                <Send className="ai-chat__send-icon" />
              </Button>
            </form>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {!open ? (
          <motion.button
            type="button"
            key="ai-fab"
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85, transition: { duration: 0.1 } }}
            transition={{ duration: 0.18 }}
            className="ai-chat__fab"
            aria-label="Open AI assistant. Drag to move it out of the way."
            title="Drag to move"
            onPointerDown={startDrag}
            onClick={() => {
              // A drop fires a click too. Without this, moving the button off a covered
              // control would also open the panel on top of it.
              if (wasDragged()) return;
              setOpen(true);
            }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.96 }}
          >
            <MessageCircle className="ai-chat__fab-icon" />
          </motion.button>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}
