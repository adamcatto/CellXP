// Workspace page — renders the full three-column workspace for a session.
// Session ID comes from the URL search param `?session=<id>`.
// When missing, ChatPageClient creates a backend session and updates the URL.

import { ChatPageClient } from '../../components/chat/ChatPageClient';

interface ChatPageProps {
  searchParams?: Promise<{ session?: string }>;
}

export default async function ChatPage({ searchParams }: ChatPageProps) {
  const params = await searchParams;
  return <ChatPageClient sessionId={params?.session} />;
}
