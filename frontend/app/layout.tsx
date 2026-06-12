import type { Metadata } from 'next';
import SpaceBackground from '../components/SpaceBackground';
import './globals.css';

export const metadata: Metadata = {
  title: 'Nebula Signals — Cosmic Trading Intelligence',
  description: 'AI-driven cryptocurrency trading signals from the edge of the market universe',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <SpaceBackground />
        <div className="appShell">{children}</div>
      </body>
    </html>
  );
}
