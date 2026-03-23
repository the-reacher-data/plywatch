export interface TaskSummaryKpi {
  key: 'tasks' | 'executions' | 'completed';
  label: string;
  value: string;
  helpText: string;
}

export function buildTaskSummaryKpis(args: {
  familyCount: number;
  executionCount: number;
  totalCompleted: number;
  totalProgress: number;
}): TaskSummaryKpi[] {
  return [
    {
      key: 'tasks',
      label: 'Tasks',
      value: String(args.familyCount),
      helpText: 'Logical task rows after grouping related executions into one visible task.',
    },
    {
      key: 'executions',
      label: 'Executions',
      value: String(args.executionCount),
      helpText: 'Raw retained executions before grouping, including subtasks and callbacks.',
    },
    {
      key: 'completed',
      label: 'Completed',
      value: `${args.totalCompleted}/${args.totalProgress}`,
      helpText: 'Completed executions over total executions in the currently loaded task families.',
    },
  ];
}
