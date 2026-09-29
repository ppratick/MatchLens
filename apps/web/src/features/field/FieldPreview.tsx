import { ArrowRight, Map } from "lucide-react";
import { Pitch } from "../../features/field/Pitch";
import type { Workspace } from "../../hooks/useWorkspace";
export function FieldPreview(
  workspace: Pick<Workspace, "setTab" | "currentFrame" | "calibrate">,
) {
  const { setTab, currentFrame, calibrate } = workspace;

  return (
    <>
      <div className="panel field-preview">
        <div className="panel-header">
          <h3>
            <Map size={16} />
            The field, from above
          </h3>
          <button className="text-button" onClick={() => setTab("field")}>
            Explore field <ArrowRight size={14} />
          </button>
        </div>
        <div className="field-preview-body">
          <div>
            <Pitch
              points={(currentFrame?.tracks || [])
                .filter((t) => t.field)
                .map((t) => ({
                  id: t.id,
                  x: t.field![0],
                  y: t.field![1],
                  team: t.team,
                }))}
            />
          </div>
          <div>
            <span className="eyebrow">SPATIAL CONTEXT</span>
            <h3>
              {currentFrame?.calibrated
                ? "A new perspective."
                : "Give your video a field."}
            </h3>
            <p>
              {currentFrame?.calibrated
                ? "Positions match the analyzed video timestamp. Unseen areas remain unknown."
                : "Identify pitch landmarks to map observed player positions onto a top-down field."}
            </p>
            <button className="button small" onClick={calibrate}>
              {currentFrame?.calibrated
                ? "Update calibration"
                : "Calibrate field"}
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
