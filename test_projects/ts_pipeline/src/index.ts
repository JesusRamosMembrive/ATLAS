// SPDX-License-Identifier: MIT
/**
 * Main composition root for the TypeScript pipeline.
 *
 * This file demonstrates the Chain of Responsibility pattern with:
 * - Generator (source) -> Processor (transform) -> Output (sink)
 *
 * @aegis-composition-root
 */

import { Generator } from './generator';
import { Processor } from './processor';
import { Output } from './output';

/**
 * Create and wire the pipeline components.
 *
 * @contract
 *   type: composition_root
 *   pattern: chain_of_responsibility
 */
function main(): void {
    // Create instances
    const gen = new Generator(5);
    const proc = new Processor((x: unknown) => (x as number) * 2);
    const out = new Output();

    // Wire the pipeline: gen -> proc -> out
    gen.setNext(proc);
    proc.setNext(out);

    // Start the pipeline
    gen.start();

    // Print results
    console.log(`Results: ${JSON.stringify(out.getResults())}`);
    console.log(`Processed count: ${proc.getProcessedCount()}`);

    // Cleanup
    gen.stop();
}

// Run the main function
main();
