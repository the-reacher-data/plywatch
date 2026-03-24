# Flower 2.0 --- Frontend Architecture Specification

## 1. Project Goal

Build a **modern lightweight web UI for Celery** that replaces Flower.

Main goals:

-   Real-time monitoring of Celery workers and tasks
-   Extremely **lightweight frontend**
-   **High performance with large datasets (10k--100k tasks)**
-   Real-time updates via **Server-Sent Events (SSE)**
-   Clean architecture and maintainable code
-   Designed as **open-source quality project**

The UI should resemble modern monitoring dashboards such as:

-   Grafana
-   Datadog
-   Linear
-   Vercel dashboards

------------------------------------------------------------------------

# 2. High-Level Architecture

The frontend follows a **layered architecture**.

    UI Components
          ↓
    Table Engine
          ↓
    State Store
          ↓
    Event Stream (SSE)
          ↓
    FastAPI Backend
          ↓
    Celery Events

The UI receives **real-time Celery events via SSE**, updates the store,
and the table updates automatically.

------------------------------------------------------------------------

# 3. Technology Stack

Frontend stack:

    Framework: SvelteKit
    Language: TypeScript (strict mode)
    Styling: TailwindCSS
    UI Components: shadcn-svelte
    Table Engine: TanStack Table
    Virtualization: TanStack Virtual
    Real-time updates: Server-Sent Events (SSE)

Tooling:

    ESLint
    Prettier
    Vitest
    Playwright

Goals of this stack:

-   minimal runtime
-   strong typing
-   high performance
-   reusable UI components

------------------------------------------------------------------------

# 4. Frontend Repository Structure

Use **feature-based modular architecture**.

    src
    │
    ├ core
    │   ├ api
    │   │   ├ http.ts
    │   │   └ sse.ts
    │   │
    │   ├ state
    │   │   └ event_bus.ts
    │   │
    │   ├ types
    │   │   └ celery.ts
    │   │
    │   └ utils
    │
    ├ features
    │
    │   ├ tasks
    │   │   ├ components
    │   │   │   └ TaskTable.svelte
    │   │   │
    │   │   ├ stores
    │   │   │   └ task_store.ts
    │   │   │
    │   │   ├ services
    │   │   │   └ task_service.ts
    │   │   │
    │   │   └ models
    │   │       └ task.ts
    │   │
    │   ├ workers
    │   ├ queues
    │   └ metrics
    │
    ├ components
    │   ├ table
    │   │   ├ DataTable.svelte
    │   │   └ TableColumn.ts
    │   │
    │   ├ layout
    │   └ ui
    │
    └ routes
        ├ +layout.svelte
        ├ +page.svelte
        ├ tasks
        ├ workers
        └ metrics

Architecture principles:

-   domain separation
-   feature isolation
-   reusable UI components

------------------------------------------------------------------------

# 5. Real-Time Event Architecture

Celery emits events such as:

    task_received
    task_started
    task_succeeded
    task_failed
    worker_online
    worker_offline

Data flow:

    Celery Workers
            ↓
    Celery Events
            ↓
    FastAPI Event Collector
            ↓
    SSE endpoint (/events)
            ↓
    Frontend SSE client
            ↓
    State store update
            ↓
    UI update

Frontend connects using:

    EventSource("/api/events")

Events must update the store **incrementally**, not re-render the full
UI.

------------------------------------------------------------------------

# 6. State Management Strategy

Use **Svelte stores**.

Important design decision:

Store tasks using a **Map instead of arrays**.

Example:

    Map<TaskId, Task>

Benefits:

    O(1) updates
    O(1) lookups
    efficient event updates

Example event handling:

    task_started → update task status
    task_succeeded → update runtime and status
    task_failed → store traceback

------------------------------------------------------------------------

# 7. Task Data Model

Example task structure:

    Task {
        id: string
        name: string
        worker: string
        queue: string
        status: "SUCCESS" | "FAILURE" | "RETRY" | "STARTED"
        runtime: number
        retries: number
        timestamp: number
    }

Optional fields:

    args
    kwargs
    result
    traceback

------------------------------------------------------------------------

# 8. Data Retention Strategy

The frontend should not store unlimited history.

Possible limits:

    max_tasks = 10000

or

    tasks from last 5 minutes

Older tasks must be evicted automatically.

------------------------------------------------------------------------

# 9. Table Architecture

The **task table is the core UI component**.

Architecture layers:

    UI Table Component
            ↓
    TanStack Table Engine
            ↓
    Virtualized Renderer
            ↓
    Task Store

Responsibilities:

TanStack Table:

    sorting
    filtering
    search
    column visibility
    column resizing

TanStack Virtual:

    render only visible rows

Example:

    100000 tasks
    DOM rows rendered ≈ 40

------------------------------------------------------------------------

# 10. Table Columns

Recommended columns:

    Task ID
    Task Name
    Worker
    Queue
    Status
    Runtime
    Retries
    Timestamp

Features:

    status badges
    sorting
    status filter
    worker filter
    task search
    column hide/show
    column resize

------------------------------------------------------------------------

# 11. UI Components

Reusable components:

    DataTable
    TaskTable
    TaskRow
    TaskStatusBadge
    MetricCard
    WorkerCard
    TaskDetailDrawer

Task detail drawer shows:

    arguments
    result
    traceback
    runtime
    worker
    queue
    timestamps

------------------------------------------------------------------------

# 12. Performance Requirements

The UI must support:

    10k – 100k tasks
    real-time updates
    smooth scrolling
    low memory usage

Performance techniques:

    virtualized tables
    Map-based state storage
    batched updates
    limited retention window

------------------------------------------------------------------------

# 13. Dashboard Pages

Main pages:

    Dashboard
    Tasks
    Workers
    Queues
    Metrics

Dashboard metrics:

    active workers
    queue size
    task throughput
    task failures
    runtime distribution

------------------------------------------------------------------------

# 14. SSE Processing Pipeline

Event handling pipeline:

    SSE client
         ↓
    event parser
         ↓
    store update
         ↓
    UI refresh

Important rule:

    avoid full table rerenders

Updates must be incremental.

------------------------------------------------------------------------

# 15. UX Capabilities

The UI should support:

    task search
    status filtering
    worker filtering
    sorting
    column resize
    column hide/show
    task detail drawer
    live updates

------------------------------------------------------------------------

# 16. Optional Advanced Features

Future improvements:

    task timeline visualization
    worker load graphs
    queue backlog charts
    task retry heatmaps

Possible chart library:

    ECharts

------------------------------------------------------------------------

# 17. Design Philosophy

The project should follow:

    clean architecture
    strong typing
    modular feature design
    high performance UI
    minimal runtime overhead

Goal:

Build a **modern, scalable and lightweight Celery monitoring UI that
improves significantly upon Flower**.
