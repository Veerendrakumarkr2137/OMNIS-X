import { useState } from "react";
import { toast } from "sonner";
import { api, errorText } from "./api";
import { Modal } from "./ui";
import type { Campus, Resource } from "./types";
const types = [
  "Classroom",
  "Laboratory",
  "Faculty",
  "Cohort",
  "Building",
  "Department",
];
export function ResourceEditor({
  c,
  resource,
  close,
}: {
  c: Campus;
  resource?: Resource;
  close: () => void;
}) {
  const ds = c.resources.filter((x) => x.kind === "Department"),
    buildings = c.resources.filter((x) => x.kind === "Building");
  const [kind, setKind] = useState(resource?.kind || "Classroom"),
    [department, setDepartment] = useState(resource?.dept || ds[0]?.name || ""),
    [busy, setBusy] = useState(false),
    [msg, setMsg] = useState("");
  const r = resource?.details;
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    const f = new FormData(e.currentTarget);
    const list = (n: string) =>
      String(f.get(n) || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    const payload = {
      name: f.get("name"),
      kind,
      dept: ["Department", "Building"].includes(kind) ? null : f.get("dept"),
      building: f.get("building"),
      capacity: Number(f.get("capacity") || 40),
      equipment: list("equipment"),
      subjects: list("subjects"),
      limit: Number(f.get("limit") || 360),
      consecutive: Number(f.get("consecutive") || 180),
      available: [
        Number(f.get("availableStart") || 480),
        Number(f.get("availableEnd") || 1080),
      ],
      ...(kind === "Cohort"
        ? {
            members: f.getAll("members"),
            semester: f.get("semester"),
            section: f.get("section"),
            batch: f.get("batch"),
          }
        : {}),
    };
    try {
      if (resource) await api.put("/resources/" + resource.id, payload);
      else await api.post("/resources", payload);
      await c.refresh();
      toast.success("Directory updated");
      close();
    } catch (e) {
      setMsg(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={resource ? "Edit " + resource.name : "Add campus resource"}
      close={close}
    >
      <form onSubmit={save}>
        <label>
          Resource type
          <select
            value={kind}
            disabled={!!resource}
            onChange={(e) => setKind(e.target.value)}
          >
            {types.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label>
          Name
          <input
            name="name"
            defaultValue={resource?.name}
            required
            maxLength={100}
          />
        </label>
        {!["Building", "Department"].includes(kind) && (
          <label>
            Department
            <select
              name="dept"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
            >
              {ds.map((d) => (
                <option key={d.id}>{d.name}</option>
              ))}
            </select>
          </label>
        )}
        {["Classroom", "Laboratory"].includes(kind) && (
          <>
            <label>
              Building
              <select
                name="building"
                defaultValue={r?.building || buildings[0]?.id}
              >
                {buildings.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Equipment (comma-separated)
              <input name="equipment" defaultValue={r?.equipment?.join(", ")} />
            </label>
          </>
        )}
        {["Classroom", "Laboratory", "Cohort"].includes(kind) && (
          <label>
            {kind === "Cohort" ? "Cohort size" : "Seat capacity"}
            <input
              name="capacity"
              type="number"
              min="1"
              max="2000"
              required
              defaultValue={r?.size || r?.capacity || 40}
            />
          </label>
        )}
        {kind === "Faculty" && (
          <>
            <label>
              Qualified subjects (comma-separated)
              <input
                name="subjects"
                required
                defaultValue={r?.subjects?.join(", ")}
              />
            </label>
            <div className="form-grid">
              {[
                ["limit", "Maximum daily minutes", r?.limit || 360],
                [
                  "consecutive",
                  "Maximum consecutive minutes",
                  r?.consecutive || 180,
                ],
                [
                  "availableStart",
                  "Availability start (minute of day)",
                  r?.available?.[0] ?? 480,
                ],
                [
                  "availableEnd",
                  "Availability end (minute of day)",
                  r?.available?.[1] ?? 1080,
                ],
              ].map(([k, label, v]) => (
                <label key={k}>
                  {label}
                  <input
                    name={String(k)}
                    type="number"
                    required
                    defaultValue={v}
                  />
                </label>
              ))}
            </div>
          </>
        )}
        {kind === "Cohort" && (
          <>
            <div className="form-grid">
              <label>
                Semester
                <input name="semester" defaultValue={r?.semester} />
              </label>
              <label>
                Section
                <input name="section" defaultValue={r?.section} />
              </label>
              <label>
                Batch
                <input name="batch" defaultValue={r?.batch} />
              </label>
            </div>
            <label>
              Batches included in this section
              <select
                name="members"
                multiple
                key={department}
                defaultValue={r?.members}
              >
                {c.resources
                  .filter(
                    (item) =>
                      item.kind === "Cohort" &&
                      item.id !== resource?.id &&
                      item.dept === department &&
                      !item.details.members?.length,
                  )
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
              </select>
            </label>
          </>
        )}
        {msg && (
          <p className="error" role="alert">
            {msg}
          </p>
        )}
        <button className="primary" disabled={busy}>
          Save resource
        </button>
      </form>
    </Modal>
  );
}
