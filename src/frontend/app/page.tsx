// Root landing page — redirects to /chat for the workspace.

import { redirect } from 'next/navigation';

export default function RootPage() {
  redirect('/chat');
}
