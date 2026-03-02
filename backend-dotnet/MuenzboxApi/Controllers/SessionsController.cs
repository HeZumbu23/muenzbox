using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using MuenzboxApi.Adapters;
using MuenzboxApi.Models;
using MuenzboxApi.Services;

namespace MuenzboxApi.Controllers;

[ApiController]
[Route("api")]
[Authorize]
public class SessionsController : ControllerBase
{
    private readonly DatabaseService _db;
    private readonly AdapterDispatcher _adapters;
    private readonly NintendoAdapter _nintendo;
    private readonly TimeUtilsService _time;
    private readonly ILogger<SessionsController> _log;
    private const int CoinMinutes = 30;

    public SessionsController(
        DatabaseService db,
        AdapterDispatcher adapters,
        NintendoAdapter nintendo,
        TimeUtilsService time,
        ILogger<SessionsController> log)
    {
        _db = db;
        _adapters = adapters;
        _nintendo = nintendo;
        _time = time;
        _log = log;
    }

    // ── POST /api/sessions ────────────────────────────────────────────────

    [HttpPost("sessions")]
    public async Task<IActionResult> StartSession([FromBody] SessionStartRequest body)
    {
        if (GetRole() != "child" || GetSub() != body.ChildId.ToString())
            return Forbid();

        if (body.Type is not ("switch" or "tv"))
            return BadRequest(new { detail = "Ungültiger Typ (switch oder tv)" });

        if (body.Coins < 1)
            return BadRequest(new { detail = "Mindestens 1 Münze erforderlich" });

        if (body.Type == "switch" && body.Coins > 2)
            return BadRequest(new { detail = "Switch: maximal 2 Münzen (60 Min) pro Session" });

        await using var conn = _db.CreateConnection();

        // Load child
        var child = await GetRowAsync(conn,
            "SELECT * FROM children WHERE id=@id",
            ("@id", body.ChildId));
        if (child is null) return NotFound(new { detail = "Kind nicht gefunden" });

        var childName = child["name"] as string ?? body.ChildId.ToString();

        // Check time window
        var allowed = ParsePeriods(child["allowed_periods"] as string);
        var weekend = ParsePeriods(child["weekend_periods"] as string);
        var active = _time.GetActivePeriods(allowed, weekend);
        if (!_time.IsInPeriods(active))
        {
            var times = string.Join(", ", active.Select(p => $"{p.Von}–{p.Bis} Uhr"));
            _log.LogWarning("[Session] {Child} ({Type}): abgelehnt – außerhalb erlaubter Zeit ({Times})",
                childName, body.Type, times);
            return StatusCode(403, new { detail = $"Außerhalb der erlaubten Zeit ({times})" });
        }

        // Check coin balance
        var coinField = body.Type == "switch" ? "switch_coins" : "tv_coins";
        var available = (int)(long)(child[coinField] ?? 0L);
        if (available < body.Coins)
        {
            _log.LogWarning("[Session] {Child} ({Type}): abgelehnt – zu wenig Münzen (hat {Available}, braucht {Requested})",
                childName, body.Type, available, body.Coins);
            return BadRequest(new { detail = $"Nicht genug Münzen (verfügbar: {available})" });
        }

        // Check for existing active session
        var existing = await GetRowAsync(conn,
            "SELECT id FROM sessions WHERE child_id=@id AND status='active'",
            ("@id", body.ChildId));
        if (existing is not null)
        {
            _log.LogWarning("[Session] {Child}: abgelehnt – Session läuft bereits", childName);
            return Conflict(new { detail = "Es läuft bereits eine Session" });
        }

        // Enable hardware first; do NOT consume coins if unlock fails
        _log.LogInformation("[Session] {Child}: Hardware-Freigabe angefordert ({Type}, {Coins} Münze(n))",
            childName, body.Type, body.Coins);

        bool hardwareOk;
        if (body.Type == "tv")
        {
            var dev = await GetTvDeviceAsync(conn);
            hardwareOk = await _adapters.TvFreigeben(dev.ControlType, dev.Identifier, dev.Config);
        }
        else
        {
            var dev = await GetNintendoDeviceAsync(conn);
            hardwareOk = await _nintendo.SwitchFreigeben(body.Coins * CoinMinutes, dev.Config);
        }

        if (!hardwareOk)
        {
            _log.LogWarning("[Session] {Child} ({Type}): Hardware-Freigabe fehlgeschlagen – Session wird nicht gestartet, keine Münze verbraucht",
                childName, body.Type);
            return StatusCode(502, new { detail = "Hardware konnte nicht freigeschaltet werden. Münzen wurden nicht verbraucht." });
        }

        var now = DateTime.UtcNow;
        var nowIso = now.ToString("o");
        var endsAt = now.AddMinutes(body.Coins * CoinMinutes).ToString("o");

        await using var tx = await conn.BeginTransactionAsync();
        try
        {
            await using (var upd = conn.CreateCommand())
            {
                upd.Transaction = (Microsoft.Data.Sqlite.SqliteTransaction)tx;
                upd.CommandText = $"UPDATE children SET {coinField}={coinField}-@coins WHERE id=@id";
                upd.Parameters.AddWithValue("@coins", body.Coins);
                upd.Parameters.AddWithValue("@id", body.ChildId);
                await upd.ExecuteNonQueryAsync();
            }

            await using (var clog = conn.CreateCommand())
            {
                clog.Transaction = (Microsoft.Data.Sqlite.SqliteTransaction)tx;
                clog.CommandText = "INSERT INTO coin_log (child_id, type, delta, reason, created_at) VALUES (@cid,@t,@d,'session',@ts)";
                clog.Parameters.AddWithValue("@cid", body.ChildId);
                clog.Parameters.AddWithValue("@t", body.Type);
                clog.Parameters.AddWithValue("@d", -body.Coins);
                clog.Parameters.AddWithValue("@ts", nowIso);
                await clog.ExecuteNonQueryAsync();
            }

            long sessionId;
            await using (var ins = conn.CreateCommand())
            {
                ins.Transaction = (Microsoft.Data.Sqlite.SqliteTransaction)tx;
                ins.CommandText =
                    "INSERT INTO sessions (child_id, type, started_at, ends_at, coins_used, status) " +
                    "VALUES (@cid,@t,@sa,@ea,@cu,'active')";
                ins.Parameters.AddWithValue("@cid", body.ChildId);
                ins.Parameters.AddWithValue("@t", body.Type);
                ins.Parameters.AddWithValue("@sa", nowIso);
                ins.Parameters.AddWithValue("@ea", endsAt);
                ins.Parameters.AddWithValue("@cu", body.Coins);
                await ins.ExecuteNonQueryAsync();

                await using var lastId = conn.CreateCommand();
                lastId.Transaction = (Microsoft.Data.Sqlite.SqliteTransaction)tx;
                lastId.CommandText = "SELECT last_insert_rowid()";
                sessionId = (long)(await lastId.ExecuteScalarAsync() ?? 0L);
            }

            await tx.CommitAsync();

            _log.LogInformation(
                "[Session] {Child} startet {Type}-Session #{SessionId}: {Coins} Münze(n) ({Minutes} Min), bis {EndsAt}, Hardware: OK",
                childName, body.Type, sessionId, body.Coins, body.Coins * CoinMinutes, endsAt);

            return Ok(new SessionResponse(
                Id: (int)sessionId,
                ChildId: body.ChildId,
                Type: body.Type,
                StartedAt: nowIso,
                EndsAt: endsAt,
                CoinsUsed: body.Coins,
                Status: "active",
                HardwareOk: true
            ));
        }
        catch
        {
            await tx.RollbackAsync();
            // Best-effort re-lock if DB update failed after unlock
            if (body.Type == "tv")
            {
                var dev = await GetTvDeviceAsync(conn);
                await _adapters.TvSperren(dev.ControlType, dev.Identifier, dev.Config);
            }
            else
            {
                var dev = await GetNintendoDeviceAsync(conn);
                await _nintendo.SwitchSperren(dev.Config);
            }
            throw;
        }
    }

