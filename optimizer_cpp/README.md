# RAID Nexus C++ Dispatch Optimizer Scaffold

This module is a placeholder for a compiled Dijkstra/A* dispatch optimizer. It is intentionally optional and isolated from the running FastAPI application.

The Python backend integration contract is:

- Check for the compiled binary at `optimizer_cpp/build/dispatch_optimizer`.
- On Windows CMake may produce `optimizer_cpp/build/dispatch_optimizer.exe`; deployment scripts can normalize or copy it to the expected path if needed.
- If the binary is not found, the Python heuristic dispatch path runs instead.
- No part of the running application requires this module.

The scaffold currently provides a standalone CLI named `dispatch_optimizer`. It reads a JSON file containing an `incident` object and an `ambulances` array, then writes a JSON assignment to stdout.

Example input:

```json
{
  "incident": {
    "id": "INC-001",
    "type": "cardiac",
    "lat": 28.6139,
    "lng": 77.209
  },
  "ambulances": [
    {
      "id": "AMB-001",
      "type": "ALS",
      "status": "available",
      "current_lat": 28.7041,
      "current_lng": 77.1025,
      "speed_kmh": 44.0
    }
  ]
}
```

Build:

```bash
cmake -S optimizer_cpp -B optimizer_cpp/build
cmake --build optimizer_cpp/build --config Release
```

Run:

```bash
optimizer_cpp/build/dispatch_optimizer sample.json
```

The current CLI uses a nearest-available-unit score as a safe placeholder. A future Dijkstra/A* implementation can replace the scoring internals while preserving the same input and output contract.
