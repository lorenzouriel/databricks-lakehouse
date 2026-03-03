# DEFINE: API Integration

> Replace Supabase POC with full FinPulse .NET API integration across all app tabs

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | API_INTEGRATION |
| **Date** | 2026-02-11 |
| **Author** | define-agent |
| **Status** | Ready for Design |
| **Clarity Score** | 14/15 |
| **Source** | BRAINSTORM_API_INTEGRATION.md |

---

## Problem Statement

The FinPulse app is a POC where 4 out of 5 data tabs (Budgets, Bills, Goals, Investments) use in-memory `useState` with no persistence, the Transactions tab uses Supabase instead of the project's .NET API, the AI Chat tab has no backend endpoint, and dashboard stats are hardcoded. Users lose all data on page refresh for most features, and the app runs against a different backend than what was built for it.

---

## Target Users

| User | Role | Pain Point |
|------|------|------------|
| Developer (self) | Full-stack developer | 4/5 tabs have no persistence, mixed data sources (Supabase + useState), dead code from Lovable/Supabase |
| End user | Personal finance tracker | Data lost on refresh for budgets/bills/goals/investments, no real login, hardcoded stats |

---

## Goals

| Priority | Goal |
|----------|------|
| **MUST** | Remove all Supabase code and dependencies (client, types, config, migrations, edge functions) |
| **MUST** | Remove all AI Chat components and hooks (no API endpoint exists) |
| **MUST** | Create API service layer with custom fetch wrapper (`src/services/`) |
| **MUST** | Implement Login and Register pages using API JWT auth (`/api/auth/*`) |
| **MUST** | Integrate Expenses & Earnings tab with API (`/api/users/{userId}/expenses` + `/earnings`) |
| **MUST** | Integrate Budgets tab with API (`/api/users/{userId}/budgets` + `/budget-spendings`) |
| **MUST** | Integrate Bills tab with API (`/api/users/{userId}/bills` + `/bill-payments`) |
| **MUST** | Integrate Goals tab with API (`/api/users/{userId}/goals`) |
| **MUST** | Integrate Investments tab with API (`/api/users/{userId}/investments`) |
| **MUST** | Compute dashboard stats from real API data (no hardcoded values) |
| **SHOULD** | Change Vite dev server port from 8080 to 5173 (matches API CORS) |
| **COULD** | Add loading states and error handling for API calls |

---

## Success Criteria

- [ ] Zero Supabase imports or references in the codebase
- [ ] Zero chat-related component files in `src/components/chat/`
- [ ] `supabase/` directory fully removed
- [ ] `@supabase/supabase-js` removed from `package.json`
- [ ] User can register, login, and logout via the .NET API
- [ ] Auth state persists across page refreshes (JWT cookie)
- [ ] All 5 data tabs perform CRUD operations against the API
- [ ] Dashboard stat cards show computed values from API data
- [ ] `npm run build` succeeds with zero errors
- [ ] App runs on port 5173 (matching API CORS policy)

---

## Acceptance Tests

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-001 | User Registration | User is on register page | Fills username, email, phone, password and submits | API returns 201, user is redirected to login |
| AT-002 | User Login | User is on login page with valid credentials | Enters email + password and submits | JWT cookie set, redirected to dashboard, `/api/auth/me` returns user info |
| AT-003 | Auth Guard | User is not authenticated | Navigates to dashboard URL | Redirected to login page |
| AT-004 | Create Expense | User is on Expenses tab, authenticated | Fills amount, category, payment method, date and submits | `POST /api/users/{userId}/expenses` called, expense appears in list |
| AT-005 | Create Earning | User is on Earnings tab, authenticated | Fills amount, category, date and submits | `POST /api/users/{userId}/earnings` called, earning appears in list |
| AT-006 | List Expenses with Filter | User has expenses in the API | Selects date range filter | `GET /api/users/{userId}/expenses?start_date=X&end_date=Y` returns filtered results |
| AT-007 | Create Budget | User is on Budgets tab | Fills name, limit, start/end date and submits | `POST /api/users/{userId}/budgets` called, budget card appears |
| AT-008 | Add Budget Spending | User has a budget | Adds spending amount for a month | `POST /api/users/{userId}/budget-spendings` called, spending tracked against budget |
| AT-009 | Create Bill | User is on Bills tab | Fills bill name, amount, due date and submits | `POST /api/users/{userId}/bills` called, bill card appears |
| AT-010 | Record Bill Payment | User has a bill | Records a payment | `POST /api/users/{userId}/bill-payments` called, payment history updated |
| AT-011 | Create Goal | User is on Goals tab | Fills name, target amount, due date and submits | `POST /api/users/{userId}/goals` called, goal card with progress appears |
| AT-012 | Update Goal Progress | User has a goal | Updates current amount | `PUT /api/users/{userId}/goals/{id}` called with new currentAmount |
| AT-013 | Create Investment | User is on Investments tab | Fills asset name, type, invested amount, purchase date | `POST /api/users/{userId}/investments` called, investment card appears |
| AT-014 | Update Investment Value | User has an investment | Updates current value | `PUT /api/users/{userId}/investments/{id}` called, P&L recalculated |
| AT-015 | Dashboard Stats | User has expenses and earnings | Views dashboard | Stats show sum of earnings, sum of expenses, balance (earnings - expenses), savings rate |
| AT-016 | Delete Entity | User has any entity (expense/budget/bill/goal/investment) | Clicks delete | `DELETE /api/users/{userId}/{entity}/{id}` called, item removed from list |
| AT-017 | Page Refresh Persistence | User has created data | Refreshes the page | All data reloads from API, nothing lost |
| AT-018 | Logout | User is authenticated | Clicks logout | `POST /api/auth/logout` called, cookie cleared, redirected to login |

