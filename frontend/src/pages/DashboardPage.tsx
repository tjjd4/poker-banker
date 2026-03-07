import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { tablesApi, jackpotApi } from "../api/client";
import type {
  TableResponse,
  TableCreate,
  JackpotPoolResponse,
} from "../types";
import Spinner from "../components/Spinner";
import { useAuthStore } from "../stores/authStore";

const STATUS_FILTERS = ["ALL", "CREATED", "OPEN", "SETTLING", "CLOSED"] as const;

const statusColor: Record<string, string> = {
  CREATED: "bg-gray-200 text-gray-800",
  OPEN: "bg-green-100 text-green-800",
  SETTLING: "bg-yellow-100 text-yellow-800",
  CLOSED: "bg-red-100 text-red-800",
};

export default function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const canManageTables = user?.role === "admin" || user?.role === "banker";
  const [tables, setTables] = useState<TableResponse[]>([]);
  const [pools, setPools] = useState<JackpotPoolResponse[]>([]);
  const [filter, setFilter] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);
  const [showCreateTable, setShowCreateTable] = useState(false);
  const [showCreatePool, setShowCreatePool] = useState(false);
  const [poolName, setPoolName] = useState("");
  const [showPools, setShowPools] = useState(false);

  const [tableForm, setTableForm] = useState<TableCreate>({
    name: "",
    blind_level: "",
    rake_interval_minutes: 30,
    rake_amount: 100,
    jackpot_per_hand: 0,
    jackpot_pool_id: undefined,
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const [tRes, pRes] = await Promise.all([
        tablesApi.list(filter === "ALL" ? undefined : filter),
        jackpotApi.listPools(),
      ]);
      setTables(tRes.data.tables);
      setPools(pRes.data.pools);
    } catch (err) {
      console.error("Failed to load data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [filter]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCreateTable = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await tablesApi.create({
        ...tableForm,
        jackpot_pool_id: tableForm.jackpot_pool_id || undefined,
      });
      setShowCreateTable(false);
      setTableForm({
        name: "",
        blind_level: "",
        rake_interval_minutes: 30,
        rake_amount: 100,
        jackpot_per_hand: 0,
        jackpot_pool_id: undefined,
      });
      loadData();
    } catch (err) {
      console.error("Failed to create table", err);
    }
  };

  const handleCreatePool = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await jackpotApi.createPool({ name: poolName });
      setPoolName("");
      setShowCreatePool(false);
      loadData();
    } catch (err) {
      console.error("Failed to create pool", err);
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <div className="flex gap-2">
          {canManageTables && (
            <>
              <button
                onClick={() => setShowPools(!showPools)}
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                {showPools ? "Hide Pools" : "Jackpot Pools"}
              </button>
              <button
                onClick={() => setShowCreateTable(true)}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Create Table
              </button>
            </>
          )}
        </div>
      </div>

      {/* Jackpot Pools Section */}
      {showPools && (
        <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Jackpot Pools</h3>
            <button
              onClick={() => setShowCreatePool(true)}
              className="rounded-md bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700"
            >
              Create Pool
            </button>
          </div>
          {pools.length === 0 ? (
            <p className="text-sm text-gray-500">No pools yet.</p>
          ) : (
            <div className="space-y-2">
              {pools.map((pool) => (
                <div
                  key={pool.id}
                  className="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2"
                >
                  <span className="text-sm font-medium">{pool.name}</span>
                  <span className="text-sm font-semibold text-green-700">
                    ${pool.balance.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Create Pool Dialog */}
          {showCreatePool && (
            <form onSubmit={handleCreatePool} className="mt-3 flex gap-2">
              <input
                type="text"
                placeholder="Pool name"
                value={poolName}
                onChange={(e) => setPoolName(e.target.value)}
                required
                className="flex-1 rounded-md border border-gray-300 px-3 py-1 text-sm"
              />
              <button
                type="submit"
                className="rounded-md bg-green-600 px-3 py-1 text-sm text-white hover:bg-green-700"
              >
                Save
              </button>
              <button
                type="button"
                onClick={() => setShowCreatePool(false)}
                className="rounded-md border border-gray-300 px-3 py-1 text-sm"
              >
                Cancel
              </button>
            </form>
          )}
        </div>
      )}

      {/* Status Filter Tabs */}
      <div className="mb-4 flex gap-1">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${
              filter === s
                ? "bg-blue-600 text-white"
                : "bg-gray-200 text-gray-700 hover:bg-gray-300"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Table List */}
      {loading ? (
        <Spinner />
      ) : tables.length === 0 ? (
        <p className="text-gray-500">No tables found.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tables.map((table) => (
            <div
              key={table.id}
              onClick={() => navigate(`/tables/${table.id}`)}
              className="cursor-pointer rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="mb-2 flex items-center justify-between">
                <h3 className="font-semibold text-gray-900">{table.name}</h3>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor[table.status] ?? "bg-gray-200"}`}
                >
                  {table.status}
                </span>
              </div>
              <p className="text-sm text-gray-600">
                Blind: {table.blind_level}
              </p>
              <p className="text-sm text-gray-600">
                Rake: ${table.rake_amount} / {table.rake_interval_minutes}min
              </p>
              {table.jackpot_per_hand > 0 && (
                <p className="text-sm text-purple-600">
                  Jackpot: ${table.jackpot_per_hand}/hand
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Create Table Modal */}
      {showCreateTable && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-semibold">Create Table</h3>
            <form onSubmit={handleCreateTable} className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Table Name
                </label>
                <input
                  type="text"
                  value={tableForm.name}
                  onChange={(e) =>
                    setTableForm({ ...tableForm, name: e.target.value })
                  }
                  required
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Blind Level
                </label>
                <input
                  type="text"
                  placeholder="e.g. 1/2, 2/5, 5/10"
                  value={tableForm.blind_level}
                  onChange={(e) =>
                    setTableForm({ ...tableForm, blind_level: e.target.value })
                  }
                  required
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Rake Amount
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={tableForm.rake_amount}
                    onChange={(e) =>
                      setTableForm({
                        ...tableForm,
                        rake_amount: Number(e.target.value),
                      })
                    }
                    required
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Rake Interval (min)
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={tableForm.rake_interval_minutes}
                    onChange={(e) =>
                      setTableForm({
                        ...tableForm,
                        rake_interval_minutes: Number(e.target.value),
                      })
                    }
                    required
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Jackpot/Hand
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={tableForm.jackpot_per_hand}
                    onChange={(e) =>
                      setTableForm({
                        ...tableForm,
                        jackpot_per_hand: Number(e.target.value),
                      })
                    }
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Jackpot Pool
                  </label>
                  <select
                    value={tableForm.jackpot_pool_id ?? ""}
                    onChange={(e) =>
                      setTableForm({
                        ...tableForm,
                        jackpot_pool_id: e.target.value || undefined,
                      })
                    }
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  >
                    <option value="">None</option>
                    {pools.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateTable(false)}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
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
