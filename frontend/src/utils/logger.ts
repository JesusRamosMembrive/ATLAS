/**
 * Development-only logging utility.
 *
 * In production builds (import.meta.env.PROD), all logging calls become no-ops.
 * This eliminates console.log pollution in production while keeping useful
 * debug output during development.
 */

const isDev = import.meta.env.DEV;

/**
 * Log debug message (only in development)
 */
export const debug = (message: string, ...args: unknown[]): void => {
  if (isDev) {
    console.log(`[DEBUG] ${message}`, ...args);
  }
};

/**
 * Log info message (only in development)
 */
export const info = (message: string, ...args: unknown[]): void => {
  if (isDev) {
    console.info(`[INFO] ${message}`, ...args);
  }
};

/**
 * Log warning message (only in development)
 */
export const warn = (message: string, ...args: unknown[]): void => {
  if (isDev) {
    console.warn(`[WARN] ${message}`, ...args);
  }
};

/**
 * Log error message (always, even in production)
 */
export const error = (message: string, ...args: unknown[]): void => {
  console.error(`[ERROR] ${message}`, ...args);
};

/**
 * Logger object for namespaced logging
 */
export const createLogger = (namespace: string) => ({
  debug: (message: string, ...args: unknown[]) =>
    debug(`[${namespace}] ${message}`, ...args),
  info: (message: string, ...args: unknown[]) =>
    info(`[${namespace}] ${message}`, ...args),
  warn: (message: string, ...args: unknown[]) =>
    warn(`[${namespace}] ${message}`, ...args),
  error: (message: string, ...args: unknown[]) =>
    error(`[${namespace}] ${message}`, ...args),
});

export default { debug, info, warn, error, createLogger };
