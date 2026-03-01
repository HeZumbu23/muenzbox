using Microsoft.Data.Sqlite;

namespace MuenzboxApi.Services;

/// <summary>
/// Manages SQLite database initialization and connection creation.
/// Each call to CreateConnection() returns a new, open connection that the
/// caller must dispose (matches the per-request pattern of the Python backend).
/// </summary>
public class DatabaseService
{
    private readonly string _dbPath;
    private readonly ILogger<DatabaseService> _log;

    public DatabaseService(IConfiguration config, ILogger<DatabaseService> log)
    {
        _dbPath = config["DATABASE_PATH"] ?? "/data/muenzbox.db";
        _log = log;
    }

    public SqliteConnection CreateConnection()
    {
        var conn = new SqliteConnection($"Data Source={_dbPath}");
        conn.Open();
        // Enable WAL mode for better concurrent read performance
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "PRAGMA journal_mode=WAL;";
        cmd.ExecuteNonQuery();
        return conn;
    }

    public async Task InitializeAsync()
    {
        var dir = Path.GetDirectoryName(_dbPath);
        if (!string.IsNullOrEmpty(dir))
            Directory.CreateDirectory(dir);

        await using var conn = CreateConnection();

        await ExecAsync(conn, """
            CREATE TABLE IF NOT EXISTS children (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                pin_hash TEXT NOT NULL,
                switch_coins INTEGER DEFAULT 0,
                switch_coins_weekly INTEGER DEFAULT 2,
                switch_coins_max INTEGER DEFAULT 10,
                tv_coins INTEGER DEFAULT 0,
                tv_coins_weekly INTEGER DEFAULT 2,
                tv_coins_max INTEGER DEFAULT 10,
                pocket_money_cents INTEGER DEFAULT 0,
                pocket_money_weekly_cents INTEGER DEFAULT 0,
                allowed_from TEXT DEFAULT '08:00',
                allowed_until TEXT DEFAULT '20:00',
                weekend_from TEXT DEFAULT '08:00',
                weekend_until TEXT DEFAULT '20:00',
                allowed_periods TEXT DEFAULT '[{"von":"08:00","bis":"20:00"}]',
                weekend_periods TEXT DEFAULT '[{"von":"08:00","bis":"20:00"}]'
            )
            """);

        await ExecAsync(conn, """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                coins_used INTEGER NOT NULL,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (child_id) REFERENCES children(id)
            )
            """);

        await ExecAsync(conn, """
            CREATE TABLE IF NOT EXISTS coin_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                delta INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (child_id) REFERENCES children(id)
            )
            """);

        await ExecAsync(conn, """
            CREATE TABLE IF NOT EXISTS pocket_money_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_id INTEGER NOT NULL,
                delta_cents INTEGER NOT NULL,
                reason TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (child_id) REFERENCES children(id)
            )
            """);

        // Migrations – ignore errors if columns already exist
        foreach (var (col, def) in new[]
        {
            ("weekend_from", "'08:00'"),
            ("weekend_until", "'20:00'"),
            ("allowed_periods", "NULL"),
            ("weekend_periods", "NULL"),
            ("pocket_money_cents", "0"),
            ("pocket_money_weekly_cents", "0"),
        })
        {
            try { await ExecAsync(conn, $"ALTER TABLE children ADD COLUMN {col} TEXT DEFAULT {def}"); }
            catch { /* already exists */ }
        }

        await ExecAsync(conn, """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                device_type TEXT NOT NULL,
                control_type TEXT NOT NULL,
                identifier TEXT,
                child_id INTEGER,
                is_active INTEGER DEFAULT 1,
                config TEXT DEFAULT '{}',
                FOREIGN KEY (child_id) REFERENCES children(id)
            )
            """);

        foreach (var col in new[] { "identifier", "name", "config" })
        {
            try { await ExecAsync(conn, $"ALTER TABLE devices ADD COLUMN {col} TEXT"); }
            catch { /* already exists */ }
        }

        // Seed default TV device if none exist
        await using var checkCmd = conn.CreateCommand();
        checkCmd.CommandText = "SELECT COUNT(*) FROM devices WHERE device_type='tv'";
        var count = (long)(await checkCmd.ExecuteScalarAsync() ?? 0L);
        if (count == 0)
        {
            var tvIdentifier = Environment.GetEnvironmentVariable("MIKROTIK_TV_ADDRESS_LIST_COMMENT") ?? "Fernseher";
            await using var seedCmd = conn.CreateCommand();
            seedCmd.CommandText =
                "INSERT INTO devices (name, device_type, control_type, identifier, config) VALUES (@n,@dt,@ct,@id,'{}')";
            seedCmd.Parameters.AddWithValue("@n", "Fernseher");
            seedCmd.Parameters.AddWithValue("@dt", "tv");
            seedCmd.Parameters.AddWithValue("@ct", "fritzbox");
            seedCmd.Parameters.AddWithValue("@id", tvIdentifier);
            await seedCmd.ExecuteNonQueryAsync();
        }

        _log.LogInformation("Database initialized: {Path}", _dbPath);
    }

    private static async Task ExecAsync(SqliteConnection conn, string sql)
    {
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        await cmd.ExecuteNonQueryAsync();
    }
}
