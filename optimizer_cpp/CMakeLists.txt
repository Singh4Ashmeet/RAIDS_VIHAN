cmake_minimum_required(VERSION 3.16)

project(raid_nexus_dispatch_optimizer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)

FetchContent_Declare(
    nlohmann_json
    URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
)
FetchContent_MakeAvailable(nlohmann_json)

add_executable(raid_optimizer src/main.cpp)
target_link_libraries(raid_optimizer PRIVATE nlohmann_json::nlohmann_json)
target_compile_features(raid_optimizer PRIVATE cxx_std_17)
