import { ArrowRight, ShieldCheck } from "lucide-react";
import { bytes } from "../../api";
import type { Workspace } from "../../hooks/useWorkspace";
export function Setup(
  workspace: Pick<Workspace, "section" | "system" | "setSection">,
) {
  const { section, system, setSection } = workspace;

  return (
    <>
      {section === "settings" && (
        <div className="page">
          <div className="page-heading">
            <div>
              <div className="eyebrow">BUILT AROUND YOUR MACHINE</div>
              <h1>
                Local, by design<span>.</span>
              </h1>
              <p>Your setup, privacy, and analysis capabilities.</p>
            </div>
            <ShieldCheck size={38} />
          </div>
          {system && (
            <div className="settings-grid">
              <div className="panel settings-panel">
                <h3>Storage & privacy</h3>
                <dl>
                  <dt>Match data</dt>
                  <dd className="path">{system.data_dir}</dd>
                  <dt>Available storage</dt>
                  <dd>{bytes(system.disk_free)}</dd>
                  <dt>Account</dt>
                  <dd>Not required</dd>
                  <dt>External services</dt>
                  <dd>No required cloud services or paid APIs</dd>
                </dl>
                <p>
                  Match data defaults outside iCloud Drive. Exported copies and
                  operating-system backups are managed separately.
                </p>
              </div>
              <div className="panel settings-panel">
                <h3>Analysis engine</h3>
                <dl>
                  <dt>Player detector</dt>
                  <dd>
                    <span
                      className={
                        "status-pill " + (system.model_ready ? "ready" : "")
                      }
                    >
                      {system.model_ready
                        ? "YOLOX installed locally"
                        : "Model not installed"}
                    </span>
                  </dd>
                  <dt>Runtime providers</dt>
                  <dd>{system.providers.join(", ")}</dd>
                  <dt>Install / validate model</dt>
                  <dd>
                    <code>.venv/bin/python run.py model install</code>
                  </dd>
                </dl>
                <p>
                  No downloads happen during ordinary analysis. Offline model
                  import is also supported.
                </p>
              </div>
              <div className="panel settings-panel">
                <h3>Capability boundaries</h3>
                {Object.entries(system.capabilities).map(([k, v]) => (
                  <div className="capability" key={k}>
                    <strong>{k.replaceAll("_", " ")}</strong>
                    <span>{v}</span>
                  </div>
                ))}
              </div>
              <div className="panel settings-panel">
                <h3>Phone capture</h3>
                <p>
                  Pair from a match, then start the separate HTTPS receiver.
                  Your phone streams to this computer over the local network.
                </p>
                <code>
                  .venv/bin/python run.py receiver --cert cert.pem --key key.pem
                </code>
                <p>
                  The certificate must be trusted by your phone. Keep it awake
                  and connected to power; background capture is not guaranteed.
                </p>
                <button
                  className="text-button"
                  onClick={() => setSection("library")}
                >
                  Choose a match <ArrowRight size={15} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
