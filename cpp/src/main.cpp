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
              << "                       Default: **/node_modules/**, **/__pycache__/**\n"
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

CliArgs parse_args(int argc, char* argv[]) {
    CliArgs args;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if (arg == "--help" || arg == "-h") {
            args.show_help = true;
            return args;
        }

        if (arg == "--root" && i + 1 < argc) {
            args.root = argv[++i];
        }
        else if (arg == "--ext" && i + 1 < argc) {
            std::string ext = argv[++i];
            if (ext[0] != '.') ext = "." + ext;
            args.extensions.push_back(ext);
        }
        else if (arg == "--exclude" && i + 1 < argc) {
            args.exclude_patterns.push_back(argv[++i]);
        }
        else if (arg == "--window" && i + 1 < argc) {
            args.window_size = std::stoul(argv[++i]);
        }
        else if (arg == "--min-tokens" && i + 1 < argc) {
            args.min_clone_tokens = std::stoul(argv[++i]);
        }
        else if (arg == "--threshold" && i + 1 < argc) {
            args.similarity_threshold = std::stof(argv[++i]);
        }
        else if (arg == "--type3") {
            args.detect_type3 = true;
        }
        else if (arg == "--max-gap" && i + 1 < argc) {
            args.max_gap_tokens = std::stoul(argv[++i]);
        }
        else if (arg == "--compare" && i + 2 < argc) {
            args.compare_file1 = argv[++i];
            args.compare_file2 = argv[++i];
        }
        else if (arg == "--socket" && i + 1 < argc) {
            args.socket_path = argv[++i];
        }
        else if (arg == "--pretty") {
            args.pretty_print = true;
        }
        else if (arg[0] == '-') {
            args.has_error = true;
            args.error_message = "Unknown option: " + arg;
            return args;
        }
        else {
            // Positional argument - treat as root if not set
            if (args.root.empty()) {
                args.root = arg;
            } else {
                args.has_error = true;
                args.error_message = "Unexpected argument: " + arg;
                return args;
            }
        }
    }

    // Validate
    if (args.root.empty() && args.compare_file1.empty() && args.socket_path.empty()) {
        args.has_error = true;
        args.error_message = "Either --root, --compare, or --socket is required";
        return args;
    }

    // Defaults
    if (args.extensions.empty()) {
        args.extensions = {".py"};
    }

    if (args.exclude_patterns.empty()) {
        args.exclude_patterns = {
            "**/node_modules/**",
            "**/__pycache__/**",
            "**/venv/**",
            "**/.git/**"
        };
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
