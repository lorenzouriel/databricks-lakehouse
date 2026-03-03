# DESIGN: Full API-App Integration

> Technical design for connecting React frontend to ASP.NET Core API with httpOnly cookie authentication

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | API_APP_INTEGRATION |
| **Date** | 2026-02-01 |
| **Author** | design-agent |
| **DEFINE** | [DEFINE_API_APP_INTEGRATION.md](./DEFINE_API_APP_INTEGRATION.md) |
| **Status** | Ready for Build |

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FINPULSE INTEGRATION                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         REACT APP (Vite)                             │    │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐       │    │
│  │  │  Pages   │───▶│  Hooks   │───▶│ API Layer│───▶│  Client  │       │    │
│  │  │Login/Reg │    │useBudgets│    │budgets.ts│    │client.ts │       │    │
│  │  │Dashboard │    │useBills  │    │bills.ts  │    │          │       │    │
│  │  └──────────┘    │useGoals  │    │goals.ts  │    │credentials│      │    │
│  │       │          │...       │    │...       │    │:'include'│       │    │
│  │       ▼          └──────────┘    └──────────┘    └────┬─────┘       │    │
│  │  ┌──────────┐         │                               │              │    │
│  │  │  Auth    │◀────────┘                               │              │    │
│  │  │ Context  │ userId, isAuthenticated                 │              │    │
│  │  └──────────┘                                         │              │    │
│  └───────────────────────────────────────────────────────┼──────────────┘    │
│                                                          │                   │
│                        HTTPS + httpOnly Cookie           │                   │
│                                                          ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      ASP.NET CORE 8 API                              │    │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐       │    │
│  │  │  CORS    │───▶│  Auth    │───▶│Controllers│───▶│ Services │       │    │
│  │  │Middleware│    │Middleware│    │ + Cookie  │    │          │       │    │
│  │  │          │    │JWT Valid │    │  Setting  │    │          │       │    │
│  │  └──────────┘    └──────────┘    └──────────┘    └────┬─────┘       │    │
│  │                                                       │              │    │
│  │                                                       ▼              │    │
│  │                                              ┌──────────────┐        │    │
│  │                                              │ EF Core +    │        │    │
│  │                                              │ SQL Server   │        │    │
│  │                                              └──────────────┘        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **API Client** | Centralized fetch wrapper with credentials | TypeScript + fetch |
| **Auth Context** | Global user state, login/logout methods | React Context |
| **API Layer** | Entity-specific CRUD functions | TypeScript modules |
| **Type Definitions** | TypeScript interfaces from C# DTOs | TypeScript |
| **Protected Route** | Route guard for authenticated pages | React Router |
| **Login/Register** | Authentication pages | React + React Hook Form |
| **CORS Middleware** | Allow cross-origin requests with credentials | ASP.NET Core |
| **Cookie Auth** | Set httpOnly cookie on login | ASP.NET Core |

---

## Key Decisions

### Decision 1: httpOnly Cookie Authentication

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-01 |

**Context:** Need secure JWT storage that prevents XSS attacks from stealing tokens.

**Choice:** Store JWT in httpOnly cookie set by the API, not in localStorage.

**Rationale:** httpOnly cookies cannot be accessed by JavaScript, preventing XSS token theft. The browser automatically sends the cookie with requests.

**Alternatives Rejected:**
1. **localStorage** - Rejected because vulnerable to XSS attacks
2. **sessionStorage** - Rejected because same XSS vulnerability, also loses state on tab close
3. **In-memory only** - Rejected because user must re-login on every page refresh

**Consequences:**
- API must set cookie with proper SameSite and Secure flags
- App must use `credentials: 'include'` on all fetch requests
- CORS must be configured to allow credentials

---

### Decision 2: Centralized API Client Pattern

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-01 |

**Context:** Need consistent error handling, auth headers, and base URL across all API calls.

**Choice:** Single `client.ts` with typed methods that all entity modules use.

**Rationale:** DRY principle - error handling, toast notifications, and credentials are configured once.

**Alternatives Rejected:**
1. **Inline fetch in hooks** - Rejected because duplicates error handling logic
2. **React Query** - Rejected because user wants manual control, adds complexity
3. **Axios** - Rejected because fetch is sufficient, no need for extra dependency

**Consequences:**
- All API calls go through single client
- Global error toast on 4xx/5xx
- Easy to add request/response interceptors later

---

