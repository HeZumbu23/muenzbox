using System.Text.Json.Serialization;

namespace MuenzboxApi.Models;

// ── Public child list entry ────────────────────────────────────────────────
public record ChildPublic(int Id, string Name, int SwitchCoins, int TvCoins);

// ── Time slot {"von":"HH:MM","bis":"HH:MM"} ───────────────────────────────
public record TimeSlot(string Von, string Bis);

// ── Full child status (requires child token) ──────────────────────────────
public record ChildStatus(
    int Id,
    string Name,
    int SwitchCoins,
    int SwitchCoinsWeekly,
    int SwitchCoinsMax,
    int TvCoins,
    int TvCoinsWeekly,
    int TvCoinsMax,
    int PocketMoneyCents,
    int PocketMoneyWeeklyCents,
    List<TimeSlot> AllowedPeriods,
    List<TimeSlot> WeekendPeriods,
    bool IsWeekendOrHoliday
);

// ── PIN verify request ────────────────────────────────────────────────────
public class PinVerifyRequest
{
    public string Pin { get; set; } = "";
}

// ── Session start request ─────────────────────────────────────────────────
public class SessionStartRequest
{
    public int ChildId { get; set; }
    public string Type { get; set; } = "";
    public int Coins { get; set; } = 1;
}

// ── Session response ──────────────────────────────────────────────────────
public record SessionResponse(
    int Id,
    int ChildId,
    string Type,
    string StartedAt,
    string EndsAt,
    int CoinsUsed,
    string Status,
    bool HardwareOk
);

// ── Admin verify request ──────────────────────────────────────────────────
public class AdminVerifyRequest
{
    public string Pin { get; set; } = "";
}

// ── Create child ──────────────────────────────────────────────────────────
public class ChildCreateRequest
{
    public string Name { get; set; } = "";
    public string Pin { get; set; } = "";
    public int SwitchCoins { get; set; } = 0;
    public int SwitchCoinsWeekly { get; set; } = 2;
    public int SwitchCoinsMax { get; set; } = 10;
    public int TvCoins { get; set; } = 0;
    public int TvCoinsWeekly { get; set; } = 2;
    public int TvCoinsMax { get; set; } = 10;
    public int PocketMoneyCents { get; set; } = 0;
    public int PocketMoneyWeeklyCents { get; set; } = 0;
    public List<TimeSlot>? AllowedPeriods { get; set; }
    public List<TimeSlot>? WeekendPeriods { get; set; }
}

// ── Update child (all fields optional) ───────────────────────────────────
public class ChildUpdateRequest
{
    public string? Name { get; set; }
    public string? Pin { get; set; }
    public int? SwitchCoins { get; set; }
    public int? SwitchCoinsWeekly { get; set; }
    public int? SwitchCoinsMax { get; set; }
    public int? TvCoins { get; set; }
    public int? TvCoinsWeekly { get; set; }
    public int? TvCoinsMax { get; set; }
    public int? PocketMoneyCents { get; set; }
    public int? PocketMoneyWeeklyCents { get; set; }
    public List<TimeSlot>? AllowedPeriods { get; set; }
    public List<TimeSlot>? WeekendPeriods { get; set; }
}

// ── Coin adjustment ───────────────────────────────────────────────────────
public class CoinAdjustRequest
{
    public string Type { get; set; } = "";
    public int Delta { get; set; }
    public string Reason { get; set; } = "admin_adjust";
}

// ── Pocket money adjustment ───────────────────────────────────────────────
public class PocketMoneyAdjustRequest
{
    public int DeltaCents { get; set; }
    public string Reason { get; set; } = "admin_adjust";
    public string? Note { get; set; }
}

// ── Device create ─────────────────────────────────────────────────────────
public class DeviceCreateRequest
{
    public string Name { get; set; } = "";
    public string Identifier { get; set; } = "";
    public string DeviceType { get; set; } = "tv";
    public string ControlType { get; set; } = "fritzbox";
    public Dictionary<string, string?> Config { get; set; } = new();
}

// ── Device update ─────────────────────────────────────────────────────────
public class DeviceUpdateRequest
{
    public string? Name { get; set; }
    public string? Identifier { get; set; }
    public string? DeviceType { get; set; }
    public string? ControlType { get; set; }
    public Dictionary<string, string?>? Config { get; set; }
    public bool? IsActive { get; set; }
}
