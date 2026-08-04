import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aether Desk | AI Trading Platform",
  description: "Personal quantitative investment assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
