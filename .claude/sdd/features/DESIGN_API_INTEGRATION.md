# DESIGN: API Integration

> Technical design for replacing Supabase POC with FinPulse .NET API integration

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | API_INTEGRATION |
| **Date** | 2026-02-11 |
| **Author** | design-agent |
| **DEFINE** | [DEFINE_API_INTEGRATION.md](./DEFINE_API_INTEGRATION.md) |
| **Status** | Ready for Build |

---

## Architecture Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│                        BROWSER (React SPA)                          │
│                                                                      │
│  ┌─────────┐   ┌──────────────┐   ┌──────────────────────────────┐  │
│  │  Pages   │   │   Contexts   │   │          Hooks               │  │
│  │          │   │              │   │                              │  │
│  │ Login    │──▶│ AuthContext   │──▶│ useTransactions              │  │
│  │ Register │   │ (userId,     │   │ useBudgets                   │  │
│  │ Index    │   │  user,       │   │ useBills                     │  │
│  │          │   │  isAuth)     │   │ useGoals                     │  │
│  └─────────┘   └──────┬───────┘   │ useInvestments               │  │
│                        │           └──────────────┬───────────────┘  │
│                        │                          │                  │
│                        ▼                          ▼                  │
│              ┌──────────────────────────────────────────────────┐    │
│              │              Services Layer                       │    │
│              │                                                  │    │
│              │  apiClient.ts ─── Base fetch wrapper              │    │
│              │       │          (credentials: 'include')        │    │
│              │       ├── authService.ts                          │    │
│              │       ├── expenseService.ts                       │    │
│              │       ├── earningService.ts                       │    │
│              │       ├── budgetService.ts                        │    │
│              │       ├── billService.ts                          │    │
│              │       ├── goalService.ts                          │    │
│              │       └── investmentService.ts                    │    │
│              │                                                  │    │
│              │  types.ts ─── TypeScript interfaces for DTOs      │    │
│              └──────────────────────┬───────────────────────────┘    │
│                                     │                                │
└─────────────────────────────────────┼────────────────────────────────┘
                                      │  HTTP (fetch + JWT cookie)
                                      ▼
                        ┌─────────────────────────────┐
                        │   FinPulse .NET API          │
                        │   ASP.NET Core 8.0           │
                        │                             │
                        │   /api/auth/*               │
                        │   /api/users/{userId}/*     │
                        │                             │
                        │   JWT in HttpOnly cookie    │
                        │   SQL Server backend        │
                        └─────────────────────────────┘
```

---

## Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| `apiClient` | Base HTTP client with auth, error handling | Native `fetch` API |
| `AuthContext` | Auth state, userId, login/logout, session restore | React Context + Provider |
| `Services` | Entity-specific CRUD operations | TypeScript + apiClient |
| `Types` | Shared interfaces matching API DTOs | TypeScript interfaces |
| `Hooks` | State management + service orchestration for components | React hooks (useState, useEffect, useCallback) |
| `Pages` | Login, Register, Dashboard (Index) | React components |

---

## Key Decisions

### Decision 1: ID Type Change (string → number)

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-11 |

**Context:** All existing hooks use `string` IDs (generated client-side with `Math.random().toString(36)`). The API returns `number` (int) IDs from SQL Server auto-increment.

**Choice:** Change all interface IDs from `string` to `number` across hooks, components, and service types.

**Rationale:** The API is the source of truth. Keeping `string` IDs would require constant `.toString()` conversions and would create type confusion.

**Alternatives Rejected:**
1. Keep string IDs and convert at service layer - Rejected because it adds unnecessary mapping complexity
2. Change API to return string IDs - Rejected because the API is already built and deployed

**Consequences:**
- All components that pass `id` props need updating
- Dialog components that receive entity objects need interface updates
- This is a one-time migration cost

---

### Decision 2: Cookie Secure Flag + HTTPS for Dev

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-11 |

**Context:** The API sets cookies with `Secure: true`, which means the browser will only send the cookie over HTTPS. For local development on `http://localhost:5173`, the cookie will NOT be stored by the browser.

**Choice:** Use Vite's built-in HTTPS dev server with a self-signed cert, OR document that the API's cookie options should be relaxed for development. The practical approach is to let the build phase test the actual behavior - if cookies don't work over HTTP localhost, we'll add `vite-plugin-mkcert` for HTTPS dev server.

**Rationale:** Many modern browsers have special handling for `localhost` that allows `Secure` cookies over HTTP. Chrome, for instance, treats `localhost` as a secure context. If this doesn't work, `vite-plugin-mkcert` generates trusted local HTTPS certs automatically.

**Alternatives Rejected:**
1. Modify API cookie settings - Rejected because we don't want to weaken the API's security model

**Consequences:**
- May need to add `vite-plugin-mkcert` if cookies don't work over HTTP localhost
- Production is already HTTPS so no issue there

---

### Decision 3: Auth State Restoration via /api/auth/me

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-11 |

**Context:** When the user refreshes the page, we need to know if they're still authenticated. The JWT is in an HttpOnly cookie (not readable by JavaScript).

**Choice:** On app mount, call `GET /api/auth/me`. If it returns 200, the user is authenticated (extract `{id, email, username}`). If 401, redirect to login.

**Rationale:** This is the only way to check auth status when using HttpOnly cookies. The `/api/auth/me` endpoint already exists and returns user info.

**Alternatives Rejected:**
1. Store userId in localStorage - Rejected because it can get out of sync with the cookie
2. Use a non-HttpOnly cookie - Rejected because it reduces security

**Consequences:**
- One extra API call on every page load (acceptable - it's fast)
- Brief loading state before auth is resolved

---

### Decision 4: Hook Interface Preservation Strategy

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-11 |

**Context:** The existing hooks return a consistent API that components depend on: `{ entities, isLoading, add*, update*, delete*, refetch }`. We need to preserve this contract while replacing the implementation.

**Choice:** Keep the same hook return shape. Replace internal `useState` with `useState` + API calls. Each mutation calls the API, then refetches the list to keep state in sync.

**Rationale:** This minimizes changes to components. Only the hooks and their type interfaces change. Components don't need to know about the API.

**Alternatives Rejected:**
1. Rewrite hooks with React Query - Rejected (YAGNI, adds complexity)
2. Pass services directly to components - Rejected because it breaks the existing abstraction

**Consequences:**
- Components remain largely unchanged (only ID type changes)
- Hooks become the integration point between UI and API

---

### Decision 5: Service Layer Pattern

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-11 |

**Context:** Need a consistent way to call the API from hooks.

**Choice:** Each entity service exports plain async functions (not classes). The `apiClient` handles base URL, credentials, JSON serialization, and error responses.

**Rationale:** Simple functions are easier to test, tree-shake, and compose. No need for class ceremony for stateless HTTP calls.

**Alternatives Rejected:**
1. Class-based services - Rejected because they add unnecessary boilerplate
2. Single monolithic API module - Rejected because it becomes unwieldy

**Consequences:**
- Each service file is small (~30-60 lines) and focused
- Easy to add new entity services later

---

### Decision 6: Remove lovable-tagger Plugin

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-11 |

**Context:** The `lovable-tagger` Vite plugin is specific to the Lovable platform. Since we're removing Supabase and taking ownership of the codebase, this dependency is no longer needed.

**Choice:** Remove `lovable-tagger` from `vite.config.ts` and `package.json`.

**Rationale:** Dead dependency with no value outside Lovable's platform.

---

### Decision 7: Property Naming Convention

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-11 |

**Context:** The existing hooks use `snake_case` property names (e.g., `expense_date`, `amount_limit`, `bill_name`). The API returns `camelCase` (e.g., `expenseDate`, `amountLimit`, `billName`) because ASP.NET Core's `System.Text.Json` serializer defaults to camelCase.

**Choice:** Change all TypeScript interfaces to use `camelCase` to match the API responses directly. Update component references accordingly.

**Rationale:** Using camelCase matches both the API output and TypeScript/JavaScript conventions. No mapping layer needed.

**Alternatives Rejected:**
1. Keep snake_case and add a mapper - Rejected because it adds unnecessary complexity
2. Configure API to return snake_case - Rejected because camelCase is the .NET convention

**Consequences:**
- All component props that reference entity fields need updating (e.g., `expense.expense_date` → `expense.expenseDate`)
- One-time migration but results in cleaner TypeScript code

---

## File Manifest

### Phase 1: Foundation (Services + Types + Auth)

| # | File | Action | Purpose | Dependencies |
|---|------|--------|---------|--------------|
| 1 | `app/src/services/types.ts` | Create | TypeScript interfaces matching API DTOs (camelCase) | None |
| 2 | `app/src/services/apiClient.ts` | Create | Base fetch wrapper: baseUrl, credentials, JSON, error handling | None |
| 3 | `app/src/services/authService.ts` | Create | register, login, logout, getMe | 1, 2 |
| 4 | `app/src/contexts/AuthContext.tsx` | Create | AuthProvider + useAuth hook (userId, user, isAuthenticated, login, logout) | 3 |

### Phase 2: Entity Services

| # | File | Action | Purpose | Dependencies |
|---|------|--------|---------|--------------|
| 5 | `app/src/services/expenseService.ts` | Create | Expenses CRUD | 1, 2 |
| 6 | `app/src/services/earningService.ts` | Create | Earnings CRUD | 1, 2 |
| 7 | `app/src/services/budgetService.ts` | Create | Budgets + BudgetSpendings CRUD | 1, 2 |
| 8 | `app/src/services/billService.ts` | Create | Bills + BillPayments CRUD | 1, 2 |
| 9 | `app/src/services/goalService.ts` | Create | Goals CRUD | 1, 2 |
| 10 | `app/src/services/investmentService.ts` | Create | Investments CRUD | 1, 2 |

### Phase 3: Hook Rewiring

| # | File | Action | Purpose | Dependencies |
|---|------|--------|---------|--------------|
| 11 | `app/src/hooks/useTransactions.tsx` | Modify | Replace Supabase → expenseService + earningService | 4, 5, 6 |
| 12 | `app/src/hooks/useBudgets.tsx` | Modify | Replace useState → budgetService | 4, 7 |
| 13 | `app/src/hooks/useBills.tsx` | Modify | Replace useState → billService | 4, 8 |
| 14 | `app/src/hooks/useGoals.tsx` | Modify | Replace useState → goalService | 4, 9 |
| 15 | `app/src/hooks/useInvestments.tsx` | Modify | Replace useState → investmentService | 4, 10 |

### Phase 4: Pages + Routing

| # | File | Action | Purpose | Dependencies |
|---|------|--------|---------|--------------|
| 16 | `app/src/pages/Login.tsx` | Create | Login form (email + password) | 4 |
| 17 | `app/src/pages/Register.tsx` | Create | Register form (username, email, phone, password) | 4 |
| 18 | `app/src/pages/Index.tsx` | Modify | Remove Chat tab, compute stats from API data | 4, 11 |
| 19 | `app/src/components/finance/Header.tsx` | Modify | Wire logout + show real user info | 4 |
| 20 | `app/src/App.tsx` | Modify | Add AuthProvider, login/register routes, auth guard | 4, 16, 17 |

### Phase 5: Cleanup + Config

| # | File | Action | Purpose | Dependencies |
|---|------|--------|---------|--------------|
| 21 | `app/vite.config.ts` | Modify | Port 8080→5173, remove lovable-tagger | None |
| 22 | `app/package.json` | Modify | Remove @supabase/supabase-js, lovable-tagger | None |
| 23 | `app/src/integrations/supabase/` | Delete | Remove entire directory | None |
| 24 | `app/src/components/chat/` | Delete | Remove entire directory (6 files) | None |
| 25 | `app/src/hooks/useAIChat.tsx` | Delete | Remove AI chat hook | None |
| 26 | `app/supabase/` | Delete | Remove entire directory (config, migrations, edge functions) | None |

### Phase 6: Component Updates (camelCase + number IDs)

| # | File | Action | Purpose | Dependencies |
|---|------|--------|---------|--------------|
| 27 | `app/src/components/finance/BudgetCard.tsx` | Modify | Update prop types: string→number IDs, snake_case→camelCase | 1 |
| 28 | `app/src/components/finance/BudgetDialog.tsx` | Modify | Update form field names to camelCase | 1 |
| 29 | `app/src/components/finance/BudgetHistoryDialog.tsx` | Modify | Update prop types | 1 |
| 30 | `app/src/components/finance/AddSpendingDialog.tsx` | Modify | Update prop types | 1 |
| 31 | `app/src/components/finance/BillCard.tsx` | Modify | Update prop types: string→number IDs, snake_case→camelCase | 1 |
| 32 | `app/src/components/finance/BillDialog.tsx` | Modify | Update form field names | 1 |
| 33 | `app/src/components/finance/PaymentDialog.tsx` | Modify | Update prop types | 1 |
| 34 | `app/src/components/finance/PaymentHistoryDialog.tsx` | Modify | Update prop types | 1 |
| 35 | `app/src/components/finance/GoalCard.tsx` | Modify | Update prop types | 1 |
| 36 | `app/src/components/finance/GoalDialog.tsx` | Modify | Update form field names | 1 |
| 37 | `app/src/components/finance/AddProgressDialog.tsx` | Modify | Update prop types | 1 |
| 38 | `app/src/components/finance/InvestmentCard.tsx` | Modify | Update prop types | 1 |
| 39 | `app/src/components/finance/InvestmentDialog.tsx` | Modify | Update form field names | 1 |
| 40 | `app/src/components/finance/UpdateValueDialog.tsx` | Modify | Update prop types | 1 |
| 41 | `app/src/components/finance/TransactionList.tsx` | Modify | Update prop types | 1 |
| 42 | `app/src/components/finance/TransactionDialog.tsx` | Modify | Update form field names | 1 |
| 43 | `app/src/components/finance/StatCard.tsx` | Modify | Accept dynamic values (if needed) | None |
| 44 | `app/src/components/finance/ExpenseChart.tsx` | Modify | Accept data props instead of hardcoded data | 11 |

**Total Files:** 44 (12 create, 18 modify, 14 delete [within 4 directories])

---

## Code Patterns

### Pattern 1: API Client (Base Fetch Wrapper)

```typescript
// src/services/apiClient.ts

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5062/api';

interface ApiError {
  message: string;
  status: number;
}

class ApiClientError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = 'ApiClientError';
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const config: RequestInit = {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }));
    throw new ApiClientError(error.message || `HTTP ${response.status}`, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

export const apiClient = {
  get: <T>(endpoint: string) => request<T>(endpoint),
  post: <T>(endpoint: string, body: unknown) =>
    request<T>(endpoint, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(endpoint: string, body: unknown) =>
    request<T>(endpoint, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(endpoint: string) =>
    request<T>(endpoint, { method: 'DELETE' }),
};

export { ApiClientError };
```

### Pattern 2: Entity Service

```typescript
// src/services/expenseService.ts
import { apiClient } from './apiClient';
import type { ExpenseResponse, CreateExpenseRequest, UpdateExpenseRequest } from './types';

const basePath = (userId: number) => `/users/${userId}/expenses`;

export const expenseService = {
  list: (userId: number, params?: { startDate?: string; endDate?: string; category?: string }) => {
    const query = new URLSearchParams();
    if (params?.startDate) query.set('start_date', params.startDate);
    if (params?.endDate) query.set('end_date', params.endDate);
    if (params?.category) query.set('category', params.category);
    const qs = query.toString();
    return apiClient.get<ExpenseResponse[]>(`${basePath(userId)}${qs ? `?${qs}` : ''}`);
  },
  create: (userId: number, data: CreateExpenseRequest) =>
    apiClient.post<ExpenseResponse>(basePath(userId), data),
  update: (userId: number, id: number, data: UpdateExpenseRequest) =>
    apiClient.put<ExpenseResponse>(`${basePath(userId)}/${id}`, data),
  delete: (userId: number, id: number) =>
    apiClient.delete<void>(`${basePath(userId)}/${id}`),
};
```

### Pattern 3: Auth Context

```typescript
// src/contexts/AuthContext.tsx
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authService } from '@/services/authService';
import type { UserInfo } from '@/services/types';

interface AuthContextType {
  user: UserInfo | null;
  userId: number | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore session on mount
  useEffect(() => {
    authService.getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await authService.login({ email, password });
    const me = await authService.getMe();
    setUser(me);
  }, []);

  const logout = useCallback(async () => {
    await authService.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      userId: user?.id ?? null,
      isAuthenticated: !!user,
      isLoading,
      login,
      register,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
```

### Pattern 4: Hook Rewiring (Example: useGoals)

```typescript
// src/hooks/useGoals.tsx - AFTER migration
import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { goalService } from '@/services/goalService';
import type { GoalResponse } from '@/services/types';

export interface GoalFormData {
  name: string;
  description?: string;
  targetAmount: number;
  currentAmount: number;
  dueDate: string;
}

export function useGoals() {
  const { userId } = useAuth();
  const [goals, setGoals] = useState<GoalResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchGoals = useCallback(async () => {
    if (!userId) return;
    try {
      const data = await goalService.list(userId);
      setGoals(data);
    } catch (error: any) {
      console.error('Error fetching goals:', error);
    } finally {
      setIsLoading(false);
    }
  }, [userId]);

  useEffect(() => { fetchGoals(); }, [fetchGoals]);

  const addGoal = useCallback(async (data: GoalFormData) => {
    if (!userId) return false;
    try {
      await goalService.create(userId, {
        name: data.name,
        description: data.description,
        targetAmount: data.targetAmount,
        currentAmount: data.currentAmount,
        currencyCode: 'BRL',
        dueDate: data.dueDate,
      });
      toast.success('Meta criada com sucesso');
      await fetchGoals();
      return true;
    } catch (error: any) {
      toast.error(error.message);
      return false;
    }
  }, [userId, fetchGoals]);

  const updateGoal = useCallback(async (id: number, data: GoalFormData) => {
    if (!userId) return false;
    try {
      await goalService.update(userId, id, {
        name: data.name,
        description: data.description,
        targetAmount: data.targetAmount,
        currentAmount: data.currentAmount,
        dueDate: data.dueDate,
      });
      toast.success('Meta atualizada com sucesso');
      await fetchGoals();
      return true;
    } catch (error: any) {
      toast.error(error.message);
      return false;
    }
  }, [userId, fetchGoals]);

  const deleteGoal = useCallback(async (id: number) => {
    if (!userId) return false;
    try {
      await goalService.delete(userId, id);
      toast.success('Meta removida com sucesso');
      await fetchGoals();
      return true;
    } catch (error: any) {
      toast.error(error.message);
      return false;
    }
  }, [userId, fetchGoals]);

  const addProgress = useCallback(async (id: number, amount: number) => {
    if (!userId) return false;
    const goal = goals.find(g => g.id === id);
    if (!goal) return false;
    const newAmount = Math.min(goal.currentAmount + amount, goal.targetAmount);
    try {
      await goalService.update(userId, id, { currentAmount: newAmount });
      toast.success('Progresso adicionado com sucesso');
      await fetchGoals();
      return true;
    } catch (error: any) {
      toast.error(error.message);
      return false;
    }
  }, [userId, goals, fetchGoals]);

  return { goals, isLoading, addGoal, updateGoal, deleteGoal, addProgress, refetch: fetchGoals };
}
```

### Pattern 5: Auth Guard in App.tsx

```typescript
// Route protection pattern
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <div className="min-h-screen flex items-center justify-center">Loading...</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

// In routes:
<Route path="/" element={<ProtectedRoute><Index /></ProtectedRoute>} />
<Route path="/login" element={<Login />} />
<Route path="/register" element={<Register />} />
```

### Pattern 6: Login Page

```typescript
// src/pages/Login.tsx
// Simple form using existing shadcn/ui components (Input, Button, Card)
// On submit: call useAuth().login(email, password)
// On success: navigate('/')
// Link to /register for new users
// Language: Portuguese (matching existing UI)
```

### Pattern 7: Dashboard Stats (Computed)

```typescript
// In Index.tsx, replace hardcoded stats:
const totalEarnings = earnings.reduce((sum, e) => sum + e.amount, 0);
const totalExpenses = expenses.reduce((sum, e) => sum + e.amount, 0);
const balance = totalEarnings - totalExpenses;
const savingsRate = totalEarnings > 0 ? ((totalEarnings - totalExpenses) / totalEarnings * 100) : 0;

// Format for display:
const formatCurrency = (value: number) =>
  `R$ ${value.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
```

---

## Data Flow

```text
1. App Mount
   │
   ├── AuthProvider calls GET /api/auth/me
   │   ├── 200 OK → Set user state, render dashboard
   │   └── 401    → Set user null, redirect to /login
   │
2. User Login (POST /api/auth/login)
   │
   ├── API sets access_token cookie (HttpOnly, Secure, SameSite=None)
   ├── Call GET /api/auth/me → Get user info
   └── Navigate to dashboard
   │
3. Dashboard Mount (Index.tsx)
   │
   ├── Each hook calls its service.list(userId) on mount
   │   ├── useTransactions → expenseService.list + earningService.list
   │   ├── useBudgets → budgetService.list
   │   ├── useBills → billService.list
   │   ├── useGoals → goalService.list
   │   └── useInvestments → investmentService.list
   │
   └── Stats computed from expenses + earnings arrays
   │
4. User Creates/Updates/Deletes Entity
   │
   ├── Hook calls service.create/update/delete(userId, data)
   ├── Service calls apiClient.post/put/delete
   ├── On success → toast + refetch list
   └── On error → toast error message
   │
5. User Logout (POST /api/auth/logout)
   │
   ├── API clears access_token cookie
   ├── Clear user state
   └── Navigate to /login
```

---

## Integration Points

| External System | Integration Type | Authentication |
|-----------------|-----------------|----------------|
| FinPulse .NET API | REST API (fetch) | JWT in HttpOnly cookie (auto-sent via `credentials: 'include'`) |

---

## Testing Strategy

| Test Type | Scope | Method | Coverage Goal |
|-----------|-------|--------|---------------|
| Manual E2E | Full auth flow | Register → Login → CRUD all tabs → Logout | All acceptance tests (AT-001 to AT-018) |
| Build Verification | Compilation | `npm run build` succeeds with zero errors | 100% compile pass |
| API Integration | Cookie + CORS | Test from browser dev tools network tab | Cookie set/sent correctly |

**Note:** Automated tests are out of scope for this integration. Focus is on getting the app working end-to-end with the API. Tests can be added later.

---

## Error Handling

| Error Type | Handling Strategy | Retry? |
|------------|-------------------|--------|
| 401 Unauthorized | Redirect to /login (session expired) | No |
| 403 Forbidden | Toast error "Access denied" | No |
| 404 Not Found | Toast error "Resource not found" | No |
| 400 Bad Request | Toast with API error message | No |
| Network Error | Toast "Connection error. Check if API is running." | No |
| 5xx Server Error | Toast "Server error. Please try again." | No |

The `apiClient` throws `ApiClientError` with status code. Hooks catch errors and show toasts. The `AuthContext` listens for 401s on `/api/auth/me` to detect session expiry.

---

## Configuration

| Config Key | Type | Default | Description |
|------------|------|---------|-------------|
| `VITE_API_URL` | string | `http://localhost:5062/api` | Base URL for the FinPulse API |

Single env variable. The API port should match whatever the .NET API runs on locally.

---

## Security Considerations

- JWT stored in HttpOnly cookie - not accessible to JavaScript (XSS-safe)
- `credentials: 'include'` on every fetch - cookie sent automatically
- `SameSite: None` + `Secure: true` - requires HTTPS (or localhost exception)
- No tokens stored in localStorage or sessionStorage
- API enforces ownership checks (userId in route must match JWT claim)
- CORS restricted to specific origins

---

## Build Order (Recommended Execution Sequence)

The build should execute in this order to minimize broken states:

```text
Step 1: Create services/types.ts + services/apiClient.ts
Step 2: Create services/authService.ts + contexts/AuthContext.tsx
Step 3: Create pages/Login.tsx + pages/Register.tsx
Step 4: Modify App.tsx (add AuthProvider, routes, guard)
Step 5: Modify vite.config.ts (port + remove lovable-tagger)
Step 6: Create all entity services (5-10)
Step 7: Rewire all hooks (11-15)
Step 8: Update all components for camelCase + number IDs (27-44)
Step 9: Modify Index.tsx (remove chat tab, dynamic stats) (18)
Step 10: Modify Header.tsx (wire auth) (19)
Step 11: Delete Supabase files + Chat files (23-26)
Step 12: Update package.json (remove deps) (22)
Step 13: npm install + npm run build (verify)
```

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-11 | design-agent | Initial version |

---

## Next Step

**Ready for:** `/build .claude/sdd/features/DESIGN_API_INTEGRATION.md`
