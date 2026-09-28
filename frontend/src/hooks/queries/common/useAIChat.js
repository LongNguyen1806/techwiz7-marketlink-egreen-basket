import { useMutation } from '@tanstack/react-query';
import { chatApi } from '../../../api/common/chatApi';
import { ApiError } from '../../../lib/ApiError';
import { CHAT_HISTORY_LIMIT, CHAT_MESSAGE_MAX, useChatStore } from '../../../stores/chat.store';

const BUSY_FALLBACK = 'The assistant is busy right now. Please try again later.';

function refusalText(error) {
  const apiError = ApiError.fromUnknown(error);
  return apiError.is('AI_UNAVAILABLE') && apiError.apiMessage ? apiError.apiMessage : BUSY_FALLBACK;
}

export function useAIChat() {
  const add = useChatStore((state) => state.add);
  const setToolsUsed = useChatStore((state) => state.setToolsUsed);

  const mutation = useMutation({
    mutationFn: chatApi.send,
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
