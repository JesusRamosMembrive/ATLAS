#pragma once

#include <nlohmann/json.hpp>
#include <string>
#include <optional>
#include <variant>

namespace aegis::server {

using json = nlohmann::json;

/**
 * JSON-RPC style request from client.
 * Format: {"id": "uuid", "method": "method_name", "params": {...}}
 */
struct Request {
    std::string id;
    std::string method;
    json params;

    static std::optional<Request> parse(const std::string& line) {
        try {
            auto j = json::parse(line);
            Request req;
            req.id = j.value("id", "");
            req.method = j.value("method", "");
            req.params = j.value("params", json::object());
            return req;
        } catch (...) {
            return std::nullopt;
        }
    }
};

/**
 * Error information for failed requests.
 */
struct ErrorInfo {
    std::string message;
    int code = -1;

    json to_json() const {
        return {{"message", message}, {"code", code}};
    }
};

/**
 * JSON-RPC style response to client.
 * Success: {"id": "uuid", "result": {...}}
 * Error:   {"id": "uuid", "error": {"message": "...", "code": N}}
 */
struct Response {
    std::string id;
    std::optional<json> result;
    std::optional<ErrorInfo> error;

    static Response success(const std::string& id, json result) {
        Response resp;
        resp.id = id;
        resp.result = std::move(result);
        return resp;
    }

    static Response failure(const std::string& id, const std::string& message, int code = -1) {
        Response resp;
        resp.id = id;
        resp.error = ErrorInfo{message, code};
        return resp;
    }

    std::string serialize() const {
        json j;
        j["id"] = id;
        if (result) {
            j["result"] = *result;
        }
        if (error) {
            j["error"] = error->to_json();
        }
        return j.dump() + "\n";
    }
};

/**
 * Error codes following JSON-RPC conventions.
 */
namespace ErrorCode {
    constexpr int PARSE_ERROR = -32700;
    constexpr int INVALID_REQUEST = -32600;
    constexpr int METHOD_NOT_FOUND = -32601;
    constexpr int INVALID_PARAMS = -32602;
    constexpr int INTERNAL_ERROR = -32603;
}

}  // namespace aegis::server
