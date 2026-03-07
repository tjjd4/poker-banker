import { useEffect, useState, type FormEvent } from "react";
import { usersApi } from "../api/client";
import type { UserResponse, UserCreate } from "../types";
import Spinner from "../components/Spinner";

const roleBadge: Record<string, string> = {
  admin: "bg-red-100 text-red-800",
  banker: "bg-blue-100 text-blue-800",
  player: "bg-green-100 text-green-800",
};

export default function UsersPage() {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({
    display_name: "",
    role: "" as "admin" | "banker" | "player",
    is_active: true,
  });

  const [createForm, setCreateForm] = useState<UserCreate>({
    username: "",
    password: "",
    display_name: "",
    role: "player",
  });

  const loadUsers = async () => {
    setLoading(true);
    try {
      const res = await usersApi.list();
      setUsers(res.data.users);
    } catch (err) {
      console.error("Failed to load users", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await usersApi.create(createForm);
      setShowCreate(false);
      setCreateForm({
        username: "",
        password: "",
        display_name: "",
        role: "player",
      });
      loadUsers();
    } catch (err) {
      console.error("Failed to create user", err);
    }
  };

  const startEdit = (user: UserResponse) => {
    setEditingId(user.id);
    setEditForm({
      display_name: user.display_name,
      role: user.role as "admin" | "banker" | "player",
      is_active: user.is_active,
    });
  };

  const handleUpdate = async () => {
    if (!editingId) return;
    try {
      await usersApi.update(editingId, editForm);
      setEditingId(null);
      loadUsers();
    } catch (err) {
      console.error("Failed to update user", err);
    }
  };

  if (loading) return <Spinner />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">User Management</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Create User
        </button>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-gray-600">
              <th className="px-4 py-3">Username</th>
              <th className="px-4 py-3">Display Name</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-b last:border-0">
                <td className="px-4 py-3 font-medium">{user.username}</td>
                <td className="px-4 py-3">
                  {editingId === user.id ? (
                    <input
                      type="text"
                      value={editForm.display_name}
                      onChange={(e) =>
                        setEditForm({
                          ...editForm,
                          display_name: e.target.value,
                        })
                      }
                      className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
                    />
                  ) : (
                    user.display_name
                  )}
                </td>
                <td className="px-4 py-3">
                  {editingId === user.id ? (
                    <select
                      value={editForm.role}
                      onChange={(e) =>
                        setEditForm({
                          ...editForm,
                          role: e.target.value as "admin" | "banker" | "player",
                        })
                      }
                      className="rounded border border-gray-300 px-2 py-1 text-sm"
                    >
                      <option value="admin">Admin</option>
                      <option value="banker">Banker</option>
                      <option value="player">Player</option>
                    </select>
                  ) : (
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${roleBadge[user.role] ?? "bg-gray-200"}`}
                    >
                      {user.role}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {editingId === user.id ? (
                    <button
                      onClick={() =>
                        setEditForm({
                          ...editForm,
                          is_active: !editForm.is_active,
                        })
                      }
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${editForm.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}
                    >
                      {editForm.is_active ? "Active" : "Inactive"}
                    </button>
                  ) : (
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${user.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}
                    >
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-500">
                  {new Date(user.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  {editingId === user.id ? (
                    <div className="flex gap-2">
                      <button
                        onClick={handleUpdate}
                        className="rounded bg-green-100 px-2 py-1 text-xs font-medium text-green-700 hover:bg-green-200"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => startEdit(user)}
                      className="rounded bg-blue-100 px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-200"
                    >
                      Edit
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create User Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-semibold">Create User</h3>
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Username
                </label>
                <input
                  type="text"
                  value={createForm.username}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, username: e.target.value })
                  }
                  required
                  minLength={3}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Password
                </label>
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, password: e.target.value })
                  }
                  required
                  minLength={6}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Display Name
                </label>
                <input
                  type="text"
                  value={createForm.display_name}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      display_name: e.target.value,
                    })
                  }
                  required
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Role
                </label>
                <select
                  value={createForm.role}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      role: e.target.value as "admin" | "banker" | "player",
                    })
                  }
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="admin">Admin</option>
                  <option value="banker">Banker</option>
                  <option value="player">Player</option>
                </select>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
