namespace MuenzboxApi.Adapters;

/// <summary>
/// Routes TV control calls to the appropriate hardware adapter based on
/// the device's control_type field. Matches the Python adapters/__init__.py.
/// </summary>
public class AdapterDispatcher
{
    private readonly MikrotikAdapter _mikrotik;
    private readonly FritzBoxAdapter _fritzBox;
    private readonly MockAdapter _mock;
    private readonly bool _useMock;

    public AdapterDispatcher(
        MikrotikAdapter mikrotik,
        FritzBoxAdapter fritzBox,
        MockAdapter mock,
        IConfiguration config)
    {
        _mikrotik = mikrotik;
        _fritzBox = fritzBox;
        _mock = mock;
        _useMock = (config["USE_MOCK_ADAPTERS"] ?? "false").ToLower() == "true";
    }

    public async Task<bool> TvFreigeben(string controlType, string identifier,
        Dictionary<string, string?>? cfg = null)
    {
        if (_useMock) return _mock.TvFreigeben();
        cfg ??= new();
        return controlType switch
        {
            "mikrotik" => await _mikrotik.TvFreigeben(identifier, cfg),
            "fritzbox" => await _fritzBox.TvFreigeben(identifier, cfg),
            _ => false  // schedule_only / none
        };
    }

    public async Task<bool> TvSperren(string controlType, string identifier,
        Dictionary<string, string?>? cfg = null)
    {
        if (_useMock) return _mock.TvSperren();
        cfg ??= new();
        return controlType switch
        {
            "mikrotik" => await _mikrotik.TvSperren(identifier, cfg),
            "fritzbox" => await _fritzBox.TvSperren(identifier, cfg),
            _ => false
        };
    }
}
