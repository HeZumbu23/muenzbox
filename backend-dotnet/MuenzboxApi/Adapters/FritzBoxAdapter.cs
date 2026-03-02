using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Xml.Linq;

namespace MuenzboxApi.Adapters;

/// <summary>
/// FritzBox LUA interface adapter. Controls devices via access profiles
/// (Standard = allowed, Gesperrt = blocked). Matches fritzbox.py.
/// </summary>
public class FritzBoxAdapter
{
    private readonly ILogger<FritzBoxAdapter> _log;
    private readonly IConfiguration _config;

    private readonly ConcurrentDictionary<string, SidEntry> _sidCache = new();
    private static readonly TimeSpan SidTtl = TimeSpan.FromMinutes(18);

    public FritzBoxAdapter(ILogger<FritzBoxAdapter> log, IConfiguration config)
    {
        _log = log;
        _config = config;
    }

    public async Task<bool> TvFreigeben(string identifier, Dictionary<string, string?> cfg)
    {
        var (host, user, pass, allowed, _) = GetCfg(cfg);
        if (string.IsNullOrEmpty(host)) { _log.LogWarning("FritzBox: Host nicht konfiguriert"); return false; }
        return await ChangeProfile(identifier, allowed, host, user, pass);
    }

    public async Task<bool> TvSperren(string identifier, Dictionary<string, string?> cfg)
    {
        var (host, user, pass, _, blocked) = GetCfg(cfg);
        if (string.IsNullOrEmpty(host)) { _log.LogWarning("FritzBox: Host nicht konfiguriert"); return false; }
        return await ChangeProfile(identifier, blocked, host, user, pass);
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    private (string host, string user, string pass, string allowed, string blocked) GetCfg(Dictionary<string, string?> cfg)
    {
        string Get(string key, string env, string def = "") =>
            (cfg.GetValueOrDefault(key) ?? _config[env] ?? def).Trim();

        return (
            Get("host", "FRITZBOX_HOST", "fritz.box"),
            Get("user", "FRITZBOX_USER"),
            Get("password", "FRITZBOX_PASS"),
            Get("allowed_profile", "FRITZBOX_ALLOWED_PROFILE", "Standard"),
            Get("blocked_profile", "FRITZBOX_BLOCKED_PROFILE", "Gesperrt")
        );
    }

    private async Task<bool> ChangeProfile(string device, string profile, string host, string user, string pass)
    {
        for (int attempt = 0; attempt < 2; attempt++)
        {
            var sid = await GetSid(host, user, pass, forceRefresh: attempt > 0);
            if (sid is null) return false;
            try
            {
                using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
                var baseUrl = $"http://{host}";

                var devUid = await GetDeviceUid(client, baseUrl, sid, device);
                if (devUid is null) return false;

                var profId = await GetProfileId(client, baseUrl, sid, profile);
                if (profId is null) return false;

                await SetProfile(client, baseUrl, sid, devUid, profId);
                _log.LogInformation("FritzBox: '{Device}' → '{Profile}'", device, profile);
                return true;
            }
            catch (HttpRequestException ex) when (ex.StatusCode == System.Net.HttpStatusCode.Forbidden && attempt == 0)
            {
                _log.LogWarning("FritzBox: SID abgelaufen, erneuere Login...");
                _sidCache.TryRemove(host, out _);
            }
            catch (Exception ex)
            {
                _log.LogError(ex, "FritzBox: Fehler beim Profilwechsel");
                return false;
            }
        }
        return false;
    }

    private async Task<string?> GetSid(string host, string user, string pass, bool forceRefresh)
    {
        if (!forceRefresh && _sidCache.TryGetValue(host, out var entry) && entry.IsValid)
            return entry.Sid;
        return await Login(host, user, pass);
    }

    private async Task<string?> Login(string host, string user, string pass)
    {
        if (string.IsNullOrEmpty(pass)) { _log.LogWarning("FritzBox: Passwort nicht konfiguriert"); return null; }
        try
        {
            var baseUrl = $"http://{host}";
            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };

            var resp = await client.GetAsync($"{baseUrl}/login_sid.lua?version=2");
            resp.EnsureSuccessStatusCode();
            var xml = XDocument.Parse(await resp.Content.ReadAsStringAsync());

            var sid = xml.Root?.Element("SID")?.Value ?? "0000000000000000";
            if (sid != "0000000000000000")
            {
                Cache(host, sid);
                return sid;
            }

            var challenge = xml.Root?.Element("Challenge")?.Value ?? "";
            if (string.IsNullOrEmpty(challenge)) { _log.LogError("FritzBox: Kein Challenge"); return null; }

            var response = challenge.StartsWith("2$")
                ? ComputePbkdf2(challenge, pass)
                : ComputeMd5(challenge, pass);

            var loginResp = await client.PostAsync(
                $"{baseUrl}/login_sid.lua?version=2",
                new FormUrlEncodedContent(new[] {
                    new KeyValuePair<string,string>("username", user),
                    new KeyValuePair<string,string>("response", response),
                }));
            loginResp.EnsureSuccessStatusCode();
            var loginXml = XDocument.Parse(await loginResp.Content.ReadAsStringAsync());
            sid = loginXml.Root?.Element("SID")?.Value ?? "0000000000000000";

            if (sid == "0000000000000000") { _log.LogError("FritzBox: Login fehlgeschlagen"); return null; }
            Cache(host, sid);
            _log.LogInformation("FritzBox: Login erfolgreich");
            return sid;
        }
        catch (Exception ex) { _log.LogError(ex, "FritzBox: Login-Fehler"); return null; }
    }

