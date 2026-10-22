# UniSim-Bridge (Current Version)

This repository contains the current working version of the UniSim-Bridge developed by the **PROTEC group** of the [Polytechnic School of the Federal University of Bahia](https://eng.ufba.br/) for automating Honeywell&reg; UniSim Design Suite simulations through Microsoft COM (Component Object Model) protocol.

It enables you to control a running UniSim case from Python, advance the solver in controlled time steps, inject disturbances, and automatically persist selected simulation variables to a SQLite database for later analysis.

**Documentation:** The full guide is available in the `docs/` folder or on the deployed [site]().

**Quick Start:**
1.  Ensure `pywin32` and `pandas` are installed.
2.  Edit `setup.py` to point to your `.usc` file and list the operations you want to track.
3.  Edit how you want the simulation to operate in `main.py`.
4.  Run `python main.py`.

For detailed explanations, see the `docs/` directory.