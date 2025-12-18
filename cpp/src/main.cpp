#include "core/similarity_detector.hpp"
#include "server/uds_server.hpp"
#include "utils/file_utils.hpp"
#include <iostream>
#include <string>
#include <vector>
#include <cstring>
#include <csignal>

using namespace aegis::similarity;
using namespace aegis::server;

// Global server pointer for signal handling
static UDSServer* g_server = nullptr;

void signal_handler(int) {
    if (g_server) {
        g_server->shutdown();
    }
}

void print_usage(const char* program) {
    std::cerr << "Usage: " << program << " [OPTIONS]\n"
              << "\n"
              << "Code Similarity Detector - Detect duplicate/similar code\n"
              << "\n"
              << "Options:\n"
              << "  --root <path>        Root directory to analyze (required)\n"
              << "  --ext <extension>    File extension to include (can be repeated)\n"
              << "                       Default: .py\n"
              << "  --exclude <pattern>  Glob pattern to exclude (can be repeated)\n"
              << "                       Default: node_modules, __pycache__, venv, .git,\n"
              << "                                _deps, build, cmake-build-*, vendor, etc.\n"
              << "  --window <size>      Rolling hash window size (default: 10)\n"
              << "  --min-tokens <n>     Minimum tokens for clone (default: 30)\n"
              << "  --threshold <f>      Similarity threshold 0.0-1.0 (default: 0.7)\n"
              << "  --type3              Enable Type-3 detection (clones with gaps)\n"
              << "  --max-gap <n>        Maximum gap for Type-3 detection (default: 5)\n"
              << "  --compare <f1> <f2>  Compare two specific files\n"
              << "  --socket <path>      Run as server on Unix socket\n"
              << "  --pretty             Pretty-print JSON output\n"
              << "  --help               Show this help message\n"
              << "\n"
              << "Examples:\n"
              << "  " << program << " --root ./src --ext .py\n"
              << "  " << program << " --root ./project --ext .py --ext .js --min-tokens 50\n"
              << "  " << program << " --compare file1.py file2.py\n"
              << "  " << program << " --socket /tmp/aegis-cpp.sock\n"
              << "\n";
}

struct CliArgs {
    std::string root;
    std::vector<std::string> extensions;
    std::vector<std::string> exclude_patterns;
    size_t window_size = 10;
    size_t min_clone_tokens = 30;
    float similarity_threshold = 0.7f;
    bool detect_type3 = false;
    size_t max_gap_tokens = 5;
    bool pretty_print = false;
    std::string compare_file1;
    std::string compare_file2;
    std::string socket_path;  // Server mode
    bool show_help = false;
    bool has_error = false;
    std::string error_message;
};

// -----------------------------------------------------------------------------
// Argument parsing helpers (reduce cyclomatic complexity of parse_args)
// -----------------------------------------------------------------------------

namespace {

bool try_parse_help(const std::string& arg, CliArgs& args) {
    if (arg == "--help" || arg == "-h") {
        args.show_help = true;
        return true;
    }
    return false;
}

bool try_parse_string_arg(const std::string& arg, const char* name,
                          int& i, int argc, char* argv[], std::string& target) {
    if (arg == name && i + 1 < argc) {
        target = argv[++i];
        return true;
    }
    return false;
}

bool try_parse_extension(const std::string& arg, int& i, int argc, char* argv[], CliArgs& args) {
    if (arg == "--ext" && i + 1 < argc) {
        std::string ext = argv[++i];
        if (ext[0] != '.') ext = "." + ext;
        args.extensions.push_back(ext);
        return true;
    }
    return false;
}

bool try_parse_exclude(const std::string& arg, int& i, int argc, char* argv[], CliArgs& args) {
    if (arg == "--exclude" && i + 1 < argc) {
        args.exclude_patterns.push_back(argv[++i]);
        return true;
    }
    return false;
}

bool try_parse_size_arg(const std::string& arg, const char* name,
                        int& i, int argc, char* argv[], size_t& target) {
    if (arg == name && i + 1 < argc) {
        target = std::stoul(argv[++i]);
        return true;
    }
    return false;
}

bool try_parse_float_arg(const std::string& arg, const char* name,
                         int& i, int argc, char* argv[], float& target) {
    if (arg == name && i + 1 < argc) {
        target = std::stof(argv[++i]);
        return true;
    }
    return false;
}

bool try_parse_flag(const std::string& arg, const char* name, bool& target) {
    if (arg == name) {
        target = true;
        return true;
    }
    return false;
}

bool try_parse_compare(const std::string& arg, int& i, int argc, char* argv[], CliArgs& args) {
    if (arg == "--compare" && i + 2 < argc) {
        args.compare_file1 = argv[++i];
        args.compare_file2 = argv[++i];
        return true;
    }
    return false;
}

bool try_parse_positional(const std::string& arg, CliArgs& args) {
    if (arg[0] == '-') return false;
    if (args.root.empty()) {
        args.root = arg;
        return true;
    }
    args.has_error = true;
    args.error_message = "Unexpected argument: " + arg;
    return true;  // Handled (with error)
}

void set_error_unknown_option(const std::string& arg, CliArgs& args) {
    args.has_error = true;
    args.error_message = "Unknown option: " + arg;
}

void validate_required_args(CliArgs& args) {
    if (args.root.empty() && args.compare_file1.empty() && args.socket_path.empty()) {
        args.has_error = true;
        args.error_message = "Either --root, --compare, or --socket is required";
    }
}

void apply_defaults(CliArgs& args) {
    if (args.extensions.empty()) {
        args.extensions = {".py"};
    }

    if (args.exclude_patterns.empty()) {
        args.exclude_patterns = {
            "**/node_modules/**",
            "**/__pycache__/**",
            "**/venv/**",
            "**/.git/**",
            "**/_deps/**",
            "**/build/**",
            "**/cmake-build-*/**",
            "**/vcpkg_installed/**",
            "**/third_party/**",
            "**/vendor/**",
            "**/external/**"
        };
    }
}

}  // anonymous namespace

