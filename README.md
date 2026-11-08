### Property Management

# Property Management System

A multi-tenant property management built with **Frappe Framework and ERPNext**, designed for landlords and property management companies.

The platform aims to simplify property operations by bringing property records, tenant management, lease administration, rent collection, maintenance and financial reporting into one system.

## 1. Project Overview

Managing rental properties involves coordinating multiple activities, including:

- Managing properties, buildings and rental units.
- Registering tenants and maintaining their records.
- Creating and managing tenancy agreements.
- Tracking rent schedules, invoices and outstanding balances.
- Recording payments and reconciling rent collections.
- Managing maintenance requests and operational expenses.
- Monitoring property performance and financial activity.

This project aims to provide a centralized system for managing these activities while leveraging ERPNext's existing accounting capabilities.

## 2. Project Objectives

The main objectives are to:

- Simplify day-to-day property management operations.
- Automate rent invoicing and payment tracking.
- Improve visibility into occupancy, collections and arrears.
- Maintain organized tenant, lease and property records.
- Integrate Kenyan payment workflows, particularly M-Pesa.
- Provide financial reporting using ERPNext.
- Support multiple independent property management businesses through a SaaS architecture.

## 3. Technology Stack

| Technology        | Purpose                                      |
| ----------------- | -------------------------------------------- |
| Frappe Framework  | Application framework and business workflows |
| ERPNext           | Accounting and financial management          |
| Python            | Backend development and business logic       |
| JavaScript        | Client-side interactions                     |
| MariaDB           | Database                                     |
| Redis             | Caching and background job infrastructure    |
| HTML / CSS        | User interface customization                 |
| M-Pesa Daraja API | Planned payment integration                  |
| Git & GitHub      | Version control and collaboration            |

## 4. Architecture

The system follows a modular approach, separating property management functionality from accounting functionality.

### Frappe Framework

Responsible for:

- Document management and DocTypes.
- User authentication and permissions.
- Business workflows.
- Background jobs and scheduled tasks.
- API endpoints.
- Application customization.

### ERPNext

Provides the financial foundation:

- Sales Invoices.
- Payment Entries.
- General Ledger.
- Accounts and financial transactions.
- Financial statements and reporting.

### Property Management App

The custom `property_management` app contains property-specific functionality:

- Property and building management.
- Rental unit management.
- Tenant records.
- Lease administration.
- Rent schedules.
- Maintenance requests.
- M-Pesa integration.
- Property-specific reports and workflows.

**Architecture principle:** Property Management owns property-specific business rules, while ERPNext handles the accounting records and financial rules.

For example, when rent becomes due, the custom application will initiate the appropriate ERPNext Sales Invoice rather than implementing a separate accounting system.

## 5. Core Business Workflow

The intended business workflow is:

```text
Property Registration
        |
        v
Building & Unit Registration
        |
        v
Tenant Registration
        |
        v
Lease Creation
        |
        v
Rent Schedule Generation
        |
        v
Rent Invoice Creation
        |
        v
Payment Collection
        |
        v
Payment Reconciliation
        |
        v
Financial Reporting
```

Maintenance management will operate alongside this workflow.

## 6. Planned Modules

| Module                 | Description                                            |
| ---------------------- | ------------------------------------------------------ |
| Property Management    | Register and manage properties and buildings           |
| Unit Management        | Manage rental units and occupancy                      |
| Tenant Management      | Maintain tenant information and records                |
| Lease Management       | Manage tenancy agreements and lease periods            |
| Rent Management        | Generate rent schedules and invoices                   |
| Payment Management     | Track payments and outstanding balances                |
| M-Pesa Integration     | Support M-Pesa payment collection workflows            |
| Maintenance Management | Track maintenance requests and work orders             |
| Financial Reporting    | Monitor collections, expenses and property performance |

These modules represent the intended product direction; implementation will happen incrementally.

## 7. SaaS Multi-Tenancy Strategy

The initial deployment architecture uses:

**One Frappe site per customer, with multiple sites sharing one Bench.**

Each customer receives:

- An independent Frappe site.
- A separate database.
- Independent business records and user accounts.
- Separate site configuration and files.
- Access to the same installed application codebase.

Illustrative deployment:

```text
                 Shared Frappe Bench
                         |
          +--------------+--------------+
          |              |              |
       Site A          Site B          Site C
          |           |              |
       Database       Database       Database
          |              |              |
       Customer A     Customer B     Customer C
```

This approach provides database-level separation between customers while allowing the application codebase to be maintained centrally.

## 8. Development Setup

### Prerequisites

The development environment requires:

- Ubuntu or another supported Linux environment.
- Python.
- Node.js and npm.
- Yarn.
- MariaDB.
- Redis.
- Frappe Bench CLI.

### Initialize the Bench

```bash
bench init --frappe-branch version-16 property-bench
cd property-bench
```

### Get ERPNext

```bash
bench get-app --branch version-16 erpnext
```

### Get the Property Management App

```bash
bench get-app https://github.com/manuelogonda/frappe-property-ms.git
```

### Create a Site

```bash
bench new-site client-a.localhost
```

### Install ERPNext and Property Management

```bash
bench --site client-a.localhost install-app erpnext
bench --site client-a.localhost install-app property_management
```

### Start Development Server

```bash
bench start
```

The commands above describe the intended setup sequence. The site creation and application installation steps will be completed as the environment is configured.

## 9. Project Roadmap

Development is organized into six phases.

| Phase   | Focus                  | Key Deliverables                                                   |
| ------- | ---------------------- | ------------------------------------------------------------------ |
| Phase 1 | Foundation             | Development environment, Git setup, Frappe and ERPNext integration |
| Phase 2 | Core Records           | Properties, buildings, units, tenants and leases                   |
| Phase 3 | Rent & Accounting      | Rent schedules, invoicing, payments and arrears                    |
| Phase 4 | Operations             | Maintenance, work orders and expenses                              |
| Phase 5 | Portals & Integrations | User portals, M-Pesa and notifications                             |
| Phase 6 | Testing & Launch       | Testing, security, deployment and documentation                    |

## 10. Development Principles

The project will follow these principles:

- **Business rules first:** Understand the business process before designing DocTypes.
- **Modular design:** Keep property-specific functionality separate from accounting functionality.
- **Reuse existing capabilities:** Leverage Frappe and ERPNext instead of unnecessarily rebuilding existing features.
- **Data integrity:** Maintain accurate relationships between properties, units, tenants, leases and financial records.
- **Security:** Apply role-based permissions and protect customer data.
- **Maintainability:** Write readable, testable and reusable code.
- **Incremental development:** Build, test and document features in manageable stages.

## 11. Project Status

**Current stage: Phase 1 — Foundation**

Initial progress:

- [x] Frappe Bench initialized.
- [x] ERPNext retrieved.
- [x] Custom Frappe application generated.
- [x] Git repository initialized.
- [x] GitHub remote configured.
- [x] Initial development branch pushed.
- [ ] Create and configure the first Frappe site.
- [ ] Install ERPNext on the site.
- [ ] Install the custom Property Management app.
- [ ] Verify the complete development environment.

## 12. Repository

GitHub: [https://github.com/manuelogonda/frappe-property-ms](https://github.com/manuelogonda/frappe-property-ms)

Application name: `property_management`

Framework: Frappe Framework

Accounting foundation: ERPNext

---

**Status:** Under active development.
