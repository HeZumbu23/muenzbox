using MuenzboxApi.Models;

namespace MuenzboxApi.Services;

/// <summary>
/// Determines if the current time is within allowed periods and whether
/// today is a weekend or German public holiday (matches Python's time_utils.py).
/// </summary>
public class TimeUtilsService
{
    public bool IsWeekendOrHoliday()
    {
        var today = DateOnly.FromDateTime(DateTime.Now);
        if (today.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday)
            return true;
        return IsGermanPublicHoliday(today);
    }

    public bool IsInPeriods(List<TimeSlot> periods)
    {
        var now = DateTime.Now;
        int currentMinutes = now.Hour * 60 + now.Minute;
        foreach (var p in periods)
        {
            if (ParseTime(p.Von) is not { } from || ParseTime(p.Bis) is not { } to)
                continue;
            if (from <= currentMinutes && currentMinutes <= to)
                return true;
        }
        return false;
    }

    public List<TimeSlot> GetActivePeriods(List<TimeSlot> allowed, List<TimeSlot> weekend)
    {
        var fallback = new List<TimeSlot> { new("08:00", "20:00") };
        if (IsWeekendOrHoliday())
            return weekend.Count > 0 ? weekend : fallback;
        return allowed.Count > 0 ? allowed : fallback;
    }

    // ── German public holiday calculator ─────────────────────────────────
    // Covers all nationwide (federal) holidays; regional ones omitted.

    private static bool IsGermanPublicHoliday(DateOnly date)
    {
        int y = date.Year;
        var easter = EasterSunday(y);

        var holidays = new HashSet<DateOnly>
        {
            new(y, 1, 1),          // Neujahr
            easter.AddDays(-2),    // Karfreitag
            easter,                // Ostersonntag
            easter.AddDays(1),     // Ostermontag
            new(y, 5, 1),          // Tag der Arbeit
            easter.AddDays(39),    // Christi Himmelfahrt
            easter.AddDays(49),    // Pfingstsonntag
            easter.AddDays(50),    // Pfingstmontag
            new(y, 10, 3),         // Tag der deutschen Einheit
            new(y, 12, 25),        // 1. Weihnachtstag
            new(y, 12, 26),        // 2. Weihnachtstag
        };
        return holidays.Contains(date);
    }

    /// <summary>Anonymous Gregorian algorithm for Easter Sunday.</summary>
    private static DateOnly EasterSunday(int year)
    {
        int a = year % 19;
        int b = year / 100;
        int c = year % 100;
        int d = b / 4;
        int e = b % 4;
        int f = (b + 8) / 25;
        int g = (b - f + 1) / 3;
        int h = (19 * a + b - d - g + 15) % 30;
        int i = c / 4;
        int k = c % 4;
        int l = (32 + 2 * e + 2 * i - h - k) % 7;
        int m = (a + 11 * h + 22 * l) / 451;
        int month = (h + l - 7 * m + 114) / 31;
        int day = ((h + l - 7 * m + 114) % 31) + 1;
        return new DateOnly(year, month, day);
    }

    private static int? ParseTime(string t)
    {
        var parts = t.Split(':');
        if (parts.Length != 2) return null;
        if (!int.TryParse(parts[0], out int h) || !int.TryParse(parts[1], out int m)) return null;
        return h * 60 + m;
    }
}
