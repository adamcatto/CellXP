import type { Metadata } from 'next';
import '@copilotkit/react-core/v2/styles.css';
import '../styles/theme.css';

export const metadata: Metadata = {
  title: 'CellXP — Genomics Copilot',
  description: 'Agentic copilot for genomics: DNA, RNA, proteins, and metabolites.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
