# BRAINSTORM: Full API-App Integration

> **Feature:** Complete integration between FinPulse API and React App
> **Date:** 2026-02-01
> **Status:** Ready for /define

---

## 1. Problem Statement

The FinPulse platform has a fully functional ASP.NET Core 8 API and a beautiful React + Vite frontend, but they are **not connected**. The app's hooks (`useBudgets`, `useBills`, `useGoals`, `useInvestments`) generate mock data locally instead of calling the real API endpoints.

**Current State:**
- Bot → API: ✅ Working (Python clients call endpoints)
- App → API: ❌ Missing (hooks use local mock data)

**Goal:** Full integration in one pass - authentication, all CRUD operations, error handling.

---

## 2. Discovery Summary

### Questions Asked & Answers

| # | Question | Answer |
|---|----------|--------|
| 1 | What to integrate first? | **(d) All at once** - Complete integration in one pass |
| 2 | Auth token storage? | **(b) httpOnly cookies** - More secure, API sets cookie |
| 3 | API base URL strategy? | **(c) Environment-based** - `VITE_API_URL` in .env |
| 4 | API integration pattern? | **(b) Centralized API client** - Single `apiClient.ts` |
| 5 | Loading/error states? | **(d) Combination** - Local loading + global toast errors |
| 6 | API response samples? | **(b) From DTOs** - Derive TypeScript from C# classes |
| 7 | Include API changes? | **(a) Yes** - Full integration, both sides |

### Key Decisions
- **httpOnly cookies** for JWT storage (requires API CORS changes)
- **Centralized API client** pattern (not React Query)
- **Environment-based** API URL configuration
- **Both API and App** changes in scope

---

## 3. Samples & Ground Truth

### C# DTOs (Source of Truth)

**Auth DTOs:**
```csharp
public class LoginRequest { Email, Password }
public class LoginResponse { AccessToken, UserId }
public class RegisterRequest { Username, PhoneNumber, Email, Password }
```

**Entity DTOs (same pattern for all):**
```csharp
// Expenses, Earnings, Budgets, Bills, Goals, Investments
public class Create{Entity}Request { ... required fields ... }
public class Update{Entity}Request { ... optional fields ... }
public class {Entity}Response { Id, UserId, ... entity fields ... }
```

### API Endpoints Pattern
```
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/logout
GET    /api/users/{userId}/expenses
POST   /api/users/{userId}/expenses
PUT    /api/users/{userId}/expenses/{id}
DELETE /api/users/{userId}/expenses/{id}
// Same pattern for: earnings, budgets, bills, goals, investments
```

---

## 4. Selected Approach

### Approach A: Layered Integration ⭐ SELECTED

**App Structure:**
```
app/src/
├── api/
│   ├── client.ts           # Centralized fetch wrapper with credentials
│   ├── auth.ts             # login, register, logout
│   ├── expenses.ts         # expense CRUD
│   ├── earnings.ts         # earning CRUD
│   ├── budgets.ts          # budget CRUD
│   ├── bills.ts            # bill CRUD
│   ├── goals.ts            # goal CRUD
│   └── investments.ts      # investment CRUD
├── types/
│   └── api.ts              # TypeScript interfaces from C# DTOs
├── contexts/
│   └── AuthContext.tsx     # User state, login/logout methods
├── hooks/
│   └── use*.tsx            # Refactored to call api/* layer
├── pages/
│   ├── Login.tsx           # New login page
│   └── Register.tsx        # New register page
└── components/
    └── ProtectedRoute.tsx  # Route guard for auth
```

**API Changes:**
```
api/FinPulse.Api/
├── Program.cs              # Add CORS policy, cookie config
├── Controllers/
│   └── AuthController.cs   # Set httpOnly cookie on login
└── Extensions/
    └── CookieAuthExtensions.cs  # Cookie helper methods
```

### Why This Approach

| Benefit | Description |
|---------|-------------|
| **Separation of concerns** | API layer → Hooks → Components |
| **Type safety** | TypeScript interfaces match C# DTOs |
| **Testability** | Each layer can be tested independently |
| **Security** | httpOnly cookies prevent XSS token theft |
| **Maintainability** | Single place for auth/error handling |

### Alternatives Considered

| Approach | Why Not Selected |
|----------|------------------|
| **Hooks-only** | Mixes concerns, duplicates fetch logic |
| **React Query** | User chose manual control, adds complexity |
| **localStorage tokens** | Less secure than httpOnly cookies |

