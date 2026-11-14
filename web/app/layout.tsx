import type { Metadata } from "next";
import "./globals.css";
import "../components/cattle/spotlight.css";

export const metadata: Metadata = {
  title: "HolyCow · Herd monitor",
  description:
    "A clear view of your herd. Review cattle observations, explore pastures and manage flight history.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
