import React, { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { apiClient } from "../api/client";
import { extractApiError } from "../api/client";

type User = {
  id: number;
  email: string;
  username: string;
  role: "admin" | "analyst";
  is_active: boolean;
  created_at: string;
  created_by?: string | null;
};

type CreateForm = {
  email: string;
  username: string;
  password: string;
  role: "admin" | "analyst";
};

const EMPTY_FORM: CreateForm = { email: "", username: "", password: "", role: "analyst" };

async function fetchUsers(): Promise<User[]> {
  const { data } = await apiClient.get<User[]>("/auth/users");
  return data;
}

async function createUser(form: CreateForm): Promise<User> {
  const { data } = await apiClient.post<User>("/auth/register", form);
  return data;
}

async function toggleUser(id: number, activate: boolean): Promise<User> {
  const action = activate ? "activate" : "deactivate";
  const { data } = await apiClient.patch<User>(`/auth/users/${id}/${action}`);
  return data;
}

export default function UserManagement() {
  const { isAdmin, user: me } = useAuth();
  const [users, setUsers] = React.useState<User[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  React.useEffect(() => {
    setLoading(true);
    fetchUsers()
      .then(setUsers)
      .catch((e) => setError(extractApiError(e, "Failed to load users")))
      .finally(() => setLoading(false));
  }, []);

  if (!isAdmin) {
    return (
      <section className="page">
        <div className="panel">
          <p className="page-note">Access restricted to administrators.</p>
        </div>
      </section>
    );
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (form.password.length < 8) {
      setFormError("Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const created = await createUser(form);
      setUsers((prev) => [created, ...prev]);
      setShowModal(false);
      setForm(EMPTY_FORM);
    } catch (err) {
      setFormError(extractApiError(err, "Failed to create user"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(u: User) {
    setActionLoading(u.id);
    try {
      const updated = await toggleUser(u.id, !u.is_active);
      setUsers((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch (err) {
      setError(extractApiError(err, "Action failed"));
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <section className="page">
      {/* Header */}
      <div className="page-header-row">
        <div>
          <h1 className="page-title">User Management</h1>
          <p className="page-note">Manage platform accounts. Only admins can access this page.</p>
        </div>
        <button className="button primary" onClick={() => { setShowModal(true); setFormError(null); setForm(EMPTY_FORM); }}>
          + New User
        </button>
      </div>

      {error && <div className="login-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Users table */}
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--text-muted)" }}>Loading…</div>
        ) : (
          <table className="data-table" style={{ width: "100%" }}>
            <thead>
              <tr>
                <th>Username</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created by</th>
                <th>Created at</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} style={{ opacity: u.is_active ? 1 : 0.55 }}>
                  <td>
                    <strong>{u.username}</strong>
                    {u.id === me?.id && <span style={{ marginLeft: 6, fontSize: "0.7rem", color: "var(--brand)", fontWeight: 600 }}>YOU</span>}
                  </td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{u.email}</td>
                  <td>
                    <span className={`status-badge ${u.role === "admin" ? "status-pass" : "status-skipped"}`}>
                      {u.role}
                    </span>
                  </td>
                  <td>
                    <span className={`status-badge ${u.is_active ? "status-pass" : "status-fail"}`}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{u.created_by ?? "—"}</td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    {u.id !== me?.id ? (
                      <button
                        className={`button ${u.is_active ? "ghost" : "primary"}`}
                        style={{ fontSize: "0.8125rem", padding: "4px 12px" }}
                        disabled={actionLoading === u.id}
                        onClick={() => handleToggle(u)}
                      >
                        {actionLoading === u.id ? "…" : u.is_active ? "Deactivate" : "Activate"}
                      </button>
                    ) : (
                      <span style={{ color: "var(--text-muted)", fontSize: "0.8125rem" }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create user modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Create New User</h2>
              <button className="modal-close" onClick={() => setShowModal(false)} aria-label="Close">✕</button>
            </div>

            <form onSubmit={handleCreate} className="login-form" style={{ gap: 14 }}>
              {formError && <div className="login-error">{formError}</div>}

              <div className="login-field">
                <label className="login-label">Email</label>
                <input className="login-input" type="email" required
                  value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  placeholder="user@company.com" disabled={submitting} />
              </div>

              <div className="login-field">
                <label className="login-label">Username</label>
                <input className="login-input" type="text" required minLength={2}
                  value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                  placeholder="john_doe" disabled={submitting} />
              </div>

              <div className="login-field">
                <label className="login-label">Password</label>
                <input className="login-input" type="password" required minLength={8}
                  value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                  placeholder="Min 8 characters" disabled={submitting} />
              </div>

              <div className="login-field">
                <label className="login-label">Role</label>
                <select className="login-input" value={form.role}
                  onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as "admin" | "analyst" }))}
                  disabled={submitting}>
                  <option value="analyst">Analyst</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                <button type="button" className="button ghost" style={{ flex: 1 }}
                  onClick={() => setShowModal(false)} disabled={submitting}>
                  Cancel
                </button>
                <button type="submit" className="login-btn" style={{ flex: 2, marginTop: 0 }}
                  disabled={submitting || !form.email || !form.username || !form.password}>
                  {submitting ? <><span className="login-spinner" /> Creating…</> : "Create User"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