### Decision 3: Environment-based API URL

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-01 |

**Context:** API runs on different URLs in development vs production.

**Choice:** Use `VITE_API_URL` environment variable loaded from `.env` files.

**Rationale:** Standard Vite pattern, no code changes needed for deployment.

**Alternatives Rejected:**
1. **Hardcoded URLs** - Rejected because requires code changes per environment
2. **Vite proxy** - Rejected because user prefers explicit environment config
3. **Runtime config fetch** - Rejected because adds complexity and latency

**Consequences:**
- Must create `.env.development` and `.env.production` files
- API URL accessed via `import.meta.env.VITE_API_URL`

---

### Decision 4: Preserve Existing Hook Interface

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-01 |

**Context:** Existing hooks return `{ budgets, isLoading, addBudget, updateBudget, deleteBudget, ... }`.

**Choice:** Keep the same interface, replace mock implementations with API calls.

**Rationale:** Zero changes to components that consume hooks. Seamless migration.

**Alternatives Rejected:**
1. **New hook names** - Rejected because requires changing all component imports
2. **Different return shape** - Rejected because breaks existing component code

**Consequences:**
- Components work without modification
- Hooks now have real `isLoading` states
- Hooks need `userId` from AuthContext

---

## File Manifest

| # | File | Action | Purpose | Dependencies |
|---|------|--------|---------|--------------|
| **API Side** |
| 1 | `api/FinPulse.Api/Program.cs` | Modify | Add CORS policy + cookie config | None |
| 2 | `api/FinPulse.Api/Controllers/AuthController.cs` | Modify | Set httpOnly cookie on login | 1 |
| **App Side - Foundation** |
| 3 | `app/.env.development` | Create | Dev API URL | None |
| 4 | `app/.env.production` | Create | Prod API URL | None |
| 5 | `app/src/types/api.ts` | Create | TypeScript interfaces from DTOs | None |
| 6 | `app/src/api/client.ts` | Create | Centralized fetch with credentials | 3, 5 |
| **App Side - Auth** |
| 7 | `app/src/api/auth.ts` | Create | Login, register, logout, me | 6 |
| 8 | `app/src/contexts/AuthContext.tsx` | Create | User state + auth methods | 7 |
| 9 | `app/src/components/ProtectedRoute.tsx` | Create | Route guard | 8 |
| 10 | `app/src/pages/Login.tsx` | Create | Login page | 7, 8 |
| 11 | `app/src/pages/Register.tsx` | Create | Register page | 7 |
| **App Side - API Layer** |
| 12 | `app/src/api/expenses.ts` | Create | Expense CRUD | 6 |
| 13 | `app/src/api/earnings.ts` | Create | Earning CRUD | 6 |
| 14 | `app/src/api/budgets.ts` | Create | Budget CRUD | 6 |
| 15 | `app/src/api/bills.ts` | Create | Bill CRUD | 6 |
| 16 | `app/src/api/goals.ts` | Create | Goal CRUD | 6 |
| 17 | `app/src/api/investments.ts` | Create | Investment CRUD | 6 |
| **App Side - Hooks** |
| 18 | `app/src/hooks/useExpenses.tsx` | Create | Expense hook with API | 8, 12 |
| 19 | `app/src/hooks/useEarnings.tsx` | Create | Earning hook with API | 8, 13 |
| 20 | `app/src/hooks/useBudgets.tsx` | Modify | Replace mock with API | 8, 14 |
| 21 | `app/src/hooks/useBills.tsx` | Modify | Replace mock with API | 8, 15 |
| 22 | `app/src/hooks/useGoals.tsx` | Modify | Replace mock with API | 8, 16 |
| 23 | `app/src/hooks/useInvestments.tsx` | Modify | Replace mock with API | 8, 17 |
| **App Side - Routing** |
| 24 | `app/src/App.tsx` | Modify | Add AuthProvider, new routes | 8, 9, 10, 11 |

**Total Files:** 24 (2 API, 22 App)

---

## Code Patterns

### Pattern 1: API Client with Credentials