---

## 5. YAGNI Applied

### Features Removed from Scope

| Feature | Reason for Removal |
|---------|-------------------|
| **Supabase integration** | Not needed - using C# API backend |
| **AI Chat backend** | Defer - focus on core CRUD first |
| **Investment market data** | Defer - requires external APIs |
| **Budget spending tracking** | Keep - API supports it |

### MVP Scope (In)
- [x] Authentication (login, register, logout)
- [x] Expenses CRUD
- [x] Earnings CRUD
- [x] Budgets CRUD
- [x] Bills CRUD
- [x] Goals CRUD
- [x] Investments CRUD (basic, no market data)
- [x] Toast notifications for errors
- [x] Loading states per component
- [x] Protected routes

### Deferred (Out)
- [ ] AI Chat integration
- [ ] Real-time market data
- [ ] Push notifications
- [ ] Offline mode

---

## 6. Draft Requirements

### Functional Requirements

**FR-1: Authentication**
- User can register with username, email, phone, password
- User can login with email/password
- JWT stored as httpOnly cookie (set by API)
- User can logout (cookie cleared)
- Protected routes redirect to login if not authenticated

**FR-2: Expenses**
- User can view list of expenses (filtered by date)
- User can add new expense (amount, category, payment method, date)
- User can edit existing expense
- User can delete expense

**FR-3: Earnings**
- User can view list of earnings
- User can add/edit/delete earnings

**FR-4: Budgets**
- User can create budgets with amount limits
- User can view active budgets
- User can update/delete budgets

**FR-5: Bills**
- User can track recurring bills
- User can mark bills as paid
- User can view payment history

**FR-6: Goals**
- User can create savings goals
- User can add progress toward goals
- User can view goal progress

**FR-7: Investments**
- User can track investments (name, type, amount)
- User can update current values
- User can delete investments

### Non-Functional Requirements

**NFR-1: Security**
- httpOnly cookies for JWT (XSS protection)
- CORS configured for app origin only
- API validates user owns resource (403 if not)

**NFR-2: UX**
- Loading spinners during API calls
- Toast notifications for errors
- Optimistic UI updates where appropriate

**NFR-3: Configuration**
- `VITE_API_URL` environment variable
- `.env.development` and `.env.production` files

---

## 7. Implementation Phases

### Phase 1: Foundation
1. Create TypeScript types from C# DTOs
2. Create centralized API client (`api/client.ts`)
3. Update API with CORS + cookie authentication
4. Create AuthContext provider

### Phase 2: Authentication
5. Create Login page
6. Create Register page
7. Create ProtectedRoute component
8. Wire up auth flow end-to-end

### Phase 3: Core CRUD
9. Refactor `useExpenses` hook
10. Refactor `useEarnings` hook
11. Refactor `useBudgets` hook
12. Refactor `useBills` hook
13. Refactor `useGoals` hook
14. Refactor `useInvestments` hook

### Phase 4: Polish
15. Add toast notifications for errors
16. Add loading states to all components
17. Test full integration
18. Clean up unused mock data code

---

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CORS misconfiguration | Medium | High | Test with browser DevTools, document exact config |
| Cookie not sent cross-origin | Medium | High | Ensure `credentials: 'include'` and proper SameSite |
| Type mismatches | Low | Medium | Generate types from DTOs, validate with tests |
| Auth state lost on refresh | Low | Medium | API validates cookie on each request |

---

## 9. Open Questions

None remaining - all clarified during brainstorming.

---

## 10. Next Steps

```bash
/define .claude/sdd/features/BRAINSTORM_API_APP_INTEGRATION.md
```

This will generate the formal requirements document with acceptance criteria.

---

## Appendix: Technology Stack Reference

| Layer | Technology | Version |
|-------|-----------|---------|
| **API** | ASP.NET Core | 8.0 |
| **API Auth** | JWT Bearer + Cookies | - |
| **API ORM** | Entity Framework Core | 8.0.11 |
| **App** | React + Vite | 18.3 / 5.4 |
| **App State** | React Context + Hooks | - |
| **App Styling** | Tailwind + shadcn/ui | 3.4 |
| **App Forms** | React Hook Form + Zod | 7.61 |
| **Database** | SQL Server | - |
