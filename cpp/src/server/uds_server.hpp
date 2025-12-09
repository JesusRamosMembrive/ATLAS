#pragma once

#include "json_protocol.hpp"
#include "core/similarity_detector.hpp"
#include <string>
#include <functional>
#include <atomic>
#include <unordered_map>
#include <memory>

namespace aegis::server {

using namespace aegis::similarity;

/**
 * Method handler function type.
 * Takes request params, returns response JSON or throws for errors.
 */
using MethodHandler = std::function<json(const json& params)>;

/**
 * Server configuration.
 */
struct ServerConfig {
    std::string socket_path = "/tmp/aegis-cpp.sock";
    int backlog = 5;
    size_t buffer_size = 65536;
};

/**
 * Unix Domain Socket server for code analysis.
 *
 * Protocol:
 * - Newline-delimited JSON messages
 * - Request:  {"id": "uuid", "method": "name", "params": {...}}
 * - Response: {"id": "uuid", "result": {...}} or {"id": "uuid", "error": {...}}
 *
 * Supported methods:
 * - analyze: Run similarity analysis on a directory
 * - file_tree: Get file tree for a directory
 * - shutdown: Gracefully stop the server
 */
class UDSServer {
public:
    using Config = ServerConfig;

    /**
     * Construct server with configuration.
     */
    explicit UDSServer(Config config = {});

    /**
     * Destructor - ensures cleanup.
     */
    ~UDSServer();

    // Non-copyable
    UDSServer(const UDSServer&) = delete;
    UDSServer& operator=(const UDSServer&) = delete;

    /**
     * Register a method handler.
     */
    void register_method(const std::string& name, MethodHandler handler);

    /**
     * Start the server (blocking).
     * Returns when shutdown is requested.
     */
    void run();

    /**
     * Request server shutdown.
     * Can be called from another thread or signal handler.
     */
    void shutdown();

    /**
     * Check if server is running.
     */
    bool is_running() const { return running_.load(); }

private:
    Config config_;
    int server_fd_ = -1;
    std::atomic<bool> running_{false};
    std::atomic<bool> shutdown_requested_{false};
    std::unordered_map<std::string, MethodHandler> methods_;

    /**
     * Create and bind the Unix socket.
     */
    bool create_socket();

    /**
     * Handle a single client connection.
     */
    void handle_client(int client_fd);

    /**
     * Process a single request line and return response.
     */
    Response process_request(const std::string& line);

    /**
     * Clean up server resources.
     */
    void cleanup();
};

/**
 * Create a UDS server with standard AEGIS methods registered.
 *
 * Methods:
 * - analyze: {"root": "/path", "extensions": [".py"], ...}
 * - file_tree: {"root": "/path", "extensions": [".py"]}
 * - shutdown: {}
 */
std::unique_ptr<UDSServer> create_aegis_server(const UDSServer::Config& config = {});

}  // namespace aegis::server
