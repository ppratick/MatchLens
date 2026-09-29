import { ModalShell } from "../../shared/ModalShell";
import type { Workspace } from "../../hooks/useWorkspace";
export function PairDialog(
  workspace: Pick<Workspace, "modal" | "pairing" | "close">,
) {
  const { modal, pairing, close } = workspace;

  return (
    <>
      {modal === "pair" && pairing && (
        <ModalShell
          title="Connect your phone."
          subtitle="Use the same local network. The receiver needs HTTPS trusted by your phone."
          onClose={close}
        >
          <p className="muted">Start the phone receiver on this computer:</p>
          <code className="code-block">
            .venv/bin/python run.py receiver --cert cert.pem --key key.pem
          </code>
          <label>
            Pairing URL
            <span className="muted">
              Replace COMPUTER-IP with this computer's LAN address.
            </span>
            <textarea
              readOnly
              rows={4}
              value={`https://COMPUTER-IP:8766/${pairing.fragment}`}
            />
          </label>
          <p>
            Open that address on your phone, grant camera access, and keep the
            page open. Pairing expires in four hours. The main application stays
            on localhost.
          </p>
          <button className="button primary" onClick={close}>
            Done
          </button>
        </ModalShell>
      )}
    </>
  );
}
