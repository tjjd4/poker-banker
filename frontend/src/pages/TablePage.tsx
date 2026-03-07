import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { tablesApi, jackpotApi, usersApi } from "../api/client";
import { useAuthStore } from "../stores/authStore";
import type {
  TableDetailResponse,
  PlayerStatusResponse,
  TransactionResponse,
  UserResponse,
  JackpotPoolResponse,
  RecordHandResponse,
} from "../types";
import Spinner from "../components/Spinner";
import ConfirmDialog from "../components/ConfirmDialog";

const statusColor: Record<string, string> = {
  CREATED: "bg-gray-200 text-gray-800",
  OPEN: "bg-green-100 text-green-800",
  SETTLING: "bg-yellow-100 text-yellow-800",
  CLOSED: "bg-red-100 text-red-800",
};

export default function TablePage() {
  const { tableId } = useParams<{ tableId: string }>();
  const user = useAuthStore((s) => s.user);
  const [table, setTable] = useState<TableDetailResponse | null>(null);
  const [players, setPlayers] = useState<PlayerStatusResponse[]>([]);
  const [transactions, setTransactions] = useState<TransactionResponse[]>([]);
  const [allUsers, setAllUsers] = useState<UserResponse[]>([]);
  const [pool, setPool] = useState<JackpotPoolResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [showTxns, setShowTxns] = useState(false);

  // Buy-in dialog state
  const [showBuyIn, setShowBuyIn] = useState(false);
  const [buyInPlayerId, setBuyInPlayerId] = useState("");
  const [buyInAmount, setBuyInAmount] = useState(1000);

  // Cash-out dialog state
  const [showCashOut, setShowCashOut] = useState(false);
  const [cashOutPlayerId, setCashOutPlayerId] = useState("");
  const [cashOutPlayerName, setCashOutPlayerName] = useState("");
  const [chipCount, setChipCount] = useState(0);

  // Jackpot trigger dialog
  const [showTrigger, setShowTrigger] = useState(false);
  const [triggerWinnerId, setTriggerWinnerId] = useState("");
  const [triggerAmount, setTriggerAmount] = useState(0);
  const [triggerDesc, setTriggerDesc] = useState("");

  // Hand result display
  const [handResult, setHandResult] = useState<RecordHandResponse | null>(null);

  // Status confirm dialog
  const [confirmStatus, setConfirmStatus] = useState<string | null>(null);
  const [showUnlock, setShowUnlock] = useState(false);
  const [unlockReason, setUnlockReason] = useState("");

  const loadData = async () => {
    if (!tableId) return;
    setLoading(true);
    try {
      const [tRes, pRes, txRes] = await Promise.all([
        tablesApi.get(tableId),
        tablesApi.getPlayers(tableId).catch(() => ({ data: { players: [] } })),
        tablesApi
          .getTransactions(tableId)
          .catch(() => ({ data: { transactions: [] } })),
      ]);
      setTable(tRes.data);
      setPlayers(pRes.data.players);
      setTransactions(txRes.data.transactions);

      if (tRes.data.jackpot_pool_id) {
        const poolRes = await jackpotApi.getPool(tRes.data.jackpot_pool_id);
        setPool(poolRes.data);
      }

      // Load all users for buy-in player selection
      try {
        const uRes = await usersApi.list();
        setAllUsers(uRes.data.users);
      } catch {
        // Non-admin can't list users
      }
    } catch (err) {
      console.error("Failed to load table data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [tableId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStatusChange = async (newStatus: string) => {
    if (!tableId) return;
    try {
      await tablesApi.updateStatus(tableId, newStatus);
      setConfirmStatus(null);
      loadData();
    } catch (err) {
      console.error("Failed to update status", err);
    }
  };

  const handleUnlock = async (e: FormEvent) => {
    e.preventDefault();
    if (!tableId) return;
    try {
      await tablesApi.unlock(tableId, unlockReason);
      setShowUnlock(false);
      setUnlockReason("");
      loadData();
    } catch (err) {
      console.error("Failed to unlock table", err);
    }
  };

  const handleBuyIn = async (e: FormEvent) => {
    e.preventDefault();
    if (!tableId) return;
    try {
      await tablesApi.buyIn(tableId, {
        player_id: buyInPlayerId,
        amount: buyInAmount,
      });
      setShowBuyIn(false);
      setBuyInPlayerId("");
      setBuyInAmount(1000);
      loadData();
    } catch (err) {
      console.error("Failed to buy in", err);
    }
  };

  const handleCashOut = async (e: FormEvent) => {
    e.preventDefault();
    if (!tableId) return;
    try {
      await tablesApi.cashOut(tableId, {
        player_id: cashOutPlayerId,
        chip_count: chipCount,
      });
      setShowCashOut(false);
      setCashOutPlayerId("");
      setChipCount(0);
      loadData();
    } catch (err) {
      console.error("Failed to cash out", err);
    }
  };

  const handleRecordHand = async () => {
    if (!tableId) return;
    try {
      const res = await jackpotApi.recordHand(tableId);
      setHandResult(res.data);
      loadData();
    } catch (err) {
      console.error("Failed to record hand", err);
    }
  };

  const handleTriggerPayout = async (e: FormEvent) => {
    e.preventDefault();
    if (!tableId || !pool) return;
    try {
      await jackpotApi.triggerPayout(tableId, {
        pool_id: pool.id,
        winner_id: triggerWinnerId,
        hand_description: triggerDesc,
        payout_amount: triggerAmount,
      });
      setShowTrigger(false);
      setTriggerWinnerId("");
      setTriggerAmount(0);
      setTriggerDesc("");
      loadData();
    } catch (err) {
      console.error("Failed to trigger payout", err);
    }
  };

  if (loading) return <Spinner />;
  if (!table) return <p className="text-red-600">Table not found.</p>;

  const canManageTables = user?.role === "admin" || user?.role === "banker";
  const activePlayers = players.filter((p) => p.is_seated);
  const playerUsers = allUsers.filter((u) => u.role === "player" && u.is_active);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{table.name}</h2>
          <p className="text-sm text-gray-600">
            Blind: {table.blind_level} | Rake: ${table.rake_amount} /{" "}
            {table.rake_interval_minutes}min
            {table.jackpot_per_hand > 0 &&
              ` | Jackpot: $${table.jackpot_per_hand}/hand`}
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-sm font-medium ${statusColor[table.status] ?? "bg-gray-200"}`}
        >
          {table.status}
        </span>
      </div>

      {/* Status Actions */}
      {canManageTables && (
        <div className="flex gap-2">
          {table.status === "CREATED" && (
            <button
              onClick={() => setConfirmStatus("OPEN")}
              className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
            >
              Open Table
            </button>
          )}
          {table.status === "OPEN" && (
            <button
              onClick={() => setConfirmStatus("SETTLING")}
              className="rounded-md bg-yellow-600 px-4 py-2 text-sm font-medium text-white hover:bg-yellow-700"
            >
              Start Settling
            </button>
          )}
          {table.status === "SETTLING" && (
            <button
              onClick={() => setConfirmStatus("CLOSED")}
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
            >
              Close Table
            </button>
          )}
          {table.status === "CLOSED" && user?.role === "admin" && (
            <button
              onClick={() => setShowUnlock(true)}
              className="rounded-md bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-700"
            >
              Unlock Table
            </button>
          )}
        </div>
      )}

      {/* Players Section */}
      {(table.status === "OPEN" || table.status === "SETTLING") && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">
              Players ({activePlayers.length})
            </h3>
            {table.status === "OPEN" && canManageTables && (
              <button
                onClick={() => setShowBuyIn(true)}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
              >
                Buy-in
              </button>
            )}
          </div>

          {activePlayers.length === 0 ? (
            <p className="text-sm text-gray-500">No players seated.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-600">
                    <th className="pb-2 pr-4">Player</th>
                    <th className="pb-2 pr-4">Total Buy-in</th>
                    <th className="pb-2 pr-4">Balance</th>
                    <th className="pb-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {activePlayers.map((p) => (
                    <tr key={p.player_id} className="border-b last:border-0">
                      <td className="py-2 pr-4 font-medium">
                        {p.display_name}
                      </td>
                      <td className="py-2 pr-4">
                        ${p.total_buy_in.toLocaleString()}
                      </td>
                      <td
                        className={`py-2 pr-4 font-semibold ${p.current_balance >= 0 ? "text-green-700" : "text-red-700"}`}
                      >
                        ${p.current_balance.toLocaleString()}
                      </td>
                      <td className="py-2">
                        {canManageTables && (
                          <div className="flex gap-2">
                            {table.status === "OPEN" && (
                              <button
                                onClick={() => {
                                  setBuyInPlayerId(p.player_id);
                                  setBuyInAmount(1000);
                                  setShowBuyIn(true);
                                }}
                                className="rounded bg-blue-100 px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-200"
                              >
                                Re-buy
                              </button>
                            )}
                            <button
                              onClick={() => {
                                setCashOutPlayerId(p.player_id);
                                setCashOutPlayerName(p.display_name);
                                setChipCount(0);
                                setShowCashOut(true);
                              }}
                              className="rounded bg-red-100 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-200"
                            >
                              Cash-out
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Jackpot Section */}
      {table.jackpot_per_hand > 0 && pool && table.status === "OPEN" && canManageTables && (
        <div className="rounded-lg border border-purple-200 bg-purple-50 p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-purple-900">
                Jackpot: {pool.name}
              </h3>
              <p className="text-2xl font-bold text-purple-700">
                ${pool.balance.toLocaleString()}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleRecordHand}
                className="rounded-md bg-purple-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-purple-700"
              >
                Record Hand
              </button>
              <button
                onClick={() => setShowTrigger(true)}
                className="rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700"
              >
                Trigger Payout
              </button>
            </div>
          </div>

          {/* Hand Result Display */}
          {handResult && (
            <div className="mt-3 rounded-md border border-purple-200 bg-white p-3">
              <p className="text-sm font-medium text-purple-800">
                Hand recorded: ${handResult.jackpot_per_hand}/hand, Pool balance:
                ${handResult.pool_balance.toLocaleString()}
                {handResult.remainder > 0 &&
                  ` (remainder: $${handResult.remainder})`}
              </p>
              <div className="mt-1 space-y-1">
                {handResult.contributions.map((c) => (
                  <p key={c.player_id} className="text-xs text-gray-600">
                    {c.display_name}: -${c.amount}
                  </p>
                ))}
              </div>
              <button
                onClick={() => setHandResult(null)}
                className="mt-2 text-xs text-purple-600 hover:underline"
              >
                Dismiss
              </button>
            </div>
          )}
        </div>
      )}

      {/* Transaction Log */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <button
          onClick={() => setShowTxns(!showTxns)}
          className="flex w-full items-center justify-between text-left"
        >
          <h3 className="font-semibold text-gray-900">
            Transaction Log ({transactions.length})
          </h3>
          <span className="text-sm text-gray-500">
            {showTxns ? "Hide" : "Show"}
          </span>
        </button>

        {showTxns && transactions.length > 0 && (
          <div className="mt-3 max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-600">
                  <th className="pb-2 pr-3">Type</th>
                  <th className="pb-2 pr-3">Amount</th>
                  <th className="pb-2 pr-3">Balance After</th>
                  <th className="pb-2 pr-3">Note</th>
                  <th className="pb-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr key={tx.id} className="border-b last:border-0">
                    <td className="py-1.5 pr-3">
                      <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs font-medium">
                        {tx.type}
                      </span>
                    </td>
                    <td
                      className={`py-1.5 pr-3 font-medium ${tx.amount >= 0 ? "text-green-700" : "text-red-700"}`}
                    >
                      {tx.amount >= 0 ? "+" : ""}
                      {tx.amount.toLocaleString()}
                    </td>
                    <td className="py-1.5 pr-3">
                      ${tx.balance_after.toLocaleString()}
                    </td>
                    <td className="py-1.5 pr-3 text-gray-500">
                      {tx.note ?? "-"}
                    </td>
                    <td className="py-1.5 text-gray-500">
                      {new Date(tx.created_at).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Confirm Status Change Dialog */}
      <ConfirmDialog
        open={confirmStatus !== null}
        title="Change Table Status"
        message={`Are you sure you want to change the table status to ${confirmStatus}?`}
        confirmLabel={`Set ${confirmStatus}`}
        onConfirm={() => confirmStatus && handleStatusChange(confirmStatus)}
        onCancel={() => setConfirmStatus(null)}
      />

      {/* Buy-in Dialog */}
      {showBuyIn && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-semibold">Buy-in</h3>
            <form onSubmit={handleBuyIn} className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Player
                </label>
                <select
                  value={buyInPlayerId}
                  onChange={(e) => setBuyInPlayerId(e.target.value)}
                  required
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="">Select player</option>
                  {playerUsers.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.display_name} ({u.username})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Amount
                </label>
                <input
                  type="number"
                  min={1}
                  value={buyInAmount}
                  onChange={(e) => setBuyInAmount(Number(e.target.value))}
                  required
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowBuyIn(false)}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  Confirm Buy-in
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Cash-out Dialog */}
      {showCashOut && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-semibold">
              Cash-out: {cashOutPlayerName}
            </h3>
            <form onSubmit={handleCashOut} className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Chip Count
                </label>
                <input
                  type="number"
                  min={0}
                  value={chipCount}
                  onChange={(e) => setChipCount(Number(e.target.value))}
                  required
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCashOut(false)}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
                >
                  Confirm Cash-out
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Trigger Payout Dialog */}
      {showTrigger && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-semibold">Trigger Jackpot Payout</h3>
            <form onSubmit={handleTriggerPayout} className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Winner
                </label>
                <select
                  value={triggerWinnerId}
                  onChange={(e) => setTriggerWinnerId(e.target.value)}
                  required
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="">Select winner</option>
                  {activePlayers.map((p) => (
                    <option key={p.player_id} value={p.player_id}>
                      {p.display_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Payout Amount (Pool: ${pool?.balance.toLocaleString()})
                </label>
                <input
                  type="number"
                  min={1}
                  max={pool?.balance}
                  value={triggerAmount}
                  onChange={(e) => setTriggerAmount(Number(e.target.value))}
                  required
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Hand Description
                </label>
                <input
                  type="text"
                  placeholder="e.g. Royal Flush"
                  value={triggerDesc}
                  onChange={(e) => setTriggerDesc(e.target.value)}
                  required
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowTrigger(false)}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700"
                >
                  Trigger Payout
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Unlock Dialog */}
      {showUnlock && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-semibold">Unlock Table</h3>
            <form onSubmit={handleUnlock} className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Reason
                </label>
                <input
                  type="text"
                  value={unlockReason}
                  onChange={(e) => setUnlockReason(e.target.value)}
                  required
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowUnlock(false)}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-700"
                >
                  Unlock
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
