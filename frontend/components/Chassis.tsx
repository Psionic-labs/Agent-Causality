/* The monitor shell around the read-only explorer. Decorative bezel/bar
 * chrome is aria-hidden; the functional page starts inside .screen-content. */

import type { ReactNode } from "react";

export function Chassis({ children }: { children: ReactNode }) {
  return (
    <div className="monitor">
      <div className="bezel">
        <div className="bezel-bar bezel-bar--top" aria-hidden="true">
          <span className="chip">CGM-7</span>
          <span className="bar-label">Causal desk</span>
          <span className="bar-rec">
            <i />
            Read-only
          </span>
        </div>

        <div className="screen">
          <div className="screen-scroll">{children}</div>
          <div className="screen-vignette" aria-hidden="true" />
          <div className="screen-glare" aria-hidden="true" />
        </div>

        <div className="bezel-foot" aria-hidden="true">
          <span className="chip chip--small">CGM</span>
          <span className="bezel-plate">File Edit View Mode Help</span>
          <span className="bezel-vents" />
          <span className="bezel-led">
            <i />
            Online
          </span>
        </div>
      </div>
    </div>
  );
}
