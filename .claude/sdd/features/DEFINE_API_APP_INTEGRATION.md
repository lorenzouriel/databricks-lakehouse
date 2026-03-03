# DEFINE: Full API-App Integration

> Connect the React frontend to the ASP.NET Core API with httpOnly cookie authentication and full CRUD for all financial entities.

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | API_APP_INTEGRATION |
| **Date** | 2026-02-01 |
| **Author** | define-agent |
| **Status** | Ready for Design |
| **Clarity Score** | 15/15 |
| **Source** | BRAINSTORM_API_APP_INTEGRATION.md |

---

## Problem Statement

The FinPulse platform has a fully functional ASP.NET Core 8 API and a polished React + Vite frontend, but they are **not connected**. The app's hooks (`useBudgets`, `useBills`, `useGoals`, `useInvestments`, `useExpenses`, `useEarnings`) generate mock data locally instead of calling the real API endpoints. Users cannot persist financial data, and authentication does not exist in the frontend.

---

## Target Users

| User | Role | Pain Point |
|------|------|------------|
| **App User** | Individual managing personal finances | Cannot save data - everything resets on refresh |
| **Developer** | Maintaining/extending the platform | Two disconnected systems, duplicated logic |

---

## Goals

| Priority | Goal |
|----------|------|
| **MUST** | User can register, login, and logout with credentials persisted securely |
| **MUST** | User can create, read, update, delete Expenses via the app |
| **MUST** | User can create, read, update, delete Earnings via the app |
| **MUST** | User can create, read, update, delete Budgets via the app |
| **MUST** | User can create, read, update, delete Bills via the app |
| **MUST** | User can create, read, update, delete Goals via the app |
| **MUST** | User can create, read, update, delete Investments via the app |
| **MUST** | All API calls use httpOnly cookie authentication (no localStorage tokens) |
| **MUST** | Unauthenticated users are redirected to login page |
| **SHOULD** | Toast notifications appear for API errors |
| **SHOULD** | Loading spinners display during API calls |
| **COULD** | Optimistic UI updates for better perceived performance |

---

## Success Criteria

Measurable outcomes:

- [ ] 100% of app hooks call real API endpoints (0 mock data generators remain)
- [ ] Authentication flow completes in < 2 seconds (register, login, logout)
- [ ] All 7 entity types (expenses, earnings, budgets, bills, goals, investments, users) have working CRUD
- [ ] JWT stored as httpOnly cookie (verified via browser DevTools - no token in localStorage/sessionStorage)
- [ ] CORS configured correctly - no browser console errors on cross-origin requests
- [ ] Protected routes redirect to /login within 100ms when unauthenticated
- [ ] API returns 401 for unauthenticated requests, 403 for unauthorized resource access

---

## Acceptance Tests

### Authentication

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-001 | Successful registration | User on /register page | User submits valid username, email, phone, password | Account created, redirected to /login, success toast shown |
| AT-002 | Registration with existing email | User on /register page | User submits email that already exists | Error toast: "Email already registered", stays on page |
| AT-003 | Successful login | User on /login page with valid account | User submits correct email/password | Cookie set, redirected to dashboard, user context populated |
| AT-004 | Login with wrong password | User on /login page | User submits incorrect password | Error toast: "Invalid credentials", stays on page |
| AT-005 | Logout | User is logged in | User clicks logout | Cookie cleared, redirected to /login, user context cleared |
| AT-006 | Protected route - unauthenticated | User is not logged in | User navigates to /dashboard | Redirected to /login |
| AT-007 | Protected route - authenticated | User is logged in | User navigates to /dashboard | Dashboard loads with user data |
| AT-008 | Session persistence | User is logged in, closes browser | User reopens browser, navigates to /dashboard | Still logged in (cookie valid) |

