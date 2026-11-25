import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, errorText, get } from "./api";
import { Empty, Modal, Pill } from "./ui";
import type { Campus, User } from "./types";

const roles = ["Student", "Faculty", "HOD", "Operator", "Admin"];
const staffRoles = ["HOD", "Operator", "Admin"];
const profileFields = ["designation", "semester", "section", "batch"] as const;
type AccountTab = "All" | "Student" | "Faculty" | "Staff";

export function Accounts({ c }: { c: Campus }) {
  const [editor, setEditor] = useState<User | { newRole?: string } | null>(
    null,
  );
  const [password, setPassword] = useState<User | null>(null);
  const [tab, setTab] = useState<AccountTab>("All");
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [department, setDepartment] = useState("");
  const [page, setPage] = useState(0);
  const [importing, setImporting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => get<User[]>("/users"),
  });
  const allUsers = users.data || [];
  const studentCount = allUsers.filter((u) => u.role === "Student").length;
  const facultyCount = allUsers.filter((u) => u.role === "Faculty").length;
  const staffCount = allUsers.filter((u) => staffRoles.includes(u.role)).length;
  const departments = c.resources.filter((r) => r.kind === "Department");
  const filtered = allUsers.filter(
    (u) =>
      (tab === "All" ||
        (tab === "Staff" ? staffRoles.includes(u.role) : u.role === tab)) &&
      (!role || u.role === role) &&
      (!department || u.dept === department) &&
      [u.name, u.id, u.email].some((value) =>
        value?.toLowerCase().includes(search.toLowerCase()),
      ),
  );

  async function mutate(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    try {
      await action();
      await c.refresh();
      setEditor(null);
      setPassword(null);
      setImporting(false);
      toast.success(message);
    } catch (problem) {
      setError(errorText(problem));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel directory">
      <div className="panel-head">
        <h2>Campus accounts</h2>
        <div className="actions">
          <button
            className="secondary"
            onClick={() => {
              setError("");
              setImporting(true);
            }}
          >
            Import CSV or Excel
          </button>
          <button
            className="secondary"
            onClick={() => {
              setError("");
              setEditor({ newRole: "Student" });
            }}
          >
            Add student
          </button>
          <button
            className="secondary"
            onClick={() => {
              setError("");
              setEditor({ newRole: "Faculty" });
            }}
          >
            Add faculty
          </button>
          <button
            className="primary"
            onClick={() => {
              setError("");
              setEditor({
                newRole:
                  tab === "Student" || tab === "Faculty" ? tab : undefined,
              });
            }}
          >
            Add account
          </button>
        </div>
      </div>
      <div className="segmented" role="tablist" aria-label="Account category">
        {(
          [
            ["All", `All (${allUsers.length})`],
            ["Student", `Students (${studentCount})`],
            ["Faculty", `Faculty (${facultyCount})`],
            ["Staff", `Staff & Admin (${staffCount})`],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? "active" : ""}
            onClick={() => {
              setTab(key);
              setRole("");
              setPage(0);
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="filters">
        <input
          aria-label="Find account"
          placeholder="Search name, ID or email"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
        />
        {(tab === "All" || tab === "Staff") && (
          <select
            aria-label="Account role"
            value={role}
            onChange={(e) => {
              setRole(e.target.value);
              setPage(0);
            }}
          >
            <option value="">All roles</option>
            {(tab === "Staff" ? staffRoles : roles).map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        )}
        <select
          aria-label="Account department"
          value={department}
          onChange={(e) => {
            setDepartment(e.target.value);
            setPage(0);
          }}
        >
          <option value="">All departments</option>
          {departments.map((d) => (
            <option key={d.id}>{d.name}</option>
          ))}
        </select>
      </div>
      {users.isPending && <p>Loading accounts…</p>}
      {users.isError && <p role="alert">{errorText(users.error)}</p>}
      {users.data && !filtered.length && <Empty>No matching accounts.</Empty>}
      {filtered.slice(page * 10, page * 10 + 10).map((u) => (
        <div className="row" key={u.id}>
          <div className="grow">
            <b>{u.name}</b>
            <small>
              {u.id} · {u.role}
              {u.dept && " · " + u.dept}
            </small>
            {u.email && <small>{u.email}</small>}
          </div>
          <Pill tone={u.active === false ? "neutral" : "teal"}>
            {u.active === false ? "Inactive" : "Active"}
          </Pill>
          <div className="actions">
            <button
              className="secondary"
              onClick={() => {
                setError("");
                setEditor(u);
              }}
            >
              Edit
            </button>
            <button
              className="secondary"
              onClick={() => {
                setError("");
                setPassword(u);
              }}
            >
              Reset password
            </button>
          </div>
        </div>
      ))}
      {filtered.length > 10 && (
        <div className="datebar">
          <button
            className="secondary"
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </button>
          <small>
            Page {page + 1} of {Math.ceil(filtered.length / 10)}
          </small>
          <button
            className="secondary"
            disabled={(page + 1) * 10 >= filtered.length}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      )}
      {editor && (
        <AccountForm
          c={c}
          target={"id" in editor ? editor : undefined}
          defaultRole={"newRole" in editor ? editor.newRole : undefined}
          busy={busy}
          error={error}
          close={() => setEditor(null)}
          save={(data, id) =>
            void mutate(
              () =>
                id
                  ? api.patch("/users/" + encodeURIComponent(id), data)
                  : api.post("/users", data),
              id ? "Account updated" : "Account created",
            )
          }
        />
      )}
      {password && (
        <Modal
          title={"Reset password for " + password.name}
          close={() => setPassword(null)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              void mutate(
                () =>
                  api.post(
                    "/users/" + encodeURIComponent(password.id) + "/password",
                    { password: form.get("password") },
                  ),
                "Password reset. Existing sessions revoked.",
              );
            }}
          >
            <label>
              New password
              <input
                name="password"
                type="password"
                autoComplete="new-password"
                minLength={12}
                required
              />
            </label>
            {error && <p role="alert">{error}</p>}
            <button className="primary" disabled={busy}>
              Reset password
            </button>
          </form>
        </Modal>
      )}
      {importing && (
        <Modal
          title="Import institutional records"
          close={() => setImporting(false)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const file = new FormData(e.currentTarget).get("file");
              if (!(file instanceof File) || file.size > 1_000_000) {
                setError("Choose a file under 1 MB.");
                return;
              }
              void mutate(async () => {
                const bytes = new Uint8Array(await file.arrayBuffer());
                let raw = "";
                for (const byte of bytes) raw += String.fromCharCode(byte);
                return api.post("/users/import", {
                  filename: file.name,
                  content: btoa(raw),
                });
              }, "Records imported");
            }}
          >
            <p>
              Use columns username, name, role, dept, resource, email and
              password. Faculty rows may include subjects separated by |.
              Student rows may include enrollments such as
              Networks:PCC|German:Elective.
            </p>
            <label>
              Institutional records
              <input type="file" name="file" accept=".csv,.xlsx" required />
            </label>
            {error && <p role="alert">{error}</p>}
            <button className="primary" disabled={busy}>
              Import records
            </button>
          </form>
        </Modal>
      )}
    </section>
  );
}

function AccountForm({
  c,
  target,
  defaultRole,
  busy,
  error,
  close,
  save,
}: {
  c: Campus;
  target?: User;
  defaultRole?: string;
  busy: boolean;
  error: string;
  close: () => void;
  save: (data: Record<string, unknown>, id?: string) => void;
}) {
  const departments = c.resources.filter((r) => r.kind === "Department");
  const [role, setRole] = useState(target?.role || defaultRole || "Student");
  const [dept, setDept] = useState(target?.dept || departments[0]?.name || "");
  const [resource, setResource] = useState(target?.resource || "");
  const scoped = ["Student", "Faculty", "HOD"].includes(role);
  const isStudent = role === "Student";
  const isFaculty = role === "Faculty";

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const payload: Record<string, unknown> = {
      dept: scoped ? dept : null,
      resource: resource || null,
      email: form.get("email") || null,
      ...Object.fromEntries(
        profileFields
          .filter((key) => form.has(key))
          .map((key) => [key, form.get(key)]),
      ),
    };
    if (!target)
      Object.assign(payload, {
        username: form.get("username"),
        name: form.get("name"),
        role,
        password: form.get("password"),
      });
    if (target) payload.active = form.get("active") === "on";
    if (isFaculty && !target && !resource)
      payload.subjects = String(form.get("subjects") || "")
        .split("|")
        .map((s) => s.trim())
        .filter(Boolean);
    if (isStudent && form.get("individual") === "on") {
      payload.enrollments = Object.fromEntries(
        String(form.get("enrollments") || "")
          .split("\n")
          .filter(Boolean)
          .map((line) => {
            const split = line.lastIndexOf(":");
            return split === -1
              ? [line.trim(), "Core"]
              : [line.slice(0, split).trim(), line.slice(split + 1).trim()];
          }),
      );
    } else if (isStudent && target) {
      payload.inherit_cohort_courses = true;
    }
    save(payload, target?.id);
  }
  return (
    <Modal
      title={
        target
          ? "Edit " + target.name
          : defaultRole === "Student"
            ? "Add student"
            : defaultRole === "Faculty"
              ? "Add faculty"
              : "Add campus account"
      }
      close={close}
    >
      <form onSubmit={submit}>
        {!target && (
          <>
            <label>
              Full name
              <input name="name" required />
            </label>
            <label>
              Faculty ID, registration ID or username
              <input name="username" required autoComplete="off" />
            </label>
            <label>
              Initial password
              <input
                name="password"
                type="password"
                minLength={12}
                autoComplete="new-password"
                required
              />
            </label>
            <label>
              Role
              <select
                value={role}
                onChange={(e) => {
                  setRole(e.target.value as User["role"]);
                  setResource("");
                }}
              >
                {roles.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </label>
          </>
        )}
        <label>
          Institutional email
          <input name="email" type="email" defaultValue={target?.email || ""} />
        </label>
        {scoped && (
          <label>
            Department
            <select
              value={dept}
              onChange={(e) => {
                setDept(e.target.value);
                if (!isFaculty || !target) setResource("");
              }}
            >
              {departments.map((r) => (
                <option key={r.id}>{r.name}</option>
              ))}
            </select>
          </label>
        )}
        {(isStudent || (isFaculty && !target)) && (
          <label>
            {isFaculty ? "Teaching profile" : "Section or laboratory batch"}
            <select
              required={isStudent}
              value={resource}
              onChange={(e) => setResource(e.target.value)}
            >
              <option value="">
                {isFaculty
                  ? "Create teaching profile"
                  : "Select section or batch"}
              </option>
              {c.resources
                .filter(
                  (r) =>
                    r.dept === dept &&
                    r.kind === (isFaculty ? "Faculty" : "Cohort"),
                )
                .map((r) => (
                  <option value={r.id} key={r.id}>
                    {r.name}
                  </option>
                ))}
            </select>
          </label>
        )}
        {isFaculty && !target && !resource && (
          <label>
            Qualified subjects separated by |<input name="subjects" required />
          </label>
        )}
        {isFaculty && (
          <label>
            Designation
            <input
              name="designation"
              defaultValue={target?.profile?.designation}
            />
          </label>
        )}
        {isStudent && (
          <>
            <div className="form-grid">
              {(["semester", "section", "batch"] as const).map((key) => (
                <label key={key}>
                  {key[0].toUpperCase() + key.slice(1)}
                  <input name={key} defaultValue={target?.profile?.[key]} />
                </label>
              ))}
            </div>
            <label className="check">
              <input
                name="individual"
                type="checkbox"
                defaultChecked={target?.profile?.has_registrations || !target}
              />{" "}
              Use individual course registration
            </label>
            <label>
              Registered subjects, one per line with optional category
              <textarea
                name="enrollments"
                rows={4}
                placeholder="Digital Signal Processing:PCC"
                defaultValue={Object.entries(target?.enrollments || {})
                  .map(([subject, category]) => subject + ":" + category)
                  .join("\n")}
              />
            </label>
          </>
        )}
        {target && (
          <label className="check">
            <input
              name="active"
              type="checkbox"
              defaultChecked={target.active !== false}
            />{" "}
            Account active
          </label>
        )}
        {error && <p role="alert">{error}</p>}
        <button className="primary" disabled={busy}>
          Save account
        </button>
      </form>
    </Modal>
  );
}
