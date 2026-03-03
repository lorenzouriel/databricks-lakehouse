# BRAINSTORM: API Integration

> Exploratory session to clarify intent and approach before requirements capture

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | API_INTEGRATION |
| **Date** | 2026-02-11 |
| **Author** | brainstorm-agent |
| **Status** | Ready for Define |

---

## Initial Idea

**Raw Input:** The app is a POC with mock data. Need to analyze the app and API, remove unnecessary files, integrate all tabs with the API, and disable tabs that don't have integration yet.

**Context Gathered:**
- App is React/Vite/TypeScript with Tailwind + shadcn/ui, built with Lovable
- 6 tabs: Expenses & Earnings, Budgets, Bills, Goals, Investments, AI Chat
- Only Transactions (expenses/earnings) has real Supabase integration; all other tabs use in-memory `useState`
- Dashboard stat cards are hardcoded (R$ 24.562,00 etc.)
- API is ASP.NET Core 8.0 with full CRUD for all entities + JWT auth
- API also has Bank Connections/Accounts/Transactions endpoints not yet in the app

**Technical Context Observed (for Define):**

| Aspect | Observation | Implication |
|--------|-------------|-------------|
| Likely Location | `app/src/services/` (new), `app/src/hooks/` (modified) | Service layer + hook rewiring |
| Current Auth | Supabase auth in app, JWT in API | Must replace Supabase auth with API JWT |
| Data Layer | Mixed: Supabase (transactions) + useState (rest) | Unify all under API service calls |
| API Pattern | REST, `/api/users/{userId}/...`, JWT cookie auth | Need custom fetch wrapper with cookie support |

---

## Discovery Questions & Answers

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | How to handle auth transition? (Replace Supabase / Keep for auth / Gradual) | **Replace Supabase entirely** | Clean break - remove all Supabase code, use API JWT auth |
| 2 | What to do with AI Chat tab? (Disable / Remove / Keep offline) | **Remove it entirely** | Delete all chat components, hooks, and Supabase Edge Function |
| 3 | Include Bank features from API? (Out of scope / Basic view / Prepare hooks) | **Out of scope for now** | Focus only on existing 5 tabs |
| 4 | HTTP client structure? (Custom fetch / Axios / TanStack Query) | **Custom fetch wrapper** | Lightweight, no extra dependency, native fetch with auth |
| 5 | Samples available? (API running / Docs / DTOs only) | **API is running and testable** | Can validate integration against real responses |

---

## Sample Data Inventory

| Type | Location | Count | Notes |
|------|----------|-------|-------|
| API DTOs | `api/FinPulse.Api/DTOs/` | 13 files | Request/Response shapes for all entities |
| API Models | `api/FinPulse.Api/Models/` | 12 files | Database entity definitions |
| Running API | `localhost` (SQL Server backend) | All endpoints | Can test real responses |
| App Hooks | `app/src/hooks/` | 6 hooks | Current data shapes to map from |
| Supabase Types | `app/src/integrations/supabase/types.ts` | 1 file | Auto-generated types (will be replaced) |

**How samples will be used:**
- API DTOs define the contract for service layer type definitions
- Running API validates integration works end-to-end
- Existing hook interfaces guide the mapping to preserve component compatibility

---

## Approaches Explored

### Approach A: Clean Replace with API Service Layer ⭐ Recommended

**Description:** Remove Supabase entirely, create a thin API service layer (`src/services/`) with a custom fetch wrapper, and rewire all hooks to call the .NET API.

**What gets removed:**
- `src/integrations/supabase/` (client + types)
- `src/components/chat/` (all 6 chat components)
- `src/hooks/useAIChat.tsx`
- `supabase/` folder (config, migrations, edge functions)
- Supabase dependencies from `package.json`
- Hardcoded stat card values from `Index.tsx`

**What gets created:**
- `src/services/apiClient.ts` - Custom fetch wrapper with JWT cookie auth
- `src/services/authService.ts` - Login/register/logout/me
- `src/services/expenseService.ts` - Expenses CRUD
- `src/services/earningService.ts` - Earnings CRUD
- `src/services/budgetService.ts` - Budgets + BudgetSpendings CRUD
- `src/services/billService.ts` - Bills + BillPayments CRUD
- `src/services/goalService.ts` - Goals CRUD
- `src/services/investmentService.ts` - Investments CRUD

**What gets modified:**
- All hooks rewired to use API services instead of useState/Supabase
- `Index.tsx` - Remove AI Chat tab, compute stats from real data
- `Header.tsx` - Wire user auth to API
- Add login/register page
- `App.tsx` - Add auth routes, protect dashboard

**Pros:**
- Clean architecture, no legacy Supabase code
- All data persisted via the .NET API
- Single auth system (JWT)
- Clear separation: services (API calls) vs hooks (state management)

