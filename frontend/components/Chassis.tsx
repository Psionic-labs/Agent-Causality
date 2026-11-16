/* Plain frame around the read-only explorer. The page fills the window. */

import type { ReactNode } from "react";

export function Chassis({ children }: { children: ReactNode }) {
  return (
    <div className="monitor">
      <div className="screen">
        <div className="screen-scroll">{children}</div>
      </div>
    </div>
  );
}
