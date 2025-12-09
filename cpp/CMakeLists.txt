cmake_minimum_required(VERSION 3.20)
project(similarity_detector VERSION 1.0.0 LANGUAGES CXX)

# C++20 standard
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Export compile commands for IDE support
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Build type defaults to Release
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Compiler warnings
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(-Wall -Wextra -Wpedantic -Werror=return-type)
    if(CMAKE_BUILD_TYPE STREQUAL "Debug")
        add_compile_options(-g -O0)
    else()
        add_compile_options(-O3)
    endif()
endif()

# =============================================================================
# Dependencies via FetchContent
# =============================================================================
include(FetchContent)

# nlohmann/json for JSON serialization
FetchContent_Declare(
    json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.11.3
)

# Google Test for unit testing
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.14.0
)

# Fetch dependencies
FetchContent_MakeAvailable(json googletest)

# =============================================================================
# Main Library (core functionality)
# =============================================================================
add_library(similarity_core STATIC
    src/core/rolling_hash.cpp
    src/core/hash_index.cpp
    src/core/similarity_detector.cpp
    src/core/clone_extender.cpp
    src/tokenizers/python_normalizer.cpp
    src/tokenizers/js_normalizer.cpp
    src/tokenizers/cpp_normalizer.cpp
    src/server/uds_server.cpp
    src/utils/file_utils.cpp
)

# Threading support
find_package(Threads REQUIRED)
target_link_libraries(similarity_core PUBLIC Threads::Threads)

target_include_directories(similarity_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_link_libraries(similarity_core PUBLIC
    nlohmann_json::nlohmann_json
)

# =============================================================================
# Main Executable
# =============================================================================
add_executable(static_analysis_motor
    src/main.cpp
)

target_link_libraries(static_analysis_motor PRIVATE
    similarity_core
)

# =============================================================================
# Tests
# =============================================================================
enable_testing()

add_executable(similarity_tests
    tests/test_rolling_hash.cpp
    tests/test_python_normalizer.cpp
    tests/test_js_normalizer.cpp
    tests/test_cpp_normalizer.cpp
    tests/test_hash_index.cpp
    tests/test_detector.cpp
    tests/test_phase3.cpp
)

target_link_libraries(similarity_tests PRIVATE
    similarity_core
    GTest::gtest_main
)

# Copy test fixtures to build directory
file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures
     DESTINATION ${CMAKE_CURRENT_BINARY_DIR}/tests)

include(GoogleTest)
gtest_discover_tests(similarity_tests)

# =============================================================================
# Install
# =============================================================================
install(TARGETS static_analysis_motor
    RUNTIME DESTINATION bin
)

# =============================================================================
# Summary
# =============================================================================
message(STATUS "")
message(STATUS "=== Similarity Detector Configuration ===")
message(STATUS "  Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  Compiler: ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
message(STATUS "")
