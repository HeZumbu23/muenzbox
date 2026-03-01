using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Data.Sqlite;
using MuenzboxApi.Models;
using MuenzboxApi.Services;

namespace MuenzboxApi.Controllers;

[ApiController]
[Route("api")]
public class ChildrenController : ControllerBase
{
    private readonly DatabaseService _db;
    private readonly AuthService _auth;
    private readonly TimeUtilsService _time;

    private static readonly string FallbackPeriods = """[{"von":"08:00","bis":"20:00"}]""";

    public ChildrenController(DatabaseService db, AuthService auth, TimeUtilsService time)
    {
        _db = db;
        _auth = auth;
        _time = time;
    }

    // ── GET /api/children ─────────────────────────────────────────────────

    [HttpGet("children")]
    public async Task<IActionResult> ListChildren()
    {
        await using var conn = _db.CreateConnection();
        var result = new List<ChildPublic>();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT id, name, switch_coins, tv_coins FROM children ORDER BY name";
        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            result.Add(new ChildPublic(
                reader.GetInt32(0),
                reader.GetString(1),
                reader.GetInt32(2),
                reader.GetInt32(3)));
        }
        return Ok(result);
    }

    // ── POST /api/children/{id}/verify-pin ────────────────────────────────

    [HttpPost("children/{childId:int}/verify-pin")]
    public async Task<IActionResult> VerifyPin(int childId, [FromBody] PinVerifyRequest body)
    {
        await using var conn = _db.CreateConnection();
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT id, name, pin_hash FROM children WHERE id=@id";
        cmd.Parameters.AddWithValue("@id", childId);
        await using var reader = await cmd.ExecuteReaderAsync();

        if (!await reader.ReadAsync())
            return NotFound(new { detail = "Kind nicht gefunden" });

        var storedHash = reader.GetString(2);
        var name = reader.GetString(1);

        if (!_auth.VerifyPin(body.Pin, storedHash))
            return Unauthorized(new { detail = "Falsche PIN" });

        var token = _auth.CreateToken(new()
        {
            ["sub"] = childId.ToString(),
            ["role"] = "child",
            ["name"] = name,
        });

        return Ok(new { token, child_id = childId, name });
    }

    // ── GET /api/children/{id}/status ─────────────────────────────────────

    [HttpGet("children/{childId:int}/status")]
    [Authorize]
    public async Task<IActionResult> GetChildStatus(int childId)
    {
        if (!IsChildAuthorized(childId))
            return Forbid();

        await using var conn = _db.CreateConnection();
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM children WHERE id=@id";
        cmd.Parameters.AddWithValue("@id", childId);
        await using var reader = await cmd.ExecuteReaderAsync();

        if (!await reader.ReadAsync())
            return NotFound(new { detail = "Kind nicht gefunden" });

        var row = ReadRow(reader);
        var allowed = ParsePeriods(row["allowed_periods"] as string ?? FallbackPeriods);
        var weekend = ParsePeriods(row["weekend_periods"] as string ?? FallbackPeriods);

        return Ok(new ChildStatus(
            Id: (int)(long)row["id"]!,
            Name: (string)row["name"]!,
            SwitchCoins: (int)(long)(row["switch_coins"] ?? 0L),
            SwitchCoinsWeekly: (int)(long)(row["switch_coins_weekly"] ?? 0L),
            SwitchCoinsMax: (int)(long)(row["switch_coins_max"] ?? 10L),
            TvCoins: (int)(long)(row["tv_coins"] ?? 0L),
            TvCoinsWeekly: (int)(long)(row["tv_coins_weekly"] ?? 0L),
            TvCoinsMax: (int)(long)(row["tv_coins_max"] ?? 10L),
            PocketMoneyCents: (int)(long)(row["pocket_money_cents"] ?? 0L),
            PocketMoneyWeeklyCents: (int)(long)(row["pocket_money_weekly_cents"] ?? 0L),
            AllowedPeriods: allowed,
            WeekendPeriods: weekend,
            IsWeekendOrHoliday: _time.IsWeekendOrHoliday()
        ));
    }

    // ── GET /api/children/{id}/active-session ─────────────────────────────

    [HttpGet("children/{childId:int}/active-session")]
    [Authorize]
    public async Task<IActionResult> GetActiveSession(int childId)
    {
        if (!IsChildAuthorized(childId))
            return Forbid();

        await using var conn = _db.CreateConnection();
        await using var cmd = conn.CreateCommand();
        cmd.CommandText =
            "SELECT * FROM sessions WHERE child_id=@id AND status='active' ORDER BY started_at DESC LIMIT 1";
        cmd.Parameters.AddWithValue("@id", childId);
        await using var reader = await cmd.ExecuteReaderAsync();

        if (!await reader.ReadAsync())
            return Ok((object?)null);

        return Ok(ReadRow(reader));
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    private bool IsChildAuthorized(int childId)
    {
        var sub = User.FindFirst("sub")?.Value;
        var role = User.FindFirst("role")?.Value;
        return role == "child" && sub == childId.ToString();
    }

    private static Dictionary<string, object?> ReadRow(SqliteDataReader reader)
    {
        var dict = new Dictionary<string, object?>();
        for (int i = 0; i < reader.FieldCount; i++)
            dict[reader.GetName(i)] = reader.IsDBNull(i) ? null : reader.GetValue(i);
        return dict;
    }

    private static List<TimeSlot> ParsePeriods(string json)
    {
        try
        {
            var opts = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
            return JsonSerializer.Deserialize<List<TimeSlot>>(json, opts) ?? Fallback();
        }
        catch { return Fallback(); }
    }

    private static List<TimeSlot> Fallback() => new() { new("08:00", "20:00") };
}