// -----------------------------------------------------------------------------
// Main parse_args (refactored to use helpers)
// -----------------------------------------------------------------------------

CliArgs parse_args(int argc, char* argv[]) {
    CliArgs args;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        // Early return for help
        if (try_parse_help(arg, args)) return args;

        // Try each argument type
        if (try_parse_string_arg(arg, "--root", i, argc, argv, args.root)) continue;
        if (try_parse_extension(arg, i, argc, argv, args)) continue;
        if (try_parse_exclude(arg, i, argc, argv, args)) continue;
        if (try_parse_size_arg(arg, "--window", i, argc, argv, args.window_size)) continue;
        if (try_parse_size_arg(arg, "--min-tokens", i, argc, argv, args.min_clone_tokens)) continue;
        if (try_parse_float_arg(arg, "--threshold", i, argc, argv, args.similarity_threshold)) continue;
        if (try_parse_flag(arg, "--type3", args.detect_type3)) continue;
        if (try_parse_size_arg(arg, "--max-gap", i, argc, argv, args.max_gap_tokens)) continue;
        if (try_parse_compare(arg, i, argc, argv, args)) continue;
        if (try_parse_string_arg(arg, "--socket", i, argc, argv, args.socket_path)) continue;
        if (try_parse_flag(arg, "--pretty", args.pretty_print)) continue;
        if (try_parse_positional(arg, args)) {
            if (args.has_error) return args;
            continue;
        }

        // Unknown option
        set_error_unknown_option(arg, args);
        return args;
    }

    validate_required_args(args);
    if (!args.has_error) {
        apply_defaults(args);
    }

    return args;
}

int main(int argc, char* argv[]) {
    auto args = parse_args(argc, argv);

    if (args.show_help) {
        print_usage(argv[0]);
        return 0;
    }

    if (args.has_error) {
        std::cerr << "Error: " << args.error_message << "\n\n";
        print_usage(argv[0]);
        return 1;
    }

    // Server mode
    if (!args.socket_path.empty()) {
        UDSServer::Config server_config;
        server_config.socket_path = args.socket_path;

        auto server = create_aegis_server(server_config);
        g_server = server.get();

        // Register shutdown method (needs access to g_server)
        server->register_method("shutdown", [](const nlohmann::json&) -> nlohmann::json {
            if (g_server) {
                g_server->shutdown();
            }
            return {{"status", "shutting_down"}};
        });

        // Set up signal handlers
        std::signal(SIGINT, signal_handler);
        std::signal(SIGTERM, signal_handler);

        server->run();
        g_server = nullptr;
        return 0;
    }

    // Configure detector
    DetectorConfig config;
    config.window_size = args.window_size;
    config.min_clone_tokens = args.min_clone_tokens;
    config.similarity_threshold = args.similarity_threshold;
    config.detect_type3 = args.detect_type3;
    config.max_gap_tokens = args.max_gap_tokens;
    config.extensions = args.extensions;
    config.exclude_patterns = args.exclude_patterns;

    SimilarityDetector detector(config);

    // Run analysis
    SimilarityReport report;

    try {
        if (!args.compare_file1.empty()) {
            // Compare two files
            report = detector.compare(args.compare_file1, args.compare_file2);
        } else {
            // Analyze directory
            report = detector.analyze(args.root);
        }
    } catch (const std::exception& e) {
        // Return error as JSON
        nlohmann::json error_response;
        error_response["error"] = {
            {"message", std::string("Analysis failed: ") + e.what()}
        };
        std::cout << error_response.dump(args.pretty_print ? 2 : -1) << "\n";
        return 1;
    }

    // Output report
    if (args.pretty_print) {
        std::cout << report.to_json_string(2) << "\n";
    } else {
        std::cout << report.to_json_string(-1) << "\n";
    }

    return 0;
}