---

## Out of Scope

- Bank Connections, Bank Accounts, Bank Transactions UI (API has endpoints but no app tab yet)
- AI Chat functionality (no API endpoint)
- Open Banking integration
- Offline/cache support
- Password reset flow
- Real-time updates / WebSocket
- User profile editing
- Multi-currency display (use BRL as default for now)

---

## Constraints

| Type | Constraint | Impact |
|------|------------|--------|
| Technical | API uses JWT in HTTP-only secure cookies with `SameSite: None` | Fetch must use `credentials: 'include'` on every request |
| Technical | API routes follow `/api/users/{userId}/...` pattern | Need userId from auth context (JWT `sub` claim or `/api/auth/me` response) |
| Technical | API CORS allows `localhost:5173` and `localhost:3000` only | Vite dev server must run on port 5173 (change from 8080) |
| Technical | API currency default is "USD", app displays "BRL" (R$) | Service layer should send `currencyCode: "BRL"` on all creates |
| Technical | API uses `decimal` for amounts, TypeScript uses `number` | No precision issues for display, but be careful with formatting |
| Dependency | API must be running for the app to function | No offline mode planned |

---

## Technical Context

| Aspect | Value | Notes |
|--------|-------|-------|
| **Deployment Location** | `app/src/services/` (new), `app/src/hooks/` (modified), `app/src/pages/` (new auth pages) | Service layer + hook rewiring + auth pages |
| **KB Domains** | React, TypeScript, REST API, JWT Auth | Frontend integration patterns |
| **IaC Impact** | None | No infrastructure changes, API already deployed |

---

## API Contract Reference

### Auth Endpoints

| Method | Endpoint | Request Body | Response |
|--------|----------|-------------|----------|
| POST | `/api/auth/register` | `{ username, phoneNumber, email, password }` | `{ userId, password }` |
| POST | `/api/auth/login` | `{ email, password }` | `{ accessToken, userId }` + sets cookie |
| POST | `/api/auth/logout` | - | `{ message }` + clears cookie |
| GET | `/api/auth/me` | - | User info |

### Entity Endpoints (all require auth, all under `/api/users/{userId}/`)

| Entity | GET (list) | POST (create) | PUT (update) | DELETE |
|--------|-----------|---------------|-------------|--------|
| **expenses** | `?start_date&end_date&category` | CreateExpenseRequest | UpdateExpenseRequest | `/{id}` |
| **earnings** | `?start_date&end_date&category` | CreateEarningRequest | UpdateEarningRequest | `/{id}` |
| **budgets** | `?start_date&end_date` | CreateBudgetRequest | UpdateBudgetRequest | `/{id}` |
| **budget-spendings** | `?budget_id&month` | CreateBudgetSpendingRequest | UpdateBudgetSpendingRequest | `/{id}` |
| **bills** | `?start_date&end_date` | CreateBillRequest | UpdateBillRequest | `/{id}` |
| **bill-payments** | `?bill_id` | CreateBillPaymentRequest | UpdateBillPaymentRequest | `/{id}` |
| **goals** | `?start_date&end_date` | CreateGoalRequest | UpdateGoalRequest | `/{id}` |
| **investments** | (standard list) | CreateInvestmentRequest | UpdateInvestmentRequest | `/{id}` |

### Key DTO Shapes (TypeScript equivalents needed)

**ExpenseResponse:** `{ id, userId, category, paymentMethod, currencyCode, amount, description?, expenseDate, status, createdAt }`

**EarningResponse:** `{ id, userId, category, paymentMethod, currencyCode, amount, description?, earningDate, status, createdAt }`

**BudgetResponse:** `{ id, userId, name, description?, amountLimit, currencyCode, startDate, endDate, status, createdAt }`

**BudgetSpendingResponse:** `{ id, budgetId, userId, month, amount, notes?, createdAt }`

**BillResponse:** `{ id, userId, billName, category, paymentMethod?, amount, currencyCode, dueDate, recurrenceType?, recurrenceInterval?, nextDueDate?, paidDate?, description?, status, createdAt }`

**BillPaymentResponse:** `{ id, billId, userId, amountPaid, paidDate, notes?, createdAt }`

