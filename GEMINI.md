# Project Overview
This is a headless personal finance and wealth management application. It utilizes a multi-tenant architecture where all operational data is scoped to a `Family` boundary. The system includes an AI-assisted document ingestion pipeline for bank statements and enforces strict double-entry accounting principles.

# Tech Stack
## Backend (finance_backend/)
- Python 3.x
- Django 4.2
- API Framework: Django Ninja (strictly preferred over Django REST Framework)
- Authentication: ninja-jwt (JSON Web Tokens)
- Hierarchical Data: django-mptt (used for the Chart of Accounts)
- Data Extraction: pandas, tabula-py (for PDF bank statement parsing)

## Frontend (frontend/)
- React 18
- TypeScript
- Build Tool: Vite
- Styling: Tailwind CSS, CSS Modules
- UI Components: Shadcn UI (accessible via standard dependencies like lucide-react, clsx, tailwind-merge)

# Coding Conventions & Architecture Rules

## Backend Guidelines
1. **API Endpoints:** All new API endpoints MUST be built using Django Ninja (`@api.get`, `@api.post`, etc.) and Pydantic-style schemas for request/response validation. Do not use standard Django views or Django REST Framework.
2. **Multi-Tenancy:** Always ensure data queries and mutations are correctly scoped to the `Family` model. Do not leak data across families.
3. **Double-Entry Accounting:** Any code modifying financial balances must enforce the accounting equation. `JournalEntry` transactions must happen within a `transaction.atomic()` block, and the sum of `TransactionLine` amounts must always equal zero.
4. **Data Types:** Always use `Decimal` (from the `decimal` module) for financial amounts. Never use floating-point numbers.
5. **Business Logic:** Keep business logic out of API endpoints. Route complex logic (like PDF extraction or transaction reconciliation) through dedicated service layers or model methods.

## Frontend Guidelines
1. **Components:** Use functional components and React Hooks exclusively.
2. **Typing:** Provide strict TypeScript interfaces/types for all component props, state, and API responses.
3. **Styling:** Use Tailwind CSS utility classes for styling. When building new UI elements, default to Shadcn UI patterns.
4. **State Management:** Keep local state collocated with components. For API data fetching, assume standard asynchronous hooks or context.

## Domain Knowledge
- **Demographics:** The system tracks statutory milestones (e.g., RESP deadlines, TFSA eligibility, CEGEP start dates, QPP eligibility) based on the `FamilyMember`'s age and role.
- **Ingestion Pipeline:** Bank statements (`BankStatementImport`) are parsed into `StagedTransaction` records. These remain in a `PENDING_REVIEW` status until manually reconciled into a formal `JournalEntry`.