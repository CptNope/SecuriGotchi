# SecuriGotchi on ClockworkPi uConsole CM4

The **ClockworkPi uConsole with Raspberry Pi Compute Module 4** is an
ARM64 Linux handheld with a 5-inch, **1280×720** display, keyboard and
trackball. The official CM4 64-bit Linux images use ClockworkPi-specific
kernel/display support. SecuriGotchi does **not** update firmware, kernels,
battery-control components or operating-system display drivers.

- ClockworkPi official images: https://github.com/clockworkpi/uConsole
- Product specifications: https://www.clockworkpi.com/uconsole
- Prefer a supported 64-bit CM4 image with Python **3.11 or later**.
- The board reports Raspberry Pi CM4, not necessarily the uConsole enclosure.
  Therefore explicitly select the uConsole profile during diagnostics.

## Install on the device (not on another computer)

After preparing the uConsole's normal OS image and reaching a terminal:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
python3 --version
git clone https://github.com/CptNope/SecuriGotchi.git
cd SecuriGotchi
python3 install.py
.venv/bin/python gotchi_doctor.py --device uconsole-cm4
.venv/bin/python gotchi_auth.py init-admin
.venv/bin/python gotchi_webui.py
```


**Python 3.11+ is required.** If the bundled operating system has an older
Python, upgrade using OS-supported packages or a compatible newer image;
do not overwrite the OS's system Python binary. Always use the project's
virtual environment for Python dependencies.

The dashboard is available on the **same uConsole** at
`http://127.0.0.1:5000` using its browser. It is not made available
to other devices or the wider internet. If you want a single-purpose desktop
window, opening the address in a browser's app mode may work depending on
your installed Chromium/browser version; it is optional.

In a **separate terminal**:

```bash
.venv/bin/python gotchi_monitor.py watch --interval 60 --source auto
```


Then inspect:

```bash
.venv/bin/python gotchi_doctor.py --device uconsole-cm4 --probe-logs
```


If native Linux log access is unavailable, the collector can show "limited"
or "unavailable"; it cannot invent missing SSH activity. The device may not
be running an SSH service at all, in which case zero events isn't a security
clearance. Never add broad administrator/root permissions just to satisfy the
log reader. An SSH tunnel is preferred to opening the development server to
your LAN.

## Performance and battery

- Install the **core only** at first. `install.py` does not add heavy vector
  embeddings or a local large language model.
- Local Ollama is optional and may be slow or unavailable for some CM4
  model sizes. The MCP server can use a separate trusted AI host; that host
  might transmit aggregate summaries to a cloud model, depending on its
  configuration and consent. MCP is **not** auto-enabled.
- The dashboard uses compact styles for a shallow landscape viewport and
  a single-column layout on a narrow/rotated viewport. It stays scrollable
  and supports hardware keyboard/trackball focus.
- 60-second collector sampling is a starting point; less frequent sampling
  may help battery use but risks missing activity in bursty OS event sources.
- Battery reporting and on-device wake/sleep handling are not implemented;
  SecuriGotchi does not alter ClockworkPi power management.

## Diagnostics profile

```bash
.venv/bin/python gotchi_doctor.py --device uconsole-cm4 --json
```


The report validates Linux/ARM64 architecture, identifies CM4 when the device
tree provides it, estimates RAM and free storage, and provides a compact-screen
readiness note. Actual screen resolution, keyboard and trackball interaction
still require testing on physical hardware. **The flag selects a profile, not
proof that a CM4 is mounted inside a uConsole.**

The above is compatibility support, **not** a claim of physical testing on
your unit. Raspberry Pi CM4 hardware, display rotation, power management and
OS image revisions may differ in practice.
