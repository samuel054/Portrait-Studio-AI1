import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Portrait Studio AI",
  description: "Identity-first AI portraits. Your face stays your face.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
