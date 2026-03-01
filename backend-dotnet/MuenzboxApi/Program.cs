using System.Text;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using MuenzboxApi.Adapters;
using MuenzboxApi.Services;

var builder = WebApplication.CreateBuilder(args);

// Load environment variables into config
builder.Configuration.AddEnvironmentVariables();

// ── Services ───────────────────────────────────────────────────────────────
builder.Services.AddSingleton<DatabaseService>();
builder.Services.AddSingleton<AuthService>();
builder.Services.AddSingleton<TimeUtilsService>();
builder.Services.AddSingleton<MockAdapter>();
builder.Services.AddSingleton<MikrotikAdapter>();
builder.Services.AddSingleton<FritzBoxAdapter>();
builder.Services.AddSingleton<NintendoAdapter>();
builder.Services.AddSingleton<AdapterDispatcher>();
builder.Services.AddHostedService<SchedulerService>();

// ── JWT Authentication ─────────────────────────────────────────────────────
var secretKey = builder.Configuration["SECRET_KEY"] ?? "changeme-in-production";
Microsoft.IdentityModel.JsonWebTokens.JsonWebTokenHandler.DefaultInboundClaimTypeMap.Clear();

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.MapInboundClaims = false;
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(secretKey)),
            ValidateIssuer = false,
            ValidateAudience = false,
            ClockSkew = TimeSpan.Zero,
        };
    });

builder.Services.AddAuthorization();

// ── Controllers with snake_case JSON ──────────────────────────────────────
builder.Services.AddControllers()
    .AddJsonOptions(opts =>
    {
        opts.JsonSerializerOptions.PropertyNamingPolicy = System.Text.Json.JsonNamingPolicy.SnakeCaseLower;
        opts.JsonSerializerOptions.PropertyNameCaseInsensitive = true;
        opts.JsonSerializerOptions.DefaultIgnoreCondition =
            System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull;
    });

// ── CORS – allow all origins (matching Python backend) ────────────────────
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
        policy.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader());
});

// ── Logging ────────────────────────────────────────────────────────────────
builder.Logging.ClearProviders();
builder.Logging.AddConsole(opts =>
    opts.FormatterName = "simple");
builder.Logging.AddSimpleConsole(opts =>
{
    opts.TimestampFormat = "yyyy-MM-dd HH:mm:ss ";
    opts.SingleLine = true;
});

var app = builder.Build();

// ── Startup: init DB ───────────────────────────────────────────────────────
var db = app.Services.GetRequiredService<DatabaseService>();
await db.InitializeAsync();

// ── Middleware ─────────────────────────────────────────────────────────────
app.UseCors();
app.UseAuthentication();
app.UseAuthorization();
app.MapControllers();

app.Run($"http://0.0.0.0:{builder.Configuration["PORT"] ?? "8420"}");
