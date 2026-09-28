import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { MessageCircle, RotateCcw, Send, Sparkles, X } from 'lucide-react';

import { Button } from '../../ui/Button';
import { Textarea } from '../../ui/Textarea';
import { usePortal, useAuth } from '../../../hooks/authentication/useAuth';
import { useAIChat } from '../../../hooks/queries/common/useAIChat';
import { usePublicConfig } from '../../../hooks/queries/guest/usePublicCatalog';
import { CHAT_MESSAGE_MAX, useChatStore } from '../../../stores/chat.store';
import { cn } from '../../../lib/cn';
import './AIChatWidget.css';

const ROLE_COPY = {
  GUEST: {
    subtitle: 'Markets, produce, stalls and how pickup works',
    greeting: 'Hi! Ask me about markets, produce, stalls or how pre-ordering works. Any language is fine.',
    suggestions: ['Which markets open on Sunday morning?', 'Who is selling strawberries?', 'How does pickup work?'],
  },
  CUSTOMER: {
    subtitle: 'Markets, produce and your orders',
    greeting: 'Hi! I can find produce and markets, and check your orders. Ask in any language.',
    suggestions: ['Where is my order?', 'Who is selling strawberries?', 'Which markets open on Sunday morning?'],
  },
  FARMER: {
    subtitle: 'Your stall, orders and products',
    greeting: 'Hi! I can summarise your stall, point out products that need attention, and explain the stall screens.',
    suggestions: ['What needs my attention today?', 'Which products are running low?', 'How do I add time off?'],
  },
  ADMIN: {
    subtitle: 'The work queue and how to use the admin screens',
    greeting: 'Hi! I can summarise what is waiting for you and explain the admin screens. Decisions stay with you.',
    suggestions: ['What is waiting for me today?', 'How is the AI listing review doing?', 'How do I set price guidelines?'],
  },
};

const TOOL_LABEL = {
  search_products: 'produce',
  get_market_info: 'markets',
  get_farmer_availability: 'stalls',
  get_my_orders: 'your orders',
  get_my_stall_overview: 'your stall',
  get_my_products: 'your products',
  get_admin_overview: 'work queue',
};

const panelTransition = { type: 'spring', stiffness: 340, damping: 34, mass: 0.85 };

export function AIChatWidget() {
  const portal = usePortal();
  const { user } = useAuth();
  const configQuery = usePublicConfig();
  const role = ROLE_COPY[user?.role] ? user.role : 'GUEST';
  const copy = ROLE_COPY[role];

  const open = useChatStore((state) => state.open);
  const setOpen = useChatStore((state) => state.setOpen);
  const messages = useChatStore((state) => state.messages);
  const toolsUsed = useChatStore((state) => state.toolsUsed);
  const claim = useChatStore((state) => state.claim);
  const reset = useChatStore((state) => state.reset);
  const { send, pending } = useAIChat();

  const [input, setInput] = useState('');
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const owner = `${portal}:${user?.id ?? 'guest'}`;
  useEffect(() => {
    claim(owner);
  }, [claim, owner]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, pending, open]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  if (configQuery.data && configQuery.data.ai_chat_enabled === false) return null;

  const submit = (text) => {
    if (send(text)) setInput('');
  };

  const lastIsAnswer = messages.at(-1)?.role === 'assistant';

  return (
    <>
      <AnimatePresence>
        {open ? (
          <motion.div
            key="ai-panel"
            initial={{ y: '110%', opacity: 0.85 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: '110%', opacity: 0.85 }}
            transition={panelTransition}
            className="ai-chat__panel"
            role="dialog"
            aria-label="MarketLink assistant"
            onKeyDown={(event) => event.key === 'Escape' && setOpen(false)}
          >
            <div className="ai-chat__header">
              <div className="ai-chat__header-copy">
                <p className="ai-chat__header-title">
                  <Sparkles aria-hidden className="ai-chat__header-icon" />
                  MarketLink assistant
                </p>
                <p className="ai-chat__header-sub">{copy.subtitle}</p>
              </div>
              <div className="ai-chat__header-actions">
                {messages.length ? (
                  <Button type="button" size="icon" variant="ghost" className="ai-chat__close" aria-label="Start a new conversation" title="New conversation" onClick={reset}>
                    <RotateCcw className="ai-chat__close-icon" />
                  </Button>
                ) : null}
                <Button type="button" size="icon" variant="ghost" className="ai-chat__close" aria-label="Close chat" onClick={() => setOpen(false)}>
                  <X className="ai-chat__close-icon" />
                </Button>
              </div>
            </div>

            <div className="ai-chat__messages" aria-live="polite">
              <div className="ai-chat__bubble ai-chat__bubble--assistant">{copy.greeting}</div>
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    'ai-chat__bubble',
                    message.role === 'user' && 'ai-chat__bubble--user',
                    message.role === 'assistant' && 'ai-chat__bubble--assistant',
                    message.role === 'notice' && 'ai-chat__bubble--notice',
                  )}
                  role={message.role === 'notice' ? 'status' : undefined}
                >
                  {message.content}
                </div>
              ))}
              {pending ? (
                <div className="ai-chat__typing" aria-label="The assistant is typing">
                  <span />
                  <span />
                  <span />
                </div>
              ) : null}
              {lastIsAnswer && toolsUsed.length ? (
                <p className="ai-chat__tools">Looked up: {toolsUsed.map((name) => TOOL_LABEL[name] ?? name).join(', ')}</p>
              ) : null}
              <div ref={bottomRef} />
            </div>

            {!pending && messages.length === 0 ? (
              <div className="ai-chat__suggestions">
                {copy.suggestions.map((suggestion) => (
                  <button key={suggestion} type="button" className="ai-chat__suggestion" onClick={() => submit(suggestion)}>
                    {suggestion}
                  </button>
                ))}
              </div>
            ) : null}

            <form
              className="ai-chat__composer"
              onSubmit={(event) => {
                event.preventDefault();
                submit(input);
              }}
            >
              <div className="ai-chat__input-wrap">
                <Textarea
                  ref={inputRef}
                  value={input}
                  onChange={(event) => setInput(event.target.value.slice(0, CHAT_MESSAGE_MAX))}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault();
                      submit(input);
                    }
                  }}
                  placeholder="Ask in any language…"
                  rows={2}
                  className="ai-chat__textarea"
                  aria-label="Message for the assistant"
                />
                {input.length > CHAT_MESSAGE_MAX - 100 ? (
                  <span className="ai-chat__counter">
                    {input.length}/{CHAT_MESSAGE_MAX}
                  </span>
                ) : null}
              </div>
              <Button type="submit" size="icon" disabled={pending || !input.trim()} aria-label="Send">
                <Send className="ai-chat__send-icon" />
              </Button>
            </form>
            <p className="ai-chat__disclaimer">The assistant reads MarketLink data but cannot change anything. It can make mistakes.</p>
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
            aria-label="Open the MarketLink assistant"
            onClick={() => setOpen(true)}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.96 }}
          >
            <MessageCircle className="ai-chat__fab-icon" />
          </motion.button>
        ) : null}
      </AnimatePresence>
    </>
  );
}
