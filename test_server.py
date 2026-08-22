"""
Serveur MCP minimal, utilisé UNIQUEMENT pour tester le checker de conformité.
Contient volontairement un outil avec une description vide (mauvaise pratique)
pour vérifier que le checker le détecte bien.
"""

from mcp.server import MCPServer

app = MCPServer("test-server-demo")


@app.tool()
def get_weather(city: str) -> str:
    """Récupère la météo actuelle pour une ville donnée."""
    return f"Il fait beau à {city}."


@app.tool(name="mystery_tool", description="")  # volontairement vide -> doit être détecté
def mystery_tool() -> str:
    return "ok"


if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run_stdio_async())

