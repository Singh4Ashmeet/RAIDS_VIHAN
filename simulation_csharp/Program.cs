using System.Net.Http.Json;
using System.Text.Json;

var configPath = Path.Combine(AppContext.BaseDirectory, "appsettings.json");
if (!File.Exists(configPath))
{
    configPath = Path.Combine(Directory.GetCurrentDirectory(), "appsettings.json");
}

var config = JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(configPath))
    ?? new Dictionary<string, string>();
var apiBaseUrl = config.GetValueOrDefault("API_BASE_URL", "http://localhost:8000").TrimEnd('/');

using var http = new HttpClient { BaseAddress = new Uri(apiBaseUrl) };
var health = await http.GetFromJsonAsync<JsonElement>("/health");

Console.WriteLine($"RAID Nexus health from {apiBaseUrl}: {health.GetProperty("status").GetString()}");
