#pragma once

#include <vector>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <functional>
#include <future>
#include <atomic>
#include <memory>
#include <stdexcept>

namespace aegis::similarity {

/**
 * A simple thread pool for parallel task execution.
 *
 * Provides efficient execution of tasks across multiple threads,
 * with automatic load balancing and synchronization.
 */
class ThreadPool {
public:
    /**
     * Create a thread pool with the specified number of threads.
     *
     * @param num_threads Number of worker threads (0 = hardware concurrency)
     */
    explicit ThreadPool(size_t num_threads = 0);

    /**
     * Destructor waits for all tasks to complete.
     */
    ~ThreadPool();

    // Non-copyable, non-movable
    ThreadPool(const ThreadPool&) = delete;
    ThreadPool& operator=(const ThreadPool&) = delete;
    ThreadPool(ThreadPool&&) = delete;
    ThreadPool& operator=(ThreadPool&&) = delete;

    /**
     * Submit a task to the thread pool.
     *
     * @param f The callable to execute
     * @param args Arguments to pass to the callable
     * @return A future for the task's return value
     */
    template<typename F, typename... Args>
    auto submit(F&& f, Args&&... args)
        -> std::future<std::invoke_result_t<F, Args...>>
    {
        using return_type = std::invoke_result_t<F, Args...>;

        auto task = std::make_shared<std::packaged_task<return_type()>>(
            std::bind(std::forward<F>(f), std::forward<Args>(args)...)
        );

        std::future<return_type> result = task->get_future();

        {
            std::unique_lock<std::mutex> lock(queue_mutex_);

            if (stop_) {
                throw std::runtime_error("Cannot submit to stopped ThreadPool");
            }

            tasks_.emplace([task]() { (*task)(); });
        }

        condition_.notify_one();
        return result;
    }

    /**
     * Execute a function in parallel over a range.
     *
     * @param begin Start index
     * @param end End index (exclusive)
     * @param f Function to call with each index
     */
    template<typename F>
    void parallel_for(size_t begin, size_t end, F&& f) {
        if (begin >= end) return;

        size_t num_tasks = end - begin;
        size_t num_workers = std::min(num_tasks, workers_.size());

        if (num_workers <= 1) {
            // Single-threaded execution
            for (size_t i = begin; i < end; ++i) {
                f(i);
            }
            return;
        }

        // Divide work among threads
        size_t chunk_size = (num_tasks + num_workers - 1) / num_workers;
        std::vector<std::future<void>> futures;
        futures.reserve(num_workers);

        for (size_t t = 0; t < num_workers; ++t) {
            size_t chunk_begin = begin + t * chunk_size;
            size_t chunk_end = std::min(chunk_begin + chunk_size, end);

            if (chunk_begin >= end) break;

            futures.push_back(submit([&f, chunk_begin, chunk_end]() {
                for (size_t i = chunk_begin; i < chunk_end; ++i) {
                    f(i);
                }
            }));
        }

        // Wait for all chunks to complete
        for (auto& future : futures) {
            future.get();
        }
    }

    /**
     * Process items in parallel and collect results.
     *
     * @param items Items to process
     * @param f Function to apply to each item
     * @return Results in the same order as input
     */
    template<typename T, typename F>
    auto parallel_map(const std::vector<T>& items, F&& f)
        -> std::vector<std::invoke_result_t<F, const T&>>
    {
        using result_type = std::invoke_result_t<F, const T&>;

        if (items.empty()) {
            return {};
        }

        std::vector<result_type> results(items.size());

        parallel_for(0, items.size(), [&](size_t i) {
            results[i] = f(items[i]);
        });

        return results;
    }

    /**
     * Get the number of worker threads.
     */
    size_t size() const { return workers_.size(); }

    /**
     * Get the number of pending tasks.
     */
    size_t pending() const {
        std::unique_lock<std::mutex> lock(queue_mutex_);
        return tasks_.size();
    }

    /**
     * Wait for all pending tasks to complete.
     */
    void wait_all();

private:
    void worker_thread();

    std::vector<std::thread> workers_;
    std::queue<std::function<void()>> tasks_;

    mutable std::mutex queue_mutex_;
    std::condition_variable condition_;
    std::condition_variable completion_condition_;
    std::atomic<bool> stop_{false};
    std::atomic<size_t> active_tasks_{0};
};

// Implementation

inline ThreadPool::ThreadPool(size_t num_threads) {
    if (num_threads == 0) {
        num_threads = std::thread::hardware_concurrency();
        if (num_threads == 0) {
            num_threads = 4;  // Fallback
        }
    }

    workers_.reserve(num_threads);
    for (size_t i = 0; i < num_threads; ++i) {
        workers_.emplace_back(&ThreadPool::worker_thread, this);
    }
}

inline ThreadPool::~ThreadPool() {
    {
        std::unique_lock<std::mutex> lock(queue_mutex_);
        stop_ = true;
    }
    condition_.notify_all();

    for (auto& worker : workers_) {
        if (worker.joinable()) {
            worker.join();
        }
    }
}

inline void ThreadPool::worker_thread() {
    while (true) {
        std::function<void()> task;

        {
            std::unique_lock<std::mutex> lock(queue_mutex_);
            condition_.wait(lock, [this] {
                return stop_ || !tasks_.empty();
            });

            if (stop_ && tasks_.empty()) {
                return;
            }

            task = std::move(tasks_.front());
            tasks_.pop();
            ++active_tasks_;
        }

        task();

        {
            std::unique_lock<std::mutex> lock(queue_mutex_);
            --active_tasks_;
            if (active_tasks_ == 0 && tasks_.empty()) {
                completion_condition_.notify_all();
            }
        }
    }
}

inline void ThreadPool::wait_all() {
    std::unique_lock<std::mutex> lock(queue_mutex_);
    completion_condition_.wait(lock, [this] {
        return tasks_.empty() && active_tasks_ == 0;
    });
}

}  // namespace aegis::similarity
