using System.Collections.Concurrent;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;

namespace MuenzboxApi.Adapters;

/// <summary>
/// MikroTik RouterOS v7 REST API adapter.
/// disabled=true  → IP excluded from address-list → TV UNLOCKED
/// disabled=false → IP active in address-list    → TV BLOCKED
/// </summary>
public class MikrotikAdapter
{
    private readonly ILogger<MikrotikAdapter> _log;
    private readonly IConfiguration _config;

    // Cache: "{host}:{identifier}" → entry .id
    private readonly ConcurrentDictionary<string, string> _entryIdCache = new();

    public MikrotikAdapter(ILogger<MikrotikAdapter> log, IConfiguration config)
    {
        _log = log;
        _config = config;
    }

    public async Task<bool> TvFreigeben(string identifier, Dictionary<string, string?> cfg)
    {
        var (host, user, pass) = GetCfg(cfg);
        if (string.IsNullOrEmpty(host)) { _log.LogWarning("MikroTik: Host nicht konfiguriert"); return false; }
        if (string.IsNullOrEmpty(user) || string.IsNullOrEmpty(pass)) { _log.LogWarning("MikroTik: Zugangsdaten unvollständig"); return false; }

        var entryId = await GetEntryId(host, user, pass, identifier);
        if (entryId is null) { _log.LogError("MikroTik: Eintrag nicht gefunden ({Id})", identifier); return false; }

        return await Patch(host, user, pass, entryId, "true", identifier);
    }

    public async Task<bool> TvSperren(string identifier, Dictionary<string, string?> cfg)
    {
        var (host, user, pass) = GetCfg(cfg);
        if (string.IsNullOrEmpty(host) || string.IsNullOrEmpty(user) || string.IsNullOrEmpty(pass)) return false;

        var entryId = await GetEntryId(host, user, pass, identifier);
        if (entryId is null) return false;

        return await Patch(host, user, pass, entryId, "false", identifier);
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    private (string host, string user, string pass) GetCfg(Dictionary<string, string?> cfg)
    {
        string Get(string key, string envKey) =>
            (cfg.GetValueOrDefault(key) ?? _config[envKey] ?? "").Trim();

        var host = Get("host", "MIKROTIK_HOST");
        var user = Get("user", "MIKROTIK_USER");
        var pass = (cfg.GetValueOrDefault("password") ?? _config["MIKROTIK_PASS"] ?? "").Trim();
        if (pass == "***") pass = "";
        return (host, user, pass);
    }

    private static List<string> BaseUrls(string host)
    {
        if (string.IsNullOrEmpty(host)) return new();
        if (host.StartsWith("http://", StringComparison.OrdinalIgnoreCase) ||
            host.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
            return new() { host.TrimEnd('/') };

        var clean = host.TrimEnd('/');
        return new() { $"https://{clean}", $"http://{clean}" };
    }

    private async Task<string?> GetEntryId(string host, string user, string pass, string identifier)
    {
        var cacheKey = $"{host}:{identifier}";
        if (_entryIdCache.TryGetValue(cacheKey, out var cached)) return cached;

        foreach (var baseUrl in BaseUrls(host))
        {
            try
            {
                using var client = CreateClient(user, pass);

                // Try filtered fetch first
                var resp = await client.GetAsync(
                    $"{baseUrl}/rest/ip/firewall/address-list?comment={Uri.EscapeDataString(identifier)}");
                if (resp.IsSuccessStatusCode)
                {
                    var entries = await resp.Content.ReadFromJsonAsync<List<JsonElement>>() ?? new();
                    var id = FindEntryId(entries, identifier);
                    if (id is not null)
                    {
                        _entryIdCache[cacheKey] = id;
                        return id;
                    }
                }

                // Fallback: full list
                resp = await client.GetAsync($"{baseUrl}/rest/ip/firewall/address-list");
                if (!resp.IsSuccessStatusCode) continue;
                var all = await resp.Content.ReadFromJsonAsync<List<JsonElement>>() ?? new();
                var id2 = FindEntryId(all, identifier);
                if (id2 is not null)
                {
                    _entryIdCache[cacheKey] = id2;
                    return id2;
                }

                _log.LogWarning("MikroTik: Kein Eintrag mit identifier={Id}", identifier);
                return null;
            }
            catch (HttpRequestException) { continue; }
            catch (Exception ex) { _log.LogError(ex, "MikroTik: Fehler beim Laden der Address-List"); return null; }
        }

        return null;
    }

    private static string? FindEntryId(List<JsonElement> entries, string identifier)
    {
        var ident = identifier.Trim().ToLowerInvariant();
        // Exact match
        foreach (var e in entries)
        {
            if (e.TryGetProperty("comment", out var c) &&
                c.GetString()?.Trim().ToLowerInvariant() == ident)
                return e.TryGetProperty(".id", out var id) ? id.GetString() : null;
        }
        // Contains match
        foreach (var e in entries)
        {
            if (e.TryGetProperty("comment", out var c))
            {
                var comment = c.GetString()?.Trim().ToLowerInvariant() ?? "";
                if (comment.Contains(ident) || ident.Contains(comment))
                    return e.TryGetProperty(".id", out var id) ? id.GetString() : null;
            }
        }
        return null;
    }

    private async Task<bool> Patch(string host, string user, string pass, string entryId,
        string disabled, string identifier)
    {
        foreach (var baseUrl in BaseUrls(host))
        {
            try
            {
                using var client = CreateClient(user, pass);
                var resp = await client.PatchAsJsonAsync(
                    $"{baseUrl}/rest/ip/firewall/address-list/{entryId}",
                    new { disabled });
                resp.EnsureSuccessStatusCode();
                _log.LogInformation("MikroTik: TV {Action} ({Id})",
                    disabled == "true" ? "freigegeben" : "gesperrt", identifier);
                return true;
            }
            catch (HttpRequestException) { continue; }
            catch (Exception ex) { _log.LogError(ex, "MikroTik: Patch-Fehler"); return false; }
        }
        _log.LogError("MikroTik: Keine Verbindung zu {Host}", host);
        return false;
    }

    private static HttpClient CreateClient(string user, string pass)
    {
        var handler = new HttpClientHandler { ServerCertificateCustomValidationCallback = (_, _, _, _) => true };
        var client = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(10) };
        var token = Convert.ToBase64String(Encoding.UTF8.GetBytes($"{user}:{pass}"));
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Basic", token);
        return client;
    }
}
