import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Lightbulb, MessageSquareText, Plus, Send, Search } from 'lucide-react';
import { useState } from 'react';

import { EmptyState } from '../components/EmptyState';
import { NextStepCard } from '../components/NextStepCard';
import { PageHeader } from '../components/PageHeader';
import { SectionFrame } from '../components/SectionFrame';
import { StatusBadge } from '../components/StatusBadge';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import { useDocumentTitle } from '../lib/useDocumentTitle';

export function ChatPage() {
  useDocumentTitle('Research Chat');

  const queryClient = useQueryClient();
  const { accessToken } = useAuth();
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [newThreadTitle, setNewThreadTitle] = useState('General bill research');
  const [message, setMessage] = useState('Which recent housing bills should I inspect before drafting?');

  const threadsQuery = useQuery({
    queryKey: ['chat-threads'],
    queryFn: () => api.listChatThreads(accessToken!),
    enabled: Boolean(accessToken),
  });

  const activeThreadId = threadsQuery.data?.some((item) => item.thread_id === selectedThreadId)
    ? selectedThreadId
    : (threadsQuery.data?.[0]?.thread_id ?? null);

  const messagesQuery = useQuery({
    queryKey: ['chat-messages', activeThreadId],
    queryFn: () => api.listChatMessages(accessToken!, activeThreadId!),
    enabled: Boolean(accessToken && activeThreadId),
  });

  const createThread = useMutation({
    mutationFn: () => api.createChatThread(accessToken!, { title: newThreadTitle }),
    onSuccess: async (thread) => {
      await queryClient.invalidateQueries({ queryKey: ['chat-threads'] });
      setSelectedThreadId(thread.thread_id);
    },
  });

  const sendMessage = useMutation({
    mutationFn: () => api.createChatMessage(accessToken!, activeThreadId!, { content: message.trim() }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['chat-messages', activeThreadId] });
      await queryClient.invalidateQueries({ queryKey: ['chat-threads'] });
      setMessage('');
    },
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Research chat"
        title="Ask questions and keep the answers saved in threads."
        description="Pick a thread on the left, read the conversation in the middle, and send the next message on the right."
        badges={
          <>
            <StatusBadge tone="info">{`${threadsQuery.data?.length ?? 0} saved threads`}</StatusBadge>
            {activeThreadId ? <StatusBadge tone="neutral">Thread selected</StatusBadge> : null}
          </>
        }
      />

      <div className="page-grid chat-layout">
        <SectionFrame
          eyebrow="Threads"
          title="Create or pick a thread"
          description="Keep one topic per thread so the research stays easy to scan."
          icon={MessageSquareText}
        >
          <div className="field-stack">
            <label className="field">
              <span className="field-label">New thread title</span>
              <input
                value={newThreadTitle}
                onChange={(event) => setNewThreadTitle(event.target.value)}
                placeholder="e.g. Housing precedent research"
              />
            </label>
            <button
              type="button"
              className="button button-primary"
              onClick={() => createThread.mutate()}
              disabled={createThread.isPending || !newThreadTitle.trim()}
            >
              <Plus size={16} />
              {createThread.isPending ? 'Creating thread...' : 'Create thread'}
            </button>
          </div>
          <div className="thread-list">
            {threadsQuery.data?.map((thread) => (
              <button
                key={thread.thread_id}
                type="button"
                className={`thread-row${activeThreadId === thread.thread_id ? ' active' : ''}`}
                onClick={() => setSelectedThreadId(thread.thread_id)}
              >
                <strong>{thread.title}</strong>
                <p>{thread.scope}</p>
              </button>
            ))}
            {!threadsQuery.data?.length ? (
              <EmptyState
                icon={MessageSquareText}
                title="No threads yet"
                description="Create the first thread above to start a conversation."
              />
            ) : null}
          </div>
        </SectionFrame>

        <SectionFrame
          eyebrow="Conversation"
          title="Read the saved messages"
          description="Assistant answers stay attached to the thread, along with any citations."
          icon={Lightbulb}
        >
          {activeThreadId ? (
            <div className="message-list">
              {messagesQuery.isLoading ? <div className="loading-line">Loading messages...</div> : null}
              {messagesQuery.data?.map((item) => (
                <article key={item.message_id} className={`message-card ${item.role === 'assistant' ? 'assistant' : 'user'}`}>
                  <div className="message-card-top">
                    <StatusBadge tone={item.role === 'assistant' ? 'info' : 'neutral'}>{item.role}</StatusBadge>
                    <span className="mono-note">{new Date(item.created_at).toLocaleTimeString()}</span>
                  </div>
                  <div className="reading-pane compact">{item.content}</div>
                  {item.citations.length ? (
                    <div className="badge-row">
                      {item.citations.map((citation, index) => (
                        <StatusBadge key={`${item.message_id}-${index}`} tone="neutral">
                          {String(citation.identifier ?? citation.citation ?? citation.title ?? 'reference')}
                        </StatusBadge>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={MessageSquareText}
              title="Pick a thread"
              description="Choose a thread from the left or create a new one to begin."
            />
          )}
        </SectionFrame>

        <SectionFrame
          eyebrow="Next message"
          title="Send the next question"
          description="Ask one clear question at a time so the answer is easier to use."
          icon={Send}
        >
          <div className="field-stack">
            <label className="field">
              <span className="field-label">Question</span>
              <textarea
                rows={12}
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="e.g. Which labor statutes are most likely to conflict with this draft?"
              />
            </label>
            <button
              type="button"
              className="button button-primary"
              onClick={() => sendMessage.mutate()}
              disabled={sendMessage.isPending || !activeThreadId || !message.trim()}
            >
              <Send size={16} />
              {sendMessage.isPending ? 'Sending...' : 'Send message'}
            </button>
            <NextStepCard
              to="/bills"
              title="Next Page (Open Workspaces)"
              description="Go back to your bill projects after the research thread is ready."
              icon={Search}
            />
          </div>
        </SectionFrame>
      </div>
    </div>
  );
}
