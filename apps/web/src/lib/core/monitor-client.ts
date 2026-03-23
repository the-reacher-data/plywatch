import { HttpMonitorClient } from '$lib/core/adapters/http-monitor-client';
import { monitorApiUrl } from '$lib/core/config';

export const monitorClient = new HttpMonitorClient(monitorApiUrl);
