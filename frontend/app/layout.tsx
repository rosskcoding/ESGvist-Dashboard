import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { RuntimeEventListeners } from "@/components/runtime-event-listeners";
import "./globals.css";

const inter = Inter({ subsets: ["latin", "cyrillic"] });

export const metadata: Metadata = {
  title: "ESGvist",
  description: "ESG data management platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} min-h-screen bg-gray-50 antialiased`}>
        <RuntimeEventListeners />
        {children}
      </body>
    </html>
  );
}
