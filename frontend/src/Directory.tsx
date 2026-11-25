import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, errorText, get } from "./api";
import { Modal } from "./ui";
import type { Campus, Resource, User } from "./types";
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
            <select name="dept" defaultValue={resource?.dept || ds[0]?.name}>
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
export function Accounts({ c }: { c: Campus }) {
  const [open, setOpen] = useState(false),
    [role, setRole] = useState("Student"),
    [dept, setDept] = useState(
      c.resources.find((r) => r.kind === "Department")?.name || "",
    ),
    [busy, setBusy] = useState(false),
    [msg, setMsg] = useState("");
  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => get<User[]>("/users"),
  });
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setMsg("");
    try {
      await api.post("/users", {
        username: f.get("username"),
        password: f.get("password"),
        name: f.get("name"),
        role,
        dept: ["Admin", "Operator"].includes(role) ? null : dept,
        resource: f.get("resource"),
      });
      await c.refresh();
      setOpen(false);
      toast.success("Account created");
    } catch (e) {
      setMsg(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel policy directory">
      <div className="panel-head">
        <h3>Campus accounts</h3>
        <button className="secondary" onClick={() => setOpen(true)}>
          Add account
        </button>
      </div>
      <details>
        <summary>View directory ({users.data?.length ?? 0})</summary>
        {users.data?.map((u) => (
          <div className="row" key={u.id}>
            <div className="grow">
              <b>{u.name}</b>
              <small>{u.id}</small>
            </div>
            <span>
              {u.role} · {u.dept || "Campus"}
            </span>
          </div>
        ))}
      </details>
      {open && (
        <Modal title="Add campus account" close={() => setOpen(false)}>
          <form onSubmit={save}>
            <label>
              Display name
              <input name="name" required />
            </label>
            <label>
              Username
              <input name="username" required autoComplete="off" />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                minLength={12}
                required
                autoComplete="new-password"
              />
            </label>
            <label>
              Role
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                {["Student", "Faculty", "HOD", "Operator", "Admin"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
            {!["Admin", "Operator"].includes(role) && (
              <label>
                Department
                <select value={dept} onChange={(e) => setDept(e.target.value)}>
                  {c.resources
                    .filter((r) => r.kind === "Department")
                    .map((r) => (
                      <option key={r.id}>{r.name}</option>
                    ))}
                </select>
              </label>
            )}
            {["Student", "Faculty"].includes(role) && (
              <label>
                Identity
                <select name="resource" required>
                  {c.resources
                    .filter(
                      (r) =>
                        r.dept === dept &&
                        r.kind === (role === "Faculty" ? "Faculty" : "Cohort"),
                    )
                    .map((r) => (
                      <option value={r.id} key={r.id}>
                        {r.name}
                      </option>
                    ))}
                </select>
              </label>
            )}
            {msg && <p className="error">{msg}</p>}
            <button className="primary" disabled={busy}>
              Create account
            </button>
          </form>
        </Modal>
      )}
    </section>
  );
}
