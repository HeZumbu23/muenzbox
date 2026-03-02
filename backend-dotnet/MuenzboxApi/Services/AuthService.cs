using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using Microsoft.IdentityModel.Tokens;

namespace MuenzboxApi.Services;

/// <summary>
/// PIN hashing (SHA-256) and JWT creation/validation –
/// identical algorithm to the Python backend so existing tokens and hashes remain valid.
/// </summary>
public class AuthService
{
    private readonly string _secretKey;
    private const string Algorithm = SecurityAlgorithms.HmacSha256;
    private const int DefaultExpireHours = 8;

    public AuthService(IConfiguration config)
    {
        _secretKey = config["SECRET_KEY"] ?? "changeme-in-production";
    }

    // ── PIN ───────────────────────────────────────────────────────────────

    public string HashPin(string pin)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(pin));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    public bool VerifyPin(string pin, string hashed)
        => HashPin(pin) == hashed;

    // ── JWT ───────────────────────────────────────────────────────────────

    public string CreateToken(Dictionary<string, string> claims, int expiresHours = DefaultExpireHours)
    {
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_secretKey));
        var creds = new SigningCredentials(key, Algorithm);

        var jwtClaims = claims.Select(kv => new Claim(kv.Key, kv.Value)).ToList();
        jwtClaims.Add(new Claim(JwtRegisteredClaimNames.Exp,
            DateTimeOffset.UtcNow.AddHours(expiresHours).ToUnixTimeSeconds().ToString(),
            ClaimValueTypes.Integer64));

        var token = new JwtSecurityToken(claims: jwtClaims, signingCredentials: creds);
        return new JwtSecurityTokenHandler().WriteToken(token);
    }

    public Dictionary<string, string>? DecodeToken(string token)
    {
        try
        {
            var handler = new JwtSecurityTokenHandler();
            handler.ValidateToken(token,
                new TokenValidationParameters
                {
                    ValidateIssuerSigningKey = true,
                    IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_secretKey)),
                    ValidateIssuer = false,
                    ValidateAudience = false,
                    ClockSkew = TimeSpan.Zero,
                },
                out var validated);

            var jwt = (JwtSecurityToken)validated;
            return jwt.Claims.ToDictionary(c => c.Type, c => c.Value);
        }
        catch
        {
            return null;
        }
    }
}