```typescript
// app/src/api/client.ts
import { toast } from 'sonner';

const API_URL = import.meta.env.VITE_API_URL;

export interface ApiError {
  message: string;
  errors?: Record<string, string[]>;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    credentials: 'include', // Send cookies
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      message: 'Something went wrong'
    }));

    // Show toast for errors
    toast.error(error.message || `Error: ${response.status}`);

    throw new Error(error.message);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// Convenience methods
export const api = {
  get: <T>(endpoint: string) => apiClient<T>(endpoint),

  post: <T>(endpoint: string, data: unknown) =>
    apiClient<T>(endpoint, { method: 'POST', body: JSON.stringify(data) }),

  put: <T>(endpoint: string, data: unknown) =>
    apiClient<T>(endpoint, { method: 'PUT', body: JSON.stringify(data) }),

  delete: <T>(endpoint: string) =>
    apiClient<T>(endpoint, { method: 'DELETE' }),
};
```

### Pattern 2: Auth Context

```typescript
// app/src/contexts/AuthContext.tsx
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authApi, LoginRequest, RegisterRequest } from '@/api/auth';

interface User {
  id: number;
  email: string;
  username: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginRequest) => Promise<boolean>;
  register: (data: RegisterRequest) => Promise<boolean>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check auth status on mount
  useEffect(() => {
    authApi.me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  const login = async (data: LoginRequest): Promise<boolean> => {
    try {
      const response = await authApi.login(data);
      setUser({ id: response.userId, email: data.email, username: '' });
      return true;
    } catch {
      return false;
    }
  };

  const register = async (data: RegisterRequest): Promise<boolean> => {
    try {
      await authApi.register(data);
      return true;
    } catch {
      return false;
    }
  };

  const logout = async () => {
    await authApi.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      register,
      logout
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
```

### Pattern 3: Entity API Module

```typescript
// app/src/api/budgets.ts
import { api } from './client';
import type {
  BudgetResponse,
  CreateBudgetRequest,
  UpdateBudgetRequest
} from '@/types/api';

export const budgetsApi = {
  getAll: (userId: number) =>
    api.get<BudgetResponse[]>(`/api/users/${userId}/budgets`),

  create: (userId: number, data: CreateBudgetRequest) =>
    api.post<BudgetResponse>(`/api/users/${userId}/budgets`, data),

  update: (userId: number, budgetId: number, data: UpdateBudgetRequest) =>
    api.put<BudgetResponse>(`/api/users/${userId}/budgets/${budgetId}`, data),

  delete: (userId: number, budgetId: number) =>
    api.delete<void>(`/api/users/${userId}/budgets/${budgetId}`),
};
```

### Pattern 4: Hook with API Integration

```typescript
// app/src/hooks/useBudgets.tsx
import { useState, useCallback, useEffect } from 'react';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { budgetsApi } from '@/api/budgets';
import type { BudgetResponse, CreateBudgetRequest } from '@/types/api';

export function useBudgets() {
  const { user } = useAuth();
  const [budgets, setBudgets] = useState<BudgetResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchBudgets = useCallback(async () => {
    if (!user) return;
    setIsLoading(true);
    try {
      const data = await budgetsApi.getAll(user.id);
      setBudgets(data);
    } catch {
      // Error toast handled by client
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchBudgets();
  }, [fetchBudgets]);

  const addBudget = useCallback(async (data: CreateBudgetRequest) => {
    if (!user) return false;
    setIsLoading(true);
    try {
      const newBudget = await budgetsApi.create(user.id, data);
      setBudgets(prev => [newBudget, ...prev]);
      toast.success('Budget created successfully');
      return true;
    } catch {
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  // ... updateBudget, deleteBudget follow same pattern

  return { budgets, isLoading, addBudget, updateBudget, deleteBudget, refetch: fetchBudgets };
}
```

### Pattern 5: Protected Route

```typescript
// app/src/components/ProtectedRoute.tsx
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
```

### Pattern 6: ASP.NET CORS + Cookie Configuration

```csharp
// api/FinPulse.Api/Program.cs - Add after builder.Services.AddControllers()

// Configure CORS for React app
builder.Services.AddCors(options =>
{
    options.AddPolicy("ReactApp", policy =>
    {
        policy.WithOrigins(
            "http://localhost:5173",  // Vite dev server
            "https://finpulse.com"    // Production
        )
        .AllowAnyHeader()
        .AllowAnyMethod()
        .AllowCredentials();  // Required for cookies
    });
});

// In app configuration (after var app = builder.Build())
app.UseCors("ReactApp");
```

### Pattern 7: Set httpOnly Cookie on Login

