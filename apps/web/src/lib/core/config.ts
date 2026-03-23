import { env } from '$env/dynamic/public';

export const monitorApiUrl = env.PUBLIC_PLYWATCH_API_URL || '';
