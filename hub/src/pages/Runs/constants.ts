export const runStatusForDeleting: TRunStatus[] = ['failed', 'stopped', 'aborted', 'done'];
export const runStatusForStopping: TRunStatus[] = ['submitted', 'pending', 'running'];
export const runStatusForAborting: TRunStatus[] = ['submitted', 'pending', 'running', 'stopping'];
export const unfinishedRuns: TRunStatus[] = ['building', 'running', 'uploading', 'downloading', 'stopping', 'stopped', 'terminating'];