**GoalResponse:** `{ id, userId, name, description?, targetAmount, currentAmount, currencyCode, dueDate, status, createdAt }`

**InvestmentResponse:** `{ id, userId, investmentType, category, assetName, broker?, currencyCode, investedAmount, currentValue?, purchaseDate, maturityDate?, annualYieldPercent?, profitLoss?, status, createdAt }`

---

## Files to Remove

| File/Directory | Reason |
|----------------|--------|
| `src/integrations/supabase/client.ts` | Supabase client - replaced by apiClient |
| `src/integrations/supabase/types.ts` | Supabase auto-generated types - replaced by TS interfaces |
| `src/integrations/supabase/` | Entire directory |
| `src/components/chat/ChatSection.tsx` | AI Chat - no API endpoint |
| `src/components/chat/ChatMessages.tsx` | AI Chat component |
| `src/components/chat/ChatInput.tsx` | AI Chat component |
| `src/components/chat/ChatSidebar.tsx` | AI Chat component |
| `src/components/chat/BotSelector.tsx` | AI Chat component |
| `src/components/chat/SpecialistDropdown.tsx` | AI Chat component |
| `src/components/chat/` | Entire directory |
| `src/hooks/useAIChat.tsx` | AI Chat hook |
| `supabase/config.toml` | Supabase project config |
| `supabase/migrations/` | Supabase migrations |
| `supabase/functions/ai-chat/` | Supabase Edge Function |
| `supabase/` | Entire directory |

---

## Files to Create

| File | Purpose |
|------|---------|
| `src/services/apiClient.ts` | Custom fetch wrapper with base URL, credentials, error handling |
| `src/services/authService.ts` | register, login, logout, getMe |
| `src/services/expenseService.ts` | CRUD for expenses |
| `src/services/earningService.ts` | CRUD for earnings |
| `src/services/budgetService.ts` | CRUD for budgets + budget spendings |
| `src/services/billService.ts` | CRUD for bills + bill payments |
| `src/services/goalService.ts` | CRUD for goals |
| `src/services/investmentService.ts` | CRUD for investments |
| `src/services/types.ts` | TypeScript interfaces matching API DTOs |
| `src/contexts/AuthContext.tsx` | Auth state (user, userId, isAuthenticated) + provider |
| `src/pages/Login.tsx` | Login page with email + password form |
| `src/pages/Register.tsx` | Register page with username, email, phone, password form |

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/hooks/useTransactions.tsx` | Replace Supabase calls with expenseService + earningService |
| `src/hooks/useBudgets.tsx` | Replace useState with budgetService API calls |
| `src/hooks/useBills.tsx` | Replace useState with billService API calls |
| `src/hooks/useGoals.tsx` | Replace useState with goalService API calls |
| `src/hooks/useInvestments.tsx` | Replace useState with investmentService API calls |
| `src/pages/Index.tsx` | Remove AI Chat tab, compute stats from API data, wrap with auth guard |
| `src/components/finance/Header.tsx` | Wire logout to authService, show user info |
| `src/App.tsx` | Add AuthProvider, login/register routes, protect dashboard route |
| `vite.config.ts` | Change port from 8080 to 5173 |
| `package.json` | Remove `@supabase/supabase-js` dependency |

---

## Assumptions

| ID | Assumption | If Wrong, Impact | Validated? |
|----|------------|------------------|------------|
| A-001 | API is running and accessible at localhost | App won't load any data | [x] User confirmed |
| A-002 | JWT cookie is set automatically by the API on login | Would need manual token handling | [ ] Test during build |
| A-003 | API returns JSON with camelCase property names (C# default serialization) | Would need property mapping | [ ] Test during build |
| A-004 | CORS preflight works with credentials: 'include' | Would get blocked by browser | [ ] Test during build |
| A-005 | API query params use snake_case (start_date, end_date) | Would need to adjust service calls | [ ] Verify from controllers |

---

## Clarity Score Breakdown

| Element | Score (0-3) | Notes |
|---------|-------------|-------|
| Problem | 3 | Specific: POC with mock data, 4/5 tabs no persistence, mixed backends |
| Users | 2 | Developer + end user identified; could add more persona detail but sufficient |
| Goals | 3 | 12 prioritized goals with MUST/SHOULD/COULD |
| Success | 3 | 10 measurable criteria, all testable |
| Scope | 3 | 8 explicit exclusions, confirmed during brainstorm |
| **Total** | **14/15** | Exceeds 12/15 threshold |

---

## Open Questions

None - ready for Design. All critical questions resolved during brainstorm phase:
- Auth approach: Replace Supabase entirely (confirmed)
- AI Chat: Remove entirely (confirmed)
- Bank features: Out of scope (confirmed)
- HTTP client: Custom fetch wrapper (confirmed)
- CORS/port: Change Vite to 5173 (confirmed)

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-11 | define-agent | Initial version from BRAINSTORM_API_INTEGRATION.md |

---

## Next Step

**Ready for:** `/design .claude/sdd/features/DEFINE_API_INTEGRATION.md`
