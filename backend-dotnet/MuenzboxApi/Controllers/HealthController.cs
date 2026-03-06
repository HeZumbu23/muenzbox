using Microsoft.AspNetCore.Mvc;

namespace MuenzboxApi.Controllers;

[ApiController]
public class HealthController : ControllerBase
{
    private readonly bool _useMock;

    public HealthController(IConfiguration config)
    {
        _useMock = (config["USE_MOCK_ADAPTERS"] ?? "false").ToLower() == "true";
    }

    [HttpGet("/api/health")]
    public IActionResult Health() => Ok(new { status = "ok", use_mock_adapters = _useMock });
}
