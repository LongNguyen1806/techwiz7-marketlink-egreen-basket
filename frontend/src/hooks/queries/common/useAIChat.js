import { useMutation } from '@tanstack/react-query';
import { chatApi } from '../../../api/common/chatApi';
import { ApiError } from '../../../lib/ApiError';
import { CHAT_HISTORY_LIMIT, CHAT_MESSAGE_MAX, useChatStore } from '../../../stores/chat.store';

// Every refusal comes back as the same neutral "busy" text (in the user's language) from the
// backend. Anything else (network down, server error) gets that same neutral wording here, so
// the widget never names a limit or an internal problem.
const BUSY_FALLBACK = 'The assistant is busy right now. Please try again later.';

function refusalText(error) {
  const apiError = ApiError.fromUnknown(error);
  return apiError.is('AI_UNAVAILABLE') && apiError.apiMessage ? apiError.apiMessage : BUSY_FALLBACK;
}

/** Send one question with the recent conversation; the reply (or the problem) lands in the store. */
export function useAIChat() {
  const add = useChatStore((state) => state.add);
  const setToolsUsed = useChatStore((state) => state.setToolsUsed);

  const mutation = useMutation({
    mutationFn: chatApi.send,
    // Shown inside the chat, not as a toast.
    meta: { silent: true },
    onSuccess: (result) => {
      add('assistant', result.reply);
      setToolsUsed(result.tools_used ?? []);
    },
    onError: (error) => add('notice', refusalText(error)),
  });

  const send = (text) => {
    const content = text.trim().slice(0, CHAT_MESSAGE_MAX);
    if (!content || mutation.isPending) return false;
    add('user', content);
    const history = useChatStore
      .getState()
      .messages.filter((message) => message.role === 'user' || message.role === 'assistant')
      .slice(-CHAT_HISTORY_LIMIT)
      .map(({ role, content: body }) => ({ role, content: body }));
    mutation.mutate(history);
    return true;
  };

  return { send, pending: mutation.isPending };
}
