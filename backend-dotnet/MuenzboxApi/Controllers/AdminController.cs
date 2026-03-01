using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Data.Sqlite;
using MuenzboxApi.Adapters;
using MuenzboxApi.Models;
using MuenzboxApi.Services;

namespace MuenzboxApi.Controllers;

[ApiController]
[Route("api/admin")]
public class AdminController : ControllerBase
{
    private readonly DatabaseService _db;
    private readonly AuthService _auth;
    private readonly AdapterDispatcher _adapters;
    private readonly NintendoAdapter _nintendo;
    private readonly MockAdapter _mock;

    private static readonly string FallbackPeriods = """[{"von":"08:00","bis":"20:00"}]""";
    private static readonly HashSet<string> AllowedDeviceTypes = new() { "tv" };
    private static readonly HashSet<string> AllowedControlTypes = new() { "fritzbox", "mikrotik", "schedule_only", "none" };

    private readonly string _adminPin;
    private readonly bool _useMock;

    public AdminController(
        DatabaseService db,
        AuthService auth,
        AdapterDispatcher adapters,
        NintendoAdapter nintendo,
        MockAdapter mock,
        IConfiguration config)
    {
        _db = db;
        _auth = auth;
        _adapters = adapters;
        _nintendo = nintendo;
        _mock = mock;
        _adminPin = config["ADMIN_PIN"] ?? "1234";
        _useMock = (config["USE_MOCK_ADAPTERS"] ?? "false").ToLower() == "true";
    }

    // ── POST /api/admin/verify ────────────────────────────────────────────

    [HttpPost("verify")]
    public IActionResult Verify([FromBody] AdminVerifyRequest body)
    {
        if (body.Pin != _adminPin)
            return Unauthorized(new { detail = "Falsche Admin-PIN" });

        var token = _auth.CreateToken(new() { ["sub"] = "admin", ["role"] = "admin" }, 12);
        return Ok(new { token });
    }

    // ═══ Children ════════════════════════════════════════════════════════

    [HttpGet("children")]
    [Authorize]
    public async Task<IActionResult> ListChildren()
    {
        if (!IsAdmin()) return Forbid();
        await using var conn = _db.CreateConnection();
        var rows = await FetchAllAsync(conn, "SELECT * FROM children ORDER BY name");
        foreach (var row in rows)
        {
            row["allowed_periods"] = ParsePeriodsAny(row["allowed_periods"] as string);
            row["weekend_periods"] = ParsePeriodsAny(row["weekend_periods"] as string);
        }
        return Ok(rows);
    }

