// SPDX-License-Identifier: MIT
/**
 * Processor module that transforms data in the pipeline.
 *
 * @contract
 *   role: processing
 *   pattern: chain_of_responsibility
 */

import { BaseModule } from './imodule';

type TransformFn = (data: unknown) => unknown;

/**
 * Transforms data using a configurable function.
 *
 * @contract
 *   thread_safety: safe_after_start
 *   invariants:
 *     - transform function must be pure
 */
export class Processor extends BaseModule {
    private readonly transform: TransformFn;
    private processedCount: number = 0;

    constructor(transform?: TransformFn) {
        super();
        this.transform = transform || ((x: unknown) => (x as number) * 2);
    }

    /**
     * Transform data and forward to next module.
     *
     * @contract
     *   precondition: data is not null
     *   postcondition: result == transform(data)
     */
    process(data: unknown): unknown {
        const result = this.transform(data);
        this.processedCount++;
        return this.forward(result);
    }

    getProcessedCount(): number {
        return this.processedCount;
    }
}