### Expenses

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-010 | View expenses | User is logged in | User navigates to expenses section | List of user's expenses from API displayed |
| AT-011 | Add expense | User is on expenses section | User fills form: amount=50, category=Food, date=today | Expense saved to API, appears in list, success toast |
| AT-012 | Edit expense | Expense exists in list | User clicks edit, changes amount to 75 | Expense updated in API, list reflects change |
| AT-013 | Delete expense | Expense exists in list | User clicks delete, confirms | Expense removed from API and list |
| AT-014 | View other user's expense | User A is logged in | API request for User B's expense | 403 Forbidden returned |

### Earnings

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-020 | View earnings | User is logged in | User navigates to earnings section | List of user's earnings from API displayed |
| AT-021 | Add earning | User is on earnings section | User fills form: amount=1000, category=Salary | Earning saved to API, appears in list |
| AT-022 | Edit earning | Earning exists | User edits amount | Earning updated in API |
| AT-023 | Delete earning | Earning exists | User deletes | Earning removed from API |

### Budgets

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-030 | View budgets | User is logged in | User navigates to budgets tab | List of user's budgets displayed |
| AT-031 | Create budget | User on budgets tab | User creates budget: name=Groceries, limit=500 | Budget saved to API, appears in list |
| AT-032 | Update budget | Budget exists | User edits limit to 600 | Budget updated in API |
| AT-033 | Delete budget | Budget exists | User deletes | Budget removed from API |

### Bills

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-040 | View bills | User is logged in | User navigates to bills tab | List of user's bills displayed |
| AT-041 | Create bill | User on bills tab | User creates bill: name=Rent, amount=1200, due=15th | Bill saved to API |
| AT-042 | Mark bill paid | Bill exists, unpaid | User marks as paid | Bill status updated, payment recorded |
| AT-043 | Delete bill | Bill exists | User deletes | Bill removed from API |

### Goals

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-050 | View goals | User is logged in | User navigates to goals tab | List of user's goals displayed |
| AT-051 | Create goal | User on goals tab | User creates: name=Vacation, target=5000, deadline=Dec | Goal saved to API |
| AT-052 | Add progress | Goal exists, current=1000 | User adds 500 progress | Goal updated: current=1500 |
| AT-053 | Delete goal | Goal exists | User deletes | Goal removed from API |

### Investments

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-060 | View investments | User is logged in | User navigates to investments tab | List of user's investments displayed |
| AT-061 | Create investment | User on investments tab | User creates: name=AAPL, type=stock, amount=1000 | Investment saved to API |
| AT-062 | Update value | Investment exists | User updates current value to 1200 | Investment updated in API |
| AT-063 | Delete investment | Investment exists | User deletes | Investment removed from API |

### Error Handling

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-070 | Network error | User performing any action | Network disconnects | Error toast: "Network error. Please try again." |
| AT-071 | Server error (500) | User performing any action | API returns 500 | Error toast: "Something went wrong. Please try again." |
| AT-072 | Validation error | User submitting form | API returns 400 with validation errors | Error toast with specific message |

---

## Out of Scope

Explicitly NOT included in this feature:

- **AI Chat integration** - Bot exists but app chat UI won't connect to it yet
- **Real-time market data** - Investment tracking is manual entry only
- **Supabase integration** - Removing; using C# API exclusively
- **Push notifications** - Future feature
- **Offline mode / PWA** - Future feature
- **Password reset** - Future feature
- **Email verification** - Future feature
- **Social login (OAuth)** - Future feature

---

## Constraints

| Type | Constraint | Impact |
|------|------------|--------|
| **Technical** | API already uses JWT Bearer auth | Must adapt to also support httpOnly cookies |
| **Technical** | App uses React Hook Form + Zod | Forms already structured, just need API wiring |
| **Technical** | API endpoints follow `/api/users/{userId}/*` pattern | App must store and use userId from auth context |
| **Security** | httpOnly cookies required | Cannot use localStorage; API must set cookie |
| **Browser** | Modern browsers only (no IE11) | Can use fetch with credentials, no polyfills |

