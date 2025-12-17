// SPDX-License-Identifier: MIT
/**
 * Output module that collects results from the pipeline.
 *
 * @contract
 *   role: sink
 *   pattern: chain_of_responsibility
 */

import { BaseModule } from './imodule';

/**
 * Collects and stores processed data.
 *
 * @contract
 *   ownership:
 *     results: owns
 *   thread_safety: not_safe
 */
export class Output extends BaseModule {
    private readonly results: unknown[] = [];

    /**
     * Store received data.
     *
     * @contract
     *   postcondition: data in this.results
     */
    process(data: unknown): unknown {
        this.results.push(data);
        return this.forward(data);
    }

    getResults(): unknown[] {
        return [...this.results];
    }

    clear(): void {
        this.results.length = 0;
    }
}
