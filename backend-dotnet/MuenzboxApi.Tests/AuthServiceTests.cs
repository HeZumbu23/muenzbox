using Microsoft.Extensions.Configuration;
using MuenzboxApi.Services;

namespace MuenzboxApi.Tests;

public class AuthServiceTests
{
    private static AuthService CreateAuthService(string secret = "unit-test-secret")
    {
        var cfg = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["SECRET_KEY"] = secret
            })
            .Build();

        return new AuthService(cfg);
    }

    [Fact]
    public void HashPin_UsesExpectedSha256Format()
    {
        var sut = CreateAuthService();

        var hash = sut.HashPin("1234");

        Assert.Equal("03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4", hash);
    }

    [Fact]
    public void VerifyPin_ReturnsTrueForMatchingPin_AndFalseOtherwise()
    {
        var sut = CreateAuthService();
        var hash = sut.HashPin("9876");

        Assert.True(sut.VerifyPin("9876", hash));
        Assert.False(sut.VerifyPin("1111", hash));
    }

    [Fact]
    public void CreateToken_AndDecodeToken_RoundTripClaims()
    {
        var sut = CreateAuthService();
        var expected = new Dictionary<string, string>
        {
            ["child_id"] = "5",
            ["name"] = "Mia"
        };

        var token = sut.CreateToken(expected, expiresHours: 2);
        var decoded = sut.DecodeToken(token);

        Assert.NotNull(decoded);
        Assert.Equal("5", decoded!["child_id"]);
        Assert.Equal("Mia", decoded["name"]);
        Assert.True(decoded.ContainsKey("exp"));
    }

    [Fact]
    public void DecodeToken_ReturnsNull_WhenSecretDoesNotMatch()
    {
        var issuer = CreateAuthService("secret-a");
        var reader = CreateAuthService("secret-b");

        var token = issuer.CreateToken(new Dictionary<string, string> { ["role"] = "admin" });
        var decoded = reader.DecodeToken(token);

        Assert.Null(decoded);
    }
}
