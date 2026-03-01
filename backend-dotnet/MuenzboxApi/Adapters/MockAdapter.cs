namespace MuenzboxApi.Adapters;

/// <summary>
/// In-memory simulation adapter – used when USE_MOCK_ADAPTERS=true.
/// Registered as singleton so state persists across requests.
/// </summary>
public class MockAdapter
{
    private bool _tvUnlocked = false;
    private int _switchMinutes = 0;
    private readonly List<MockLogEntry> _log = new();
    private const int MaxLog = 20;

    public bool TvFreigeben()
    {
        _tvUnlocked = true;
        AddLog("TV freigegeben ✅");
        return true;
    }

    public bool TvSperren()
    {
        _tvUnlocked = false;
        AddLog("TV gesperrt 🔒");
        return true;
    }

    public bool TvStatus() => _tvUnlocked;

    public bool SwitchFreigeben(int minutes)
    {
        _switchMinutes = minutes;
        AddLog($"Switch freigegeben für {minutes} Minuten ✅");
        return true;
    }

    public bool SwitchSperren()
    {
        _switchMinutes = 0;
        AddLog("Switch gesperrt 🔒");
        return true;
    }

    public object GetStatus() => new
    {
        tv_unlocked = _tvUnlocked,
        switch_minutes = _switchMinutes,
        switch_unlocked = _switchMinutes > 0,
        log = _log.AsReadOnly(),
    };

    private void AddLog(string msg)
    {
        _log.Insert(0, new MockLogEntry(DateTime.Now.ToString("HH:mm:ss"), msg));
        if (_log.Count > MaxLog) _log.RemoveAt(_log.Count - 1);
    }
}

public record MockLogEntry(string Time, string Msg);
