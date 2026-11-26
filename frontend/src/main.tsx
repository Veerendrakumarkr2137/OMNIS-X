import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Routes,
  Route,
  NavLink,
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Toaster, toast } from "sonner";
import {
  Activity,
  Bell,
  Boxes,
  Building2,
  CalendarDays,
  ChartNoAxesCombined,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  FlaskConical,
  GitPullRequest,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Network,
  PanelLeftClose,
  Plus,
  Radio,
  Search,
  Settings2,
  Sun,
  X,
} from "lucide-react";
import { api, errorText, get, isTransientConnectionError, isDemoWorkspace } from "./api";
import { Brand, Modal } from "./ui";
import { Login } from "./Login";
const DashboardPage = React.lazy(() =>
  import("./Dashboard").then((m) => ({ default: m.DashboardPage })),
);
const Recovery = React.lazy(() =>
  import("./Recovery").then((m) => ({ default: m.Recovery })),
);
const Twin = React.lazy(() =>
  import("./Twin").then((m) => ({ default: m.Twin })),
);
function page(
  name:
    | "Analytics"
    | "AuditPage"
    | "Incidents"
    | "Notices"
    | "Resources"
    | "Scenarios"
    | "Settings"
    | "Timetable",
) {
  return React.lazy(() =>
    import("./Pages").then((m) => ({
      default: m[name] as React.ComponentType<{
        c: Campus;
        report?: () => void;
      }>,
    })),
  );
}
const Analytics = page("Analytics"),
  AuditPage = page("AuditPage"),
  Incidents = page("Incidents"),
  Notices = page("Notices"),
  Resources = page("Resources"),
  Scenarios = page("Scenarios"),
  Settings = page("Settings"),
  Timetable = page("Timetable");
import { Substitutions } from "./Substitutions";
import { FailureForm } from "./FailureForm";
import {
  privileged,
  type Campus,
  type Dashboard,
  type Incident,
  type Lesson,
  type Notice,
  type Plan,
  type Resource,
  type User,
} from "./types";
import "./styles.css";
import { Events } from "./Events";

const client = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: true } },
});

window.addEventListener("vite:preloadError", (event) => {
  if (!navigator.onLine) return;
  const key = "omnis-workspace-reload";
  try {
    // Reload once per build so an unavailable asset doesn't cause a loop.
    if (sessionStorage.getItem(key) === import.meta.url) return;
    sessionStorage.setItem(key, import.meta.url);
  } catch {
    return;
  }
  event.preventDefault();
  window.location.reload();
});

class WorkspaceViewBoundary extends React.Component<
  React.PropsWithChildren,
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <section className="panel" role="alert">
        <p>This workspace page couldn’t load.</p>
        <button className="secondary" onClick={() => window.location.reload()}>
          Reload page
        </button>
      </section>
    );
  }
}

