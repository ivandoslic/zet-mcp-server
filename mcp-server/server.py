from fastmcp import FastMCP

mcp = FastMCP("ZET Tramvaji 🚃")

@mcp.tool()
def find_stops(name: str) -> str:
    """Pronađi stajališta po imenu."""
    return f"TODO: pretraži SQLite za '{name}'"

@mcp.tool()
def next_departures(stop_id: str, minutes: int = 30) -> str:
    """Iduća polazišta s određenog stajališta."""
    return f"TODO: vrati polazišta za stop {stop_id} u narednih {minutes} min"

if __name__ == "__main__":
    mcp.run(transport="sse", port=8000)