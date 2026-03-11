import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NEPSE-ALPHA ULTIMATE — Stock Prediction Intelligence",
  description: "Five-Layer Stock Prediction Intelligence for Nepal Stock Exchange. Daily, Weekly, Monthly predictions powered by BSTS, Kalman Filter, and Machine Learning.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