**Cons:**
- Bigger initial change (more files touched at once)
- Need login/register page (app currently has none visible)

**Why Recommended:** Produces a clean, maintainable codebase with no mixed data sources. The service layer makes future API changes easy to adapt.

---

### Approach B: Incremental Hook-by-Hook Migration

**Description:** Keep existing structure, replace one hook at a time. Add API calls inside existing hooks without creating a separate service layer.

**Pros:**
- Smaller changes per step
- Easier to test incrementally

**Cons:**
- Messy transition period with mixed Supabase + API calls
- No clear separation of concerns (API calls mixed into hooks)
- Supabase removal has to happen later as separate cleanup
- More total work due to intermediate states

**Why not recommended:** Creates technical debt and the mixed state makes debugging harder.

---

## Selected Approach

| Attribute | Value |
|-----------|-------|
| **Chosen** | Approach A - Clean Replace with API Service Layer |
| **User Confirmation** | 2026-02-11 |
| **Reasoning** | Clean break from Supabase, single auth system, clear service layer architecture |

---

## Key Decisions Made

| # | Decision | Rationale | Alternative Rejected |
|---|----------|-----------|----------------------|
| 1 | Replace Supabase entirely | Single auth system, no sync issues | Keep Supabase for auth only |
| 2 | Remove AI Chat completely | No API endpoint, removes complexity | Disable temporarily |
| 3 | Custom fetch wrapper (no axios/react-query) | Lightweight, no extra dependency | Axios, TanStack Query |
| 4 | Bank features out of scope | Focus on existing tabs first | Add basic bank view |
| 5 | Service layer pattern (`src/services/`) | Clean separation from hooks | API calls inline in hooks |

---

## Features Removed (YAGNI)

| Feature Suggested | Reason Removed | Can Add Later? |
|-------------------|----------------|----------------|
| Bank Connections/Accounts UI | No current tab, complex feature requiring external provider | Yes |
| AI Chat integration | No API endpoint exists yet | Yes |
| Open Banking sync | Requires external provider setup | Yes |
| Offline/cache support (React Query) | Adds complexity, not needed for MVP | Yes |
| Password reset flow | Can add after core integration works | Yes |
| Real-time updates (WebSocket) | Polling or manual refresh is sufficient | Yes |

---

## Incremental Validations

| Section | Presented | User Feedback | Adjusted? |
|---------|-----------|---------------|-----------|
| Architecture approach (service layer vs incremental) | ✅ | Approved Approach A (clean replace) | No |
| Scope & YAGNI (5 tabs + auth, defer bank/chat) | ✅ | Confirmed scope is correct | No |

---

## Suggested Requirements for /define

Based on this brainstorm session, the following should be captured in the DEFINE phase:

### Problem Statement (Draft)
The FinPulse app is a POC with mock data and mixed data sources (Supabase + in-memory state). It needs to be integrated with the FinPulse .NET API to persist all data, use proper JWT authentication, and remove unnecessary code.

### Target Users (Draft)
| User | Pain Point |
|------|------------|
| Developer (self) | App has no real persistence for 4 out of 5 tabs, mock data everywhere |
| End user | Data is lost on page refresh for budgets, bills, goals, investments |

### Success Criteria (Draft)
- [ ] All Supabase code and dependencies removed
- [ ] All AI Chat components and hooks removed
- [ ] Login and Register pages functional with API JWT auth
- [ ] Expenses & Earnings tab reads/writes to API
- [ ] Budgets tab (with spendings) reads/writes to API
- [ ] Bills tab (with payments) reads/writes to API
- [ ] Goals tab reads/writes to API
- [ ] Investments tab reads/writes to API
- [ ] Dashboard stats computed from real API data
- [ ] No hardcoded/mock data remaining
- [ ] App builds without errors

### Constraints Identified
- API uses JWT in HTTP-only cookies - fetch must use `credentials: 'include'`
- API routes follow `/api/users/{userId}/...` - need userId from auth context
- API CORS allows `localhost:5173` and `localhost:3000` - app dev server must match
- App currently runs on port 8080 (Vite config) - may need CORS update on API side
- Currency default in API is "USD" but app shows "BRL" (R$) - needs alignment

### Out of Scope (Confirmed)
- Bank Connections, Bank Accounts, Bank Transactions UI
- AI Chat functionality
- Open Banking integration
- Offline/cache support
- Password reset flow
- Real-time updates

---

## Session Summary

| Metric | Value |
|--------|-------|
| Questions Asked | 5 |
| Approaches Explored | 2 |
| Features Removed (YAGNI) | 6 |
| Validations Completed | 2 |

---

## Next Step

**Ready for:** `/define .claude/sdd/features/BRAINSTORM_API_INTEGRATION.md`
