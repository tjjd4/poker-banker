import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";

const navItems = [
  { to: "/dashboard", label: "Dashboard", roles: ["admin", "banker"] },
  { to: "/users", label: "Users", roles: ["admin"] },
  { to: "/insurance", label: "Insurance", roles: ["admin", "banker"] },
  { to: "/reports", label: "Reports", roles: ["admin", "banker"] },
  { to: "/player-portal", label: "Player Portal", roles: ["player"] },
];

export default function Layout() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const visibleItems = navItems.filter(
    (item) => user && item.roles.includes(user.role),
  );

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <aside className="flex w-60 flex-col bg-gray-900 text-white">
        <div className="border-b border-gray-700 px-6 py-5">
          <h1 className="text-xl font-bold">Poker Banker</h1>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-gray-800 text-white"
                    : "text-gray-300 hover:bg-gray-800 hover:text-white"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-gray-700 p-4">
          {user && (
            <p className="mb-3 truncate text-xs text-gray-400">
              {user.role.toUpperCase()}
            </p>
          )}
          <button
            onClick={handleLogout}
            className="w-full rounded-md bg-gray-800 px-3 py-2 text-sm text-gray-300 hover:bg-gray-700 hover:text-white"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