---

## Technical Context

| Aspect | Value | Notes |
|--------|-------|-------|
| **App Deployment Location** | `app/src/` | React + Vite SPA |
| **API Deployment Location** | `api/FinPulse.Api/` | ASP.NET Core 8 |
| **KB Domains** | react, typescript, aspnetcore, jwt, cors | Patterns to consult |
| **IaC Impact** | None | No infrastructure changes, just code |

### File Structure (New/Modified)

**App (New Files):**
```
app/src/
├── api/
│   ├── client.ts           # NEW: Centralized fetch with credentials
│   ├── auth.ts             # NEW: login, register, logout
│   ├── expenses.ts         # NEW: expense CRUD
│   ├── earnings.ts         # NEW: earning CRUD
│   ├── budgets.ts          # NEW: budget CRUD
│   ├── bills.ts            # NEW: bill CRUD
│   ├── goals.ts            # NEW: goal CRUD
│   └── investments.ts      # NEW: investment CRUD
├── types/
│   └── api.ts              # NEW: TypeScript interfaces from DTOs
├── contexts/
│   └── AuthContext.tsx     # NEW: User state + auth methods
├── pages/
│   ├── Login.tsx           # NEW: Login page
│   └── Register.tsx        # NEW: Register page
├── components/
│   └── ProtectedRoute.tsx  # NEW: Route guard
├── .env.development        # NEW: VITE_API_URL=http://localhost:5000
└── .env.production         # NEW: VITE_API_URL=https://api.finpulse.com
```

**App (Modified Files):**
```
app/src/
├── hooks/
│   ├── useBudgets.tsx      # MODIFY: Replace mock with API calls
│   ├── useBills.tsx        # MODIFY: Replace mock with API calls
│   ├── useGoals.tsx        # MODIFY: Replace mock with API calls
│   ├── useInvestments.tsx  # MODIFY: Replace mock with API calls
│   ├── useExpenses.tsx     # NEW or MODIFY: Add if missing
│   └── useEarnings.tsx     # NEW or MODIFY: Add if missing
├── App.tsx                 # MODIFY: Add AuthProvider, routes
└── pages/Index.tsx         # MODIFY: Use auth context for userId
```

**API (Modified Files):**
```
api/FinPulse.Api/
├── Program.cs              # MODIFY: Add CORS policy, cookie config
└── Controllers/
    └── AuthController.cs   # MODIFY: Set httpOnly cookie on login
```

---

## Assumptions

| ID | Assumption | If Wrong, Impact | Validated? |
|----|------------|------------------|------------|
| A-001 | API is running and accessible at configured URL | Integration fails completely | [ ] Test at dev start |
| A-002 | Database schema supports all required operations | Missing tables = 500 errors | [x] Verified - schema complete |
| A-003 | Browser supports credentials: 'include' | Cookies won't be sent | [x] Modern browsers only |
| A-004 | Same-site cookie policy works cross-origin | Auth fails in prod | [ ] Test with actual domains |
| A-005 | API can handle concurrent requests | Race conditions | [x] EF Core handles this |

---

## Clarity Score Breakdown

| Element | Score (0-3) | Notes |
|---------|-------------|-------|
| Problem | 3 | Crystal clear - API and app disconnected, mock data |
| Users | 3 | App users and developers identified with pain points |
| Goals | 3 | 12 specific, prioritized goals with MoSCoW |
| Success | 3 | 7 measurable criteria with specific metrics |
| Scope | 3 | Explicit in/out lists, deferrals documented |
| **Total** | **15/15** | Ready for Design |

---

## Open Questions

None - all clarified during brainstorming phase.

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-01 | define-agent | Initial version from BRAINSTORM document |

---

## Next Step

**Ready for:** `/design .claude/sdd/features/DEFINE_API_APP_INTEGRATION.md`
