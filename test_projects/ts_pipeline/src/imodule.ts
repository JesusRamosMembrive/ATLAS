// SPDX-License-Identifier: MIT
/**
 * Base interface for pipeline modules.
 *
 * @contract
 *   type: interface
 *   pattern: chain_of_responsibility
 */

/**
 * Abstract base interface for pipeline modules.
 * Implements the Chain of Responsibility pattern.
 */
export interface IModule {
    /**
     * Set the next module in the chain.
     *
     * @contract
     *   precondition: module is not null
     *   postcondition: this._next == module
     */
    setNext(module: IModule): IModule;

    /**
     * Process data and pass to next module.
     *
     * @contract
     *   thread_safety: safe_if_immutable_data
     */
    process(data: unknown): unknown;
}

/**
 * Abstract base class implementing IModule.
 */
export abstract class BaseModule implements IModule {
    protected next: IModule | null = null;

    setNext(module: IModule): IModule {
        this.next = module;
        return module;
    }

    abstract process(data: unknown): unknown;

    protected forward(data: unknown): unknown {
        if (this.next !== null) {
            return this.next.process(data);
        }
        return data;
    }
}
