#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

using json = nlohmann::json;

namespace {

constexpr double kEarthRadiusKm = 6371.0;
constexpr double kDefaultSpeedKmh = 40.0;
constexpr double kPi = 3.14159265358979323846;

double to_radians(double degrees) {
    return degrees * kPi / 180.0;
}

double haversine_km(double lat1, double lng1, double lat2, double lng2) {
    const double dlat = to_radians(lat2 - lat1);
    const double dlng = to_radians(lng2 - lng1);
    const double a = std::sin(dlat / 2.0) * std::sin(dlat / 2.0) +
                     std::cos(to_radians(lat1)) * std::cos(to_radians(lat2)) *
                         std::sin(dlng / 2.0) * std::sin(dlng / 2.0);
    const double c = 2.0 * std::atan2(std::sqrt(a), std::sqrt(1.0 - a));
    return kEarthRadiusKm * c;
}

double read_number(const json& value, const std::vector<std::string>& keys) {
    for (const auto& key : keys) {
        if (value.contains(key) && value.at(key).is_number()) {
            return value.at(key).get<double>();
        }
    }

    if (value.contains("location") && value.at("location").is_object()) {
        return read_number(value.at("location"), keys);
    }

    throw std::runtime_error("Missing numeric coordinate");
}

std::string read_string(const json& value, const std::string& key, const std::string& fallback = "") {
    if (value.contains(key) && value.at(key).is_string()) {
        return value.at(key).get<std::string>();
    }
    return fallback;
}

bool is_available(const json& ambulance) {
    return read_string(ambulance, "status", "available") == "available";
}

double type_bonus(const json& incident, const json& ambulance) {
    const auto incident_type = read_string(incident, "type");
    const auto severity = read_string(incident, "severity");
    const auto ambulance_type = read_string(ambulance, "type");

    if ((incident_type == "cardiac" || severity == "critical") && ambulance_type == "ALS") {
        return -2.0;
    }
    return 0.0;
}

json optimize(const json& input) {
    if (!input.contains("incident") || !input.at("incident").is_object()) {
        throw std::runtime_error("Input must include an incident object");
    }
    if (!input.contains("ambulances") || !input.at("ambulances").is_array()) {
        throw std::runtime_error("Input must include an ambulances array");
    }

    const auto& incident = input.at("incident");
    const double incident_lat = read_number(incident, {"lat", "latitude", "location_lat"});
    const double incident_lng = read_number(incident, {"lng", "lon", "longitude", "location_lng"});

    double best_score = std::numeric_limits<double>::infinity();
    json best_assignment;

    for (const auto& ambulance : input.at("ambulances")) {
        if (!ambulance.is_object() || !is_available(ambulance)) {
            continue;
        }

        const double ambulance_lat = read_number(ambulance, {"current_lat", "lat", "latitude", "location_lat"});
        const double ambulance_lng = read_number(ambulance, {"current_lng", "lng", "lon", "longitude", "location_lng"});
        const double speed = ambulance.value("speed_kmh", kDefaultSpeedKmh);
        const double safe_speed = speed > 0.0 ? speed : kDefaultSpeedKmh;
        const double distance_km = haversine_km(ambulance_lat, ambulance_lng, incident_lat, incident_lng);
        const double eta_minutes = (distance_km / safe_speed) * 60.0;
        const double score = eta_minutes + type_bonus(incident, ambulance);

        if (score < best_score) {
            best_score = score;
            best_assignment = {
                {"ambulance_id", ambulance.value("id", "")},
                {"incident_id", incident.value("id", "")},
                {"distance_km", distance_km},
                {"eta_minutes", eta_minutes},
                {"score", score},
                {"optimizer", "cpp_placeholder"}};
        }
    }

    if (best_assignment.is_null()) {
        return {
            {"status", "error"},
            {"message", "No available ambulances"},
            {"assignment", nullptr}};
    }

    return {
        {"status", "success"},
        {"message", "Optimal assignment selected"},
        {"assignment", best_assignment}};
}

}  // namespace

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "Usage: dispatch_optimizer <input.json>\n";
        return 1;
    }

    try {
        std::ifstream input_file(argv[1]);
        if (!input_file) {
            throw std::runtime_error("Unable to open input JSON file");
        }

        json input;
        input_file >> input;

        const json result = optimize(input);
        std::cout << std::fixed << std::setprecision(3) << result.dump(2) << "\n";
        return result.value("status", "error") == "success" ? 0 : 2;
    } catch (const std::exception& exc) {
        const json error = {
            {"status", "error"},
            {"message", exc.what()},
            {"assignment", nullptr}};
        std::cout << error.dump(2) << "\n";
        return 1;
    }
}
