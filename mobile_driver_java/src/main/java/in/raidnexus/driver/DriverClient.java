package in.raidnexus.driver;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public final class DriverClient {
    private final HttpClient client;
    private final String apiBaseUrl;
    private final String bearerToken;

    public DriverClient(String apiBaseUrl, String bearerToken) {
        this.client = HttpClient.newHttpClient();
        this.apiBaseUrl = stripTrailingSlash(apiBaseUrl);
        this.bearerToken = bearerToken;
    }

    public String getFleetState() throws IOException, InterruptedException {
        return get("/api/ambulances");
    }

    public String getDriverDispatches(String driverId) throws IOException, InterruptedException {
        return get("/api/driver/dispatches/" + driverId);
    }

    public String postLocation(double lat, double lng, String timestamp) throws IOException, InterruptedException {
        String body = String.format(
            "{\"lat\":%.6f,\"lng\":%.6f,\"timestamp\":\"%s\"}",
            lat,
            lng,
            timestamp
        );
        return post("/api/driver/location", body);
    }

    public String postStatus(String status) throws IOException, InterruptedException {
        return post("/api/driver/status", String.format("{\"status\":\"%s\"}", status));
    }

    private String get(String path) throws IOException, InterruptedException {
        HttpRequest request = baseRequest(path).GET().build();
        return send(request);
    }

    private String post(String path, String body) throws IOException, InterruptedException {
        HttpRequest request = baseRequest(path)
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();
        return send(request);
    }

    private HttpRequest.Builder baseRequest(String path) {
        return HttpRequest.newBuilder(URI.create(apiBaseUrl + path))
            .header("Accept", "application/json")
            .header("Content-Type", "application/json")
            .header("Authorization", "Bearer " + bearerToken);
    }

    private String send(HttpRequest request) throws IOException, InterruptedException {
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() >= 400) {
            throw new IOException("RAID Nexus API error " + response.statusCode() + ": " + response.body());
        }
        return response.body();
    }

    private static String stripTrailingSlash(String value) {
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }
}
