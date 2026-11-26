import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  Eye,
  EyeOff,
  GraduationCap,
  ShieldCheck,
  Wrench,
  BookOpen,
  Layers3,
  RadioTower,
  LockKeyhole,
} from "lucide-react";
import { z } from "zod";
import { api, errorText, get, isDemoWorkspace } from "./api";
import { Brand, CampusArt } from "./ui";
import type { User } from "./types";
const demoRoles = [
  ["Admin", ShieldCheck],
  ["HOD", Layers3],
  ["Faculty", BookOpen],
  ["Student", GraduationCap],
  ["Operator", Wrench],
] as const;
const accessLabels: Record<User["role"], string> = {
  Admin: "Administrator",
  HOD: "Department head",
  Faculty: "Faculty",
  Student: "Student",
  Operator: "Operations",
};

export function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const reduced = useReducedMotion();
  const [params] = useSearchParams();
  const selectedPortal = demoRoles.find(
    ([role]) => role.toLowerCase() === params.get("access"),
  )?.[0];
  const [config, setConfig] = useState({ demo: false, batch_demo: false, quick_demo: false }),
    [shown, setShown] = useState(false),
    [loading, setLoading] = useState(""),
    [error, setError] = useState("");
  const { register, handleSubmit } = useForm<{
    username: string;
    password: string;
    remember: boolean;
  }>();
  useEffect(() => {
    get<typeof config>("/config")
      .then(setConfig)
      .catch((e) => setError(errorText(e)));
  }, []);
  async function enter(
    username: string,
    password: string,
    remember = false,
    portal = selectedPortal,
  ) {
    if (loading) return;
    const check = z
      .object({
        username: z.string().trim().min(1),
        password: z.string().min(1),
      })
      .safeParse({ username, password });
    if (!check.success) {
      setError("Enter your login ID or institutional email and password.");
      return;
    }
    setError("");
    setLoading(username);
    try {
      onLogin(
        (
          await api.post<User>("/auth/login", {
            username,
            password,
            remember,
            portal,
          })
        ).data,
      );
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading("");
    }
  }
  async function quickEnter(role: User["role"]) {
    if (loading || !config.quick_demo) return;
    setLoading(role);
    setError("");
    try {
      await api.post<User>("/auth/login", {
        username: role.toLowerCase(),
        password: role[0] + role.toLowerCase().slice(1) + "@123",
        remember: false,
        portal: role,
      }, { baseURL: "/demo/api" });
      window.location.assign("/demo/");
    } catch (e) {
      setError(errorText(e));
      setLoading("");
    }
  }
  return (
    <main className="login">
      <section className="login-cover">
        <Brand />
        <motion.div
          className="cover-body"
          initial={reduced ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
        >
          <div className="eyebrow mint">
            <span className="line" /> INSTITUTIONAL DIGITAL TWIN
          </div>
          <h1>
            Predict. Adapt.
            <br />
            <em>Recover.</em>
          </h1>
          <p>
            One connected view of your campus, from the first sign of disruption
            to a recovered timetable.
          </p>
          <CampusArt />
        </motion.div>
        <div className="cover-footer">
          <span>
            <RadioTower size={14} /> CAMPUS INTELLIGENCE
          </span>
          <span>OMNIS-X / 01</span>
        </div>
      </section>
      <section className="login-form">
        <div className="login-inner">
          <div className="login-symbol">
            <LockKeyhole size={23} />
          </div>
          <div className="eyebrow">OMNIS-X ACCESS</div>
          <h2>
            {selectedPortal
              ? accessLabels[selectedPortal] + " sign-in"
              : "Welcome back."}
          </h2>
          <p>Sign in with your institutional account.</p>
          <nav className="access-portals" aria-label="Access portals">
            {demoRoles.map(([role, Icon]) => (
              <Link
                key={role}
                to={"/?access=" + role.toLowerCase()}
                aria-current={selectedPortal === role ? "page" : undefined}
              >
                <Icon size={15} aria-hidden="true" />
                {accessLabels[role]}
              </Link>
            ))}
          </nav>
          <form
            onSubmit={handleSubmit((x) =>
              enter(x.username, x.password, x.remember),
            )}
          >
            <label>
              Login ID or institutional email
              <input
                autoComplete="username"
                placeholder="Faculty ID, USN, username or email"
                required
                {...register("username")}
              />
            </label>
            <label>
              Password
              <div className="password">
                <input
                  autoComplete="current-password"
                  type={shown ? "text" : "password"}
                  placeholder="Enter your password"
                  required
                  {...register("password")}
                />
                <button
                  type="button"
                  className="icon"
                  aria-label={shown ? "Hide password" : "Show password"}
                  onClick={() => setShown(!shown)}
                >
                  {shown ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </label>
            <label className="check">
              <input type="checkbox" {...register("remember")} /> Remember me
            </label>
            {error && (
              <p role="alert" className="error">
                {error}
              </p>
            )}
            <button className="primary wide" disabled={!!loading}>
              {loading ? "Signing in…" : "Sign in"}
              <ArrowRight size={16} />
            </button>
          </form>
          {!config.demo && config.quick_demo && (
            <div className="demo-area">
              <div className="demo-title"><span>QUICK DEMO ACCESS</span><div /></div>
              <p>Explore a fictional campus. No institutional credentials needed.</p>
              <div className="demo-grid">
                {demoRoles.map(([role, Icon]) => (
                  <button key={role} disabled={!!loading} onClick={() => quickEnter(role)}>
                    <Icon size={16} /> {accessLabels[role]} <ArrowUpRight size={12} />
                  </button>
                ))}
              </div>
            </div>
          )}
          {isDemoWorkspace && <p><a href="/">Return to institutional sign-in</a></p>}
          {config.demo && (
            <div className="demo-area">
              <div className="demo-title">
                <span>DEMO ACCESS</span>
                <div />
              </div>
              <p>
                {selectedPortal === "Student" && config.batch_demo
                  ? "Try the Section B timetable for either batch."
                  : "Explore the demonstration timetable as a guest."}
              </p>
              <div className="demo-grid">
                {demoRoles
                  .filter(([r]) => !selectedPortal || r === selectedPortal)
                  .map(([r, I]) => (
                    <button
                      key={r}
                      disabled={!!loading}
                      onClick={() =>
                        enter(
                          r.toLowerCase(),
                          r[0] + r.toLowerCase().slice(1) + "@123",
                          false,
                          r,
                        )
                      }
                    >
                      <I size={16} />
                      {selectedPortal === "Student" && config.batch_demo
                        ? "Batch B1 demo"
                        : r}
                      <ArrowUpRight size={12} />
                    </button>
                  ))}
                {selectedPortal === "Student" && config.batch_demo && (
                  <button
                    disabled={!!loading}
                    onClick={() => enter("student-b2", "DemoB2-Student!26")}
                  >
                    <GraduationCap size={16} />
                    Batch B2 demo
                    <ArrowUpRight size={12} />
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
