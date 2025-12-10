#include "utils/file_utils.hpp"
#include <algorithm>
#include <regex>

namespace aegis::similarity {

std::optional<std::string> FileUtils::read_file(const std::filesystem::path& path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) {
        return std::nullopt;
    }

    std::ostringstream ss;
    ss << file.rdbuf();

    if (file.fail() && !file.eof()) {
        return std::nullopt;
    }

    return ss.str();
}

std::string FileUtils::get_extension(const std::filesystem::path& path) {
    return path.extension().string();
}

std::vector<std::filesystem::path> FileUtils::find_files(
    const std::filesystem::path& root,
    const std::vector<std::string>& extensions,
    const std::vector<std::string>& exclude_patterns
) {
    std::vector<std::filesystem::path> result;

    if (!std::filesystem::exists(root) || !std::filesystem::is_directory(root)) {
        return result;
    }

    try {
        for (const auto& entry : std::filesystem::recursive_directory_iterator(
            root,
            std::filesystem::directory_options::skip_permission_denied
        )) {
            if (!entry.is_regular_file()) {
                continue;
            }

            const auto& path = entry.path();

            // Check extension
            if (!has_allowed_extension(path, extensions)) {
                continue;
            }

            // Check exclusion patterns
            if (auto rel_path = relative_path(path, root); matches_any_pattern(std::filesystem::path(rel_path), exclude_patterns)) {
                continue;
            }

            result.push_back(path);
        }
    } catch (const std::filesystem::filesystem_error& e) {
        // Log error but continue
        // In production, we'd want proper logging here
    }

    // Sort for deterministic order
    std::ranges::sort(result);

    return result;
}

bool FileUtils::matches_any_pattern(
    const std::filesystem::path& path,
    const std::vector<std::string>& patterns
) {
    for (const auto& pattern : patterns) {
        if (matches_pattern(path, pattern)) {
            return true;
        }
    }
    return false;
}

bool FileUtils::matches_pattern(
    const std::filesystem::path& path,
    const std::string_view pattern
) {
    const std::string path_str = path.generic_string();

    // Convert glob pattern to regex
    std::string regex_str;
    regex_str.reserve(pattern.size() * 2);

    size_t i = 0;
    while (i < pattern.size()) {
        char c = pattern[i];

        if (c == '*') {
            if (i + 1 < pattern.size() && pattern[i + 1] == '*') {
                // ** matches any number of directories
                regex_str += ".*";
                i += 2;
                // Skip the following /
                if (i < pattern.size() && pattern[i] == '/') {
                    i++;
                }
            } else {
                // * matches anything except /
                regex_str += "[^/]*";
                i++;
            }
        } else if (c == '?') {
            regex_str += "[^/]";
            i++;
        } else if (c == '.' || c == '[' || c == ']' || c == '(' || c == ')' ||
                   c == '{' || c == '}' || c == '+' || c == '^' || c == '$' ||
                   c == '|' || c == '\\') {
            // Escape regex special characters
            regex_str += '\\';
            regex_str += c;
            i++;
        } else {
            regex_str += c;
            i++;
        }
    }

    try {
        const std::regex re(regex_str, std::regex::icase);
        return std::regex_search(path_str, re);
    } catch (const std::regex_error&) {
        return false;
    }
}

std::string FileUtils::relative_path(
    const std::filesystem::path& path,
    const std::filesystem::path& base
) {
    try {
        return std::filesystem::relative(path, base).generic_string();
    } catch (const std::filesystem::filesystem_error&) {
        return path.generic_string();
    }
}

bool FileUtils::has_allowed_extension(
    const std::filesystem::path& path,
    const std::vector<std::string>& extensions
) {
    const std::string ext = get_extension(path);
    if (ext.empty()) {
        return false;
    }

    for (const auto& allowed : extensions) {
        if (ext == allowed) {
            return true;
        }
    }

    return false;
}

}  // namespace aegis::similarity