    private void Cache(string host, string sid) =>
        _sidCache[host] = new SidEntry(sid, DateTime.UtcNow + SidTtl);

    private static async Task<string?> GetDeviceUid(HttpClient client, string baseUrl, string sid, string deviceName)
    {
        var resp = await client.PostAsync($"{baseUrl}/data.lua",
            Form(sid, "netDev", "all"));
        resp.EnsureSuccessStatusCode();
        var data = JsonDocument.Parse(await resp.Content.ReadAsStringAsync());
        var root = data.RootElement.GetProperty("data");

        var active = root.TryGetProperty("active", out var a) ? a.EnumerateArray() : Enumerable.Empty<JsonElement>();
        var passive = root.TryGetProperty("passive", out var p) ? p.EnumerateArray() : Enumerable.Empty<JsonElement>();

        foreach (var dev in active.Concat(passive))
        {
            if (dev.TryGetProperty("name", out var n) && n.GetString() == deviceName)
            {
                if (dev.TryGetProperty("UID", out var uid)) return uid.GetString();
                if (dev.TryGetProperty("uid", out var uid2)) return uid2.GetString();
            }
        }
        return null;
    }

    private static async Task<string?> GetProfileId(HttpClient client, string baseUrl, string sid, string profileName)
    {
        var resp = await client.PostAsync($"{baseUrl}/data.lua", Form(sid, "kidProfils", null));
        resp.EnsureSuccessStatusCode();
        var data = JsonDocument.Parse(await resp.Content.ReadAsStringAsync());
        if (!data.RootElement.TryGetProperty("data", out var root)) return null;
        if (!root.TryGetProperty("profiles", out var profiles)) return null;

        foreach (var prof in profiles.EnumerateArray())
        {
            var name = prof.TryGetProperty("Name", out var n) ? n.GetString() :
                       prof.TryGetProperty("name", out var n2) ? n2.GetString() : null;
            if (name == profileName)
            {
                if (prof.TryGetProperty("Id", out var id)) return id.GetString();
                if (prof.TryGetProperty("id", out var id2)) return id2.GetString();
            }
        }
        return null;
    }

    private static async Task SetProfile(HttpClient client, string baseUrl, string sid, string devUid, string profId)
    {
        var resp = await client.PostAsync($"{baseUrl}/data.lua",
            new FormUrlEncodedContent(new[]
            {
                new KeyValuePair<string,string>("xhr", "1"),
                new KeyValuePair<string,string>("sid", sid),
                new KeyValuePair<string,string>("lang", "de"),
                new KeyValuePair<string,string>("page", "kids_device"),
                new KeyValuePair<string,string>("xhrId", "all"),
                new KeyValuePair<string,string>("dev", devUid),
                new KeyValuePair<string,string>("profile", profId),
                new KeyValuePair<string,string>("apply", ""),
            }));
        resp.EnsureSuccessStatusCode();
    }

    private static FormUrlEncodedContent Form(string sid, string page, string? xhrId) =>
        new(new[]
        {
            new KeyValuePair<string,string>("xhr", "1"),
            new KeyValuePair<string,string>("sid", sid),
            new KeyValuePair<string,string>("lang", "de"),
            new KeyValuePair<string,string>("page", page),
            new KeyValuePair<string,string>("xhrId", xhrId ?? "all"),
        }.Where(kv => !string.IsNullOrEmpty(kv.Value)));

    // ── PBKDF2 / MD5 challenge responses ──────────────────────────────────

    private static string ComputePbkdf2(string challenge, string password)
    {
        // Format: "2$<iter1>$<salt1hex>$<iter2>$<salt2hex>"
        var parts = challenge.Split('$');
        int iter1 = int.Parse(parts[1]);
        byte[] salt1 = Convert.FromHexString(parts[2]);
        int iter2 = int.Parse(parts[3]);
        byte[] salt2 = Convert.FromHexString(parts[4]);

        byte[] hash1 = Rfc2898DeriveBytes.Pbkdf2(
            Encoding.UTF8.GetBytes(password), salt1, iter1, HashAlgorithmName.SHA256, 32);
        byte[] hash2 = Rfc2898DeriveBytes.Pbkdf2(
            hash1, salt2, iter2, HashAlgorithmName.SHA256, 32);
        return $"{challenge}${Convert.ToHexString(hash2).ToLowerInvariant()}";
    }

    private static string ComputeMd5(string challenge, string password)
    {
        var raw = $"{challenge}-{password}";
        var bytes = Encoding.Unicode.GetBytes(raw); // UTF-16 LE
        var md5 = Convert.ToHexString(MD5.HashData(bytes)).ToLowerInvariant();
        return $"{challenge}-{md5}";
    }
}

internal record SidEntry(string Sid, DateTime ExpiresAt)
{
    public bool IsValid => DateTime.UtcNow < ExpiresAt && Sid != "0000000000000000";
}
