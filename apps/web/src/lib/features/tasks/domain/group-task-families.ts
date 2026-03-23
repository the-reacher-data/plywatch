import type { CanvasKind, TaskState, TaskSummary } from '$lib/core/contracts/monitor';

export interface TaskFamilyView {
  root: TaskSummary;
  children: TaskSummary[];
  aggregateState: TaskState;
  totalRetries: number;
  completedCount: number;
  totalCount: number;
  lastSeenAt: string;
  canvasKind: CanvasKind | null;
  displayName: string;
  progressValue: number | null;
  progressTotal: number | null;
}

const runningStates = new Set<TaskState>(['sent', 'received', 'started', 'retrying']);
const queuedOnlyStates = new Set<TaskState>(['sent', 'received']);

function sortByLastSeenDesc(left: TaskSummary, right: TaskSummary): number {
  return right.lastSeenAt.localeCompare(left.lastSeenAt);
}

function sortByFirstSeenAsc(left: TaskSummary, right: TaskSummary): number {
  return left.firstSeenAt.localeCompare(right.firstSeenAt);
}

function isQueuedOnlyTask(task: TaskSummary): boolean {
  return queuedOnlyStates.has(task.state);
}

function familyKey(task: TaskSummary): string {
  return task.rootId ?? task.id;
}

function pickRoot(items: TaskSummary[], key: string): TaskSummary {
  const parentIds = new Set(
    items
      .map((item) => item.parentId)
      .filter((parentId): parentId is string => parentId !== null)
      .filter((parentId) => items.some((item) => item.id === parentId))
  );

  return (
    items.find((item) => item.kind === 'job' && item.id === key && item.parentId !== item.id) ??
    items.find((item) => item.kind === 'job' && item.parentId === null) ??
    items.find((item) => item.kind === 'job' && parentIds.has(item.id)) ??
    items.find((item) => item.id === key && item.parentId !== item.id) ??
    items.find((item) => item.parentId === null) ??
    items.find((item) => parentIds.has(item.id)) ??
    items.find((item) => item.id === key) ??
    [...items].sort(sortByFirstSeenAsc)[0]
  );
}

function aggregateState(root: TaskSummary, items: TaskSummary[]): TaskState {
  // Queued: every item is waiting to be picked up — nothing executing yet.
  if (items.every((item) => queuedOnlyStates.has(item.state))) {
    return 'sent';
  }
  // Any item still in flight (including callbacks/errbacks) keeps the family running.
  if (items.some((item) => runningStates.has(item.state))) {
    return 'started';
  }
  if (root.state === 'failed') {
    return 'failed';
  }
  if (root.state === 'lost') {
    return 'failed';
  }
  const jobItems = items.filter((item) => item.kind === 'job');
  if (jobItems.some((item) => item.state === 'failed' || item.state === 'lost')) {
    return 'failed';
  }
  if (root.kind === 'callback_error') {
    return 'failed';
  }
  return 'succeeded';
}

function familyLastSeenAt(items: TaskSummary[]): string {
  return [...items].sort(sortByLastSeenDesc)[0]?.lastSeenAt ?? '';
}

function completedCount(items: TaskSummary[]): number {
  return items.filter((item) => item.state === 'succeeded' || item.state === 'failed' || item.state === 'lost').length;
}

function familyCanvasKind(items: TaskSummary[]): CanvasKind | null {
  const first = items.find((item) => item.canvasKind !== null);
  return first?.canvasKind ?? null;
}

function familyDisplayName(root: TaskSummary): string {
  return root.name ?? root.id;
}

function isVisibleRootKind(kind: TaskSummary['kind']): boolean {
  return kind !== 'callback' && kind !== 'callback_error';
}

function canvasProgress(items: TaskSummary[], canvasKind: CanvasKind | null): [number | null, number | null] {
  if (canvasKind === null) {
    return [null, null];
  }
  const members = items.filter((item) => item.canvasRole !== null);
  if (members.length === 0) {
    return [null, null];
  }
  const done = members.filter((item) => item.state === 'succeeded' || item.state === 'failed' || item.state === 'lost').length;
  return [done, members.length];
}

function hasVisibleRoot(family: TaskFamilyView): boolean {
  return [family.root, ...family.children].some((item) => isVisibleRootKind(item.kind));
}

function buildFamily(items: TaskSummary[], key: string): TaskFamilyView {
  const root = pickRoot(items, key);
  const children = items
    .filter((item) => item.id !== root.id)
    .sort(sortByFirstSeenAsc);
  const canvasKind = familyCanvasKind(items);
  const [progressValue, progressTotal] = canvasProgress(items, canvasKind);
  return {
    root,
    children,
    aggregateState: aggregateState(root, items),
    totalRetries: items.reduce((sum, item) => sum + item.retries, 0),
    completedCount: completedCount(items),
    totalCount: items.length,
    lastSeenAt: familyLastSeenAt(items),
    canvasKind,
    displayName: familyDisplayName(root),
    progressValue,
    progressTotal,
  } satisfies TaskFamilyView;
}

export function buildTaskFamilies(items: TaskSummary[]): TaskFamilyView[] {
  const grouped = new Map<string, TaskSummary[]>();
  for (const item of items) {
    const key = familyKey(item);
    grouped.set(key, [...(grouped.get(key) ?? []), item]);
  }

  const families = Array.from(grouped.entries()).flatMap(([key, familyItems]) => {
    const root = pickRoot(familyItems, key);
    const detachedQueuedDescendants = isQueuedOnlyTask(root)
      ? []
      : familyItems.filter(
          (item) => item.id !== root.id && item.parentId !== null && isQueuedOnlyTask(item)
        );
    const detachedIds = new Set(detachedQueuedDescendants.map((item) => item.id));
    const remainingItems = familyItems.filter((item) => !detachedIds.has(item.id));

    const result: TaskFamilyView[] = [];
    if (remainingItems.length > 0) {
      result.push(buildFamily(remainingItems, key));
    }
    for (const item of detachedQueuedDescendants.sort(sortByFirstSeenAsc)) {
      result.push(buildFamily([item], item.id));
    }
    return result;
  });

  return families
    .filter(hasVisibleRoot)
    .sort((left, right) => right.lastSeenAt.localeCompare(left.lastSeenAt));
}
