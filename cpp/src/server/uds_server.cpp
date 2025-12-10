#include "server/uds_server.hpp"
#include "utils/file_utils.hpp"
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <poll.h>
#include <cstring>
#include <iostream>
#include <filesystem>

namespace aegis::server {

namespace fs = std::filesystem;

UDSServer::UDSServer(Config config)
    : config_(std::move(config))
{
}

UDSServer::~UDSServer() {
    cleanup();
}

void UDSServer::register_method(const std::string& name, MethodHandler handler) {
    methods_[name] = std::move(handler);
}

bool UDSServer::create_socket() {
    // Remove existing socket file
    unlink(config_.socket_path.c_str());

    // Create socket
    server_fd_ = socket(AF_UNIX, SOCK_STREAM, 0);
    if (server_fd_ < 0) {
        std::cerr << "Failed to create socket: " << strerror(errno) << std::endl;
        return false;
    }

    // Bind to socket path
    struct sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, config_.socket_path.c_str(), sizeof(addr.sun_path) - 1);

    if (bind(server_fd_, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr)) < 0) {
        std::cerr << "Failed to bind socket: " << strerror(errno) << std::endl;
        close(server_fd_);
        server_fd_ = -1;
        return false;
    }

    // Listen for connections
    if (listen(server_fd_, config_.backlog) < 0) {
        std::cerr << "Failed to listen on socket: " << strerror(errno) << std::endl;
        close(server_fd_);
        server_fd_ = -1;
        return false;
    }

    return true;
}

void UDSServer::run() {
    if (!create_socket()) {
        return;
    }

    running_.store(true);
    std::cerr << "Server listening on " << config_.socket_path << std::endl;

    while (!shutdown_requested_.load()) {
        // Use poll for non-blocking accept with timeout
        struct pollfd pfd{};
        pfd.fd = server_fd_;
        pfd.events = POLLIN;

        int poll_result = poll(&pfd, 1, 100);  // 100ms timeout
        if (poll_result < 0) {
            if (errno == EINTR) continue;
            std::cerr << "Poll error: " << strerror(errno) << std::endl;
            break;
        }

        if (poll_result == 0) {
            continue;  // Timeout, check shutdown flag
        }

        // Accept connection
        int client_fd = accept(server_fd_, nullptr, nullptr);
        if (client_fd < 0) {
            if (errno == EINTR) continue;
            std::cerr << "Accept error: " << strerror(errno) << std::endl;
            continue;
        }

        // Handle client (single-threaded for simplicity)
        handle_client(client_fd);
        close(client_fd);
    }

    running_.store(false);
    cleanup();
    std::cerr << "Server shutdown complete" << std::endl;
}