    [HttpPost("children")]
    [Authorize]
    public async Task<IActionResult> CreateChild([FromBody] ChildCreateRequest body)
    {
        if (!IsAdmin()) return Forbid();
        var allowedJson = SerializePeriods(body.AllowedPeriods);
        var weekendJson = SerializePeriods(body.WeekendPeriods);
        var pinHash = _auth.HashPin(body.Pin);

        await using var conn = _db.CreateConnection();
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO children
              (name, pin_hash, switch_coins, switch_coins_weekly, switch_coins_max,
               tv_coins, tv_coins_weekly, tv_coins_max,
               pocket_money_cents, pocket_money_weekly_cents,
               allowed_periods, weekend_periods)
            VALUES
              (@name,@ph,@sc,@scw,@scm,@tc,@tcw,@tcm,@pm,@pmw,@ap,@wp)
            """;
        cmd.Parameters.AddWithValue("@name", body.Name);
        cmd.Parameters.AddWithValue("@ph", pinHash);
        cmd.Parameters.AddWithValue("@sc", body.SwitchCoins);
        cmd.Parameters.AddWithValue("@scw", body.SwitchCoinsWeekly);
        cmd.Parameters.AddWithValue("@scm", body.SwitchCoinsMax);
        cmd.Parameters.AddWithValue("@tc", body.TvCoins);
        cmd.Parameters.AddWithValue("@tcw", body.TvCoinsWeekly);
        cmd.Parameters.AddWithValue("@tcm", body.TvCoinsMax);
        cmd.Parameters.AddWithValue("@pm", body.PocketMoneyCents);
        cmd.Parameters.AddWithValue("@pmw", body.PocketMoneyWeeklyCents);
        cmd.Parameters.AddWithValue("@ap", allowedJson);
        cmd.Parameters.AddWithValue("@wp", weekendJson);
        await cmd.ExecuteNonQueryAsync();

        await using var idCmd = conn.CreateCommand();
        idCmd.CommandText = "SELECT last_insert_rowid()";
        var id = (long)(await idCmd.ExecuteScalarAsync() ?? 0L);

        Response.StatusCode = 201;
        return Ok(new { id, name = body.Name });
    }

    [HttpPut("children/{childId:int}")]
    [Authorize]
    public async Task<IActionResult> UpdateChild(int childId, [FromBody] ChildUpdateRequest body)
    {
        if (!IsAdmin()) return Forbid();
        await using var conn = _db.CreateConnection();

        var child = await GetRowAsync(conn, "SELECT * FROM children WHERE id=@id", ("@id", childId));
        if (child is null) return NotFound(new { detail = "Kind nicht gefunden" });

        var updates = new Dictionary<string, object>();
        if (body.Name is not null) updates["name"] = body.Name;
        if (body.Pin is not null) updates["pin_hash"] = _auth.HashPin(body.Pin);
        if (body.SwitchCoins.HasValue) updates["switch_coins"] = body.SwitchCoins.Value;
        if (body.SwitchCoinsWeekly.HasValue) updates["switch_coins_weekly"] = body.SwitchCoinsWeekly.Value;
        if (body.SwitchCoinsMax.HasValue) updates["switch_coins_max"] = body.SwitchCoinsMax.Value;
        if (body.TvCoins.HasValue) updates["tv_coins"] = body.TvCoins.Value;
        if (body.TvCoinsWeekly.HasValue) updates["tv_coins_weekly"] = body.TvCoinsWeekly.Value;
        if (body.TvCoinsMax.HasValue) updates["tv_coins_max"] = body.TvCoinsMax.Value;
        if (body.PocketMoneyCents.HasValue) updates["pocket_money_cents"] = body.PocketMoneyCents.Value;
        if (body.PocketMoneyWeeklyCents.HasValue) updates["pocket_money_weekly_cents"] = body.PocketMoneyWeeklyCents.Value;
        if (body.AllowedPeriods is not null) updates["allowed_periods"] = SerializePeriods(body.AllowedPeriods);
        if (body.WeekendPeriods is not null) updates["weekend_periods"] = SerializePeriods(body.WeekendPeriods);

        if (updates.Count > 0)
        {
            var setClause = string.Join(", ", updates.Keys.Select(k => $"{k}=@{k}"));
            await using var cmd = conn.CreateCommand();
            cmd.CommandText = $"UPDATE children SET {setClause} WHERE id=@id";
            foreach (var (k, v) in updates) cmd.Parameters.AddWithValue($"@{k}", v);
            cmd.Parameters.AddWithValue("@id", childId);
            await cmd.ExecuteNonQueryAsync();
        }

        return Ok(new { ok = true });
    }

    [HttpDelete("children/{childId:int}")]
    [Authorize]
    public async Task<IActionResult> DeleteChild(int childId)
    {
        if (!IsAdmin()) return Forbid();
        await using var conn = _db.CreateConnection();
        foreach (var sql in new[]
        {
            "DELETE FROM children WHERE id=@id",
            "DELETE FROM sessions WHERE child_id=@id",
            "DELETE FROM coin_log WHERE child_id=@id",
            "DELETE FROM pocket_money_log WHERE child_id=@id",
        })
        {
            await using var cmd = conn.CreateCommand();
            cmd.CommandText = sql;
            cmd.Parameters.AddWithValue("@id", childId);
            await cmd.ExecuteNonQueryAsync();
        }
        return Ok(new { ok = true });
    }

    [HttpPost("children/{childId:int}/adjust-coins")]
    [Authorize]
    public async Task<IActionResult> AdjustCoins(int childId, [FromBody] CoinAdjustRequest body)
    {
        if (!IsAdmin()) return Forbid();
        if (body.Type is not ("switch" or "tv"))
            return BadRequest(new { detail = "Ungültiger Typ" });

        await using var conn = _db.CreateConnection();
        var child = await GetRowAsync(conn, "SELECT * FROM children WHERE id=@id", ("@id", childId));
        if (child is null) return NotFound(new { detail = "Kind nicht gefunden" });

        var coinField = body.Type == "switch" ? "switch_coins" : "tv_coins";
        var maxField = body.Type == "switch" ? "switch_coins_max" : "tv_coins_max";
        var current = (int)(long)(child[coinField] ?? 0L);
        var max = (int)(long)(child[maxField] ?? 10L);
        var newVal = Math.Max(0, Math.Min(current + body.Delta, max));

        var now = DateTime.UtcNow.ToString("o");
        await ExecAsync(conn, $"UPDATE children SET {coinField}=@v WHERE id=@id",
            ("@v", newVal), ("@id", childId));
        await ExecAsync(conn,
            "INSERT INTO coin_log (child_id, type, delta, reason, created_at) VALUES (@cid,@t,@d,@r,@ts)",
            ("@cid", childId), ("@t", body.Type), ("@d", body.Delta), ("@r", body.Reason), ("@ts", now));

        return Ok(new { ok = true, new_value = newVal });
    }

    [HttpPost("children/{childId:int}/adjust-pocket-money")]
    [Authorize]
    public async Task<IActionResult> AdjustPocketMoney(int childId, [FromBody] PocketMoneyAdjustRequest body)
    {
        if (!IsAdmin()) return Forbid();
        await using var conn = _db.CreateConnection();
        var child = await GetRowAsync(conn, "SELECT * FROM children WHERE id=@id", ("@id", childId));
        if (child is null) return NotFound(new { detail = "Kind nicht gefunden" });

        var current = (int)(long)(child["pocket_money_cents"] ?? 0L);
        var newVal = Math.Max(0, current + body.DeltaCents);
        var now = DateTime.UtcNow.ToString("o");

        await ExecAsync(conn, "UPDATE children SET pocket_money_cents=@v WHERE id=@id",
            ("@v", newVal), ("@id", childId));
        await ExecAsync(conn,
            "INSERT INTO pocket_money_log (child_id, delta_cents, reason, note, created_at) VALUES (@cid,@d,@r,@n,@ts)",
            ("@cid", childId), ("@d", body.DeltaCents), ("@r", body.Reason),
            ("@n", (object?)body.Note ?? DBNull.Value), ("@ts", now));

        return Ok(new { ok = true, new_value_cents = newVal });
    }

    // ═══ Sessions ════════════════════════════════════════════════════════

    [HttpGet("sessions")]
    [Authorize]
    public async Task<IActionResult> ListSessions()
    {
        if (!IsAdmin()) return Forbid();
        await using var conn = _db.CreateConnection();
        var rows = await FetchAllAsync(conn, """
            SELECT s.*, c.name as child_name
            FROM sessions s
            JOIN children c ON s.child_id = c.id
            ORDER BY s.started_at DESC
            LIMIT 100
            """);
        return Ok(rows);
    }

    [HttpPost("sessions/{sessionId:int}/cancel")]
    [Authorize]
    public async Task<IActionResult> CancelSession(int sessionId)
    {
        if (!IsAdmin()) return Forbid();
        await using var conn = _db.CreateConnection();

        var session = await GetRowAsync(conn,
            "SELECT * FROM sessions WHERE id=@id AND status='active'",
            ("@id", sessionId));
        if (session is null) return NotFound(new { detail = "Aktive Session nicht gefunden" });

        await ExecAsync(conn, "UPDATE sessions SET status='cancelled' WHERE id=@id", ("@id", sessionId));

        var type = (string)(session["type"] ?? "");
        if (type == "tv")
        {
            var dev = await GetTvDeviceAsync(conn);
            await _adapters.TvSperren(dev.ControlType, dev.Identifier, dev.Config);
        }
        else if (type == "switch")
        {
            await _nintendo.SwitchSperren();
        }

        return Ok(new { ok = true });
    }

    // ═══ Logs ════════════════════════════════════════════════════════════

    [HttpGet("coin-log")]
    [Authorize]
    public async Task<IActionResult> GetCoinLog([FromQuery] int? child_id)
    {
        if (!IsAdmin()) return Forbid();
        await using var conn = _db.CreateConnection();
        string sql = child_id.HasValue
            ? "SELECT l.*, c.name as child_name FROM coin_log l JOIN children c ON l.child_id = c.id WHERE l.child_id=@cid ORDER BY l.created_at DESC LIMIT 200"
            : "SELECT l.*, c.name as child_name FROM coin_log l JOIN children c ON l.child_id = c.id ORDER BY l.created_at DESC LIMIT 200";

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        if (child_id.HasValue) cmd.Parameters.AddWithValue("@cid", child_id.Value);
        var rows = await FetchAllAsync(cmd);
        return Ok(rows);
    }

    [HttpGet("pocket-money-log")]
    [Authorize]
    public async Task<IActionResult> GetPocketMoneyLog([FromQuery] int? child_id)
    {
        if (!IsAdmin()) return Forbid();
        await using var conn = _db.CreateConnection();
        string sql = child_id.HasValue
            ? "SELECT l.*, c.name as child_name FROM pocket_money_log l JOIN children c ON l.child_id = c.id WHERE l.child_id=@cid ORDER BY l.created_at DESC LIMIT 200"
            : "SELECT l.*, c.name as child_name FROM pocket_money_log l JOIN children c ON l.child_id = c.id ORDER BY l.created_at DESC LIMIT 200";

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        if (child_id.HasValue) cmd.Parameters.AddWithValue("@cid", child_id.Value);
        var rows = await FetchAllAsync(cmd);
        return Ok(rows);
    }

    // ═══ Mock Status ═════════════════════════════════════════════════════

    [HttpGet("mock-status")]
    [Authorize]
    public IActionResult GetMockStatus()
    {
        if (!IsAdmin()) return Forbid();
        if (!_useMock) return Ok((object?)null);
        return Ok(_mock.GetStatus());
    }

    // ═══ Devices ═════════════════════════════════════════════════════════

    [HttpGet("devices")]
    [Authorize]
    public async Task<IActionResult> ListDevices()
    {
        if (!IsAdmin()) return Forbid();
        await using var conn = _db.CreateConnection();
        var rows = await FetchAllAsync(conn, """
            SELECT d.*, c.name as child_name
            FROM devices d
            LEFT JOIN children c ON d.child_id = c.id
            ORDER BY d.device_type, d.name
            """);
        foreach (var row in rows)
        {
            var configJson = row["config"] as string ?? "{}";
            var cfg = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(configJson) ?? new();
            row["config"] = MaskConfig(cfg);
        }
        return Ok(rows);
    }

    [HttpPost("devices")]
    [Authorize]
    public async Task<IActionResult> CreateDevice([FromBody] DeviceCreateRequest body)
    {
        if (!IsAdmin()) return Forbid();
        if (!AllowedDeviceTypes.Contains(body.DeviceType))
            return BadRequest(new { detail = $"Unbekannter Typ: {body.DeviceType}" });
        if (!AllowedControlTypes.Contains(body.ControlType))
            return BadRequest(new { detail = $"Unbekannter Steuertyp: {body.ControlType}" });

        await using var conn = _db.CreateConnection();
        await using var cmd = conn.CreateCommand();
        cmd.CommandText =
            "INSERT INTO devices (name, device_type, control_type, identifier, config, is_active) VALUES (@n,@dt,@ct,@id,@cfg,1)";
        cmd.Parameters.AddWithValue("@n", body.Name);
        cmd.Parameters.AddWithValue("@dt", body.DeviceType);
        cmd.Parameters.AddWithValue("@ct", body.ControlType);
        cmd.Parameters.AddWithValue("@id", body.Identifier);
        cmd.Parameters.AddWithValue("@cfg", JsonSerializer.Serialize(body.Config));
        await cmd.ExecuteNonQueryAsync();

        await using var idCmd = conn.CreateCommand();
        idCmd.CommandText = "SELECT last_insert_rowid()";
        var id = (long)(await idCmd.ExecuteScalarAsync() ?? 0L);

        Response.StatusCode = 201;
        return Ok(new { id, name = body.Name });
    }

    [HttpPut("devices/{deviceId:int}")]
    [Authorize]
    public async Task<IActionResult> UpdateDevice(int deviceId, [FromBody] DeviceUpdateRequest body)
    {
        if (!IsAdmin()) return Forbid();
        await using var conn = _db.CreateConnection();

        var device = await GetRowAsync(conn, "SELECT * FROM devices WHERE id=@id", ("@id", deviceId));
        if (device is null) return NotFound(new { detail = "Gerät nicht gefunden" });

        var updates = new Dictionary<string, object>();
        if (body.Name is not null) updates["name"] = body.Name;
        if (body.Identifier is not null) updates["identifier"] = body.Identifier;
        if (body.DeviceType is not null)
        {
            if (!AllowedDeviceTypes.Contains(body.DeviceType))
                return BadRequest(new { detail = $"Unbekannter Typ: {body.DeviceType}" });
            updates["device_type"] = body.DeviceType;
        }
        if (body.ControlType is not null)
        {
            if (!AllowedControlTypes.Contains(body.ControlType))
                return BadRequest(new { detail = $"Unbekannter Steuertyp: {body.ControlType}" });
            updates["control_type"] = body.ControlType;
        }
        if (body.Config is not null)
        {
            var existingJson = device["config"] as string ?? "{}";
            var existing = JsonSerializer.Deserialize<Dictionary<string, string?>>(existingJson) ?? new();
            var merged = new Dictionary<string, string?>(existing);
            foreach (var (k, v) in body.Config) merged[k] = v;
            if (merged.GetValueOrDefault("password") == "***")
                merged["password"] = existing.GetValueOrDefault("password");
            updates["config"] = JsonSerializer.Serialize(merged);
        }
        if (body.IsActive.HasValue) updates["is_active"] = body.IsActive.Value ? 1 : 0;

        if (updates.Count > 0)
        {
            var setClause = string.Join(", ", updates.Keys.Select(k => $"{k}=@{k}"));
            await using var cmd = conn.CreateCommand();
            cmd.CommandText = $"UPDATE devices SET {setClause} WHERE id=@id";
            foreach (var (k, v) in updates) cmd.Parameters.AddWithValue($"@{k}", v);
            cmd.Parameters.AddWithValue("@id", deviceId);
            await cmd.ExecuteNonQueryAsync();
        }

        return Ok(new { ok = true });
    }

    [HttpDelete("devices/{deviceId:int}")]
    [Authorize]
    public async Task<IActionResult> DeleteDevice(int deviceId)
    {
        if (!IsAdmin()) return Forbid();
        await using var conn = _db.CreateConnection();

        var device = await GetRowAsync(conn, "SELECT id FROM devices WHERE id=@id", ("@id", deviceId));
        if (device is null) return NotFound(new { detail = "Gerät nicht gefunden" });

        await ExecAsync(conn, "DELETE FROM devices WHERE id=@id", ("@id", deviceId));
        return Ok(new { ok = true });
    }

    // ── Private helpers ───────────────────────────────────────────────────

    private bool IsAdmin()
    {
        var role = User.FindFirst("role")?.Value;
        return role == "admin";
    }

    private static async Task<Dictionary<string, object?>?> GetRowAsync(
        SqliteConnection conn, string sql, params (string name, object value)[] ps)
    {
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        foreach (var (n, v) in ps) cmd.Parameters.AddWithValue(n, v);
        await using var r = await cmd.ExecuteReaderAsync();
        if (!await r.ReadAsync()) return null;
        var row = new Dictionary<string, object?>();
        for (int i = 0; i < r.FieldCount; i++) row[r.GetName(i)] = r.IsDBNull(i) ? null : r.GetValue(i);
        return row;
    }

    private static async Task<List<Dictionary<string, object?>>> FetchAllAsync(
        SqliteConnection conn, string sql)
    {
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        return await FetchAllAsync(cmd);
    }

    private static async Task<List<Dictionary<string, object?>>> FetchAllAsync(SqliteCommand cmd)
    {
        var rows = new List<Dictionary<string, object?>>();
        await using var r = await cmd.ExecuteReaderAsync();
        while (await r.ReadAsync())
        {
            var row = new Dictionary<string, object?>();
            for (int i = 0; i < r.FieldCount; i++) row[r.GetName(i)] = r.IsDBNull(i) ? null : r.GetValue(i);
            rows.Add(row);
        }
        return rows;
    }

    private static async Task ExecAsync(SqliteConnection conn, string sql,
        params (string name, object value)[] ps)
    {
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        foreach (var (n, v) in ps) cmd.Parameters.AddWithValue(n, v);
        await cmd.ExecuteNonQueryAsync();
    }

    private static Dictionary<string, object?> MaskConfig(Dictionary<string, JsonElement> cfg)
    {
        var result = new Dictionary<string, object?>();
        foreach (var (k, v) in cfg)
            result[k] = k == "password" && v.GetString() is not null ? "***" : v.GetString();
        return result;
    }

    private static string SerializePeriods(List<TimeSlot>? periods)
    {
        var list = periods ?? new List<TimeSlot> { new("08:00", "20:00") };
        return JsonSerializer.Serialize(list.Select(p => new { von = p.Von, bis = p.Bis }));
    }

    private static object ParsePeriodsAny(string? json)
    {
        if (string.IsNullOrEmpty(json)) return new[] { new { von = "08:00", bis = "20:00" } };
        try
        {
            return JsonSerializer.Deserialize<List<Dictionary<string, string?>>>(json)
                   ?? (object)new[] { new { von = "08:00", bis = "20:00" } };
        }
        catch { return new[] { new { von = "08:00", bis = "20:00" } }; }
    }

    private static async Task<(string ControlType, string Identifier, Dictionary<string, string?> Config)>
        GetTvDeviceAsync(SqliteConnection conn)
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
            var config = JsonSerializer.Deserialize<Dictionary<string, string?>>(configJson) ?? new();
            return (controlType, identifier, config);
        }
        return ("fritzbox", "Fernseher", new());
    }
}
