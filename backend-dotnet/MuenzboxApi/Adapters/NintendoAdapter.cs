using Python.Runtime;

namespace MuenzboxApi.Adapters;

/// <summary>
/// Nintendo Switch parental controls via Python.NET (pythonnet).
/// Loads nintendo_bridge.py and calls synchronous wrapper functions which
/// internally run the async pynintendoparental library via asyncio.run().
///
/// Python.NET requires:
///   - libpython3.12 accessible (set PYTHONNET_PYDLL)
///   - pynintendoparental + aiohttp installed in the Python environment
/// </summary>
public class NintendoAdapter
{
    private readonly ILogger<NintendoAdapter> _log;
    private readonly string _token;
    private readonly string _tz;
    private readonly string _lang;
    private readonly bool _useMock;
    private readonly MockAdapter _mock;
    private readonly int _timeoutSeconds;

    private static readonly object _engineLock = new();
    private static bool _engineInitialized = false;
    private static bool _engineAvailable = false;
    private static IntPtr _threadState = IntPtr.Zero;

    public NintendoAdapter(
        ILogger<NintendoAdapter> log,
        IConfiguration config,
        MockAdapter mock)
    {
        _log = log;
        _mock = mock;
        _token = config["NINTENDO_TOKEN"] ?? "";
        _tz = config["NINTENDO_TIMEZONE"] ?? "Europe/Berlin";
        _lang = config["NINTENDO_LANG"] ?? "de-DE";
        _useMock = (config["USE_MOCK_ADAPTERS"] ?? "false").ToLower() == "true";
        _timeoutSeconds = ParseTimeoutSeconds(config["NINTENDO_TIMEOUT_SECONDS"]);

        EnsureEngineInitialized();
    }

    private static void EnsureEngineInitialized()
    {
        lock (_engineLock)
        {
            if (_engineInitialized) return;
            _engineInitialized = true;
            try
            {
                // Allow override via environment variable PYTHONNET_PYDLL
                PythonEngine.Initialize();
                _threadState = PythonEngine.BeginAllowThreads();
                _engineAvailable = true;
            }
            catch (Exception ex)
            {
                // Python not available – Nintendo integration disabled
                Console.Error.WriteLine($"[NintendoAdapter] Python.NET init failed (GIL setup): {ex.Message}");
                _engineAvailable = false;
            }
        }
    }

    private string BridgePath =>
        Path.Combine(AppContext.BaseDirectory, "Nintendo");

    /// <summary>Unlock Switch for <paramref name="minutes"/> minutes.</summary>
    public async Task<bool> SwitchFreigeben(int minutes)
    {
        return await SwitchFreigeben(minutes, new Dictionary<string, string?>());
    }

    public async Task<bool> SwitchFreigeben(int minutes, Dictionary<string, string?> cfg)
    {
        if (_useMock) return _mock.SwitchFreigeben(minutes);
        var (token, tz, lang, timeoutSeconds) = GetCfg(cfg);
        if (string.IsNullOrEmpty(token)) { _log.LogWarning("Nintendo: Token nicht konfiguriert"); return false; }
        if (!_engineAvailable) { _log.LogWarning("Nintendo: Python.NET nicht verfügbar"); return false; }

        return await Task.Run(() => CallBridge("switch_freigeben_sync", token, tz, lang, timeoutSeconds, minutes));
    }

    /// <summary>Lock Switch by setting daily limit to 0.</summary>
    public async Task<bool> SwitchSperren()
    {
        return await SwitchSperren(new Dictionary<string, string?>());
    }

    public async Task<bool> SwitchSperren(Dictionary<string, string?> cfg)
    {
        if (_useMock) return _mock.SwitchSperren();
        var (token, tz, lang, timeoutSeconds) = GetCfg(cfg);
        if (string.IsNullOrEmpty(token)) { _log.LogWarning("Nintendo: Token nicht konfiguriert"); return false; }
        if (!_engineAvailable) { _log.LogWarning("Nintendo: Python.NET nicht verfügbar"); return false; }

        return await Task.Run(() => CallBridge("switch_sperren_sync", token, tz, lang, timeoutSeconds));
    }

    // ── Python.NET call ───────────────────────────────────────────────────

    private (string token, string tz, string lang, int timeoutSeconds) GetCfg(Dictionary<string, string?> cfg)
    {
        string Get(string key, string fallback) =>
            (cfg.GetValueOrDefault(key) ?? fallback).Trim();

        var timeoutRaw = Get("timeout_seconds", _timeoutSeconds.ToString());

        return (
            Get("token", _token),
            Get("timezone", _tz),
            Get("lang", _lang),
            ParseTimeoutSeconds(timeoutRaw)
        );
    }

    private static int ParseTimeoutSeconds(string? raw)
    {
        if (int.TryParse(raw, out var parsed))
            return Math.Clamp(parsed, 5, 120);
        return 20;
    }

    private bool CallBridge(string funcName, string token, string tz, string lang, int timeoutSeconds, int? minutes = null)
    {
        try
        {
            // GIL must be acquired per call after Initialize()+BeginAllowThreads()
            using (Py.GIL())
            {
                dynamic sys = Py.Import("sys");

                // Add bridge directory to sys.path if not already there
                bool pathFound = false;
                foreach (var p in sys.path)
                {
                    if ((string)p == BridgePath) { pathFound = true; break; }
                }
                if (!pathFound) sys.path.insert(0, BridgePath);

                dynamic bridge = Py.Import("nintendo_bridge");

                bool result;
                if (funcName == "switch_freigeben_sync" && minutes.HasValue)
                    result = (bool)bridge.switch_freigeben_sync(token, tz, lang, minutes.Value, timeoutSeconds);
                else
                    result = (bool)bridge.switch_sperren_sync(token, tz, lang, timeoutSeconds);

                _log.LogInformation("Nintendo: {Func} (timeout={Timeout}s) → {Result}", funcName, timeoutSeconds, result);
                return result;
            }
        }
        catch (PythonException pex)
        {
            var current = (Exception)pex;
            while (current.InnerException is not null)
                current = current.InnerException;

            var cause = string.IsNullOrWhiteSpace(current.Message)
                ? "Unbekannter Python-Fehler"
                : current.Message.Trim();
            var tokenPrefix = string.IsNullOrEmpty(token) ? "<leer>" : token[..Math.Min(10, token.Length)];

            // Do not pass the exception object to avoid noisy Python/.NET stack traces in logs.
            _log.LogError("Nintendo: Python error in {Func} (token={TokenPrefix}...): {Cause}", funcName, tokenPrefix, cause);
            return false;
        }
        catch (Exception ex)
        {
            _log.LogError(ex, "Nintendo: Fehler in {Func}", funcName);
            return false;
        }
    }
}