const links = [
  {
    name: "Overview",
    url: "/",
    icon: LayoutDashboard,
    group: "Workspace",
    access: "all",
  },
  {
    name: "Digital twin",
    url: "/twin",
    icon: Network,
    group: "Workspace",
    access: "staff",
  },
  {
    name: "Scenario lab",
    url: "/scenarios",
    icon: FlaskConical,
    group: "Workspace",
    access: "staff",
  },
  {
    name: "Recovery studio",
    url: "/recovery",
    icon: GitPullRequest,
    group: "Workspace",
    access: "staff",
  },
  {
    name: "Timetable",
    url: "/timetable",
    icon: CalendarDays,
    group: "Operations",
    access: "all",
  },
  {
    name: "Incident center",
    url: "/incidents",
    icon: CircleAlert,
    group: "Operations",
    access: "incident",
  },
  {
    name: "Substitute requests",
    url: "/substitutions",
    icon: GitPullRequest,
    group: "Operations",
    access: "faculty",
  },
  {
    name: "Resources",
    url: "/resources",
    icon: Boxes,
    group: "Operations",
    access: "staff",
  },
  {
    name: "Analytics",
    url: "/analytics",
    icon: ChartNoAxesCombined,
    group: "Operations",
    access: "staff",
  },
  {
    name: "Notifications",
    url: "/notifications",
    icon: Bell,
    group: "System",
    access: "all",
  },
  {
    name: "College events",
    url: "/events",
    icon: CalendarDays,
    group: "Operations",
    access: "all",
  },
  {
    name: "Audit history",
    url: "/audit",
    icon: History,
    group: "System",
    access: "admin",
  },
  {
    name: "Settings",
    url: "/settings",
    icon: Settings2,
    group: "System",
    access: "admin",
  },
];
function Root() {
  const cache = useQueryClient(),
    nav = useNavigate();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await get<User>("/auth/me");
      } catch (e) {
        if ((e as { response?: { status: number } }).response?.status === 401)
          return null;
        throw e;
      }
    },
    staleTime: Infinity,
    retry: (failureCount, error) =>
      failureCount < 2 && isTransientConnectionError(error),
    retryDelay: (attempt) => Math.min(2000 * 2 ** attempt, 8000),
  });
  useEffect(() => {
    const id = api.interceptors.response.use(
      (r) => r,
      (e) => {
        if (
          e.response?.status === 401 &&
          !["/auth/me", "/auth/login"].includes(e.config?.url)
        ) {
          cache.clear();
          cache.setQueryData(["me"], null);
          nav("/");
        }
        return Promise.reject(e);
      },
    );
    return () => api.interceptors.response.eject(id);
  }, [cache, nav]);
  if (me.isPending || (me.isError && me.isFetching))
    return (
      <div className="loading" role="status" aria-live="polite">
        <Brand />
        <p>Connecting to campus…</p>
        <p>The campus server may be waking up. This can take a minute or more.</p>
      </div>
    );
  if (me.isError)
    return (
      <div className="loading">
        <Brand />
        <p>{errorText(me.error)}</p>
        <button className="secondary" onClick={() => me.refetch()}>
          Retry connection
        </button>
      </div>
    );
  const login = (u: User) => {
    toast.dismiss();
    cache.setQueryData(["me"], u);
    nav("/");
  };
  const clearSession = () => {
    cache.clear();
    cache.setQueryData(["me"], null);
    nav("/");
  };
  return me.data ? (
    <Workspace
      user={me.data}
      passwordChanged={clearSession}
      logout={async () => {
        try {
          await api.post("/auth/logout");
          cache.clear();
          cache.setQueryData(["me"], null);
          nav("/");
        } catch (e) {
          toast.error(errorText(e));
        }
      }}
    />
  ) : (
    <Login onLogin={login} />
  );
}
function Workspace({
  user,
  logout,
  passwordChanged,
}: {
  user: User;
  logout: () => void;
  passwordChanged: () => void;
}) {
  const cache = useQueryClient(),
    nav = useNavigate(),
    loc = useLocation(),
    staff = privileged(user);
  const [drawer, showDrawer] = useState(false),
    [collapse, setCollapse] = useState(false),
    [form, setForm] = useState(false),
    [pop, setPop] = useState(""),
    [q, setQ] = useState(""),
    [reported, setReported] = useState<Incident | null>(null);
  const [dark, setDark] = useState(
    localStorage.getItem("omnis-theme") === "dark",
  );
  const [passwordError, setPasswordError] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("omnis-theme", dark ? "dark" : "light");
    return () => {
      delete document.documentElement.dataset.theme;
    };
  }, [dark]);
  useEffect(() => {
    showDrawer(false);
    setPop("");
  }, [loc.pathname]);
  const data = useQuery({
    queryKey: ["campus", user.id],
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
    queryFn: async () => {
      const [dash, resources, lessons, cases, plans, notices] =
        await Promise.all([
          get<Dashboard>("/dashboard"),
          get<Resource[]>("/resources"),
          get<Lesson[]>("/timetable"),
          user.role !== "Student" ? get<Incident[]>("/incidents") : [],
          staff ? get<Plan[]>("/recovery/plans") : [],
          get<Notice[]>("/notifications"),
        ]);
      return { dash, resources, lessons, cases, plans, notices };
    },
  });
  if (!data.data)
    return (
      <div className="loading">
        <Brand />
        <p>
          {data.isError ? errorText(data.error) : "Loading your workspace…"}
        </p>
        {data.isError && <button onClick={() => data.refetch()}>Retry</button>}
      </div>
    );
  const c: Campus = {
    ...data.data,
    user,
    refresh: async () => {
      await cache.invalidateQueries();
    },
    name: (id) =>
      data.data.resources.find((r) => r.id === id)?.name ||
      data.data.dash.assignment_names[id] ||
      id,
  };
  const allowed = links.filter(
    (l) =>
      l.access === "all" ||
      (l.access === "faculty" && user.role === "Faculty") ||
      (l.access === "admin" && user.role === "Admin") ||
      (l.access === "staff" && staff) ||
      (l.access === "incident" && user.role !== "Student"),
  );
  const current =
      allowed.find((l) => l.url === loc.pathname)?.name || "Overview",
    unread = c.notices.filter((n) => !n.seen).length;
  const go = (s: string) => {
    setPop("");
    nav(s);
  };
  const pages: Record<string, React.ReactNode> = {
    "/": (
      <DashboardPage
        c={c}
        report={() => setForm(true)}
        refreshedAt={data.dataUpdatedAt}
        refreshing={data.isFetching}
        stale={data.isError}
      />
    ),
    "/twin": <Twin c={c} />,
    "/scenarios": <Scenarios c={c} />,
    "/recovery": <Recovery c={c} />,
    "/timetable": <Timetable key={loc.search} c={c} />,
    "/incidents": <Incidents c={c} report={() => setForm(true)} />,
    "/resources": <Resources key={loc.search} c={c} />,
    "/analytics": <Analytics c={c} />,
    "/notifications": <Notices c={c} />,
    "/events": <Events c={c} />,
    "/substitutions": <Substitutions c={c} />,
    "/audit": <AuditPage c={c} />,
    "/settings": <Settings c={c} />,
  };
  return (
    <div className={"shell " + (collapse ? "collapsed" : "")}>
      {drawer && (
        <button
          className="scrim"
          aria-label="Close navigation"
          onClick={() => showDrawer(false)}
        />
      )}
      <aside className={drawer ? "sidebar opened" : "sidebar"}>
        <Brand />
        <div className="campus-label">
          <div className="campus-icon">
            <Building2 size={18} />
          </div>
          <div>
            <b>
              {c.dash.campus_name ??
                (c.dash.demo ? "Meridian Institute" : "Campus workspace")}
            </b>
            <small>
              {user.dept
                ? [
                    user.dept,
                    user.profile?.semester &&
                      "Semester " + user.profile.semester,
                    user.profile?.section && "Section " + user.profile.section,
                    user.profile?.batch,
                  ]
                    .filter(Boolean)
                    .join(" · ")
                : c.dash.demo
                  ? "Demo campus"
                  : ""}
            </small>
          </div>
        </div>
        <nav>
          {["Workspace", "Operations", "System"].map((g) => (
            <div className="navgroup" key={g}>
              <label>{g}</label>
              {allowed
                .filter((l) => l.group === g)
                .map((l) => (
                  <NavLink end key={l.url} to={l.url} title={l.name}>
                    <l.icon size={17} />
                    <span>{l.name}</span>
                    {l.url === "/notifications" && unread > 0 && (
                      <small>{unread}</small>
                    )}
                  </NavLink>
                ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="online" />
          Campus online{" "}
          <button
            title="Collapse navigation"
            aria-label="Collapse navigation"
            onClick={() => setCollapse(!collapse)}
          >
            <PanelLeftClose size={16} />
          </button>
        </div>
      </aside>
      <main className="main">
        <header className="top">
          <button
            className="icon mobile-menu"
            aria-label="Open navigation"
            onClick={() => showDrawer(true)}
          >
            <Menu size={19} />
          </button>
          {collapse && (
            <button
              className="icon"
              aria-label="Expand navigation"
              onClick={() => setCollapse(false)}
            >
              <Menu size={17} />
            </button>
          )}
          <div className="crumb">
            Workspace <ChevronRight size={13} />
            <b>{current}</b>
          </div>
          <div className="top-actions">
            <button
              className="icon"
              aria-label="Search workspace"
              onClick={() => setPop("search")}
            >
              <Search size={17} />
            </button>
            <button
              className="icon"
              aria-label="Toggle theme"
              onClick={() => setDark(!dark)}
            >
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button
              aria-label="Open notifications"
              className="icon bell"
              onClick={() =>
                setPop(pop === "notifications" ? "" : "notifications")
              }
            >
              <Bell size={17} />
              {unread > 0 && <i />}
            </button>
            <span className="divider" />
            <button
              className="profile"
              aria-label="Account menu"
              onClick={() => setPop(pop === "account" ? "" : "account")}
            >
              <span className="avatar">
                {user.name
                  .split(" ")
                  .map((s) => s[0])
                  .slice(0, 2)
                  .join("")}
              </span>
              <div>
                <b>{user.name}</b>
                <small>
                  {[user.role, user.dept].filter(Boolean).join(" · ")}
                </small>
              </div>
              <ChevronDown size={13} />
            </button>
          </div>
          {pop === "account" && (
            <div className="popover">
              <b>{user.name}</b>
              <p>
                {user.role} · {user.dept || "Institute"}
              </p>
              <p>
                {user.profile?.designation || user.id}
                {user.email && " · " + user.email}
              </p>
              <button
                className="secondary"
                onClick={() => {
                  setPasswordError("");
                  setPop("password");
                }}
              >
                Change password
              </button>
              <button className="secondary" onClick={logout}>
                <LogOut size={15} />
                Sign out
              </button>
            </div>
          )}
          {pop === "notifications" && (
            <div className="popover">
              <h3>Notifications</h3>
              {c.notices.slice(0, 3).map((n) => (
                <div key={n.id} className="row">
                  <div>
                    <b>{n.title}</b>
                    <small>{n.message}</small>
                  </div>
                </div>
              ))}
              <button className="textbtn" onClick={() => go("/notifications")}>
                Open notification center
              </button>
            </div>
          )}
        </header>
        <div className="content">
          {data.isError && (
            <p className="error">
              Live refresh interrupted. Showing the last campus snapshot.
            </p>
          )}
          {staff && loc.pathname === "/" && (
            <div className="overview-top">
              <span>
                <i className={data.isError ? undefined : "online"} />{" "}
                {data.isError ? "Live refresh interrupted" : "Workspace online"}
              </span>
              <button className="textbtn" onClick={() => setForm(true)}>
                <Plus size={14} />
                Report incident
              </button>
            </div>
          )}
          <WorkspaceViewBoundary key={loc.pathname}>
            <React.Suspense fallback={<p>Loading workspace view…</p>}>
              <Routes>
                {allowed.map((l) => (
                  <Route key={l.url} path={l.url} element={pages[l.url]} />
                ))}
                <Route path="*" element={<Navigate replace to="/" />} />
              </Routes>
            </React.Suspense>
          </WorkspaceViewBoundary>
          <footer>
            OMNIS-X{" "}
            <span>
              {c.dash.demo_profile
                ? [
                    user.dept || c.dash.demo_profile.demo_label,
                    "Demonstration",
                  ].join(" · ")
                : c.dash.campus_name
                  ? c.dash.campus_name + " · Demonstration"
                  : c.dash.demo
                    ? "Meridian Institute · Fictional demonstration campus"
                    : "Campus workspace"}
            </span>
          </footer>
        </div>
      </main>
      {pop === "search" && (
        <Modal title="Search workspace" close={() => setPop("")}>
          <input
            autoFocus
            placeholder="Search pages or sessions"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {allowed
            .filter((l) => l.name.toLowerCase().includes(q.toLowerCase()))
            .map((l) => (
              <button
                className="row linkrow"
                key={l.url}
                onClick={() => go(l.url)}
              >
                <l.icon size={16} />
                {l.name}
              </button>
            ))}
          {q &&
            c.lessons
              .filter((s) => s.subject.toLowerCase().includes(q.toLowerCase()))
              .slice(0, 5)
              .map((s) => (
                <button
                  className="row linkrow"
                  key={s.id}
                  onClick={() =>
                    go("/timetable?day=" + s.day + "&session=" + s.id)
                  }
                >
                  <CalendarDays size={16} />
                  {s.subject} · {s.day}
                </button>
              ))}
        </Modal>
      )}
      {form && (
        <FailureForm
          c={c}
          kind={user.role === "Faculty" ? "absence" : "incident"}
          close={() => setForm(false)}
          done={(x) => {
            setForm(false);
            setReported(x);
          }}
        />
      )}
      {pop === "password" && (
        <Modal title="Change password" close={() => setPop("")}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              if (form.get("password") !== form.get("confirm")) {
                setPasswordError("The new passwords do not match.");
                return;
              }
              setChangingPassword(true);
              setPasswordError("");
              try {
                await api.post("/auth/password", {
                  current_password: form.get("current"),
                  password: form.get("password"),
                });
                passwordChanged();
                toast.success(
                  "Password changed. Sign in with your new password.",
                );
              } catch (problem) {
                setPasswordError(errorText(problem));
              } finally {
                setChangingPassword(false);
              }
            }}
          >
            <label>
              Current password
              <input
                name="current"
                type="password"
                required
                autoComplete="current-password"
              />
            </label>
            <label>
              New password
              <input
                name="password"
                type="password"
                minLength={12}
                required
                autoComplete="new-password"
              />
            </label>
            <label>
              Confirm new password
              <input
                name="confirm"
                type="password"
                minLength={12}
                required
                autoComplete="new-password"
              />
            </label>
            {passwordError && <p role="alert">{passwordError}</p>}
            <button className="primary" disabled={changingPassword}>
              Save password
            </button>
          </form>
        </Modal>
      )}
      {reported && (
        <Modal
          title="Report recorded"
          description={reported.title + " · " + reported.day}
          close={() => setReported(null)}
        >
          <p>
            {reported.impact.sessions.length} affected sessions ·{" "}
            {reported.impact.students} affected students.
          </p>
          <p>
            Recovery status · <b>{reported.status}</b>
          </p>
          <button
            className="primary"
            onClick={() => {
              setReported(null);
              nav(staff ? "/recovery?case=" + reported.id : "/incidents");
            }}
          >
            {staff ? "View recovery plans" : "View my reports"}
          </button>
        </Modal>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename={isDemoWorkspace ? "/demo" : "/"}>
      <QueryClientProvider client={client}>
        <Root />
        <Toaster position="bottom-right" richColors />
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
