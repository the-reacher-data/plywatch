import { describe, expect, it } from 'vitest';

import { buildTaskSummaryKpis } from '$lib/features/tasks/components/task-summary-kpis';

describe('task-summary-kpis', () => {
  it('builds labeled task summary counters with help text', () => {
    const kpis = buildTaskSummaryKpis({
      familyCount: 16,
      executionCount: 48,
      totalCompleted: 32,
      totalProgress: 32,
    });

    expect(kpis).toEqual([
      expect.objectContaining({
        key: 'tasks',
        label: 'Tasks',
        value: '16',
      }),
      expect.objectContaining({
        key: 'executions',
        label: 'Executions',
        value: '48',
      }),
      expect.objectContaining({
        key: 'completed',
        label: 'Completed',
        value: '32/32',
      }),
    ]);
    expect(kpis.every((kpi) => kpi.helpText.length > 0)).toBe(true);
  });
});
