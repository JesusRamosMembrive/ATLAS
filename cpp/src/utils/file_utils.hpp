#pragma once

#include <string>
#include <string_view>
#include <vector>
#include <filesystem>
#include <optional>
#include <fstream>
#include <sstream>

namespace aegis::similarity {

/**
 * Utility functions for file operations.
 */
class FileUtils {
public:
    /**
     * Read entire file contents into a string.
     *
     * @param path Path to the file
     * @return File contents or nullopt if read fails
     */
    static std::optional<std::string> read_file(const std::filesystem::path& path);

    /**
     * Get file extension (including dot).
     */
    static std::string get_extension(const std::filesystem::path& path);

    /**
     * Find all files matching extensions in a directory.
     *
     * @param root Root directory to search
     * @param extensions File extensions to include (e.g., {".py", ".js"})
     * @param exclude_patterns Glob patterns to exclude (e.g., node_modules, __pycache__)
     * @return List of matching file paths
     */
    static std::vector<std::filesystem::path> find_files(
        const std::filesystem::path& root,
        const std::vector<std::string>& extensions,
        const std::vector<std::string>& exclude_patterns = {}
    );

    /**
     * Check if a path matches any of the exclusion patterns.
     *
     * Supports simple glob patterns:
     * - ** matches any number of directories
     * - * matches any sequence of characters in a single path component
     *
     * @param path The path to check
     * @param patterns The patterns to match against
     * @return true if path matches any pattern
     */
    static bool matches_any_pattern(
        const std::filesystem::path& path,
        const std::vector<std::string>& patterns
    );

    /**
     * Check if a path matches a single glob pattern.
     */
    static bool matches_pattern(
        const std::filesystem::path& path,
        std::string_view pattern
    );

    /**
     * Get relative path from a base directory.
     */
    static std::string relative_path(
        const std::filesystem::path& path,
        const std::filesystem::path& base
    );

    /**
     * Check if extension is in the allowed list.
     */
    static bool has_allowed_extension(
        const std::filesystem::path& path,
        const std::vector<std::string>& extensions
    );
};

}  // namespace aegis::similarity
