// ---- Auth ----

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

// ---- Users ----

export interface UserCreate {
  username: string;
  password: string;
  display_name: string;
  role: "admin" | "banker" | "player";
}

export interface UserUpdate {
  display_name?: string;
  role?: "admin" | "banker" | "player";
  is_active?: boolean;
}

export interface UserResponse {
  id: string;
  username: string;
  display_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface UserListResponse {
  users: UserResponse[];
  total: number;
}

// ---- Tables ----

export interface TableCreate {
  name: string;
  blind_level: string;
  rake_interval_minutes: number;
  rake_amount: number;
  jackpot_per_hand?: number;
  jackpot_pool_id?: string;
}

export interface TableStatusUpdate {
  status: "OPEN" | "SETTLING" | "CLOSED";
}

export interface TableUnlock {
  reason: string;
}

export interface TableResponse {
  id: string;
  name: string;
  blind_level: string;
  rake_interval_minutes: number;
  rake_amount: number;
  jackpot_per_hand: number;
  jackpot_pool_id: string | null;
  status: string;
  banker_id: string;
  opened_at: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlayerSeatResponse {
  id: string;
  player_id: string;
  player_display_name: string;
  seated_at: string;
  left_at: string | null;
  is_active: boolean;
}

export interface TableDetailResponse extends TableResponse {
  players: PlayerSeatResponse[];
}

export interface TableListResponse {
  tables: TableResponse[];
  total: number;
}

// ---- Transactions ----

export interface BuyInRequest {
  player_id: string;
  amount: number;
}

export interface CashOutRequest {
  player_id: string;
  chip_count: number;
}

export interface TransactionResponse {
  id: string;
  table_id: string;
  player_id: string;
  type: string;
  amount: number;
  balance_after: number;
  note: string | null;
  created_by: string;
  created_at: string;
}

export interface BuyInResponse {
  transaction: TransactionResponse;
  total_buy_in: number;
  current_balance: number;
}

export interface CashOutResponse {
  transactions: TransactionResponse[];
  chip_count: number;
  total_buy_in: number;
  rake_amount: number;
  net_result: number;
  seated_minutes: number;
}

export interface PlayerStatusResponse {
  player_id: string;
  display_name: string;
  total_buy_in: number;
  current_balance: number;
  is_seated: boolean;
  seated_at: string | null;
  left_at: string | null;
}

export interface TablePlayersResponse {
  table_id: string;
  players: PlayerStatusResponse[];
}

export interface TransactionListResponse {
  transactions: TransactionResponse[];
  total: number;
}

// ---- Insurance ----

export interface InsuranceCreateRequest {
  buyer_id: string;
  opponent_id: string;
  buyer_hand: string[];
  opponent_hand: string[];
  community_cards: string[];
}

export interface InsuranceConfirmRequest {
  insured_amount: number;
  seller_id?: string;
}

export interface InsuranceResolveRequest {
  is_hit: boolean;
  final_community_cards: string[];
}

export interface InsuranceCalcResponse {
  id: string;
  table_id: string;
  buyer_id: string;
  buyer_hand: string[];
  opponent_hand: string[];
  community_cards: string[];
  outs: number;
  total_combinations: number;
  win_probability: number;
  odds: number;
  created_at: string;
}

export interface InsuranceDetailResponse {
  id: string;
  table_id: string;
  buyer_id: string;
  seller_id: string | null;
  buyer_hand: string[];
  opponent_hand: string[];
  community_cards: string[];
  outs: number;
  win_probability: number;
  odds: number;
  insured_amount: number;
  payout_amount: number;
  is_hit: boolean | null;
  created_at: string;
}

export interface InsuranceListResponse {
  events: InsuranceDetailResponse[];
  total: number;
}

// ---- Jackpot ----

export interface JackpotPoolCreate {
  name: string;
}

export interface JackpotTriggerRequest {
  pool_id: string;
  winner_id: string;
  hand_description: string;
  payout_amount: number;
}

export interface JackpotPoolResponse {
  id: string;
  name: string;
  balance: number;
  banker_id: string;
  created_at: string;
  updated_at: string;
}

export interface JackpotPoolListResponse {
  pools: JackpotPoolResponse[];
  total: number;
}

export interface HandContribution {
  player_id: string;
  display_name: string;
  amount: number;
}

export interface RecordHandResponse {
  pool_id: string;
  pool_balance: number;
  jackpot_per_hand: number;
  contributions: HandContribution[];
  remainder: number;
}

export interface JackpotTriggerResponse {
  id: string;
  pool_id: string;
  table_id: string;
  winner_id: string;
  hand_description: string;
  payout_amount: number;
  pool_balance_after: number;
  triggered_by: string;
  created_at: string;
}