void UDSServer::handle_client(int client_fd) {
    std::string buffer;
    buffer.reserve(config_.buffer_size);
    char chunk[4096];

    while (!shutdown_requested_.load()) {
        // Use poll for non-blocking read
        struct pollfd pfd{};
        pfd.fd = client_fd;
        pfd.events = POLLIN;

        int poll_result = poll(&pfd, 1, 100);
        if (poll_result < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (poll_result == 0) continue;

        ssize_t bytes = read(client_fd, chunk, sizeof(chunk) - 1);
        if (bytes <= 0) {
            break;  // Connection closed or error
        }

        chunk[bytes] = '\0';
        buffer += chunk;

        // Process complete lines
        size_t pos;
        while ((pos = buffer.find('\n')) != std::string::npos) {
            std::string line = buffer.substr(0, pos);
            buffer.erase(0, pos + 1);

            if (line.empty()) continue;

            Response response = process_request(line);
            std::string response_str = response.serialize();

            // Send response
            ssize_t written = write(client_fd, response_str.c_str(), response_str.size());
            if (written < 0) {
                std::cerr << "Write error: " << strerror(errno) << std::endl;
                return;
            }

            // Check for shutdown method
            if (shutdown_requested_.load()) {
                return;
            }
        }
    }
}

Response UDSServer::process_request(const std::string& line) {
    auto req_opt = Request::parse(line);
    if (!req_opt) {
        return Response::failure("", "Failed to parse request", ErrorCode::PARSE_ERROR);
    }

    const auto& req = *req_opt;

    // Find handler
    auto it = methods_.find(req.method);
    if (it == methods_.end()) {
        return Response::failure(req.id, "Method not found: " + req.method,
                                 ErrorCode::METHOD_NOT_FOUND);
    }

    // Execute handler
    try {
        json result = it->second(req.params);
        return Response::success(req.id, std::move(result));
    } catch (const std::exception& e) {
        return Response::failure(req.id, e.what(), ErrorCode::INTERNAL_ERROR);
    }
}

void UDSServer::shutdown() {
    shutdown_requested_.store(true);
}

void UDSServer::cleanup() {
    if (server_fd_ >= 0) {
        close(server_fd_);
        server_fd_ = -1;
    }
    unlink(config_.socket_path.c_str());
}

// =============================================================================
// Factory function with AEGIS methods
// =============================================================================

std::unique_ptr<UDSServer> create_aegis_server(const UDSServer::Config& config) {
    auto server = std::make_unique<UDSServer>(config);

    // Register 'analyze' method
    server->register_method("analyze", [](const json& params) -> json {
        std::string root = params.value("root", "");
        if (root.empty()) {
            throw std::runtime_error("Missing 'root' parameter");
        }

        // Get extensions
        std::vector<std::string> extensions;
        if (params.contains("extensions")) {
            for (const auto& ext : params["extensions"]) {
                extensions.push_back(ext.get<std::string>());
            }
        }
        if (extensions.empty()) {
            extensions = {".py"};  // Default
        }

        // Configure detector
        DetectorConfig cfg;
        cfg.extensions = extensions;
        cfg.window_size = params.value("window_size", 10);
        cfg.min_clone_tokens = params.value("min_tokens", 30);
        cfg.max_gap_tokens = params.value("max_gap", 5);
        cfg.similarity_threshold = params.value("min_similarity", 0.7f);
        cfg.num_threads = params.value("threads", 4);
        cfg.detect_type3 = params.value("type3", false);

        // Run analysis
        SimilarityDetector detector(cfg);
        auto report = detector.analyze(root);

        // Convert to JSON
        return report.to_json();
    });

    // Register the 'file_tree' method
    server->register_method("file_tree", [](const json& params) -> json {
        std::string root = params.value("root", "");
        if (root.empty()) {
            throw std::runtime_error("Missing 'root' parameter");
        }

        std::vector<std::string> extensions;
        if (params.contains("extensions")) {
            for (const auto& ext : params["extensions"]) {
                extensions.push_back(ext.get<std::string>());
            }
        }

        // Build file tree
        json files = json::array();
        for (const auto& entry : fs::recursive_directory_iterator(root)) {
            if (!entry.is_regular_file()) continue;

            std::string ext = entry.path().extension().string();
            if (!extensions.empty()) {
                bool match = false;
                for (const auto& e : extensions) {
                    if (ext == e) { match = true; break; }
                }
                if (!match) continue;
            }

            json file_info;
            file_info["path"] = entry.path().string();
            file_info["name"] = entry.path().filename().string();
            file_info["size"] = entry.file_size();
            files.push_back(file_info);
        }

        return {{"files", files}, {"count", files.size()}};
    });

    // Register 'compare_files' method
    server->register_method("compare_files", [](const json& params) -> json {
        std::string file1 = params.value("file1", "");
        std::string file2 = params.value("file2", "");

        if (file1.empty() || file2.empty()) {
            throw std::runtime_error("Missing 'file1' or 'file2' parameter");
        }

        // Configure detector
        DetectorConfig cfg;
        cfg.window_size = params.value("window_size", 10);
        cfg.min_clone_tokens = params.value("min_tokens", 30);
        cfg.similarity_threshold = params.value("min_similarity", 0.7f);
        cfg.detect_type3 = params.value("type3", false);
        cfg.max_gap_tokens = params.value("max_gap", 5);

        // Run comparison
        SimilarityDetector detector(cfg);
        auto report = detector.compare(file1, file2);

        return report.to_json();
    });

    // Register 'get_hotspots' method
    server->register_method("get_hotspots", [](const json& params) -> json {
        std::string root = params.value("root", "");
        if (root.empty()) {
            throw std::runtime_error("Missing 'root' parameter");
        }

        // Get extensions
        std::vector<std::string> extensions;
        if (params.contains("extensions")) {
            for (const auto& ext : params["extensions"]) {
                extensions.push_back(ext.get<std::string>());
            }
        }
        if (extensions.empty()) {
            extensions = {".py"};
        }

        size_t limit = params.value("limit", 10);

        // Run analysis
        DetectorConfig cfg;
        cfg.extensions = extensions;
        cfg.min_clone_tokens = params.value("min_tokens", 30);
        cfg.similarity_threshold = params.value("min_similarity", 0.7f);

        SimilarityDetector detector(cfg);
        auto report = detector.analyze(root);

        // Extract top hotspots
        json result = json::array();
        size_t count = 0;
        for (const auto& hotspot : report.hotspots) {
            if (count >= limit) break;
            result.push_back({
                {"file", hotspot.file_path},
                {"duplication_score", hotspot.duplication_score},
                {"clone_count", hotspot.clone_count},
                {"duplicated_lines", hotspot.duplicated_lines},
                {"total_lines", hotspot.total_lines}
            });
            count++;
        }

        return {{"hotspots", result}, {"count", count}};
    });

    // Register 'get_file_clones' method
    server->register_method("get_file_clones", [](const json& params) -> json {
        std::string root = params.value("root", "");
        std::string target_file = params.value("file", "");

        if (root.empty() || target_file.empty()) {
            throw std::runtime_error("Missing 'root' or 'file' parameter");
        }

        // Get extensions
        std::vector<std::string> extensions;
        if (params.contains("extensions")) {
            for (const auto& ext : params["extensions"]) {
                extensions.push_back(ext.get<std::string>());
            }
        }
        if (extensions.empty()) {
            extensions = {".py"};
        }

        // Run analysis
        DetectorConfig cfg;
        cfg.extensions = extensions;
        cfg.min_clone_tokens = params.value("min_tokens", 30);
        cfg.similarity_threshold = params.value("min_similarity", 0.7f);

        SimilarityDetector detector(cfg);
        auto report = detector.analyze(root);

        // Filter clones involving the target file
        json file_clones = json::array();
        for (const auto& clone : report.clones) {
            bool involves_file = false;
            for (const auto& loc : clone.locations) {
                // Check if path contains target file (could be absolute or relative)
                if (loc.file.find(target_file) != std::string::npos ||
                    target_file.find(loc.file) != std::string::npos) {
                    involves_file = true;
                    break;
                }
            }
            if (involves_file) {
                file_clones.push_back(clone.to_json());
            }
        }

        return {{"file", target_file}, {"clones", file_clones}, {"count", file_clones.size()}};
    });

    // Register 'get_cache_stats' method
    server->register_method("get_cache_stats", [](const json& /*params*/) -> json {
        // Create a detector to access cache stats
        // Note: Each call creates a new detector with its own cache
        // In a production system, we'd want a persistent detector instance
        return {
            {"message", "Cache stats not available in stateless mode"},
            {"note", "Each request creates a new detector instance"}
        };
    });

    // Note: 'shutdown' method must be registered by caller who has access to the server pointer
    // This avoids capturing a reference that becomes invalid

    return server;
}

}  // namespace aegis::server
