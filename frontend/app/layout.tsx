import type { Metadata } from "next";
import { Chassis } from "../components/Chassis.tsx";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent-Causality DAG Explorer",
  description: "Read-only visual explorer for agent causal traces: failure diagnosis, causal DAG, timeline, and evidence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Chassis>{children}</Chassis>
      </body>
    </html>
  );
}
