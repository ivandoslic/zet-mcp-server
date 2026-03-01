# 🚃 ZET MCP Server

> Real-time Zagreb tram data, served via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

Connect any MCP-compatible AI assistant (Claude, VS Code Copilot, etc.) to live ZET tram schedules and let it answer natural language questions like:
- *"Which trams stop at Glavni kolodvor?"*
- *"When is the next tram 5 towards Park Maksimir from Vjesnik?"*
- *"Where are all tram 13 vehicles right now?"*
- *"What's the last tram tonight from Glavni kolodvor towards Dubrava?"*

---

## 🚀 Getting Started

### Prerequisites

- [Docker](https://www.docker.com/get-started) and Docker Compose

### Run

```bash
# 1. Clone the repository
git clone https://github.com/ivandoslic/zet-mcp-server.git
cd zet-mcp-server

# 2. Create your .env file
cp .env.example .env

# 3. Build and start both services
docker compose up --build
```

On first start, `gtfs-sync` will download and import the full ZET static schedule (can take some time). After that, real-time data refreshes every 15 seconds automatically.

The MCP server will be available at:
```
http://localhost:8000/sse
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GTFS_STATIC_URL` | ZET static feed URL | ZET GTFS static data endpoint |
| `GTFS_RT_URL` | ZET RT feed URL | ZET GTFS Realtime endpoint |
| `GTFS_RT_REFRESH_INTERVAL` | `15` | Real-time refresh interval (seconds) |
| `GTFS_STATIC_REFRESH_HOURS` | `24` | Static schedule refresh interval (hours) |
| `MCP_PORT` | `8000` | Port the MCP server listens on |
| `DB_PATH` | `/data/zet.db` | Path to the SQLite database |

---

## 🛠 Available MCP Tools

| Tool | Parameters | Description |
|---|---|---|
| `search_stops` | `name` | Search for stops by name (partial match) |
| `routes_at_stop` | `stop_id` | Get all routes serving a stop today |
| `next_arrivals` | `stop_id`, `minutes`, `headsign?`, `route?` | Upcoming arrivals at a stop, with real-time corrections |
| `vehicle_positions` | `route` | Current GPS positions of all vehicles on a line |
| `last_departure` | `stop_id`, `route?`, `headsign?` | Last departure of the day from a stop |

---

## 🔌 Integrations

### Claude Desktop

Install [mcp-remote](https://www.npmjs.com/package/mcp-remote) (requires Node.js):

```bash
npm install -g mcp-remote
```

Add to your `claude_desktop_config.json`:

**Windows:** `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json`  
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "zet-tramvaji": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8000/sse"]
    }
  }
}
```

Restart Claude Desktop — you should see the ZET tools available in the chat interface.

### VS Code (GitHub Copilot)

Add to your VS Code `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "zet-tramvaji": {
        "type": "sse",
        "url": "http://localhost:8000/sse"
      }
    }
  }
}
```

### Any MCP Client

The server uses the standard **SSE (Server-Sent Events)** transport, making it compatible with any MCP client that supports HTTP/SSE. Point your client to:

```
http://localhost:8000/sse
```

---

## 🗺 Roadmap

- [ ] **Frontend** — A standalone web interface for exploring tram schedules without an AI assistant
- [ ] **Route planning** — Real-time A→B routing across the ZET network
- [ ] **Nearby stops** — Find stops near a GPS coordinate (client sends location, server returns closest stops)
- [ ] **Alerts** — Surface any service disruptions from the GTFS-RT alerts feed

---

## 📄 Data

ZET tram data is publicly available and licensed under the **Open Licence of the Republic of Croatia**:  
👉 http://data.gov.hr/otvorena-dozvola

Per [ZET's terms](https://www.zet.hr/preuzimanja/odredbe/datoteke-u-gtfs-formatu/669), the GTFS data is available for **testing purposes**.

- **Static schedule:** https://www.zet.hr/gtfs-scheduled/latest
- **Real-time feed:** https://www.zet.hr/gtfs-rt-protobuf

---

## 📝 License

This project is released under the **MIT License** — you are free to use, modify, and distribute it for any purpose.