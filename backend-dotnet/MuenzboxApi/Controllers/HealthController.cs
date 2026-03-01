using Microsoft.AspNetCore.Mvc;

namespace MuenzboxApi.Controllers;

[ApiController]
public class HealthController : ControllerBase
{
    [HttpGet("/api/health")]
    public IActionResult Health() => Ok(new { status = "ok" });
}
