#pragma once

#include <unordered_map>
#include <list>
#include <mutex>
#include <optional>
#include <functional>
#include <cstddef>

namespace aegis::similarity {

/**
 * Thread-safe LRU (Least Recently Used) cache.
 *
 * Provides O(1) lookup and eviction of least recently used items
 * when the cache reaches capacity.
 *
 * @tparam Key The key type
 * @tparam Value The value type
 */
template<typename Key, typename Value>
class LRUCache {
public:
    /**
     * Create an LRU cache with the specified capacity.
     *
     * @param capacity Maximum number of items to store
     */
    explicit LRUCache(size_t capacity)
        : capacity_(capacity)
    {
    }

    /**
     * Get a value from the cache.
     *
     * Moves the item to the front (most recently used).
     *
     * @param key The key to look up
     * @return The value if found, nullopt otherwise
     */
    std::optional<Value> get(const Key& key) {
        std::lock_guard<std::mutex> lock(mutex_);

        auto it = map_.find(key);
        if (it == map_.end()) {
            return std::nullopt;
        }

        // Move to front (most recently used)
        list_.splice(list_.begin(), list_, it->second);
        return it->second->second;
    }

    /**
     * Get a value, computing it if not present.
     *
     * @param key The key to look up
     * @param compute Function to compute the value if not cached
     * @return The cached or computed value
     */
    template<typename F>
    Value get_or_compute(const Key& key, F&& compute) {
        {
            std::lock_guard<std::mutex> lock(mutex_);

            auto it = map_.find(key);
            if (it != map_.end()) {
                // Move to front
                list_.splice(list_.begin(), list_, it->second);
                return it->second->second;
            }
        }

        // Compute outside the lock (may take time)
        Value value = compute();

        // Insert into cache
        put(key, value);
        return value;
    }

    /**
     * Insert or update a value in the cache.
     *
     * @param key The key
     * @param value The value to store
     */
    void put(const Key& key, const Value& value) {
        std::lock_guard<std::mutex> lock(mutex_);

        auto it = map_.find(key);
        if (it != map_.end()) {
            // Update existing entry
            it->second->second = value;
            list_.splice(list_.begin(), list_, it->second);
            return;
        }

        // Check capacity
        if (map_.size() >= capacity_) {
            // Evict least recently used
            auto& lru = list_.back();
            map_.erase(lru.first);
            list_.pop_back();
        }

        // Insert new entry at front
        list_.emplace_front(key, value);
        map_[key] = list_.begin();
    }

    /**
     * Insert or update a value (move version).
     */
    void put(const Key& key, Value&& value) {
        std::lock_guard<std::mutex> lock(mutex_);

        auto it = map_.find(key);
        if (it != map_.end()) {
            it->second->second = std::move(value);
            list_.splice(list_.begin(), list_, it->second);
            return;
        }

        if (map_.size() >= capacity_) {
            auto& lru = list_.back();
            map_.erase(lru.first);
            list_.pop_back();
        }

        list_.emplace_front(key, std::move(value));
        map_[key] = list_.begin();
    }

    /**
     * Check if a key exists in the cache.
     *
     * Does NOT update the access order.
     */
    bool contains(const Key& key) const {
        std::lock_guard<std::mutex> lock(mutex_);
        return map_.find(key) != map_.end();
    }

    /**
     * Remove a key from the cache.
     *
     * @return true if the key was removed
     */
    bool remove(const Key& key) {
        std::lock_guard<std::mutex> lock(mutex_);

        auto it = map_.find(key);
        if (it == map_.end()) {
            return false;
        }

        list_.erase(it->second);
        map_.erase(it);
        return true;
    }

    /**
     * Clear all entries from the cache.
     */
    void clear() {
        std::lock_guard<std::mutex> lock(mutex_);
        map_.clear();
        list_.clear();
    }

    /**
     * Get the current number of items in the cache.
     */
    size_t size() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return map_.size();
    }

    /**
     * Get the cache capacity.
     */
    size_t capacity() const {
        return capacity_;
    }

    /**
     * Check if the cache is empty.
     */
    bool empty() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return map_.empty();
    }

    /**
     * Cache statistics.
     */
    struct Stats {
        size_t hits = 0;
        size_t misses = 0;
        size_t current_size = 0;
        size_t capacity = 0;

        [[nodiscard]] float hit_rate() const {
            size_t total = hits + misses;
            return total > 0 ? static_cast<float>(hits) / static_cast<float>(total) : 0.0f;
        }
    };

    /**
     * Get cache statistics (requires tracking enabled).
     */
    Stats get_stats() const {
        std::lock_guard<std::mutex> lock(mutex_);
        Stats stats;
        stats.hits = hits_;
        stats.misses = misses_;
        stats.current_size = map_.size();
        stats.capacity = capacity_;
        return stats;
    }

    /**
     * Reset statistics counters.
     */
    void reset_stats() const
    {
        std::lock_guard<std::mutex> lock(mutex_);
        hits_ = 0;
        misses_ = 0;
    }

private:
    using ListType = std::list<std::pair<Key, Value>>;
    using MapType = std::unordered_map<Key, typename ListType::iterator>;

    size_t capacity_;
    ListType list_;          // Front = most recently used
    MapType map_;            // Key -> list iterator

    mutable std::mutex mutex_;

    // Statistics (optional tracking)
    mutable size_t hits_ = 0;
    mutable size_t misses_ = 0;
};

/**
 * Specialized cache for tokenized files.
 * Uses file modification time to invalidate entries.
 */
template<typename Value>
class FileCache {
public:
    struct CacheEntry {
        Value value;
        std::time_t mtime;  // Modification time when cached
    };

    explicit FileCache(size_t capacity)
        : cache_(capacity)
    {
    }

    /**
     * Get a cached file, checking if it's still valid.
     *
     * @param path File path
     * @param current_mtime Current file modification time
     * @return The cached value if valid, nullopt otherwise
     */
    std::optional<Value> get(const std::string& path, std::time_t current_mtime) {
        auto entry = cache_.get(path);
        if (entry && entry->mtime == current_mtime) {
            return entry->value;
        }
        return std::nullopt;
    }

    /**
     * Store a file in the cache.
     */
    void put(const std::string& path, const Value& value, std::time_t mtime) {
        cache_.put(path, CacheEntry{value, mtime});
    }

    void put(const std::string& path, Value&& value, std::time_t mtime) {
        cache_.put(path, CacheEntry{std::move(value), mtime});
    }

    /**
     * Invalidate a specific file.
     */
    bool invalidate(const std::string& path) {
        return cache_.remove(path);
    }

    /**
     * Clear all cached files.
     */
    void clear() {
        cache_.clear();
    }

    [[nodiscard]] size_t size() const { return cache_.size(); }
    [[nodiscard]] size_t capacity() const { return cache_.capacity(); }

private:
    LRUCache<std::string, CacheEntry> cache_;
};

}  // namespace aegis::similarity