    // ── POST /api/sessions/{id}/end ───────────────────────────────────────

    [HttpPost("sessions/{sessionId:int}/end")]
    public async Task<IActionResult> EndSession(int sessionId)
    {
        await using var conn = _db.CreateConnection();

        var session = await GetRowAsync(conn,
            "SELECT * FROM sessions WHERE id=@id AND status='active'",
            ("@id", sessionId));
        if (session is null) return NotFound(new { detail = "Aktive Session nicht gefunden" });

        var childId = (long)(session["child_id"] ?? 0L);
        if (GetRole() != "child" || GetSub() != childId.ToString())
            return Forbid();

        await ExecAsync(conn,
            "UPDATE sessions SET status='completed' WHERE id=@id",
            ("@id", sessionId));

        var type = (string)(session["type"] ?? "");
        _log.LogInformation("[Session] Kind {ChildId} beendet {Type}-Session #{SessionId} manuell",
            childId, type, sessionId);

        if (type == "tv")
        {
            var dev = await GetTvDeviceAsync(conn);
            await _adapters.TvSperren(dev.ControlType, dev.Identifier, dev.Config);
        }
        else if (type == "switch")
        {
            var dev = await GetNintendoDeviceAsync(conn);
            await _nintendo.SwitchSperren(dev.Config);
        }

        return Ok(new { status = "completed" });
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    private string GetSub() => User.FindFirst("sub")?.Value ?? "";
    private string GetRole() => User.FindFirst("role")?.Value ?? "";

    private static async Task<Dictionary<string, object?>?> GetRowAsync(
        Microsoft.Data.Sqlite.SqliteConnection conn,
        string sql,
        params (string name, object value)[] parameters)
    {
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        foreach (var (name, value) in parameters)
            cmd.Parameters.AddWithValue(name, value);
        await using var reader = await cmd.ExecuteReaderAsync();
        if (!await reader.ReadAsync()) return null;
        var row = new Dictionary<string, object?>();
        for (int i = 0; i < reader.FieldCount; i++)
            row[reader.GetName(i)] = reader.IsDBNull(i) ? null : reader.GetValue(i);
        return row;
    }

    private static async Task ExecAsync(
        Microsoft.Data.Sqlite.SqliteConnection conn,
        string sql,
        params (string name, object value)[] parameters)
    {
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        foreach (var (name, value) in parameters)
            cmd.Parameters.AddWithValue(name, value);
        await cmd.ExecuteNonQueryAsync();
    }

    private static List<Models.TimeSlot> ParsePeriods(string? json)
    {
        if (string.IsNullOrEmpty(json)) return Fallback();
        try
        {
            var opts = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
            return JsonSerializer.Deserialize<List<Models.TimeSlot>>(json, opts) ?? Fallback();
        }
        catch { return Fallback(); }
    }

    private static List<Models.TimeSlot> Fallback() => new() { new("08:00", "20:00") };

    private static Task<(string ControlType, string Identifier, Dictionary<string, string?> Config)>
        GetTvDeviceAsync(Microsoft.Data.Sqlite.SqliteConnection conn) =>
        GetDeviceAsync(conn, "tv", "fritzbox", "Fernseher");

    private static async Task<(string ControlType, string Identifier, Dictionary<string, string?> Config)>
        GetNintendoDeviceAsync(Microsoft.Data.Sqlite.SqliteConnection conn)
    {
        await using var cmd = conn.CreateCommand();
        cmd.CommandText =
            "SELECT identifier, control_type, config FROM devices WHERE device_type IN ('nintendo','switch') AND is_active=1 ORDER BY CASE WHEN device_type='nintendo' THEN 0 ELSE 1 END LIMIT 1";
        await using var r = await cmd.ExecuteReaderAsync();
        if (await r.ReadAsync())
        {
            var identifier = r.IsDBNull(0) ? "Nintendo Switch" : r.GetString(0);
            var controlType = r.IsDBNull(1) ? "nintendo" : r.GetString(1);
            var configJson = r.IsDBNull(2) ? "{}" : r.GetString(2);
            var config = JsonSerializer.Deserialize<Dictionary<string, string?>>(configJson) ?? new();
            return (controlType, identifier, config);
        }

        return ("nintendo", "Nintendo Switch", new());
    }

    private static async Task<(string ControlType, string Identifier, Dictionary<string, string?> Config)>
        GetDeviceAsync(Microsoft.Data.Sqlite.SqliteConnection conn, string deviceType, string fallbackControlType, string fallbackIdentifier)
    {
        await using var cmd = conn.CreateCommand();
        cmd.CommandText =
            "SELECT identifier, control_type, config FROM devices WHERE device_type=@dt AND is_active=1 LIMIT 1";
        cmd.Parameters.AddWithValue("@dt", deviceType);
        await using var r = await cmd.ExecuteReaderAsync();
        if (await r.ReadAsync())
        {
            var identifier = r.IsDBNull(0) ? fallbackIdentifier : r.GetString(0);
            var controlType = r.IsDBNull(1) ? fallbackControlType : r.GetString(1);
            var configJson = r.IsDBNull(2) ? "{}" : r.GetString(2);
            var config = JsonSerializer.Deserialize<Dictionary<string, string?>>(configJson) ?? new();
            return (controlType, identifier, config);
        }
        return (fallbackControlType, fallbackIdentifier, new());
    }
}
