using MuenzboxApi.Adapters;

namespace MuenzboxApi.Services;

/// <summary>
/// Background service that reproduces the two APScheduler jobs from the Python backend:
///   1. Weekly coin refill – every Saturday at 00:00 local time.
///   2. Session expiry check – every minute.
/// </summary>
public class SchedulerService : BackgroundService
{
    private readonly IServiceProvider _sp;
    private readonly ILogger<SchedulerService> _log;

    // Track which Saturday we last processed so we don't fire twice
    private DateOnly _lastWeeklyRefillDate = DateOnly.MinValue;

    public SchedulerService(IServiceProvider sp, ILogger<SchedulerService> log)
    {
        _sp = sp;
        _log = log;
    }

    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        _log.LogInformation("Scheduler started");

        using var timer = new PeriodicTimer(TimeSpan.FromMinutes(1));
        while (await timer.WaitForNextTickAsync(ct))
        {
            var now = DateTime.Now;

            try { await ExpireSessionsAsync(); }
            catch (Exception ex) { _log.LogError(ex, "Scheduler: error in ExpireSessionsAsync"); }

            // Saturday 00:00 check (fire within the first minute of Saturday)
            var today = DateOnly.FromDateTime(now);
            if (now.DayOfWeek == DayOfWeek.Saturday
                && now.Hour == 0
                && now.Minute == 0
                && today != _lastWeeklyRefillDate)
            {
                _lastWeeklyRefillDate = today;
                try { await WeeklyCoinRefillAsync(); }
                catch (Exception ex) { _log.LogError(ex, "Scheduler: error in WeeklyCoinRefillAsync"); }
            }
        }
    }

    // ── Weekly refill ─────────────────────────────────────────────────────

    private async Task WeeklyCoinRefillAsync()
    {
        _log.LogInformation("Scheduler: weekly coin refill started");
        var now = DateTime.UtcNow.ToString("o");
        var db = _sp.GetRequiredService<DatabaseService>();
        await using var conn = db.CreateConnection();

        await using var childCmd = conn.CreateCommand();
        childCmd.CommandText = "SELECT * FROM children";

        var children = new List<Dictionary<string, object?>>();
        await using (var reader = await childCmd.ExecuteReaderAsync())
        {
            while (await reader.ReadAsync())
            {
                var row = new Dictionary<string, object?>();
                for (int i = 0; i < reader.FieldCount; i++)
                    row[reader.GetName(i)] = reader.IsDBNull(i) ? null : reader.GetValue(i);
                children.Add(row);
            }
        }

        foreach (var child in children)
        {
            var id = (long)child["id"]!;
            var switchCoins = (long)(child["switch_coins"] ?? 0L);
            var switchWeekly = (long)(child["switch_coins_weekly"] ?? 0L);
            var switchMax = (long)(child["switch_coins_max"] ?? 10L);
            var tvCoins = (long)(child["tv_coins"] ?? 0L);
            var tvWeekly = (long)(child["tv_coins_weekly"] ?? 0L);
            var tvMax = (long)(child["tv_coins_max"] ?? 10L);
            var pmCents = (long)(child["pocket_money_cents"] ?? 0L);
            var pmWeeklyCents = (long)(child["pocket_money_weekly_cents"] ?? 0L);

            var newSwitch = Math.Min(switchCoins + switchWeekly, switchMax);
            var newTv = Math.Min(tvCoins + tvWeekly, tvMax);
            var newPm = pmCents + pmWeeklyCents;
            var switchDelta = newSwitch - switchCoins;
            var tvDelta = newTv - tvCoins;

            await using var updCmd = conn.CreateCommand();
            updCmd.CommandText =
                "UPDATE children SET switch_coins=@sw, tv_coins=@tv, pocket_money_cents=@pm WHERE id=@id";
            updCmd.Parameters.AddWithValue("@sw", newSwitch);
            updCmd.Parameters.AddWithValue("@tv", newTv);
            updCmd.Parameters.AddWithValue("@pm", newPm);
            updCmd.Parameters.AddWithValue("@id", id);
            await updCmd.ExecuteNonQueryAsync();

            if (switchDelta > 0) await InsertCoinLogAsync(conn, id, "switch", switchDelta, "weekly_refill", now);
            if (tvDelta > 0)     await InsertCoinLogAsync(conn, id, "tv", tvDelta, "weekly_refill", now);

            if (pmWeeklyCents > 0)
            {
                await using var pmCmd = conn.CreateCommand();
                pmCmd.CommandText =
                    "INSERT INTO pocket_money_log (child_id, delta_cents, reason, note, created_at) VALUES (@cid,@d,'weekly_refill',NULL,@ts)";
                pmCmd.Parameters.AddWithValue("@cid", id);
                pmCmd.Parameters.AddWithValue("@d", pmWeeklyCents);
                pmCmd.Parameters.AddWithValue("@ts", now);
                await pmCmd.ExecuteNonQueryAsync();
            }
        }

        _log.LogInformation("Scheduler: weekly refill done ({Count} children)", children.Count);
    }

    // ── Session expiry ────────────────────────────────────────────────────

    private async Task ExpireSessionsAsync()
    {
        var now = DateTime.UtcNow.ToString("o");
        var db = _sp.GetRequiredService<DatabaseService>();
        var dispatcher = _sp.GetRequiredService<AdapterDispatcher>();
        await using var conn = db.CreateConnection();

        await using var expCmd = conn.CreateCommand();
        expCmd.CommandText =
            "SELECT * FROM sessions WHERE status='active' AND ends_at <= @now";
        expCmd.Parameters.AddWithValue("@now", now);

        var expired = new List<Dictionary<string, object?>>();
        await using (var reader = await expCmd.ExecuteReaderAsync())
        {
            while (await reader.ReadAsync())
            {
                var row = new Dictionary<string, object?>();
                for (int i = 0; i < reader.FieldCount; i++)
                    row[reader.GetName(i)] = reader.IsDBNull(i) ? null : reader.GetValue(i);
                expired.Add(row);
            }
        }

        foreach (var session in expired)
        {
            var sessionId = (long)session["id"]!;
            var type = (string)(session["type"] ?? "");
            var childId = (long)(session["child_id"] ?? 0L);

            await using var updCmd = conn.CreateCommand();
            updCmd.CommandText = "UPDATE sessions SET status='completed' WHERE id=@id";
            updCmd.Parameters.AddWithValue("@id", sessionId);
            await updCmd.ExecuteNonQueryAsync();

            _log.LogInformation("Scheduler: session {Id} ({Type}) for child {Child} expired",
                sessionId, type, childId);

            if (type == "tv")
            {
                var dev = await GetTvDeviceAsync(conn);
                await dispatcher.TvSperren(dev.ControlType, dev.Identifier, dev.Config);
            }
            else if (type == "switch")
            {
                var nintendo = _sp.GetRequiredService<NintendoAdapter>();
                await nintendo.SwitchSperren();
            }
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    private static async Task InsertCoinLogAsync(
        Microsoft.Data.Sqlite.SqliteConnection conn,
        long childId, string type, long delta, string reason, string now)
    {
        await using var cmd = conn.CreateCommand();
        cmd.CommandText =
            "INSERT INTO coin_log (child_id, type, delta, reason, created_at) VALUES (@cid,@t,@d,@r,@ts)";
        cmd.Parameters.AddWithValue("@cid", childId);
        cmd.Parameters.AddWithValue("@t", type);
        cmd.Parameters.AddWithValue("@d", delta);
        cmd.Parameters.AddWithValue("@r", reason);
        cmd.Parameters.AddWithValue("@ts", now);
        await cmd.ExecuteNonQueryAsync();
    }

    private static async Task<(string ControlType, string Identifier, Dictionary<string, string?> Config)>
        GetTvDeviceAsync(Microsoft.Data.Sqlite.SqliteConnection conn)
    {
        await using var cmd = conn.CreateCommand();
        cmd.CommandText =
            "SELECT identifier, control_type, config FROM devices WHERE device_type='tv' AND is_active=1 LIMIT 1";
        await using var r = await cmd.ExecuteReaderAsync();
        if (await r.ReadAsync())
        {
            var identifier = r.IsDBNull(0) ? "Fernseher" : r.GetString(0);
            var controlType = r.IsDBNull(1) ? "fritzbox" : r.GetString(1);
            var configJson = r.IsDBNull(2) ? "{}" : r.GetString(2);
            var config = System.Text.Json.JsonSerializer
                .Deserialize<Dictionary<string, string?>>(configJson) ?? new();
            return (controlType, identifier, config);
        }
        return ("fritzbox", "Fernseher", new());
    }
}
