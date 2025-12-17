// SPDX-License-Identifier: MIT
/**
 * Generator module that produces data for the pipeline.
 *
 * @contract
 *   role: source
 *   pattern: chain_of_responsibility
 */

import { BaseModule } from './imodule';

/**
 * Generates sequential data for the pipeline.
 *
 * @contract
 *   lifecycle:
 *     phases: [created, started, stopped]
 *     start_method: start
 *     stop_method: stop
 *   ownership:
 *     data: owns
 */
export class Generator extends BaseModule {
    private readonly count: number;
    private data: number[] = [];
    private running: boolean = false;

    constructor(count: number = 10) {
        super();
        this.count = count;
    }

    /**
     * Start generating data.
     *
     * @contract
     *   precondition: not this.running
     *   postcondition: this.running == true
     */
    start(): void {
        this.running = true;
        this.data = Array.from({ length: this.count }, (_, i) => i + 1);
        for (const item of this.data) {
            this.process(item);
        }
    }

    stop(): void {
        this.running = false;
    }

    /**
     * Process and forward generated data.
     *
     * @contract
     *   postcondition: data forwarded to next module
     */
    process(data: unknown): unknown {
        return this.forward(data);
    }
}