```csharp
// api/FinPulse.Api/Controllers/AuthController.cs - Modified Login

[HttpPost("login")]
public async Task<IActionResult> Login([FromBody] LoginRequest request)
{
    var result = await _userService.LoginAsync(request);

    if (result == null)
    {
        return Unauthorized(new { message = "Invalid credentials" });
    }

    // Set httpOnly cookie
    Response.Cookies.Append("access_token", result.AccessToken, new CookieOptions
    {
        HttpOnly = true,
        Secure = true,  // HTTPS only in production
        SameSite = SameSiteMode.None,  // Cross-origin
        Expires = DateTimeOffset.UtcNow.AddDays(7)
    });

    return Ok(new { userId = result.UserId });
}

[HttpPost("logout")]
public IActionResult Logout()
{
    Response.Cookies.Delete("access_token");
    return Ok(new { message = "Logged out successfully" });
}
```

### Pattern 8: Read JWT from Cookie in Middleware

```csharp
// api/FinPulse.Api/Program.cs - Modify JWT configuration

.AddJwtBearer(options =>
{
    options.TokenValidationParameters = new TokenValidationParameters { /* existing */ };

    // Read token from cookie instead of Authorization header
    options.Events = new JwtBearerEvents
    {
        OnMessageReceived = context =>
        {
            context.Token = context.Request.Cookies["access_token"];
            return Task.CompletedTask;
        }
    };
});
```

---

## Data Flow

```text
1. User opens app
   │
   ├──[Not Authenticated]──▶ Redirect to /login
   │
   └──[Has Cookie]──▶ AuthContext calls /api/auth/me
                       │
                       ├──[Valid]──▶ Set user state, show dashboard
                       │
                       └──[Invalid/Expired]──▶ Clear cookie, redirect to /login

2. User performs CRUD action (e.g., Add Budget)
   │
   ▼
   Component calls hook method (e.g., addBudget)
   │
   ▼
   Hook sets isLoading=true
   │
   ▼
   Hook calls API layer (budgetsApi.create)
   │
   ▼
   API layer calls client (api.post with credentials:'include')
   │
   ▼
   Browser sends request with httpOnly cookie
   │
   ▼
   API validates JWT from cookie
   │
   ├──[401 Unauthorized]──▶ Client shows toast, hook returns false
   │
   └──[200 OK]──▶ Client returns data
                   │
                   ▼
                   Hook updates local state
                   │
                   ▼
                   Hook shows success toast
                   │
                   ▼
                   Hook sets isLoading=false
                   │
                   ▼
                   Component re-renders with new data
```

---

## Integration Points

| External System | Integration Type | Authentication |
|-----------------|-----------------|----------------|
| ASP.NET Core API | REST + httpOnly cookie | JWT in cookie |
| SQL Server | EF Core (API side) | Connection string |
| Sonner (Toast) | npm package | N/A |
| React Router | npm package | N/A |

---

## Testing Strategy

| Test Type | Scope | Files | Tools | Coverage Goal |
|-----------|-------|-------|-------|---------------|
| **Manual E2E** | Full auth flow | - | Browser | All AT-00x tests |
| **API Integration** | Endpoints | `*.http` | VS Code REST Client | Happy paths |
| **Component** | Hooks | Future | React Testing Library | Core hooks |

### Manual Test Checklist

```text
[ ] Register new user → redirects to login
[ ] Login with valid credentials → redirects to dashboard
[ ] Login with invalid credentials → shows error toast
[ ] Logout → redirects to login, cookie cleared
[ ] Access /dashboard without auth → redirects to login
[ ] Create budget → appears in list
[ ] Edit budget → changes reflected
[ ] Delete budget → removed from list
[ ] Network error → shows error toast
[ ] Refresh page while logged in → stays logged in
```

---

## Error Handling

| Error Type | Handling Strategy | Retry? |
|------------|-------------------|--------|
| **Network Error** | Toast: "Network error. Please try again." | No |
| **401 Unauthorized** | Redirect to /login | No |
| **403 Forbidden** | Toast: "Access denied" | No |
| **400 Validation** | Toast with validation message | No |
| **500 Server Error** | Toast: "Something went wrong" | No |

---

## Configuration

### App Environment Variables

| Config Key | Type | Default | Description |
|------------|------|---------|-------------|
| `VITE_API_URL` | string | `http://localhost:5000` | API base URL |

### API Configuration (appsettings.json)

| Config Key | Type | Description |
|------------|------|-------------|
| `Jwt:SecretKey` | string | JWT signing key |
| `Jwt:Issuer` | string | Token issuer |
| `Jwt:Audience` | string | Token audience |
| `ConnectionStrings:DefaultConnection` | string | SQL Server connection |

---

## Security Considerations

- **httpOnly cookies** prevent JavaScript access to tokens (XSS protection)
- **SameSite=None + Secure** required for cross-origin cookies
- **CORS whitelist** limits which origins can make requests
- **API validates userId** in route matches JWT claim (prevents accessing other users' data)
- **BCrypt password hashing** already in place
- **HTTPS required** in production for Secure cookies

---

## Observability

| Aspect | Implementation |
|--------|----------------|
| **Logging** | Browser console for client, ASP.NET Core ILogger for API |
| **Errors** | Toast notifications for user, console.error for devs |
| **Network** | Browser DevTools Network tab for debugging |

---

## Type Definitions Reference

```typescript
// app/src/types/api.ts

// Auth
export interface LoginRequest { email: string; password: string; }
export interface LoginResponse { userId: number; }
export interface RegisterRequest { username: string; phoneNumber: string; email: string; password: string; }
export interface RegisterResponse { userId: number; }

// Expense
export interface ExpenseResponse {
  id: number; userId: number; category: string; paymentMethod: string;
  currencyCode: string; amount: number; description?: string; expenseDate: string;
}
export interface CreateExpenseRequest {
  category: string; paymentMethod: string; currencyCode: string;
  amount: number; description?: string; expenseDate: string;
}
export interface UpdateExpenseRequest { /* all optional */ }

// Earning
export interface EarningResponse {
  id: number; userId: number; category: string; paymentMethod: string;
  currencyCode: string; amount: number; description?: string; earningDate: string;
}
export interface CreateEarningRequest { /* same fields as Expense */ }

// Budget
export interface BudgetResponse {
  id: number; userId: number; name: string; description?: string;
  amountLimit: number; currencyCode: string; startDate: string; endDate: string;
}
export interface CreateBudgetRequest {
  name: string; description?: string; amountLimit: number;
  currencyCode: string; startDate: string; endDate: string;
}

// Bill
export interface BillResponse {
  id: number; userId: number; billName: string; category: string;
  paymentMethod?: string; amount: number; currencyCode: string;
  dueDate: string; recurrenceType?: string; recurrenceInterval?: number;
  nextDueDate?: string; paidDate?: string; description?: string;
}
export interface CreateBillRequest { /* required fields */ }

// Goal
export interface GoalResponse {
  id: number; userId: number; name: string; description?: string;
  targetAmount: number; currentAmount: number; currencyCode: string; dueDate: string;
}
export interface CreateGoalRequest { /* required fields */ }

// Investment
export interface InvestmentResponse {
  id: number; userId: number; investmentType: string; category: string;
  assetName: string; broker?: string; currencyCode: string;
  investedAmount: number; currentValue?: number; purchaseDate: string;
  maturityDate?: string; annualYieldPercent?: number; profitLoss?: number;
}
export interface CreateInvestmentRequest { /* required fields */ }
```

---

## Build Order

Execute files in this order to satisfy dependencies:

```text
Phase 1: API Configuration
  1. Program.cs (CORS + Cookie middleware)
  2. AuthController.cs (Cookie setting)

Phase 2: App Foundation
  3. .env.development
  4. .env.production
  5. types/api.ts
  6. api/client.ts

Phase 3: App Authentication
  7. api/auth.ts
  8. contexts/AuthContext.tsx
  9. components/ProtectedRoute.tsx
  10. pages/Login.tsx
  11. pages/Register.tsx

Phase 4: App API Layer
  12. api/expenses.ts
  13. api/earnings.ts
  14. api/budgets.ts
  15. api/bills.ts
  16. api/goals.ts
  17. api/investments.ts

Phase 5: App Hooks
  18. hooks/useExpenses.tsx
  19. hooks/useEarnings.tsx
  20. hooks/useBudgets.tsx (modify)
  21. hooks/useBills.tsx (modify)
  22. hooks/useGoals.tsx (modify)
  23. hooks/useInvestments.tsx (modify)

Phase 6: App Routing
  24. App.tsx (integrate all)
```

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-01 | design-agent | Initial version |

---

## Next Step

**Ready for:** `/build .claude/sdd/features/DESIGN_API_APP_INTEGRATION.md`
